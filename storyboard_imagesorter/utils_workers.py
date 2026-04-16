# Storyboard Imagesorter
# Copyright (C) 2026 by Reiner Prokein (Haizy Tiles)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# utils_workers.py
# This module contains utility functions and worker classes for asynchronous tasks.
# It provides helpers for zoom conversion and stylesheet generation, as well as
# a robust ImageLoadWorker that handles background thumbnail loading with
# retry logic to ensure file stability during concurrent writes.

import os
import sys
import time
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, Qt, QByteArray
from PyQt6.QtGui import QImage
import constants


def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and PyInstaller (frozen).
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def zoom_to_px(pct):
    """Converts zoom percentage to pixel size."""
    return max(1, int(constants.BASE_SIZE * pct / 100))


def _btn(bg, hover, icon=False):
    """Generates a standardized stylesheet for toolbar buttons."""
    w = f"min-width:{constants.TOOLBAR_H}px;" if icon else "min-width:78px;"
    pad = "0px 6px" if icon else "0px 11px"
    fs = "16px" if icon else "12px"

    return (
        f"QPushButton{{background:{bg};color:#e0e0e0;border:none;"
        f"padding:{pad};border-radius:5px;min-height:{constants.TOOLBAR_H}px;{w}font-size:{fs};font-weight:500;}}"
        f"QPushButton:hover{{background:{hover};}}"
        f"QPushButton:disabled{{background:#222;color:#3a3a3a;}}"
    )


class WorkerSignals(QObject):
    """Signals for the ImageLoadWorker."""
    finished = pyqtSignal(str, QImage)

class ImageLoadWorker(QRunnable):
    def __init__(self, path, size, signals, retries=4):
        super().__init__()
        self.path = path
        self.size = size
        self.signals = signals
        self.cancelled = False
        self.retries = retries

    def run(self):
        if self.cancelled:
            return

        img = QImage()
        # Maximum resolution to keep in memory for sharp zooming
        MAX_QUALITY_SIZE = 1200

        # FAST PATH: Try immediate load first.
        # For most manual imports, this is all that's needed.
        if os.path.exists(self.path):
            img.load(self.path)

        # SLOW PATH: If fast path failed (e.g., file locked or partially written),
        # use retry logic to wait for stability.
        if img.isNull() and not self.cancelled:
            for attempt in range(self.retries):
                if self.cancelled:
                    return

                try:
                    if os.path.exists(self.path):
                        stat1 = os.stat(self.path)
                        size1 = stat1.st_size
                        mtime1 = stat1.st_mtime

                        if size1 > 0:
                            # Wait a bit to see if the file is still changing
                            time.sleep(0.25)
                            stat2 = os.stat(self.path)
                            size2 = stat2.st_size
                            mtime2 = stat2.st_mtime

                            if size1 == size2 and mtime1 == mtime2:
                                # File is stable — try loading again
                                img.load(self.path)
                                if not img.isNull():
                                    break
                except Exception:
                    pass

                time.sleep(0.25)

        if not img.isNull() and not self.cancelled:
            # Calculate high-quality scale factor for zoom cache
            ratio = min(MAX_QUALITY_SIZE / img.width(), MAX_QUALITY_SIZE / img.height(), 1.0)
            new_w = int(img.width() * ratio)
            new_h = int(img.height() * ratio)

            scaled = img.scaled(
                new_w,
                new_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            if not self.cancelled:
                self.signals.finished.emit(self.path, scaled)


def load_image_safely(path, retries=3):
    """
    Synchronous version of the stability check for use in blocking loops (like Export).
    Attempts an immediate load first for speed; only uses retry logic if loading fails.
    """
    # 1. FAST PATH: Try to load immediately without any artificial delays.
    if os.path.exists(path):
        img = QImage(path)
        if not img.isNull():
            return img

    # 2. SLOW PATH: If the fast path failed, use retry logic to wait for stability.
    for _ in range(retries):
        try:
            if os.path.exists(path):
                stat1 = os.stat(path)
                size1 = stat1.st_size
                mtime1 = stat1.st_mtime

                if size1 > 0:
                    # Wait a short period to see if the file is still changing
                    time.sleep(0.2)
                    stat2 = os.stat(path)
                    if size1 == stat2.st_size and mtime1 == stat2.st_mtime:
                        img = QImage(path)
                        if not img.isNull():
                            return img
        except Exception:
            pass
        # Wait before the next retry attempt
        time.sleep(0.2)

    return QImage()
