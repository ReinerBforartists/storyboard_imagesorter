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
from PyQt6.QtCore import (
    Qt, QRect, QTimer, pyqtProperty,
    QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QImage, QPixmap, QMouseEvent,
    QPaintEvent, QKeyEvent, QShowEvent, QResizeEvent
)
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QHeaderView, QSpinBox,
    QPushButton, QTableWidgetItem, QFrame, QWidget,
    QComboBox, QStackedWidget, QScrollArea, QFileDialog
)

import utils_workers
from commands import RemoveSelectedCommand, MoveToStashCommand
import ui_components
import ui_styles

# ─── SHARED HELPERS ──────────────────────────────────────────────────────────

_FOLDER_ROW_STYLE = ui_styles.STYLE_INPUT
_CHOOSE_BTN_STYLE = ui_styles.STYLE_BUTTON_DEFAULT
_COLLISION_STYLE_WARN = ui_styles.STYLE_COLLISION_WARN
_EXPORT_BTN_STYLE = ui_styles.STYLE_BUTTON_PRIMARY
_CANCEL_BTN_STYLE = ui_styles.STYLE_BUTTON_DEFAULT


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
        self.setStyleSheet(f"background:#1e1e1e;color:{ui_styles.TEXT_PRIMARY};")
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
        self.table.setStyleSheet(ui_styles.STYLE_TABLE)
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
            self.mapping_btn.setStyleSheet(ui_styles.STYLE_TOGGLE_ACTIVE)
        else:
            self.mapping_btn.setStyleSheet(ui_styles.STYLE_TOGGLE_INACTIVE)

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

        # Collision check & Path validation
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
        elif not folder or not os.path.isdir(folder):
            # Warning when button is disabled due to invalid path
            self._collision_lbl.setText("⚠  Please select a valid export folder to enable export.")
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
        self.setStyleSheet(f"background:#1e1e1e;color:{ui_styles.TEXT_PRIMARY};")

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
        elif not folder or not os.path.isdir(folder):
            # Warning when button is disabled due to invalid path
            self._collision_lbl.setText("⚠  Please select a valid export folder to enable export.")
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
            btn.setStyleSheet(ui_styles.STYLE_TOGGLE_ACTIVE)
        else:
            btn.setStyleSheet(ui_styles.STYLE_TOGGLE_INACTIVE)

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
        self.setMinimumWidth(440)
        self.setMaximumWidth(500)
        self.setStyleSheet(
            f"QDialog{{background-color:#1e1e1e;color:{ui_styles.TEXT_PRIMARY};}}"
            f"QLabel{{background:transparent;}}"
            + ui_styles.STYLE_BUTTON_DEFAULT
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
        title = QLabel("Storyboard Imagesorter v0.9.2")
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

        # ─── Hotkeys section ─────────────────────────────────────────────────────
        hotkey_title = QLabel("Keyboard & Mouse Shortcuts")
        hotkey_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        hotkey_title.setStyleSheet("color:#4d8fcc;margin-top:2px;")
        hotkey_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hotkey_title)

        # Structured hotkeys dictionary
        hotkeys_data = {
            "Main View": [
                ("Space", "Open / Close Full-screen Lightbox"),
                ("Ctrl + A / Ctrl + D", "Select All / Deselect All"),
                ("Ctrl + A / Ctrl + D", "Select All / Deselect All"),
                ("Ctrl + O", "Open Import dialog"),
                ("C", "Clear colors from selected"),
                ("Delete", "Remove selected images"),
                ("W", "Move selected to Stash"),
                ("← / → (Arrows)", "Move selection left or right"),
                ("Ctrl + ← / → (Arrows)", "Move selection to Start / End"),
                ("F", "Focus view on first selected image"),
                ("Home / Pos 1", "Jump to first image"),
                ("End / Ende", "Jump to last image"),
                ("Page Up / Page Down", "Scroll through images"),
                ("Tab", "Toggle Stash open / closed"),
                ("B", "Toggle Sidebar open / closed"),
                ("+ / -", "Zoom in / out of the canvas"),
                ("Scroll", "Scroll through sequences"),
                ("Shift + Scroll", "**Fast scroll** through large sequences"),
                ("Right-Click (Color)", "Select all cards with this color"),
                ("Shift + Right-Click (Color)", "Add color to current selection"),
            ],
            "Lightbox Mode": [
                ("Esc / Space", "Close Lightbox"),
                ("← / → (Arrows)", "Previous / Next image"),
                ("Scroll", "Previous / Next image"),
                ("W", "Move current image to Stash"),
                ("Delete", "Remove current image"),
            ],
            "Mouse & Interactions": [
                ("Shift + Click", "Extend selection"),
                ("Ctrl + Click", "Toggle single image selection"),
                ("Mouse Drag (empty area)", "Rectangle / lasso selection"),
                ("Drag Image(s)", "Reorder via Drag & Drop"),
                ("Double-Click", "Open in system viewer"),
                ("Drag → Stash", "Move to stash"),
                ("Double-Click Stash", "Return image to main view"),
            ]
        }

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            f"QScrollArea{{border:none;background:transparent;}}"
            + ui_styles.STYLE_SCROLLBAR
        )

        grid_widget = QWidget()
        grid_widget.setStyleSheet("background:#252525;border-radius:6px;")
        grid = QVBoxLayout(grid_widget)
        grid.setContentsMargins(12, 8, 12, 8)
        grid.setSpacing(3)

        # Iterating through categories
        for section_name, shortcuts in hotkeys_data.items():
            # Add Section Header
            header_lbl = QLabel(section_name)
            header_lbl.setStyleSheet("color:#4d8fcc; font-weight:bold; font-size:12px; margin-top:10px; margin-bottom:2px;")
            grid.addWidget(header_lbl)

            for key, desc_text in shortcuts:
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

# ─── LIGHTBOX (WITH NOTE DISPLAY & HEADER ACTIONS) ─────────────────────────────

class Lightbox(QDialog):
    """Full-screen image viewer with dual-mode motion feedback:
    'Remove' (scale down) and 'Stash' (slide down).
    """

    @pyqtProperty(float)
    def image_opacity(self):
        return self._image_opacity

    @image_opacity.setter
    def image_opacity(self, value):
        self._image_opacity = value
        self.update()

    @pyqtProperty(float)
    def image_scale(self):
        return self._image_scale

    @image_scale.setter
    def image_scale(self, value):
        self._image_scale = value
        self.update()

    @pyqtProperty(float)
    def image_y_offset(self):
        return self._image_y_offset

    @image_y_offset.setter
    def image_y_offset(self, value):
        self._image_y_offset = value
        self.update()

    def __init__(self, cards: list[ui_components.ThumbnailCard], start_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sorter = parent
        self.index = start_index
        self._last_action_time = 0.0
        self._text_flash_active = False

        # Animation state
        self._image_opacity = 1.0
        self._image_scale = 1.0
        self._image_y_offset = 0.0
        self._is_animating = False
        self._pending_action = None

        # Initialize flash timer for text feedback
        self._text_flash_timer = QTimer(self)
        self._text_flash_timer.setSingleShot(True)
        self._text_flash_timer.setInterval(300)
        self._text_flash_timer.timeout.connect(self._clear_text_flash)

        # Setup Fade Animation (Common for both)
        self.fade_animation = QPropertyAnimation(self, b"image_opacity")
        self.fade_animation.setDuration(400)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_animation.finished.connect(self._on_animation_finished)

        # Setup Scale Animation (Only for removal)
        self.scale_animation = QPropertyAnimation(self, b"image_scale")
        self.scale_animation.setDuration(400)
        self.scale_animation.setStartValue(1.0)
        self.scale_animation.setEndValue(0.5)
        self.scale_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # Setup Slide Animation (Only for stash)
        self.slide_animation = QPropertyAnimation(self, b"image_y_offset")
        self.slide_animation.setDuration(400)
        self.slide_animation.setStartValue(0.0)
        self.slide_animation.setEndValue(250.0)
        self.slide_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # Initial index safety guard
        if cards:
            self.index = max(0, min(start_index, len(cards) - 1))

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")

        # Image cache to avoid repeated disk reads during animation.
        self._cached_image: QImage | None = None
        self._cached_path: str | None = None

        self._setup_close_button()
        self._setup_header_buttons()
        self._setup_message_label()
        self._load_current()

    def _setup_close_button(self) -> None:
        self.close_btn = QPushButton("✕", self)
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(
            "QPushButton{background:rgba(40,40,40,180);color:white;border-radius:16px;"
            f"font-size:16px;font-weight:bold;border:1px solid rgba(255,255,255,30);}}"
            "QPushButton:hover{background:rgba(200,40,40,200);border:1px solid white;}"
        )
        self.close_btn.clicked.connect(self.accept)

    def _setup_header_buttons(self) -> None:
        """Create compact header container with action buttons."""
        self.header_container = QWidget(self)
        self.header_container.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self.header_container)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(8)

        self.remove_btn = QPushButton("✕ Remove", self)
        self.remove_btn.setFixedSize(95, 28)
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.setToolTip("Remove image\nDel")
        self.remove_btn.setStyleSheet(ui_styles.STYLE_BUTTON_DANGER)
        self.remove_btn.clicked.connect(self._on_remove)
        lay.addWidget(self.remove_btn)

        self.stash_btn = QPushButton("↓ Move to Stash", self)
        self.stash_btn.setFixedSize(128, 28)
        self.stash_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stash_btn.setToolTip("Move image to stash\nW")
        self.stash_btn.setStyleSheet(ui_styles.STYLE_BUTTON_PRIMARY)
        self.stash_btn.clicked.connect(self._on_move_to_stash)
        lay.addWidget(self.stash_btn)

        lay.addStretch()
        self.header_container.setGeometry(0, 0, self.width(), 40)
        self.header_container.show()

    def _setup_message_label(self) -> None:
        """Create temporary status message label in the top-right corner."""
        self._message_label = QLabel("", self)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self._message_label.setStyleSheet(ui_styles.STYLE_STATUS_LABEL)
        self._message_label.setVisible(False)

        self._message_timer = QTimer(self)
        self._message_timer.setSingleShot(True)
        self._message_timer.timeout.connect(self._clear_message)
        self._message_timer.setInterval(2000)

    def _update_header_buttons_state(self) -> None:
        """Enable/disable buttons based on availability and animation state."""
        has_cards = bool(self.sorter.cards)
        enabled = has_cards and not self._is_animating
        self.remove_btn.setEnabled(enabled)
        self.stash_btn.setEnabled(enabled)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        """Helper to toggle buttons state."""
        self.remove_btn.setEnabled(enabled)
        self.stash_btn.setEnabled(enabled)

    def _on_remove(self) -> None:
        """Trigger the Scale + Fade animation for removal."""
        if self._is_animating or not self.sorter.cards:
            return

        self._pending_action = "remove"
        self._is_animating = True
        self._update_header_buttons_state()  # replaces _set_buttons_enabled(False)

        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.scale_animation.setStartValue(1.0)
        self.scale_animation.setEndValue(0.5)

        self.fade_animation.start()
        self.scale_animation.start()

    def _on_move_to_stash(self) -> None:
        """Trigger the Slide + Fade animation for stashing."""
        if self._is_animating or not self.sorter.cards:
            return

        self._pending_action = "stash"
        self._is_animating = True
        self._update_header_buttons_state()  # replaces _set_buttons_enabled(False)

        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.slide_animation.setStartValue(0.0)
        self.slide_animation.setEndValue(250.0)

        self.fade_animation.start()
        self.slide_animation.start()

    def _on_animation_finished(self) -> None:
        """Execute the actual command after all animations have finished."""
        if not self.sorter.cards or self.index < 0 or self.index >= len(self.sorter.cards):
            self._reset_after_action()
            return

        path = self.sorter.cards[self.index].path

        if self._pending_action == "remove":
            data = [{'path': path, 'index': self.index}]
            self.sorter.undo_stack.push(RemoveSelectedCommand(self.sorter, data))
            self.show_message("Image removed")
            self._flash_text_success()

        elif self._pending_action == "stash":
            self.sorter.undo_stack.push(MoveToStashCommand(self.sorter, [path]))
            self.show_message("Moved to stash")
            self._flash_text_success()

        # Reset before navigating so the next image renders with clean values.
        self._reset_after_action()
        self._navigate_after_change()

    def _reset_after_action(self) -> None:
        """Stop all animations and reset properties for the next image."""
        # Stop animations before resetting values, otherwise a still-running
        # animation will immediately overwrite the reset on the next tick.
        self.fade_animation.stop()
        self.scale_animation.stop()
        self.slide_animation.stop()

        # Use property setters so update() is triggered correctly.
        self.image_opacity = 1.0
        self.image_scale = 1.0
        self.image_y_offset = 0.0

        self._is_animating = False
        self._pending_action = None
        self._update_header_buttons_state()

    def _navigate_after_change(self) -> None:
        """Navigate safely after removal/move with strict index bounds."""
        current_cards = self.sorter.cards
        if not current_cards:
            self.accept()
            return

        self.index = max(0, min(self.index, len(current_cards) - 1))
        self._load_current()  # reload cache for the new image

    def show_message(self, text: str, duration: int = 2000) -> None:
        """Update or restart the status message timer."""
        self._message_label.setText(f"✓ {text}")
        self._message_label.adjustSize()
        self._message_label.setVisible(True)
        self._message_timer.stop()
        self._message_timer.start(duration)
        self._reposition_message_label()

    def _clear_message(self) -> None:
        """Hide the message label after timeout."""
        self._message_label.setVisible(False)
        self._message_label.clear()

    def _reposition_message_label(self) -> None:
        """Position message label in top-right, next to close button."""
        margin = 8
        x = self.close_btn.x() - self._message_label.width() - margin
        y = self.close_btn.y()
        self._message_label.setGeometry(x, y, self._message_label.width(), 24)

    def _flash_text_success(self) -> None:
        """Trigger a brief text highlight to indicate successful action."""
        self._text_flash_active = True
        self._text_flash_timer.start()
        self.update()

    def _clear_text_flash(self) -> None:
        """Clear the text highlight after timeout."""
        self._text_flash_active = False
        self.update()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._reposition_close_button()
        self._reposition_header_buttons()
        self._reposition_message_label()
        self._update_header_buttons_state()
        self.setFocus()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._reposition_close_button()
        self._reposition_header_buttons()
        self._reposition_message_label()
        self.update()

    def _reposition_close_button(self) -> None:
        margin = 10
        self.close_btn.move(self.width() - self.close_btn.width() - margin, margin)

    def _reposition_header_buttons(self) -> None:
        self.header_container.setGeometry(0, 0, self.width(), 40)

    def _load_current(self) -> None:
        """Load and cache the current image to avoid repeated disk reads during animation."""
        current_cards = self.sorter.cards
        if current_cards and 0 <= self.index < len(current_cards):
            path = current_cards[self.index].path
            self._cached_image = QImage(path)
            self._cached_path = path
        else:
            self._cached_image = None
            self._cached_path = None
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 220))

        current_cards = self.sorter.cards
        if not current_cards or self.index < 0 or self.index >= len(current_cards):
            p.end()
            return

        # Use cached image instead of loading from disk on every frame.
        img = self._cached_image
        path = self._cached_path

        if img is None or img.isNull() or img.width() == 0 or img.height() == 0:
            p.setPen(QColor("#aaa"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Cannot load image")
            p.end()
            return

        pad = 60
        area = self.rect().adjusted(pad, pad, -pad, -pad)
        scaled = img.scaled(
            area.width(), area.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        base_x = area.x() + (area.width() - scaled.width()) // 2
        base_y = area.y() + (area.height() - scaled.height()) // 2

        draw_w = int(scaled.width() * self._image_scale)
        draw_h = int(scaled.height() * self._image_scale)

        x = base_x + (scaled.width() - draw_w) // 2
        y = base_y + (scaled.height() - draw_h) // 2 + self._image_y_offset

        p.setOpacity(self._image_opacity)
        p.drawImage(QRect(int(x), int(y), draw_w, draw_h), scaled)

        # Reset opacity for UI elements.
        p.setOpacity(1.0)
        p.setPen(QColor("#ccc"))
        p.setFont(QFont("Arial", 11))

        note = ""
        if hasattr(self.sorter, 'custom_notes'):
            note = self.sorter.custom_notes.get(path, "")

        info_text = f"{self.index + 1} / {len(current_cards)}"
        if note:
            info_text += f"  —  {note}"

        text_rect = self.rect().adjusted(40, 0, -40, -10)

        flash_color = QColor("#ffffff") if self._text_flash_active else QColor("#ccc")
        flash_font = QFont("Arial", 12, QFont.Weight.Bold) if self._text_flash_active else QFont("Arial", 11)
        p.setPen(flash_color)
        p.setFont(flash_font)
        p.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap,
            info_text,
        )

        if self.index > 0:
            p.setFont(QFont("Arial", 32))
            p.setPen(QColor("#fff"))
            p.drawText(QRect(0, 0, 60, self.height()), Qt.AlignmentFlag.AlignCenter, "‹")
        if self.index < len(current_cards) - 1:
            p.setFont(QFont("Arial", 32))
            p.setPen(QColor("#fff"))
            p.drawText(QRect(self.width() - 60, 0, 60, self.height()), Qt.AlignmentFlag.AlignCenter, "›")

        p.end()

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta < 0 and self.index < len(self.sorter.cards) - 1:
            self.index += 1
            self._load_current()
        elif delta > 0 and self.index > 0:
            self.index -= 1
            self._load_current()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.close_btn.geometry().contains(event.pos()):
                self.accept()
                return

            if event.pos().x() < 60 and self.index > 0:
                self.index -= 1
                self._load_current()
            elif event.pos().x() > self.width() - 60 and self.index < len(self.sorter.cards) - 1:
                self.index += 1
                self._load_current()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard navigation and closing."""
        k = event.key()

        if k == Qt.Key.Key_Escape:
            self.accept()
            event.accept()
            return

        if k == Qt.Key.Key_Space:
            # Space closes the lightbox, main window re-opens it on next press.
            self.accept()
            event.accept()
            return

        if k in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            if self.index > 0:
                self.index -= 1
                self._load_current()
            event.accept()
            return

        if k in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            if self.index < len(self.sorter.cards) - 1:
                self.index += 1
                self._load_current()
            event.accept()
            return

        if k == Qt.Key.Key_W:
            self._on_move_to_stash()
            event.accept()
            return

        if k == Qt.Key.Key_Delete:
            self._on_remove()
            event.accept()
            return

        event.ignore()
