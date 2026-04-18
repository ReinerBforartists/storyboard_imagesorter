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
# ui_cards.py
# ThumbnailCard: the main draggable image card shown in the canvas.

import os
from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QLabel, QPushButton,
    QSizePolicy, QStackedWidget, QTextEdit, QApplication,
)

from PyQt6.QtGui import QPixmap, QDrag, QPainter
from PyQt6.QtCore import Qt, QMimeData, QPoint, pyqtSignal
from PyQt6 import sip  # Used to check if the C++ object still exists

import constants
from utils_workers import WorkerSignals, ImageLoadWorker

MIME_INTERNAL = constants.MIME_INTERNAL


# ─── THUMBNAIL CARD ──────────────────────────────────────────────────────────

class ThumbnailCard(QFrame):
    """Draggable thumbnail card with inline note editing and color tagging."""

    clicked = pyqtSignal(int)
    note_changed = pyqtSignal(str, str)

    def __init__(self, path, index, size, thread_pool, sorter):
        super().__init__()
        self.path = path
        self.index = index
        self._size = size
        self._selected = False
        self._color = None
        self._drag_over = False
        self._drop_indicator = None
        self._changed = False
        self._is_note_mode = False
        self.thread_pool = thread_pool
        self.sorter = sorter
        self.drag_start_pos = None
        self._worker = None
        self._source_image = None  # High-quality cache for sharp zooming
        self._current_style = None  # Cache to avoid redundant setStyleSheet calls
        self.setAcceptDrops(True)

        self._idx_font_size = 10
        self._name_font_size = 9

        self._setup_ui()

        self._settings_index_visible = True
        self._settings_name_visible = True
        self._settings_notes_visible = True

    def _setup_ui(self):
        self.setFixedSize(self._size + 16, self._size + 64)
        self._apply_style()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6, 4, 6, 2)
        self.main_layout.setSpacing(1)

        # --- Image Section ---
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.img_container = QWidget()
        self.img_container.setFixedHeight(self._size)
        self.img_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.img_container.setStyleSheet("background:transparent;")
        img_lay = QVBoxLayout(self.img_container)
        img_lay.setContentsMargins(0, 0, 0, 0)
        img_lay.setSpacing(0)

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        img_lay.addWidget(self.img_label)

        self.reload_btn = QPushButton("↻", self.img_container)
        self.reload_btn.setFixedSize(22, 22)
        self.reload_btn.move(self._size - 26, 4)
        self.reload_btn.setStyleSheet(
            "QPushButton{background:#e8872a;color:#fff;border:none;border-radius:11px;"
            "font-size:13px;font-weight:bold;padding:0;}"
            "QPushButton:hover{background:#ff9f35;}"
        )
        self.reload_btn.setVisible(False)
        self.reload_btn.clicked.connect(self._do_reload)

        self.note_editor = QTextEdit()
        self.note_editor.setPlaceholderText("Type note here...")
        self.note_editor.setStyleSheet(
            "background:#2a2a2a; color:#eee; border:1px solid #404040; "
            "border-radius:3px; font-size:10px; padding:4px;"
        )
        self.note_editor.textChanged.connect(self._on_text_changed)

        self.stack.addWidget(self.img_container)
        self.stack.addWidget(self.note_editor)
        self.main_layout.addWidget(self.stack)

        # --- Color Accent Bar (Always visible, part of layout) ---
        self.color_bar = QFrame()
        self.color_bar.setFixedHeight(6)
        # Default theme color: neutral dark grey
        self.color_bar.setStyleSheet("background-color: #404040; border: none;")
        self.main_layout.addWidget(self.color_bar)

        # --- Text Labels Section (Solid Dark Grey) ---
        self.idx_label = QLabel(str(self.index + 1))
        self.idx_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.idx_label)

        self.name_label = QLabel(os.path.basename(self.path))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.name_label)

        # --- Actions Section ---
        self.toggle_btn = QPushButton("📝 + Add Note")
        self.toggle_btn.setFixedHeight(34)
        self.toggle_btn.setStyleSheet(
            "QPushButton{background:#333; color:#aaa; border:1px solid #444; "
            "border-radius:3px; font-size:9px; padding:2px 6px; text-align:left;}"
            "QPushButton:hover{background:#444; color:#fff;}"
        )
        self.toggle_btn.clicked.connect(self.toggle_mode)
        self.main_layout.addWidget(self.toggle_btn)

        # Initialize stack height correctly
        self.stack.setFixedHeight(self._size)
        self.load_thumbnail()

    # ── Note editor ───────────────────────────────────────────────────────────

    def _on_text_changed(self):
        new_text = self.note_editor.toPlainText().strip()
        self.note_changed.emit(self.path, new_text)
        self._update_button_preview(new_text)

    def _update_button_preview(self, text):
        if not text:
            self.toggle_btn.setText("📝 + Add Note")
            return

        metrics = self.toggle_btn.fontMetrics()
        available_width = self.toggle_btn.width() - 12
        emoji_prefix = "📝 "

        lines = text.splitlines()
        if not lines:
            self.toggle_btn.setText(emoji_prefix + text)
            return

        line1_raw = lines[0]
        full_line1 = emoji_prefix + line1_raw

        if metrics.horizontalAdvance(full_line1) <= available_width:
            display_line1 = full_line1
        else:
            display_line1 = metrics.elidedText(full_line1, Qt.TextElideMode.ElideRight, available_width)

        if len(lines) > 1:
            line2_raw = lines[1]
            display_line2 = metrics.elidedText(line2_raw, Qt.TextElideMode.ElideRight, available_width)
            self.toggle_btn.setText(f"{display_line1}\n{display_line2}")
        else:
            self.toggle_btn.setText(display_line1)

    def toggle_mode(self):
        if self._is_note_mode:
            self._is_note_mode = False
            self.stack.setCurrentIndex(0)
            self.stack.setFixedHeight(self._size)
            current_text = self.note_editor.toPlainText().strip()
            self._update_button_preview(current_text)
        else:
            self._is_note_mode = True
            self.stack.setCurrentIndex(1)
            self.stack.setFixedHeight(max(self._size, 120))
            self.toggle_btn.setText("🖼 Show Image")

        self._apply_style()
        self.set_label_visibility(
            self._settings_index_visible,
            self._settings_name_visible,
            self._settings_notes_visible
        )

    def set_note_text(self, text: str):
        self.note_editor.blockSignals(True)
        self.note_editor.setPlainText(text if text else "")
        self._update_button_preview(text if text else "")
        self.note_editor.blockSignals(False)

    # ── Visibility / sizing ───────────────────────────────────────────────────

    def set_label_visibility(self, show_index: bool, show_filename: bool, show_notes: bool):
        self._settings_index_visible = show_index
        self._settings_name_visible = show_filename
        self._settings_notes_visible = show_notes

        self.idx_label.setVisible(show_index)
        self.name_label.setVisible(show_filename)
        self.toggle_btn.setVisible(show_notes)

        scale = 1.0 + ((self._size / 200.0) - 1.0) * 0.6
        self._idx_font_size = max(8, int(10 * scale))
        self._name_font_size = max(7, int(9 * scale))

        # Solid dark grey background for text labels
        base_label_style = "background-color: #2a2a2a; color: white;"

        self.idx_label.setStyleSheet(f"{base_label_style} font-size:{self._idx_font_size}px;")
        self.name_label.setStyleSheet(f"{base_label_style} font-size:{self._name_font_size}px;")

        self.toggle_btn.setStyleSheet(
            f"QPushButton{{background:#333; color:#aaa; border:1px solid #444; "
            f"border-radius:3px; font-size:{max(8, int(9 * scale))}px; padding:2px 6px; text-align:left;}}"
            f"QPushButton:hover{{background:#444; color:#fff;}}"
        )

        self.main_layout.activate()
        required_height = self.main_layout.sizeHint().height()
        self.setFixedSize(self._size + 16, int(required_height))

        current_color = self.sorter.temp_colors.get(self.path)
        if current_color:
            self.set_color(current_color)

    def update_size(self, size: int):
        if self._size == size:
            return
        self._size = size
        self.img_container.setFixedHeight(size)

        if self._source_image and not self._source_image.isNull():
            scaled_img = self._source_image.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.img_label.setPixmap(QPixmap.fromImage(scaled_img))
        else:
            self.load_thumbnail()

        if self._is_note_mode:
            self.stack.setFixedHeight(max(self._size, 120))
        else:
            self.stack.setFixedHeight(self._size)

        self.reload_btn.move(size - 26, 4)
        self.set_label_visibility(
            self._settings_index_visible,
            self._settings_name_visible,
            self._settings_notes_visible
        )

    # ── Thumbnail loading ─────────────────────────────────────────────────────

    def load_thumbnail(self):
        if self._source_image and not self._source_image.isNull():
            return

        if self._worker:
            self._worker.cancelled = True
            self._worker = None

        self._load_id = getattr(self, '_load_id', 0) + 1  # Monoton steigend
        current_id = self._load_id

        sig = WorkerSignals()
        sig.finished.connect(lambda path, img: self._on_loaded(path, img, current_id))
        self._worker = ImageLoadWorker(self.path, self._size, sig)
        self.thread_pool.start(self._worker)

    def unload_thumbnail(self):
        """Unloads the thumbnail and cancels any active loading process."""
        if self._worker:
            self._worker.cancelled = True
            self._worker = None

        # Clear the source image cache
        self._source_image = None

        try:
            if self.img_label:
                self.img_label.clear()
        except (RuntimeError, AttributeError):
            pass

    def _on_loaded(self, path, image, load_id):
        if sip.isdeleted(self):
            return
        if load_id != self._load_id:   # Veraltetes Signal → verwerfen
            return
        try:
            self._source_image = image
            if self.img_label:
                scaled_img = image.scaled(
                    self._size, self._size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.img_label.setPixmap(QPixmap.fromImage(scaled_img))
        except (RuntimeError, AttributeError):
            pass

    # ── State ─────────────────────────────────────────────────────────────────

    def mark_changed(self, changed: bool):
        self._changed = changed
        self.reload_btn.setVisible(changed)
        if changed:
            s = "background:#252525;border:2px solid #e8872a;border-radius:5px;"
            if s != self._current_style:
                self._current_style = s
                self.setStyleSheet(s)
        else:
            self._apply_style()

    def _do_reload(self):
        self._source_image = None
        self.load_thumbnail()
        self.mark_changed(False)

    def _apply_style(self):
        if self._drag_over:
            s = "background:#1e3d6e;border:2px solid #4d8fcc;border-radius:5px;"
        elif self._selected:
            s = "background:#172d4e;border:2px solid #2d6fab;border-radius:5px;"
        else:
            s = "background:#252525;border:2px solid #404040;border-radius:5px;"
        if s != self._current_style:
            self._current_style = s
            self.setStyleSheet(s)

    def set_selected(self, sel):
        self._selected = sel
        self._apply_style()

    def set_color(self, color_hex: str | None):
        """Sets the card's color via a dedicated Accent Bar.
        The text area remains solid dark grey for maximum readability."""
        self._color = color_hex
        if color_hex:
            # Use the neon color for the bar
            self.color_bar.setStyleSheet(f"background-color: {color_hex}; border: none;")
        else:
            # Revert to neutral theme grey
            self.color_bar.setStyleSheet("background-color: #404040; border: none;")

    def update_index(self, index):
        self.index = index
        self.idx_label.setText(str(index + 1))

    # ── Mouse / drag ──────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self.note_editor.underMouse():
                return
            self.drag_start_pos = e.pos()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self.note_editor.hasFocus():
                return
            self.clicked.emit(self.index)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self.note_editor.underMouse():
                return
            self.sorter._open_image(self.path)

    def mouseMoveEvent(self, e):
        if self.note_editor.hasFocus():
            return
        if not (e.buttons() & Qt.MouseButton.LeftButton) or self.drag_start_pos is None:
            return
        if (e.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        sel = [c.path for c in self.sorter.cards if c._selected]
        if self.path not in sel:
            sel = [self.path]

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MIME_INTERNAL, ",".join(sel).encode())
        drag.setMimeData(mime)

        px = self.img_label.pixmap()
        if not px or px.isNull():
            px = QPixmap(84, 84)
            px.fill(Qt.GlobalColor.transparent)

        count = len(sel)
        if count > 1:
            off = min(count - 1, 3) * 4
            preview = QPixmap(84 + off, 84 + off)
            preview.fill(Qt.GlobalColor.transparent)
            p = QPainter(preview)
            for i in range(min(count, 4)):
                p.setOpacity(0.5 + 0.5 * (i == min(count, 4) - 1))
                o = (min(count, 4) - 1 - i) * 4
                p.drawPixmap(o, o, px.scaled(84, 84, Qt.AspectRatioMode.KeepAspectRatio))
            p.end()
            drag.setPixmap(preview)
        else:
            drag.setPixmap(px.scaled(84, 84, Qt.AspectRatioMode.KeepAspectRatio))

        drag.setHotSpot(QPoint(42, 42))
        drag.exec(Qt.DropAction.MoveAction)
