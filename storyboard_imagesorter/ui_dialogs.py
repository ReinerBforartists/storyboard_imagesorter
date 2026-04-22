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
    QComboBox, QStackedWidget, QScrollArea, QFileDialog
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QImage, QPixmap
)
from PyQt6.QtCore import (
    Qt, QRect, QTimer
)

import utils_workers

# ─── SHARED HELPERS ──────────────────────────────────────────────────────────

_FOLDER_ROW_STYLE = (
    "background:#252525;color:#d0d0d0;border:1px solid #404040;"
    "border-radius:4px;padding:2px 4px;min-height:26px;"
)
_CHOOSE_BTN_STYLE = (
    "QPushButton{background:#2a2a2a;color:#d0d0d0;border:1px solid #404040;"
    "border-radius:4px;padding:2px 10px;min-height:26px;}"
    "QPushButton:hover{background:#383838;}"
)
_COLLISION_STYLE_WARN = (
    "background:#3a1010;color:#ff7070;border:1px solid #7a2020;"
    "border-radius:4px;padding:4px 8px;font-size:11px;"
)
_COLLISION_STYLE_OK = (
    "background:#0f2a18;color:#5dba7a;border:1px solid #1e5c35;"
    "border-radius:4px;padding:4px 8px;font-size:11px;"
)
_EXPORT_BTN_STYLE = (
    "QPushButton{background:#1a3f6f;color:#d0e8ff;border:1px solid #2d6fab;"
    "border-radius:4px;padding:4px 18px;min-height:28px;font-weight:bold;}"
    "QPushButton:hover{background:#245a9e;}"
    "QPushButton:disabled{background:#252525;color:#555;border-color:#383838;}"
)
_CANCEL_BTN_STYLE = (
    "QPushButton{background:#2a2a2a;color:#d0d0d0;border:1px solid #404040;"
    "border-radius:4px;padding:4px 18px;min-height:28px;}"
    "QPushButton:hover{background:#383838;}"
)


def _make_folder_row(dialog, initial_dir=""):
    """
    Returns (layout, path_edit, choose_btn).
    Clicking choose_btn opens a native folder picker and updates path_edit.
    """
    row = QHBoxLayout()
    row.setSpacing(6)
    path_edit = QLineEdit(initial_dir)
    path_edit.setPlaceholderText("Choose export folder…")
    path_edit.setStyleSheet(_FOLDER_ROW_STYLE)
    row.addWidget(path_edit, 1)
    choose_btn = QPushButton("Choose Folder")
    choose_btn.setStyleSheet(_CHOOSE_BTN_STYLE)
    choose_btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def _pick():
        current = path_edit.text() or ""
        folder = QFileDialog.getExistingDirectory(dialog, "Select Export Folder", current)
        if folder:
            path_edit.setText(folder)

    choose_btn.clicked.connect(_pick)
    row.addWidget(choose_btn)
    return row, path_edit, choose_btn


# ─── EXPORT PREVIEW DIALOG ──────────────────────────────────────────────────

class ExportPreviewDialog(QDialog):
    """
    Single-step image export dialog:
    prefix → folder picker → live collision warning → Export button.
    """

    def __init__(self, cards, parent=None, initial_prefix="image_",
                 mapping_enabled=False, initial_dir=""):
        super().__init__(parent)
        self.cards = cards
        self._folder = initial_dir
        self.setWindowTitle("Export Images")
        self.setFixedWidth(500)  # Standardized width to match ContactSheetDialog
        self.setStyleSheet("background:#1e1e1e;color:#d0d0d0;")
        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        # ── Prefix row ───────────────────────────────────────────────────────
        prefix_row = QHBoxLayout()
        prefix_lbl = QLabel("Filename prefix:")
        prefix_lbl.setFixedWidth(120)
        prefix_row.addWidget(prefix_lbl)
        self.prefix_edit = QLineEdit(initial_prefix)
        self.prefix_edit.setStyleSheet(_FOLDER_ROW_STYLE)
        prefix_row.addWidget(self.prefix_edit)
        lay.addLayout(prefix_row)

        # ── Mapping Toggle Button (Full Width like in other dialogs) ───────
        self.mapping_btn = QPushButton()
        self.mapping_btn.setCheckable(True)
        self.mapping_btn.setChecked(mapping_enabled)
        self._update_mapping_button_style(mapping_enabled)
        self.mapping_btn.toggled.connect(self._on_mapping_toggled)
        lay.addWidget(self.mapping_btn)

        # --- Whitespace after settings section ---
        lay.addSpacing(10)

        # ── Preview table ─────────────────────────────────────────────────────
        info = QLabel(f"{len(cards)} images will be exported with these names:")
        info.setStyleSheet("color:#bbb;font-size:12px;margin-bottom:2px;")
        lay.addWidget(info)

        self.table = QTableWidget(len(cards), 2)
        self.table.setHorizontalHeaderLabels(["New name", "Original file"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet(
            "QTableWidget{background:#252525;border:1px solid #383838;"
            "gridline-color:#2e2e2e;}"
            "QHeaderView::section{background:#2a2a2a;color:#ccc;border:none;padding:4px;}"
            "QTableWidget::item{padding:3px 6px;}"
        )
        lay.addWidget(self.table)

        # --- Whitespace after preview table ---
        lay.addSpacing(15)

        # ── Folder row ────────────────────────────────────────────────────────
        folder_lbl = QLabel("Export folder:")
        folder_lbl.setStyleSheet("color:#bbb;font-size:12px;")
        lay.addWidget(folder_lbl)
        folder_row, self._folder_edit, _ = _make_folder_row(self, initial_dir)
        lay.addLayout(folder_row)

        # ── Collision warning ─────────────────────────────────────────────────
        self._collision_lbl = QLabel("")
        self._collision_lbl.setWordWrap(True)
        self._collision_lbl.setVisible(False)
        lay.addWidget(self._collision_lbl)

        # --- Whitespace before final action buttons ---
        lay.addSpacing(10)

        # ── Buttons row ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_CANCEL_BTN_STYLE)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self._export_btn = QPushButton("Export")
        self._export_btn.setStyleSheet(_EXPORT_BTN_STYLE)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._export_btn)
        lay.addLayout(btn_row)

        # ── Debounce timer & initial load ─────────────────────────────────────
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._refresh)

        self.prefix_edit.textChanged.connect(self._trigger_update)
        self._folder_edit.textChanged.connect(self._trigger_update)

        # Initial population
        self._refresh()

    def _on_mapping_toggled(self, checked):
        """Handles the button toggle and updates its visual state."""
        self._update_mapping_button_style(checked)

    def _update_mapping_button_style(self, checked):
        """Applies consistent styling to the mapping toggle button (Full Width)."""
        status = "☑" if checked else "☐"
        text = f"{status}  Include filename mapping (.txt)"
        self.mapping_btn.setText(text)

        if checked:
            self.mapping_btn.setStyleSheet(
                "QPushButton{background:#172d4e;color:#4d8fcc;"
                "border:1px solid #2d6fab;padding:5px 10px;text-align:left;}"
            )
        else:
            self.mapping_btn.setStyleSheet(
                "QPushButton{background:#2a2a2a;color:#eee;"
                "border:1px solid #383838;padding:5px 10px;text-align:left;}"
            )

    def _trigger_update(self):
        """Starts/restarts the debounce timer."""
        self._update_timer.start(400)

    def _refresh(self):
        """Rebuild table preview and collision warning."""
        prefix = self.prefix_edit.text()
        folder = self._folder_edit.text().strip()

        # Table
        digits = len(str(len(self.cards)))
        self.table.blockSignals(True)
        for i, card in enumerate(self.cards):
            ext = os.path.splitext(card.path)[1]
            new_name = f"{prefix}{str(i + 1).zfill(digits)}{ext}"
            self.table.setItem(i, 0, QTableWidgetItem(new_name))
            self.table.setItem(i, 1, QTableWidgetItem(os.path.basename(card.path)))
        self.table.blockSignals(False)

        # Collision check
        collisions = []
        if folder and os.path.isdir(folder):
            try:
                existing = set(os.listdir(folder))
                filenames = [
                    f"{prefix}{str(i + 1).zfill(digits)}{os.path.splitext(c.path)[1]}"
                    for i, c in enumerate(self.cards)
                ]
                collisions = [f for f in filenames if f in existing]
            except OSError:
                pass

        if collisions:
            names = ", ".join(collisions[:5])
            if len(collisions) > 5:
                names += f" … (+{len(collisions) - 5} more)"
            self._collision_lbl.setText(
                f"⚠  {len(collisions)} file(s) will be overwritten: {names}"
            )
            self._collision_lbl.setStyleSheet(_COLLISION_STYLE_WARN)
            self._collision_lbl.setVisible(True)
        else:
            self._collision_lbl.setVisible(False)

        self._export_btn.setEnabled(bool(folder and os.path.isdir(folder)))

    def get_prefix(self):
        return self.prefix_edit.text()

    def get_folder(self):
        return self._folder_edit.text().strip()

    def get_mapping_enabled(self):
        """Returns the current state of the mapping toggle."""
        return self.mapping_btn.isChecked()


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
        init_notes=True,
        init_index=True,
        init_mode="grid",
        init_grid_per_page=20,
        init_list_per_page=10,
        initial_dir=""
    ):
        super().__init__(parent)
        self.cards = cards
        self._initial_dir = initial_dir
        self.setWindowTitle("Export Contact Sheet")
        self.setFixedWidth(500)  # Standardized width
        self.setStyleSheet("background:#1e1e1e;color:#d0d0d0;")

        # Setup Debounce Timer for consistency across dialogs
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._apply_settings_debounced)

        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.setContentsMargins(14, 14, 14, 14)

        # ── Shared styles ────────────────────────────────────────────────────
        LABEL_WIDTH = 120
        INDENT = 16
        input_style = (
            "background:#2a2a2a;color:#d0d0d0;border:1px solid #404040;"
            "border-radius:4px;padding:2px 4px;min-height:26px;"
        )

        def make_row(label_text, widget, indent=False):
            """Fixed-width label | widget stretches to fill remaining space."""
            row = QHBoxLayout()
            row.setContentsMargins(INDENT if indent else 0, 0, 0, 0)
            row.setSpacing(8)
            lbl = QLabel(label_text)
            lbl.setFixedWidth(LABEL_WIDTH - (INDENT if indent else 0))
            row.addWidget(lbl)
            row.addWidget(widget, 1)
            return row

        def make_spin(min_val, max_val, value):
            s = QSpinBox()
            s.setRange(min_val, max_val)
            s.setValue(value)
            s.setStyleSheet(input_style)
            s.setButtonSymbols(QSpinBox.ButtonSymbols.PlusMinus)
            s.setMinimumHeight(28)
            return s

        # --- SECTION 1: Prefix Input ---
        self.prefix_edit = QLineEdit(initial_prefix)
        self.prefix_edit.setStyleSheet(
            "background:#252525;color:#d0d0d0;border:1px solid #404040;"
            "border-radius:4px;padding:4px;min-height:26px;"
        )
        lay.addLayout(make_row("Filename prefix:", self.prefix_edit))

        # Space between Prefix and Export Mode
        lay.addSpacing(15)

        # --- SECTION 2: Layout Mode Selection ---
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Grid (Contact Sheet)", "grid")
        self.mode_combo.addItem("List (Storyboard)", "list")
        self.mode_combo.setCurrentIndex(0 if init_mode == "grid" else 1)
        self.mode_combo.setStyleSheet(input_style)
        self.mode_combo.currentIndexChanged.connect(self._toggle_mode_ui)
        lay.addLayout(make_row("Export Mode:", self.mode_combo))

        # --- SECTION 3: Mode-Specific Options (using StackedWidget) ---
        self.options_stack = QStackedWidget()
        self.options_stack.setFixedHeight(72)

        grid_page = QWidget()
        grid_lay = QVBoxLayout(grid_page)
        grid_lay.setContentsMargins(0, 0, 0, 0)
        grid_lay.setSpacing(8)

        self.cols_spin = make_spin(1, 20, init_cols)
        grid_lay.addLayout(make_row("Columns:", self.cols_spin, indent=True))

        self.grid_per_page_spin = make_spin(1, 500, init_grid_per_page)
        grid_lay.addLayout(make_row("Images per page:", self.grid_per_page_spin, indent=True))

        list_page = QWidget()
        list_lay = QVBoxLayout(list_page)
        list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.setSpacing(8)

        self.list_per_page_spin = make_spin(1, 500, init_list_per_page)
        list_lay.addLayout(make_row("Images per page:", self.list_per_page_spin, indent=True))
        list_lay.addStretch()

        self.options_stack.addWidget(grid_page)   # Index 0
        self.options_stack.addWidget(list_page)   # Index 1
        lay.addWidget(self.options_stack)

        # Space before Thumb Size to separate Export Mode section
        lay.addSpacing(15)

        # --- SECTION 4: Thumb Size (always visible) ---
        self.thumb_spin = make_spin(40, self.THUMB_MAX, min(init_thumb, self.THUMB_MAX))
        lay.addLayout(make_row("Thumb size (px):", self.thumb_spin))

        # Spacer before separator
        lay.addSpacing(10)

        # --- Separator ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#383838;margin-top:2px;margin-bottom:2px;")
        lay.addWidget(sep)

        # Spacer before toggle buttons
        lay.addSpacing(10)

        # --- SECTION 5: Toggle Buttons ---
        self.index_cb = QPushButton("☑  Show index number")
        self.index_cb.setCheckable(True)
        self.index_cb.setChecked(init_index)

        self.label_cb = QPushButton("☑  Show filenames")
        self.label_cb.setCheckable(True)
        self.label_cb.setChecked(init_labels)

        self.note_cb = QPushButton("☐  Show notes")
        self.note_cb.setCheckable(True)
        self.note_cb.setChecked(init_notes)

        self._update_toggle_style(self.index_cb, init_index)
        self._update_toggle_style(self.label_cb, init_labels)
        self._update_toggle_style(self.note_cb, init_notes)

        self.index_cb.toggled.connect(
            lambda: self._update_toggle_style(self.index_cb, self.index_cb.isChecked())
        )
        self.label_cb.toggled.connect(
            lambda: self._update_toggle_style(self.label_cb, self.label_cb.isChecked())
        )
        self.note_cb.toggled.connect(
            lambda: self._update_toggle_style(self.note_cb, self.note_cb.isChecked())
        )

        toggle_lay = QVBoxLayout()
        toggle_lay.setSpacing(3)
        toggle_lay.setContentsMargins(0, 0, 0, 0)
        toggle_lay.addWidget(self.index_cb)
        toggle_lay.addWidget(self.label_cb)
        toggle_lay.addWidget(self.note_cb)
        lay.addLayout(toggle_lay)

        # Spacer before folder row
        lay.addSpacing(10)

        # --- SECTION 6: Export Folder ---
        folder_lbl = QLabel("Export folder:")
        folder_lbl.setStyleSheet("color:#bbb;font-size:12px;")
        lay.addWidget(folder_lbl)
        folder_row, self._folder_edit, _ = _make_folder_row(self, initial_dir)
        lay.addLayout(folder_row)

        # --- Collision warning ---
        self._collision_lbl = QLabel("")
        self._collision_lbl.setWordWrap(True)
        self._collision_lbl.setVisible(False)
        lay.addWidget(self._collision_lbl)

        # Spacer before buttons
        lay.addSpacing(6)

        # --- SECTION 7: Export / Cancel ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_CANCEL_BTN_STYLE)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self._export_btn = QPushButton("Export")
        self._export_btn.setStyleSheet(_EXPORT_BTN_STYLE)
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._export_btn)
        lay.addLayout(btn_row)

        self._toggle_mode_ui()

        # Connect debounce triggers
        self.prefix_edit.textChanged.connect(self._trigger_update)
        self.cols_spin.valueChanged.connect(self._trigger_update)
        self.grid_per_page_spin.valueChanged.connect(self._trigger_update)
        self.list_per_page_spin.valueChanged.connect(self._trigger_update)
        self.thumb_spin.valueChanged.connect(self._trigger_update)
        self._folder_edit.textChanged.connect(self._trigger_update)
        self.mode_combo.currentIndexChanged.connect(self._trigger_update)

        # Initial state
        self._update_collision_warning()

        # Finalize size
        self.adjustSize()

    def _trigger_update(self):
        """Starts/restarts the debounce timer."""
        self._update_timer.start(400)

    def _apply_settings_debounced(self):
        """Called after typing pause — refresh collision warning."""
        self._update_collision_warning()

    def _update_collision_warning(self):
        """Compute expected output filenames and warn about collisions."""
        folder = self._folder_edit.text().strip()
        prefix = self.prefix_edit.text()
        mode = self.mode_combo.currentData()
        per_page = (
            self.grid_per_page_spin.value()
            if mode == "grid"
            else self.list_per_page_spin.value()
        )
        num_chunks = max(1, -(-len(self.cards) // per_page)) if self.cards else 1
        suffix = "grid" if mode == "grid" else "list"
        expected = [
            f"{prefix}_{suffix}_{i + 1:02d}.png" for i in range(num_chunks)
        ]

        collisions = []
        if folder and os.path.isdir(folder):
            try:
                existing = set(os.listdir(folder))
                collisions = [f for f in expected if f in existing]
            except OSError:
                pass

        if collisions:
            names = ", ".join(collisions[:5])
            if len(collisions) > 5:
                names += f" … (+{len(collisions) - 5} more)"
            self._collision_lbl.setText(
                f"⚠  {len(collisions)} file(s) will be overwritten: {names}"
            )
            self._collision_lbl.setStyleSheet(_COLLISION_STYLE_WARN)
            self._collision_lbl.setVisible(True)
        else:
            self._collision_lbl.setVisible(False)

        self._export_btn.setEnabled(bool(folder and os.path.isdir(folder)))

    def _toggle_mode_ui(self):
        """Switches the visible options based on selected mode."""
        idx = self.mode_combo.currentIndex()
        self.options_stack.setCurrentIndex(idx)

    def _update_toggle_style(self, btn, checked):
        """Updates button appearance for checkboxes."""
        status = "☑" if checked else "☐"
        if btn == self.label_cb:
            text = f"{status}  Show filenames"
        elif btn == self.note_cb:
            text = f"{status}  Show notes"
        else:
            text = f"{status}  Show index number"
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

    def get_prefix(self):
        return self.prefix_edit.text()

    def get_folder(self):
        return self._folder_edit.text().strip()

    def get_mode(self):
        return self.mode_combo.currentData()

    def get_cols(self):
        return self.cols_spin.value()

    def get_thumb_size(self):
        return self.thumb_spin.value()

    def get_grid_per_page(self):
        return self.grid_per_page_spin.value()

    def get_list_per_page(self):
        return self.list_per_page_spin.value()

    def get_labels_enabled(self):
        return self.label_cb.isChecked()

    def get_notes_enabled(self):
        return self.note_cb.isChecked()

    def get_index_enabled(self):
        return self.index_cb.isChecked()

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
        copyright_lbl.setStyleSheet("color: #999;")
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
            ("Space", "Open / Close Lightbox"),
            ("Escape", "Close Lightbox"),
            ("← → (in Lightbox)", "Previous / Next image"),
            ("+ / -", "Zoom in / out"),
            ("Ctrl + A", "Select all"),
            ("Ctrl + D", "Deselect all"),
            ("Ctrl + Z", "Undo"),
            ("Ctrl + Y / Ctrl + Shift + Z", "Redo"),
            ("Ctrl + Shift + C", "Clear colors from selected"),
            ("Delete", "Remove selected images"),
            ("← → (Main View)", "Move selected images"),
            ("Ctrl + ← / →", "Move selection to Start / End"),
            ("F", "Focus view on first selected image"),
            ("Home / Pos 1", "Jump to first image"),
            ("End / Ende", "Jump to last image"),
            ("Page Up / Page Down", "Scroll through images"),
            ("Tab", "Toggle Stash open / closed"),
            ("B", "Toggle Sidebar open / closed"),
            ("Shift + Click", "Extend selection"),
            ("Ctrl + Click", "Toggle single image selection"),
            ("Mouse Drag (empty area)", "Rectangle / lasso selection"),
            ("Drag Image(s)", "Reorder via Drag & Drop"),
            ("Double-Click", "Open in system viewer"),
            ("Drag → Stash", "Move to stash"),
            ("Double-Click Stash", "Return image to main view"),
            ("Shift + Scroll", "Fast scroll through images"),
            ("Right-Click (Color)", "Select cards by color"),
            ("Shift + Right-Click (Color)", "Add color selection"),
        ]

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            "QScrollBar:vertical{background:#181818;width:6px;}"
            "QScrollBar::handle:vertical{background:#333;border-radius:3px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )

        grid_widget = QWidget()
        grid_widget.setStyleSheet("background:#252525;border-radius:6px;")
        grid = QVBoxLayout(grid_widget)
        grid.setContentsMargins(12, 8, 12, 8)
        grid.setSpacing(3)

        for key, desc_text in hotkeys:
            row = QHBoxLayout()
            row.setSpacing(8)
            k_lbl = QLabel(key)
            k_lbl.setStyleSheet("color:#e0e0e0;font-family:monospace;font-size:11px;min-width:160px;")
            d_lbl = QLabel(desc_text)
            d_lbl.setStyleSheet("color:#bbb;font-size:11px;")
            row.addWidget(k_lbl)
            row.addWidget(d_lbl, 1)
            grid.addLayout(row)

        scroll_area.setWidget(grid_widget)
        scroll_area.setFixedHeight(280)
        lay.addWidget(scroll_area)

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
        # Safety check for race conditions during direct disk access in paint event
        if img.isNull() or img.width() == 0 or img.height() == 0:
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
