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
# ui_toolbar.py
# UI construction mixin for ImageSorter.
# Builds the main window layout, toolbar, canvas, and settings menu.

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QLabel,
    QComboBox, QSlider, QSpinBox, QMenu, QWidgetAction,
    QWidget, QMessageBox, QApplication, QProgressBar,
)
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtCore import Qt, QPoint, QFileSystemWatcher

import constants
import utils_workers
import ui_sidebar
import ui_components
import settings_manager


class ToolbarMixin:
    """
    Mixin that provides all UI-construction methods to ImageSorter.
    Expects self to be an ImageSorter instance.
    """

    # ── Main layout ───────────────────────────────────────────────────────────

    def _build_ui(self):
        """Assembles the full window: toolbar → sidebar + workspace → stash."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 0)
        main_layout.setSpacing(6)

        main_layout.addLayout(self._build_toolbar())

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = ui_sidebar.ColorSidebar(self, self.custom_color)
        body_layout.addWidget(self.sidebar)

        self.sidebar_toggle = QPushButton("‹")
        self.sidebar_toggle.setToolTip("Toggle Sidebar (B)")
        self.sidebar_toggle.setFixedSize(16, 30)
        self.sidebar_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_toggle.setStyleSheet("""
            QPushButton {
                background: #252525;
                color: #888;
                border: 1px solid #333;
                border-left: none;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #333;
                color: white;
                border-left: 1px solid #4d8fcc;
            }
        """)
        self.sidebar_toggle.clicked.connect(self._toggle_sidebar)
        body_layout.addWidget(self.sidebar_toggle)

        # Initial sidebar visibility
        if not self.settings_manager.get("sidebar_visible", True):
            self.sidebar.hide()
            self.sidebar_toggle.setText("›")
        else:
            self.sidebar.show()
            self.sidebar_toggle.setText("‹")

        self.workspace = QWidget()
        self.workspace_layout = QVBoxLayout(self.workspace)
        self.workspace_layout.setContentsMargins(0, 0, 0, 0)
        self.workspace_layout.setSpacing(6)
        self.workspace_layout.addWidget(self._build_canvas(), 1)

        stash_expanded = self.settings_manager.get("stash_visible", True)
        self.stash_zone = ui_components.StashZone(self, initial_expanded=stash_expanded)
        self.workspace_layout.addWidget(self.stash_zone)

        body_layout.addWidget(self.workspace, 1)
        main_layout.addLayout(body_layout, 1)

        QApplication.instance().installEventFilter(self)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self).activated.connect(self._open_lightbox)

    def _build_toolbar(self):
        """Builds the top toolbar with all action buttons and zoom controls."""
        tb = QHBoxLayout()
        tb.setSpacing(5)

        b_add = QPushButton("＋ Import")
        b_add.setToolTip("Import images — summary file in the same folder is applied automatically")
        b_add.clicked.connect(self._add_files_dialog)
        b_add.setStyleSheet(utils_workers._btn("#1a6b3a", "#1f8348"))

        b_rem = QPushButton("✕ Remove")
        b_rem.setToolTip("Remove selected image(s) from the sequence")
        b_rem.clicked.connect(self._remove_selected)
        b_rem.setStyleSheet(utils_workers._btn("#6b1a1a", "#8a2020"))

        b_exp = QPushButton("↓ Export ▾")
        b_exp.setToolTip("Export images or contact sheet")
        b_exp.clicked.connect(self._show_export_menu)
        b_exp.setStyleSheet(utils_workers._btn("#1a4a6b", "#1f5f8a"))

        b_sort = QPushButton("⇅ Sort ▾")
        b_sort.setToolTip("Sort images by name or date")
        b_sort.clicked.connect(self._show_sort_menu)
        b_sort.setStyleSheet(utils_workers._btn("#3a2a5a", "#4e3a78"))

        for w in (b_add, b_rem):
            tb.addWidget(w)
        tb.addWidget(self._sep())
        for w in (b_exp, b_sort):
            tb.addWidget(w)
        tb.addWidget(self._sep())

        # Undo / Redo Group
        b_undo = QPushButton("↺")
        b_undo.setToolTip("Undo (Ctrl+Z)")
        b_undo.clicked.connect(self.undo_stack.undo)
        b_redo = QPushButton("↻")
        b_redo.setToolTip("Redo (Ctrl+Y)")
        b_redo.clicked.connect(self.undo_stack.redo)

        # Movement Group (Step by step and Absolute jumps)
        b_start = QPushButton("⇠|")
        b_start.setToolTip("Move selection to START (Ctrl + ←)")
        b_start.clicked.connect(lambda: self._move_selection_absolute("start"))

        b_bk = QPushButton("⇠")
        b_bk.setToolTip("Move selection left (←)\nCtrl + ← : Move selection to Start")
        # Modified: Check for Ctrl modifier during click
        b_bk.clicked.connect(lambda: self._move_selected_with_modifier(-1))

        b_fw = QPushButton("⇢")
        b_fw.setToolTip("Move selection right (→)\nCtrl + → : Move selection to End")
        # Modified: Check for Ctrl modifier during click
        b_fw.clicked.connect(lambda: self._move_selected_with_modifier(1))

        b_end = QPushButton("|⇢")
        b_end.setToolTip("Move selection to END (Ctrl + →)")
        b_end.clicked.connect(lambda: self._move_selection_absolute("end"))

        # Apply styles to all movement/undo buttons
        for w in (b_undo, b_redo, b_start, b_bk, b_fw, b_end):
            w.setStyleSheet(utils_workers._btn("#252535", "#32324a", True))

        # Layout: Undo/Redo | Sep | Start | Left | Right | End
        for w in (b_undo, b_redo):
            tb.addWidget(w)
        tb.addWidget(self._sep())
        for w in (b_start, b_bk, b_fw, b_end):
            tb.addWidget(w)
        tb.addWidget(self._sep())

        b_gear = QPushButton("⚙")
        b_gear.setToolTip("Settings")
        b_gear.clicked.connect(self._show_settings_menu)
        b_gear.setStyleSheet(utils_workers._btn("#1e1e1e", "#2e2e2e", True))
        tb.addWidget(b_gear)

        tb.addStretch()

        # --- PROGRESS, STATUS AND COUNT SECTION ---
        self.status_container = QHBoxLayout()
        self.status_container.setSpacing(10)
        tb.addLayout(self.status_container)

        # Progress Bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(150)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2a2a2a;
                border: 1px solid #404040;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #2d6fab;
                border-radius: 2px;
            }
        """)
        self.progress_bar.setVisible(False)
        self.status_container.addWidget(self.progress_bar)

        # Cancel Button (hidden by default, shown alongside progress bar)
        self.cancel_btn = QPushButton("✕ Cancel")
        self.cancel_btn.setFixedHeight(20)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet(
            "QPushButton{background:#5a1a1a;color:#e0e0e0;border:none;"
            "padding:0 8px;border-radius:3px;font-size:11px;font-weight:500;}"
            "QPushButton:hover{background:#8a2020;}"
        )
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_operation)
        self.status_container.addWidget(self.cancel_btn)

        # Status Label (for messages like "Exporting...")
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #4d8fcc; font-size: 12px; font-weight: bold; min-width: 150px;")
        self.status_container.addWidget(self.status_label)

        # Count Label (for "X images · Y selected")
        self.count_label = QLabel("0 images")
        self.count_label.setStyleSheet("font-size:11px;color:#bbb;min-width:95px;")
        self.status_container.addWidget(self.count_label)

        # Zoom controls
        lbl_z = QLabel("Zoom")
        lbl_z.setStyleSheet("font-size:11px;color:#bbb;")
        self.zoom_box = QComboBox()
        self.zoom_box.setToolTip("Zoom (Ctrl + Scroll Wheel)")
        for z in constants.ZOOM_STEPS:
            self.zoom_box.addItem(f"{z}%", z)
        self.zoom_box.setCurrentIndex(constants.ZOOM_STEPS.index(100))
        self.zoom_box.currentIndexChanged.connect(self._zoom_changed)

        for w in (lbl_z, self.zoom_box):
            self.status_container.addWidget(w)
        tb.addWidget(self._sep())

        b_about = QPushButton("ℹ")
        b_about.setToolTip("About Storyboard Imagesorter")
        b_about.clicked.connect(self._show_about)
        b_about.setStyleSheet(utils_workers._btn("#1e1e1e", "#2e2e2e", True))
        tb.addWidget(b_about)

        return tb


    def _build_canvas(self):
        """Builds the main scrollable image canvas and connects its signals."""
        self.scroll = ui_components.FileDropScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea{border:none;background:#181818;}")

        self.scroll.files_dropped.connect(self._add_images_bulk)
        self.scroll.summary_dropped.connect(self.import_notes_from_summary)
        self.scroll.verticalScrollBar().valueChanged.connect(
            lambda _: self._lazy_timer.start(80)
        )

        self.container = ui_components.LassoContainer(self)
        self.flow_layout = ui_components.FlowLayout(
            self.container,
            margin=10,
            spacing=self.current_spacing
        )
        self.container.setLayout(self.flow_layout)
        self.scroll.setWidget(self.container)

        self.empty_state = ui_components.EmptyState(self.scroll.viewport())
        self.empty_state.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._update_empty_state()

        return self.scroll

    # ── Settings menu ─────────────────────────────────────────────────────────

    def _show_settings_menu(self):
        """Gap slider, auto-reload toggle, label visibility toggles, and reset."""
        menu = QMenu(self)
        menu.setStyleSheet(constants.MENU_STYLE)

        # Gap control
        gap_wa = QWidgetAction(menu)
        gap_container = QWidget()
        gap_container.setStyleSheet("background:#252525; border:1px solid #383838; border-radius:6px;")
        gap_row = QHBoxLayout(gap_container)
        gap_row.setContentsMargins(12, 6, 12, 6)
        gap_row.setSpacing(8)

        lbl = QLabel("Gap")
        lbl.setStyleSheet("font-size:11px;color:#bbb;")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(self.current_spacing)
        slider.setFixedWidth(110)

        spin = QSpinBox()
        spin.setMinimumHeight(30)
        spin.setRange(0, 100)
        spin.setValue(self.current_spacing)
        spin.setFixedWidth(48)
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.PlusMinus)

        # Scroll zone opacity control
        sz_wa = QWidgetAction(menu)
        sz_container = QWidget()
        sz_container.setStyleSheet("background:#252525; border:1px solid #383838; border-radius:6px;")
        sz_row = QHBoxLayout(sz_container)
        sz_row.setContentsMargins(12, 6, 12, 6)
        sz_row.setSpacing(8)

        sz_lbl = QLabel("Scroll zone opacity")
        sz_lbl.setStyleSheet("font-size:11px;color:#bbb;")
        sz_slider = QSlider(Qt.Orientation.Horizontal)
        sz_slider.setRange(0, 255)
        sz_slider.setValue(self.settings_manager.get("scroll_zone_alpha", 80))
        sz_slider.setFixedWidth(110)

        sz_spin = QSpinBox()
        sz_spin.setMinimumHeight(30)
        sz_spin.setRange(0, 255)
        sz_spin.setValue(self.settings_manager.get("scroll_zone_alpha", 80))
        sz_spin.setFixedWidth(48)
        sz_spin.setButtonSymbols(QSpinBox.ButtonSymbols.PlusMinus)

        def _sync_sz(val, block_widget):
            block_widget.blockSignals(True)
            block_widget.setValue(val)
            block_widget.blockSignals(False)
            self.settings_manager.set("scroll_zone_alpha", val)
            self._save_settings()

        sz_slider.valueChanged.connect(lambda v: _sync_sz(v, sz_spin))
        sz_spin.valueChanged.connect(lambda v: _sync_sz(v, sz_slider))
        for w in (sz_lbl, sz_slider, sz_spin):
            sz_row.addWidget(w)
        sz_wa.setDefaultWidget(sz_container)
        menu.addAction(sz_wa)

        def _sync_and_apply(val, block_widget):
            block_widget.blockSignals(True)
            block_widget.setValue(val)
            block_widget.blockSignals(False)
            self.current_spacing = val
            self.flow_layout.setSpacing(val)
            self._rebuild_flow_completely()
            self._save_settings()

        slider.valueChanged.connect(lambda v: _sync_and_apply(v, spin))
        spin.valueChanged.connect(lambda v: _sync_and_apply(v, slider))
        for w in (lbl, slider, spin):
            gap_row.addWidget(w)
        gap_wa.setDefaultWidget(gap_container)
        menu.addAction(gap_wa)

        # Styles für die Toggle-Buttons
        _ss_active = (
            "QPushButton{background:#172d4e;color:#4d8fcc;"
            "border:1px solid #2d6fab;border-radius:4px;padding:4px 10px;font-size:11px;}"
        )
        _ss_inactive = (
            "QPushButton{background:#2a2a2a;color:#aaa;"
            "border:1px solid #383838;border-radius:4px;padding:4px 10px;font-size:11px;}"
        )

        # Auto-reload toggle (optimiert)
        ar_wa = QWidgetAction(menu)
        ar_container = QWidget()
        ar_container.setStyleSheet("background: transparent;")
        ar_row = QHBoxLayout(ar_container)
        ar_row.setContentsMargins(12, 2, 12, 2)
        ar_row.setSpacing(8)

        ar_cb = QPushButton()
        ar_cb.setCheckable(True)
        initial_ar = self.settings_manager.get("auto_reload", True)
        ar_cb.setChecked(initial_ar)
        # Initiales Aussehen setzen OHNE Signal-Trigger
        status_icon = "✓" if initial_ar else ""
        ar_cb.setText(f"↻  Auto-reload changed images {status_icon}")
        ar_cb.setStyleSheet(_ss_active if initial_ar else _ss_inactive)

        def _toggle_ar(checked):
            self.settings_manager.set("auto_reload", checked)
            self._save_settings()
            status = "✓" if checked else ""
            ar_cb.setText(f"↻  Auto-reload changed images {status}")
            ar_cb.setStyleSheet(_ss_active if checked else _ss_inactive)

        ar_cb.toggled.connect(_toggle_ar)
        ar_row.addWidget(ar_cb)
        ar_wa.setDefaultWidget(ar_container)
        menu.addAction(ar_wa)
        menu.addSeparator()

        # Label visibility toggles (DER FIX FÜR DEN LAG)
        label_wa = QWidgetAction(menu)
        label_container = QWidget()
        label_layout = QVBoxLayout(label_container)
        label_layout.setContentsMargins(12, 6, 12, 6)
        label_layout.setSpacing(4)

        def create_toggle_button(text: str, setting_key: str) -> QPushButton:
            btn = QPushButton()
            btn.setCheckable(True)
            current_val = self.settings_manager.get(setting_key, True)

            # 1. Optik manuell setzen (kein Signal-Trigger!)
            btn.setText(f"☑ {text}" if current_val else f"☐ {text}")
            btn.setStyleSheet(_ss_active if current_val else _ss_inactive)

            # 2. Internen Status setzen (da noch kein .connect erfolgt, wird kein Signal ausgelöst!)
            btn.setChecked(current_val)

            def _on_toggle_changed(checked: bool):
                self.settings_manager.set(setting_key, checked)
                self._save_settings()
                self._apply_label_settings() # Die teure Funktion wird NUR beim Klick aufgerufen
                btn.setText(f"☑ {text}" if checked else f"☐ {text}")
                btn.setStyleSheet(_ss_active if checked else _ss_inactive)

            # 3. Erst JETZT die Verbindung herstellen für zukünftige Klicks
            btn.toggled.connect(_on_toggle_changed)
            return btn

        label_layout.addWidget(create_toggle_button("Show Index", "show_index"))
        label_layout.addWidget(create_toggle_button("Show Filename", "show_filename"))
        label_layout.addWidget(create_toggle_button("Show Notes", "show_notes"))

        label_wa.setDefaultWidget(label_container)
        menu.addAction(label_wa)

        menu.addSeparator()

        menu.addAction("  Reset all settings to defaults", self._reset_settings)

        btn = self.sender()
        if btn:
            menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))


    def _reset_settings(self):
        """Resets all settings to defaults after confirmation."""
        reply = QMessageBox.question(
            self, "Reset settings",
            "Reset all settings (gap, zoom, export prefix, contact sheet) to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.settings_manager = settings_manager.SettingsManager()

        self.current_spacing = self.settings_manager.get("gap")
        self.saved_export_prefix = self.settings_manager.get("export_prefix")
        self.saved_contact_cols = self.settings_manager.get("contact_cols")
        self.saved_contact_thumb = self.settings_manager.get("contact_thumb")
        self.saved_contact_labels = self.settings_manager.get("contact_labels")
        self.saved_contact_notes = self.settings_manager.get("contact_notes", False)

        self.flow_layout.setSpacing(self.current_spacing)
        self._apply_label_settings()

        self.zoom_box.blockSignals(True)
        self.zoom_box.setCurrentIndex(constants.ZOOM_STEPS.index(100))
        self.zoom_box.blockSignals(False)
        self.icon_size = utils_workers.zoom_to_px(100)

        for card in self.cards:
            card.update_size(self.icon_size)

        self._rebuild_flow_completely()
        self._save_settings()
