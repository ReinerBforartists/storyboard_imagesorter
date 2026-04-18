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
# ui_dialogs.py
# This module contains various dialog widgets used throughout the application.
# It provides specialized interfaces for export previews, contact sheet configuration,
# and information displays such as the About dialog and a full-screen Lightbox view.

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QHeaderView, QDialogButtonBox, QSpinBox,
    QPushButton, QTableWidgetItem, QFrame, QWidget, QCheckBox,
    QComboBox, QStackedWidget
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QImage, QPixmap
)
from PyQt6.QtCore import (
    Qt, QRect
)

import utils_workers

# ─── EXPORT PREVIEW DIALOG ──────────────────────────────────────────────────

class ExportPreviewDialog(QDialog):
    """
    A dialog that allows users to preview filenames and choose
    export options like mapping and summary.
    """

    def __init__(self, cards, parent=None, initial_prefix="image_", mapping_enabled=False):
        super().__init__(parent)
        self.cards = cards
        self.setWindowTitle("Export preview")
        self.resize(520, 480)
        self.setStyleSheet("background:#1e1e1e;color:#d0d0d0;")
        lay = QVBoxLayout(self)

        # Prefix input row
        prefix_row = QHBoxLayout()
        prefix_row.addWidget(QLabel("Filename prefix:"))
        self.prefix_edit = QLineEdit(initial_prefix)
        self.prefix_edit.setStyleSheet(
            "background:#252525;color:#d0d0d0;border:1px solid #404040;"
            "border-radius:4px;padding:2px;"
        )
        prefix_row.addWidget(self.prefix_edit)
        lay.addLayout(prefix_row)

        # Options row (Mapping Checkbox)
        options_row = QHBoxLayout()
        self.mapping_cb = QCheckBox("Include filename mapping (.txt)")
        self.mapping_cb.setChecked(mapping_enabled)
        self.mapping_cb.setStyleSheet(
            "QCheckBox { color: #bbb; font-size: 12px; spacing: 8px; }"
            "QCheckBox::indicator { width: 18px; height: 18px; border-radius: 3px;"
            " background: #2a2a2a; border: 1px solid #404040; }"
            "QCheckBox::indicator:checked { background: #2d6fab; border: 1px solid #4d8fcc; }"
        )
        options_row.addWidget(self.mapping_cb)
        options_row.addStretch()
        lay.addLayout(options_row)

        # Info label
        info = QLabel(f"{len(cards)} images will be exported with these names:")
        info.setStyleSheet("color:#bbb;font-size:12px;margin-bottom:4px;")
        lay.addWidget(info)

        # Export preview table
        self.table = QTableWidget(len(cards), 2)
        self.table.setHorizontalHeaderLabels(["New name", "Original file"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet(
            "QTableWidget{background:#252525;border:1px solid #383838;"
            "gridline-color:#2e2e2e;}"
            "QHeaderView::section{background:#2a2a2a;color:#ccc;border:none;"
            "padding:4px;}"
            "QTableWidget::item{padding:3px 6px;}"
        )
        self._populate_table(self.prefix_edit.text())
        lay.addWidget(self.table)

        # Dialog buttons (Ok/Cancel)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.setStyleSheet(
            "QPushButton{background:#2a2a2a;color:#d0d0d0;border:1px solid #404040;"
            "border-radius:4px;padding:4px 18px;min-height:28px;}"
            "QPushButton:hover{background:#383838;}"
        )
        lay.addWidget(btns)
        self.prefix_edit.textChanged.connect(self._populate_table)

    def _populate_table(self, prefix):
        """Updates the table preview as the user types the prefix."""
        digits = len(str(len(self.cards)))
        for i, card in enumerate(self.cards):
            ext = os.path.splitext(card.path)[1]
            new_name = f"{prefix}{str(i + 1).zfill(digits)}{ext}"
            self.table.setItem(i, 0, QTableWidgetItem(new_name))
            self.table.setItem(i, 1, QTableWidgetItem(os.path.basename(card.path)))

    def get_prefix(self):
        """Returns the current text from the prefix input field."""
        return self.prefix_edit.text()

    def get_mapping_enabled(self):
        """Returns whether the mapping checkbox is checked."""
        return self.mapping_cb.isChecked()


# ─── CONTACT SHEET DIALOG ─────────────────────────────────────────────────────

class ContactSheetDialog(QDialog):
    """
    A professional dialog for configuring contact sheet or storyboard list exports.
    Supports grid mode (contact sheet) and list mode (storyboard).
    """
    THUMB_MAX = 512

    def __init__(
        self,
        cards,
        parent=None,
        initial_prefix="Sheet_",
        init_cols=5,
        init_thumb=150,
        init_labels=True,
        init_notes=False,
        init_mode="grid",
        init_per_page=24
    ):
        super().__init__(parent)
        self.cards = cards
        self.setWindowTitle("Export Settings")
        self.resize(400, 500)
        self.setStyleSheet("background:#1e1e1e;color:#d0d0d0;")

        lay = QVBoxLayout(self)
        lay.setSpacing(15)

        # Styles for common widgets
        spin_style = (
            "background:#2a2a2a;color:#d0d0d0;border:1px solid #404040;"
            "border-radius:4px;padding:2px 4px;min-height:26px;"
        )

        # --- SECTION 1: Prefix Input ---
        prefix_row = QHBoxLayout()
        prefix_row.addWidget(QLabel("Filename prefix:"))
        self.prefix_edit = QLineEdit(initial_prefix)
        self.prefix_edit.setStyleSheet(
            "background:#252525;color:#d0d0d0;border:1px solid #404040;"
            "border-radius:4px;padding:4px;"
        )
        prefix_row.addWidget(self.prefix_edit)
        lay.addLayout(prefix_row)

        # --- SECTION 2: Layout Mode Selection ---
        mode_lay = QHBoxLayout()
        mode_lay.addWidget(QLabel("Export Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Grid (Contact Sheet)", "grid")
        self.mode_combo.addItem("List (Storyboard)", "list")
        self.mode_combo.setCurrentIndex(0 if init_mode == "grid" else 1)
        self.mode_combo.setStyleSheet(spin_style)
        self.mode_combo.setFixedWidth(200)
        self.mode_combo.currentIndexChanged.connect(self._toggle_mode_ui)
        mode_lay.addWidget(self.mode_combo)
        mode_lay.addStretch()
        lay.addLayout(mode_lay)

        # --- SECTION 3: Mode-Specific Options (using StackedWidget) ---
        self.options_stack = QStackedWidget()

        # Page 0: Grid Options
        grid_page = QWidget()
        grid_lay = QVBoxLayout(grid_page)
        grid_lay.setContentsMargins(0, 0, 0, 0)
        grid_row1 = QHBoxLayout()
        grid_row1.addWidget(QLabel("Columns:"))
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 20)
        self.cols_spin.setValue(init_cols)
        self.cols_spin.setStyleSheet(spin_style)
        grid_row1.addWidget(self.cols_spin)
        grid_lay.addLayout(grid_row1)

        # Page 1: List Options
        list_page = QWidget()
        list_lay = QVBoxLayout(list_page)
        list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.addWidget(QLabel("Optimized for long notes and readability."))

        self.options_stack.addWidget(grid_page)  # Index 0
        self.options_stack.addWidget(list_page)  # Index 1
        lay.addWidget(self.options_stack)

        # --- SECTION 4: Common Settings (Pagination, Thumb Size, Labels, Notes) ---
        common_group = QFrame()
        common_group.setStyleSheet("background:#252525; border-radius:6px; padding:10px;")
        common_lay = QVBoxLayout(common_group)

        # Pagination
        page_row = QHBoxLayout()
        page_row.addWidget(QLabel("Images per page:"))
        self.per_page_spin = QSpinBox()
        self.per_page_spin.setRange(1, 500)
        self.per_page_spin.setValue(init_per_page)
        self.per_page_spin.setStyleSheet(spin_style)
        page_row.addWidget(self.per_page_spin)
        page_row.addStretch()
        common_lay.addLayout(page_row)

        # Thumbnail Size
        thumb_row = QHBoxLayout()
        thumb_row.addWidget(QLabel("Thumb size (px):"))
        self.thumb_spin = QSpinBox()
        self.thumb_spin.setRange(40, self.THUMB_MAX)
        self.thumb_spin.setValue(min(init_thumb, self.THUMB_MAX))
        self.thumb_spin.setStyleSheet(spin_style)
        thumb_row.addWidget(self.thumb_spin)
        thumb_row.addStretch()
        common_lay.addLayout(thumb_row)

        # Toggles
        self.label_cb = QPushButton("☑  Show filenames")
        self.label_cb.setCheckable(True)
        self.label_cb.setChecked(init_labels)
        self._update_toggle_style(self.label_cb, init_labels)
        self.label_cb.toggled.connect(
            lambda: self._update_toggle_style(self.label_cb, self.label_cb.isChecked())
        )
        common_lay.addWidget(self.label_cb)

        self.note_cb = QPushButton("☐  Show notes")
        self.note_cb.setCheckable(True)
        self.note_cb.setChecked(init_notes)
        self._update_toggle_style(self.note_cb, init_notes)
        self.note_cb.toggled.connect(
            lambda: self._update_toggle_style(self.note_cb, self.note_cb.isChecked())
        )
        common_lay.addWidget(self.note_cb)

        lay.addWidget(common_group)

        # --- SECTION 5: Buttons ---
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.setStyleSheet(
            "QPushButton{background:#2a2a2a;color:#d0d0d0;border:1px solid #404040;padding:6px 18px;}"
        )
        lay.addWidget(btns)

        # Final stretch to push everything up
        lay.addStretch()

        self._toggle_mode_ui()

    def _toggle_mode_ui(self):
        """Switches the visible options based on selected mode."""
        idx = self.mode_combo.currentIndex()
        self.options_stack.setCurrentIndex(idx)

    def _update_toggle_style(self, btn, checked):
        """Updates button appearance for checkboxes."""
        status = "☑" if checked else "☐"
        if btn == self.label_cb:
            text = f"{status}  Show filenames"
        else:
            text = f"{status}  Show notes"
        btn.setText(text)

        if checked:
            btn.setStyleSheet(
                "QPushButton{background:#172d4e;color:#4d8fcc;"
                "border:1px solid #2d6fab;padding:5px 10px;text-align:left;}"
            )
        else:
            btn.setStyleSheet(
                "QPushButton{background:#2a2a2a;color:#eee;"
                "border:1px solid #383838;padding:5px 10px;text-align:left;}"
            )

    # Getters for the Export Logic
    def get_prefix(self):
        return self.prefix_edit.text()

    def get_mode(self):
        return self.mode_combo.currentData()

    def get_cols(self):
        return self.cols_spin.value()

    def get_thumb_size(self):
        return self.thumb_spin.value()

    def get_per_page(self):
        return self.per_page_spin.value()

    def get_labels_enabled(self):
        return self.label_cb.isChecked()

    def get_notes_enabled(self):
        return self.note_cb.isChecked()


# ─── ABOUT DIALOG ─────────────────────────────────────────────────────────────

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Storyboard Imagesorter")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setMaximumWidth(500)
        self.setStyleSheet(
            "QDialog{background-color:#1e1e1e;color:#d0d0d0;}"
            "QLabel{background:transparent;}"
            "QPushButton{background-color:#2a2a2a;color:#d0d0d0;border:1px solid #404040;"
            "border-radius:5px;padding:8px 20px;min-height:30px;}"
            "QPushButton:hover{background-color:#3a3a3a;}"
        )

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(24, 20, 24, 20)

        # Icon section
        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Path to the logo
        icon_path = utils_workers.resource_path("icon.png")

        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                icon.setPixmap(pixmap)

        lay.addWidget(icon)

        # Title section
        title = QLabel("Storyboard Imagesorter v0.9.0")
        title.setFont(QFont("Arial", 17, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#4d8fcc;")
        lay.addWidget(title)

        # Description section
        desc = QLabel(
            "A simple tool for sorting and exporting image sequences\n"
            "for storyboards, previs & animatics."
        )
        desc.setFont(QFont("Arial", 10))
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        lay.addWidget(desc)

        # Copyright section
        copyright_lbl = QLabel("Copyright © 2026 by Reiner Prokein (Haizy Tiles)")
        copyright_lbl.setFont(QFont("Arial", 9))
        copyright_lbl.setStyleSheet("color: #666;")
        copyright_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(copyright_lbl)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#383838;")
        lay.addWidget(sep)

        # Hotkeys section
        hotkey_title = QLabel("Keyboard & Mouse Shortcuts")
        hotkey_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        hotkey_title.setStyleSheet("color:#4d8fcc;margin-top:2px;")
        hotkey_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hotkey_title)

        hotkeys = [
            ("Space", "Open/Close Lightbox"),
            ("Escape", "Close Lightbox"),
            ("← → (in Lightbox)", "Previous / Next image"),
            ("Plus / Minus", "Zoom in / out"),
            ("Ctrl + A", "Select all"),
            ("Ctrl + D", "Deselect all"),
            ("Ctrl + Z", "Undo"),
            ("Ctrl + Y / Ctrl+Shift+Z", "Redo"),
            ("Ctrl + Shift + C", "Clear colors from selected"),
            ("Delete", "Remove selected images"),
            ("← → (Main View)", "Move selected images"),
            ("Ctrl + ← / →", "Move selection to Start / End"),
            ("Tab", "Toggle Stash open/closed"),
            ("B", "Toggle Sidebar open/closed"),
            ("Shift + Click", "Add to selection"),
            ("Ctrl + Click", "Toggle single image selection"),
            ("Mouse Drag", "(Rectangle selection)"),
            ("Drag Image(s)", "Reorder via Drag & Drop"),
            ("Double-Click", "Open in system viewer"),
            ("Drag → Stash", "Move to stash"),
            ("Double-Click Stash", "Return image to main view"),
            ("Shift + Scroll", "Fast scroll through images"),
            ("Right-Click (Color)", "Select cards by color"),
            ("Shift + Right-Click", "Add color to selection"),
            ("Pos 1", "Set view to first image"),
            ("Home", "Set view to last image"),
            ("Page Up", "Scroll through the list"),
            ("Page Down", "Scroll through the list"),
        ]

        grid_widget = QWidget()
        grid_widget.setStyleSheet("background:#252525;border-radius:6px;")
        grid = QVBoxLayout(grid_widget)
        grid.setContentsMargins(12, 8, 12, 8)
        grid.setSpacing(3)

        for key, desc_text in hotkeys:
            row = QHBoxLayout()
            row.setSpacing(8)
            k_lbl = QLabel(key)
            k_lbl.setStyleSheet("color:#e0e0e0;font-family:monospace;font-size:11px;min-width:150px;")
            d_lbl = QLabel(desc_text)
            d_lbl.setStyleSheet("color:#bbb;font-size:11px;")
            row.addWidget(k_lbl)
            row.addWidget(d_lbl, 1)
            grid.addLayout(row)

        lay.addWidget(grid_widget)

        # Bottom button row
        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Close")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setMinimumHeight(36)
        ok_btn.setFixedWidth(140)
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

        self.adjustSize()


# ─── LIGHTBOX (WITH NOTE DISPLAY) ─────────────────────────────────────────────

class Lightbox(QDialog):
    def __init__(self, cards, start_index, parent=None):
        super().__init__(parent)
        self.cards = cards
        self.index = start_index
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")
        self._setup_close_button()
        self._load_current()

    def _setup_close_button(self):
        self.close_btn = QPushButton("✕", self)
        self.close_btn.setFixedSize(36, 36)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(40, 40, 40, 180);
                color: white;
                border-radius: 18px;
                font-size: 20px;
                font-weight: bold;
                border: 1px solid rgba(255, 255, 255, 30);
            }
            QPushButton:hover {
                background: rgba(200, 40, 40, 200);
                border: 1px solid white;
            }
        """)
        self.close_btn.clicked.connect(self.accept)

    def showEvent(self, event):
        super().showEvent(event)
        self._reposition_button()
        self.setFocus()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._reposition_button()
        self.update()

    def _reposition_button(self):
        margin = 20
        self.close_btn.move(self.width() - self.close_btn.width() - margin, margin)

    def _load_current(self):
        self.update()

    def paintEvent(self, e):
        if not self.cards:
            return
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 220))

        path = self.cards[self.index].path
        img = QImage(path)
        if img.isNull():
            p.setPen(QColor("#aaa"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Cannot load image")
            return

        pad = 60
        area = self.rect().adjusted(pad, pad, -pad, -pad)
        scaled = img.scaled(area.width(), area.height(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
        x = area.x() + (area.width() - scaled.width()) // 2
        y = area.y() + (area.height() - scaled.height()) // 2
        p.drawImage(x, y, scaled)

        p.setPen(QColor("#ccc"))
        p.setFont(QFont("Arial", 11))

        note = ""
        if self.parent() and hasattr(self.parent(), 'custom_notes'):
            note = self.parent().custom_notes.get(path, "")

        info_text = f"{self.index + 1} / {len(self.cards)}"
        if note:
            info_text += f"  —  {note}"

        text_rect = self.rect().adjusted(40, 0, -40, -30)
        p.drawText(text_rect,
                   Qt.AlignmentFlag.AlignBottom |
                   Qt.AlignmentFlag.AlignHCenter |
                   Qt.TextFlag.TextWordWrap,
                   info_text)

        if self.index > 0:
            p.setFont(QFont("Arial", 32))
            p.setPen(QColor("#fff"))
            p.drawText(QRect(0, 0, 60, self.height()), Qt.AlignmentFlag.AlignCenter, "‹")
        if self.index < len(self.cards) - 1:
            p.setFont(QFont("Arial", 32))
            p.setPen(QColor("#fff"))
            p.drawText(QRect(self.width() - 60, 0, 60, self.height()), Qt.AlignmentFlag.AlignCenter, "›")

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key.Key_Escape, Qt.Key.Key_Space):
            self.accept()
            return
        elif k in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.index = max(0, self.index - 1)
            self.update()
        elif k in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self.index = min(len(self.cards) - 1, self.index + 1)
            self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if e.pos().x() < 60 and self.index > 0:
                self.index -= 1
                self.update()
            elif e.pos().x() > self.width() - 60 and self.index < len(self.cards) - 1:
                self.index += 1
                self.update()
