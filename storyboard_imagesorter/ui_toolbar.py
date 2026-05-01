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
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QSlider, QSpinBox, QMenu, QWidgetAction,
    QWidget, QMessageBox, QProgressBar,
)
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtCore import Qt, QPoint, QFileSystemWatcher

import constants
import utils_workers
import ui_sidebar
import ui_components
import ui_styles


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
        self.sidebar_toggle.setToolTip("Toggle sidebar\nB")
        self.sidebar_toggle.setFixedSize(16, 30)
        self.sidebar_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_toggle.setStyleSheet(ui_styles.STYLE_SIDEBAR_TOGGLE)
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

        self.installEventFilter(self)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self).activated.connect(self._open_lightbox)

    def _build_toolbar(self):
        """Builds the top toolbar with all action buttons and zoom controls."""
        tb = QHBoxLayout()
        tb.setSpacing(5)

        b_add = QPushButton("＋ Import")
        b_add.setToolTip("Import images\nSummary file in the same folder is applied automatically\nCtrl+O")
        b_add.clicked.connect(self._add_files_dialog)
        b_add.setStyleSheet(ui_styles.STYLE_TB_ADD)

        b_rem = QPushButton("✕ Remove")
        b_rem.setToolTip("Remove selected image(s) from the sequence\nDel")
        b_rem.clicked.connect(self._remove_selected)
        b_rem.setStyleSheet(ui_styles.STYLE_TB_REMOVE)

        b_exp = QPushButton("↓ Export ▾")
        b_exp.setToolTip("Export images or contact sheet")
        b_exp.clicked.connect(self._show_export_menu)
        b_exp.setStyleSheet(ui_styles.STYLE_TB_EXPORT)

        b_sort = QPushButton("⇅ Sort ▾")
        b_sort.setToolTip("Sort images by name or date")
        b_sort.clicked.connect(self._show_sort_menu)
        b_sort.setStyleSheet(ui_styles.STYLE_TB_SORT)

        for w in (b_add, b_rem):
            tb.addWidget(w)
        tb.addWidget(self._sep())
        for w in (b_exp, b_sort):
            tb.addWidget(w)
        tb.addWidget(self._sep())

        # Undo / Redo Group
        b_undo = QPushButton("↺")
        b_undo.setToolTip("Undo\nCtrl+Z")
        b_undo.clicked.connect(self.undo_stack.undo)
        b_redo = QPushButton("↻")
        b_redo.setToolTip("Redo\nCtrl+Y")
        b_redo.clicked.connect(self.undo_stack.redo)

        # Movement Group (Step by step and Absolute jumps)
        b_start = QPushButton("⇠|")
        b_start.setToolTip("Move selection to start\nCtrl+←")
        b_start.clicked.connect(lambda: self._move_selection_absolute("start"))

        b_bk = QPushButton("⇠")
        b_bk.setToolTip("Move selection one step left\n← / Ctrl+← to move to start")
        # Modified: Check for Ctrl modifier during click
        b_bk.clicked.connect(lambda: self._move_selected_with_modifier(-1))

        b_fw = QPushButton("⇢")
        b_fw.setToolTip("Move selection one step right\n→ / Ctrl+→ to move to end")
        # Modified: Check for Ctrl modifier during click
        b_fw.clicked.connect(lambda: self._move_selected_with_modifier(1))

        b_end = QPushButton("|⇢")
        b_end.setToolTip("Move selection to end\nCtrl+→")
        b_end.clicked.connect(lambda: self._move_selection_absolute("end"))

        # Apply styles to all movement/undo buttons
        for w in (b_undo, b_redo, b_start, b_bk, b_fw, b_end):
            w.setStyleSheet(ui_styles.STYLE_TB_NAV)

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
        b_gear.setStyleSheet(ui_styles.STYLE_TB_UTIL)
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
        self.progress_bar.setStyleSheet(ui_styles.STYLE_PROGRESS_BAR)
        self.progress_bar.setVisible(False)
        self.status_container.addWidget(self.progress_bar)

        # Cancel Button (hidden by default, shown alongside progress bar)
        self.cancel_btn = QPushButton("✕ Cancel")
        self.cancel_btn.setFixedHeight(20)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet(ui_styles.STYLE_CANCEL_BTN_SMALL)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_operation)
        self.status_container.addWidget(self.cancel_btn)

        # Status Label (for messages like "Exporting...")
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(ui_styles.STYLE_STATUS_LABEL)
        self.status_container.addWidget(self.status_label)

        # Count Label (for "X images · Y selected")
        self.count_label = QLabel("0 images")
        self.count_label.setStyleSheet(ui_styles.STYLE_COUNT_LABEL)
        self.status_container.addWidget(self.count_label)

        # Zoom controls
        lbl_z = QLabel("Zoom")
        lbl_z.setStyleSheet(ui_styles.STYLE_ZOOM_LABEL)
        self.zoom_box = QComboBox()
        self.zoom_box.setToolTip("Zoom\nCtrl+Scroll")
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
        b_about.setStyleSheet(ui_styles.STYLE_TB_UTIL)
        tb.addWidget(b_about)

        return tb


    def _build_canvas(self):
        """Builds the main scrollable image canvas and connects its signals."""
        self.scroll = ui_components.FileDropScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea{border:none;background:#181818;}")

        self.scroll.files_dropped.connect(self._add_images_bulk)
        self.scroll.summary_dropped.connect(self.import_notes_from_summary)

        # To prevent continuous scrolling from resetting the timer indefinitely,
        # we only restart the timer if it is not already active.
        # This ensures that the visibility check actually triggers during long scrolls.
        def _on_scroll_changed():
            if not self._lazy_timer.isActive():
                self._lazy_timer.start(30)

        self.scroll.verticalScrollBar().valueChanged.connect(_on_scroll_changed)

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
        menu.setStyleSheet(ui_styles.MENU_STYLE)

        # Absolute widths to guarantee perfect vertical alignment of all controls
        LABEL_WIDTH = 100
        SLIDER_WIDTH = 100
        SPIN_WIDTH = 45
        CONTROL_X_OFFSET = LABEL_WIDTH + SLIDER_WIDTH + 10

        # --- SECTION 1: LAYOUT & SYSTEM CONFIG ---
        config_group = QWidgetAction(menu)
        config_container = QWidget()
        config_container.setStyleSheet(
            "background:#252525; border:1px solid #383838; border-radius:6px;"
        )
        config_vbox = QVBoxLayout(config_container)
        config_vbox.setContentsMargins(12, 8, 12, 8)
        config_vbox.setSpacing(10)

        # Gap control (Slider + Spin)
        gap_row = QHBoxLayout()
        lbl_gap = QLabel("Gap")
        lbl_gap.setFixedWidth(LABEL_WIDTH)
        lbl_gap.setStyleSheet(ui_styles.STYLE_ZOOM_LABEL)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(self.current_spacing)
        slider.setFixedWidth(SLIDER_WIDTH)
        spin_gap = QSpinBox()
        spin_gap.setRange(0, 100)
        spin_gap.setValue(self.current_spacing)
        spin_gap.setFixedWidth(SPIN_WIDTH)
        spin_gap.setButtonSymbols(QSpinBox.ButtonSymbols.PlusMinus)

        gap_row.addWidget(lbl_gap)
        gap_row.addWidget(slider)
        gap_row.addWidget(spin_gap)
        gap_row.addStretch()
        config_vbox.addLayout(gap_row)

        # Scroll zone opacity (Slider + Spin)
        sz_row = QHBoxLayout()
        lbl_sz = QLabel("Scroll zone opacity")
        lbl_sz.setFixedWidth(LABEL_WIDTH)
        lbl_sz.setStyleSheet(ui_styles.STYLE_ZOOM_LABEL)
        slider_sz = QSlider(Qt.Orientation.Horizontal)
        slider_sz.setRange(0, 255)
        slider_sz.setValue(self.settings_manager.get("scroll_zone_alpha", 80))
        slider_sz.setFixedWidth(SLIDER_WIDTH)
        spin_sz = QSpinBox()
        spin_sz.setRange(0, 255)
        spin_sz.setValue(self.settings_manager.get("scroll_zone_alpha", 80))
        spin_sz.setFixedWidth(SPIN_WIDTH)
        spin_sz.setButtonSymbols(QSpinBox.ButtonSymbols.PlusMinus)

        sz_row.addWidget(lbl_sz)
        sz_row.addWidget(slider_sz)
        sz_row.addWidget(spin_sz)
        sz_row.addStretch()
        config_vbox.addLayout(sz_row)

        # Undo limit (Aligned exactly with Spinboxes above)
        undo_row = QHBoxLayout()
        lbl_undo = QLabel("Undo limit")
        lbl_undo.setFixedWidth(LABEL_WIDTH)
        lbl_undo.setStyleSheet(ui_styles.STYLE_ZOOM_LABEL)
        undo_spin = QSpinBox()
        undo_spin.setRange(5, 1000)
        undo_spin.setValue(self.settings_manager.get("undo_limit", 50))
        undo_spin.setFixedWidth(SPIN_WIDTH)
        undo_spin.setButtonSymbols(QSpinBox.ButtonSymbols.PlusMinus)

        undo_row.addWidget(lbl_undo)
        undo_row.addSpacing(CONTROL_X_OFFSET - LABEL_WIDTH)
        undo_row.addWidget(undo_spin)
        undo_row.addStretch()
        config_vbox.addLayout(undo_row)

        config_group.setDefaultWidget(config_container)
        menu.addAction(config_group)

        menu.addSeparator()

        # --- SECTION 2: VISUALS & AUTOMATION (Toggles) ---
        visuals_group = QWidgetAction(menu)
        visuals_container = QWidget()
        visuals_container.setStyleSheet("background: transparent;")
        visuals_vbox = QVBoxLayout(visuals_container)
        visuals_vbox.setContentsMargins(12, 5, 12, 5)
        visuals_vbox.setSpacing(6)

        ss_active = ui_styles.STYLE_TOGGLE_ACTIVE
        ss_inactive = ui_styles.STYLE_TOGGLE_INACTIVE

        # Group A: Automation (Auto-reload toggle)
        ar_cb = QPushButton()
        ar_cb.setCheckable(True)
        initial_ar = self.settings_manager.get("auto_reload", True)
        ar_cb.setChecked(initial_ar)
        status_icon = "✓" if initial_ar else ""
        ar_cb.setText(f"↻  Auto-reload images {status_icon}")
        ar_cb.setStyleSheet(ss_active if initial_ar else ss_inactive)

        def _toggle_ar(checked):
            """Handles auto-reload toggle logic."""
            self.settings_manager.set("auto_reload", checked)
            self.settings_manager.request_save()
            icon = "✓" if checked else ""
            ar_cb.setText(f"↻  Auto-reload images {icon}")
            ar_cb.setStyleSheet(ss_active if checked else ss_inactive)

        ar_cb.toggled.connect(_toggle_ar)
        visuals_vbox.addWidget(ar_cb)

        # Whitespace between Automation and Visual Toggles
        visuals_vbox.addSpacing(10)

        # Group B: Visual Display (Label visibility toggles)
        def create_toggle_btn(text, key):
            """Creates a stylized toggle button for settings."""
            btn = QPushButton()
            btn.setCheckable(True)
            val = self.settings_manager.get(key, True)
            btn.setChecked(val)
            btn.setText(f"☑ {text}" if val else f"☐ {text}")
            btn.setStyleSheet(ss_active if val else ss_inactive)

            def _on_toggled(checked):
                """Updates setting and UI when button is toggled."""
                self.settings_manager.set(key, checked)
                self.settings_manager.request_save()
                self._apply_label_settings()
                btn.setText(f"☑ {text}" if checked else f"☐ {text}")
                btn.setStyleSheet(ss_active if checked else ss_inactive)

            btn.toggled.connect(_on_toggled)
            return btn

        visuals_vbox.addWidget(create_toggle_btn("Show Index", "show_index"))
        visuals_vbox.addWidget(create_toggle_btn("Show Filename", "show_filename"))
        visuals_vbox.addWidget(create_toggle_btn("Show Notes", "show_notes"))

        visuals_group.setDefaultWidget(visuals_container)
        menu.addAction(visuals_group)

        menu.addSeparator()

        # --- RESET ACTION (Standard QAction for consistency) ---
        reset_action = menu.addAction(" ~  Reset all settings to defaults")
        reset_action.triggered.connect(self._reset_settings)

        # --- LOGIC FOR SYNCING SLIDERS/SPINS (Config Group) ---
        def _sync_gap(val, s_spin, s_slider):
            """Syncs gap slider and spinbox."""
            s_spin.blockSignals(True)
            s_spin.setValue(val)
            s_spin.blockSignals(False)
            s_slider.blockSignals(True)
            s_slider.setValue(val)
            s_slider.blockSignals(False)
            self.current_spacing = val
            self.flow_layout.setSpacing(val)
            self.settings_manager.request_save()

        def _sync_sz(val, s_spin, s_slider):
            """Syncs scroll zone opacity slider and spinbox."""
            s_spin.blockSignals(True)
            s_spin.setValue(val)
            s_spin.blockSignals(False)
            s_slider.blockSignals(True)
            s_slider.setValue(val)
            s_slider.blockSignals(False)
            self.settings_manager.set("scroll_zone_alpha", val)
            self.settings_manager.request_save()

        def _sync_undo(val):
            """Syncs undo limit to settings and reliably updates status feedback."""
            self.settings_manager.set("undo_limit", val)
            self.settings_manager.request_save()

            # Ensure status label is visible before updating.
            if not self.status_label.isVisible():
                self.status_label.show()

            # setUndoLimit() strictly requires an empty stack.
            if self.undo_stack.count() == 0:
                self.undo_stack.setUndoLimit(val)
                self.show_status("New Undo limit applied")
            else:
                self.show_status("Undo limit changed, requires restart")

        slider.valueChanged.connect(lambda v: _sync_gap(v, spin_gap, slider))
        spin_gap.valueChanged.connect(lambda v: _sync_gap(v, spin_gap, slider))
        slider_sz.valueChanged.connect(lambda v: _sync_sz(v, spin_sz, slider_sz))
        spin_sz.valueChanged.connect(lambda v: _sync_sz(v, spin_sz, slider_sz))
        undo_spin.valueChanged.connect(_sync_undo)

        btn = self.sender()
        if btn:
            menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))

    def _reset_settings(self):
        """Resets all application settings to defaults after explicit user confirmation."""
        reply = QMessageBox.warning(
            self,
            "Reset settings",
            "Reset all settings to defaults?\n\n"
            "Note: This will also clear the undo/redo history.\n"
            "Are you sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Get the absolute source of truth: The defaults defined in SettingsManager
        defaults = self.settings_manager._defaults.copy()
        self.settings_manager.settings = defaults

        # Sync local UI variables with the retrieved defaults
        self.current_spacing = defaults["gap"]
        self.saved_export_prefix = defaults["export_prefix"]
        self.saved_contact_prefix = defaults["contact_export_prefix"]
        self.saved_contact_cols = defaults["contact_cols"]
        self.saved_contact_thumb = defaults["contact_thumb"]
        self.saved_contact_labels = defaults["contact_labels"]
        self.saved_contact_notes = defaults["contact_notes"]
        self.saved_contact_index = defaults["contact_show_index"]
        self.saved_contact_grid_per_page = defaults["contact_grid_per_page"]
        self.saved_contact_list_per_page = defaults["contact_list_per_page"]
        self.custom_color = defaults["custom_color"]
        self.last_export_dir = defaults["last_export_dir"]

        # Reset directly accessible UI components
        self.flow_layout.setSpacing(self.current_spacing)
        self.undo_stack.clear()
        self.undo_stack.setUndoLimit(defaults["undo_limit"])

        # Reset zoom control
        self.zoom_box.blockSignals(True)
        if defaults["zoom_pct"] in constants.ZOOM_STEPS:
            self.zoom_box.setCurrentIndex(constants.ZOOM_STEPS.index(defaults["zoom_pct"]))
        else:
            self.zoom_box.setCurrentIndex(0)
        self.zoom_box.blockSignals(False)
        self.icon_size = utils_workers.zoom_to_px(defaults["zoom_pct"])

        # Clear user-specific data (notes and temporary colors)
        self.custom_notes.clear()
        self.temp_colors.clear()

        # Reset sidebar and stash visibility based on defaults
        if defaults["sidebar_visible"]:
            self.sidebar.show()
            self.sidebar_toggle.setText("‹")
        else:
            self.sidebar.hide()
            self.sidebar_toggle.setText("›")

        # FIX: StashZone has no collapse/expand, use toggle() and is_expanded()
        if self.stash_zone.is_expanded() != defaults["stash_visible"]:
            self.stash_zone.toggle()

        # Rebuild UI state to reflect defaults
        self._apply_label_settings()
        for card in self.cards:
            card.update_size(self.icon_size)
        self._rebuild_flow_completely()

        # Persist changes immediately to disk
        self.settings_manager.save()
