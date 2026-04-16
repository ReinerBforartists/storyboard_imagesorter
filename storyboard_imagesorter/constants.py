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
# constants.py
# This module defines global constants and configuration settings for the application.
# It includes MIME types, UI dimension parameters, supported image formats,
# and QSS (Qt Style Sheets) strings used to style menus and main components.


MIME_INTERNAL = "application/x-image-paths"
ZOOM_STEPS = [25, 50, 75, 100, 125, 150, 175, 200]
BASE_SIZE = 200
TOOLBAR_H = 32
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')

MENU_STYLE = (
    "QMenu{background:#252525;color:#d0d0d0;border:1px solid #383838;"
    "border-radius:6px;padding:4px;}"
    "QMenu::item{padding:6px 18px;border-radius:4px;}"
    "QMenu::item:selected{background:#2d6fab;}"
    "QMenu::separator{height:1px;background:#383838;margin:4px 8px;}"
)

APP_STYLE = """
    QWidget { background:#181818; color:#d0d0d0; }
    QComboBox {
        background:#2a2a2a; color:#d0d0d0; border:1px solid #404040;
        border-radius:5px; padding:0 8px; min-height:30px; min-width:72px; font-size:12px;
    }
    QComboBox::drop-down { border:none; width:16px; }
    QComboBox QAbstractItemView {
        background:#252525; color:#d0d0d0; selection-background-color:#2d6fab;
    }
    QSlider::groove:horizontal { height:4px; background:#2e2e2e; border-radius:2px; }
    QSlider::handle:horizontal {
        background:#4d8fcc; width:13px; height:13px; margin:-5px 0; border-radius:6px;
    }
    QSlider::sub-page:horizontal { background:#2d6fab; border-radius:2px; }
    QLabel { background:transparent; }
    QScrollBar:vertical { background:#181818; width:7px; }
    QScrollBar::handle:vertical { background:#333; border-radius:3px; min-height:24px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
    QToolTip {
        background:#2a2a2a; color:#d0d0d0; border:1px solid #555;
        border-radius:4px; padding:4px 8px; font-size:11px;
    }
"""
