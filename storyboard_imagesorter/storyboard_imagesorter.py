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
# storyboard_imagesorter.py
# This is the main entry point of the Storyboard Imagesorter application.
# It defines the ImageSorter class, which orchestrates the entire UI and core logic.
# The class manages image card lifecycles, selection states, sorting, and undo/redo operations.
# It also handles file system watching, user settings persistence, and export workflows.

import sys
import os
import platform
import subprocess

from PyQt6 import sip
from PyQt6.QtWidgets import (
    QApplication, QWidget, QFileDialog, QMessageBox, QMenu, QFrame, QTextEdit,
)
from PyQt6.QtGui import QUndoStack
from PyQt6.QtCore import (
    Qt, QPoint, QThreadPool, QTimer, QEvent,
)

import constants
import utils_workers
import commands
import ui_components
import ui_dialogs
import settings_manager
from export_manager import ExportManager
from ui_toolbar import ToolbarMixin

class ImageSorter(ToolbarMixin, ExportManager, QWidget):
    """
    Main application window.
    UI construction lives in ToolbarMixin, export/import in ExportManager.
    This class owns application state and all card/selection/sort logic.
    """

    APP_STYLE = constants.APP_STYLE

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Storyboard Imagesorter")
        self.resize(1200, 750)
        self.setStyleSheet(self.APP_STYLE)

        self.settings_manager = settings_manager.SettingsManager()

        self.custom_notes: dict[str, str] = {}
        self.temp_colors: dict[str, str] = {}

        self.icon_size = utils_workers.zoom_to_px(self.settings_manager.get("zoom_pct"))
        self.current_spacing = self.settings_manager.get("gap")
        self.last_export_dir = self.settings_manager.get("last_export_dir")
        self.saved_export_prefix = self.settings_manager.get("export_prefix")
        self.saved_contact_prefix = self.settings_manager.get("contact_export_prefix", "Sheet_")
        self.saved_contact_cols = self.settings_manager.get("contact_cols")
        self.saved_contact_thumb = self.settings_manager.get("contact_thumb")
        self.saved_contact_labels = self.settings_manager.get("contact_labels")
        self.saved_contact_notes = self.settings_manager.get("contact_notes", True)
        self.saved_contact_index = self.settings_manager.get("contact_show_index", True)
        self.saved_contact_grid_per_page = self.settings_manager.get("contact_grid_per_page", 20)
        self.saved_contact_list_per_page = self.settings_manager.get("contact_list_per_page", 10)
        self.custom_color = self.settings_manager.get("custom_color", "#ffffff")

        self.cards: list[ui_components.ThumbnailCard] = []
        self._cancelled = False
        self._last_clicked: int | None = None
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(6)

        # Initialize Undo Stack with limit from settings
        undo_limit = self.settings_manager.get("undo_limit", 50)
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(undo_limit)

        self._resize_timer = QTimer(singleShot=True)
        self._resize_timer.timeout.connect(self._rebuild_flow_completely)
        self._lazy_timer = QTimer(singleShot=True)
        self._lazy_timer.timeout.connect(self._update_visible_cards)

        # Cache for card positions to avoid heavy .y() calls during scrolling
        self._y_cache = []

        self._setup_shortcuts()
        self._build_ui()

        self._status_timer = QTimer(singleShot=True)
        self._status_timer.timeout.connect(self.status_label.clear)

        # FIX: Install event filter on the window to catch clicks even in empty areas
        self.installEventFilter(self)
        QApplication.instance().installEventFilter(self)

        saved_zoom = self.settings_manager.get("zoom_pct")
        if saved_zoom in constants.ZOOM_STEPS:
            self.zoom_box.blockSignals(True)
            self.zoom_box.setCurrentIndex(constants.ZOOM_STEPS.index(saved_zoom))
            self.zoom_box.blockSignals(False)

        self.flow_layout.setSpacing(self.current_spacing)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_settings(self):
        """Syncs current UI state into SettingsManager and requests a debounced save."""
        sm = self.settings_manager
        sm.set("last_export_dir", self.last_export_dir)
        sm.set("gap", self.current_spacing)
        sm.set("zoom_pct", self.zoom_box.currentData() if hasattr(self, 'zoom_box') else 100)
        sm.set("export_prefix", self.saved_export_prefix)
        sm.set("contact_export_prefix", self.saved_contact_prefix)
        sm.set("contact_cols", self.saved_contact_cols)
        sm.set("contact_thumb", self.saved_contact_thumb)
        sm.set("contact_labels", self.saved_contact_labels)
        sm.set("contact_notes", self.saved_contact_notes)
        sm.set("contact_show_index", self.saved_contact_index)
        sm.set("contact_grid_per_page", self.saved_contact_grid_per_page)
        sm.set("contact_list_per_page", self.saved_contact_list_per_page)
        sm.set("custom_color", self.custom_color)
        sm.set("sidebar_visible", self.sidebar.isVisible())
        sm.set("stash_visible", self.stash_zone.is_expanded())
        # Trigger the debounced save
        sm.request_save()

    def _save_last_dir(self, path):
        self.last_export_dir = path
        self.settings_manager.update_export_dir(path)
        self._save_settings()

    def handle_custom_note(self, path: str, text: str):
        if text:
            self.custom_notes[path] = text
        elif path in self.custom_notes:
            del self.custom_notes[path]

    def _apply_label_settings(self):
        show_idx = self.settings_manager.get("show_index", True)
        show_name = self.settings_manager.get("show_filename", True)
        show_notes = self.settings_manager.get("show_notes", False)  # default matches settings

        scroll_y = self.scroll.verticalScrollBar().value()
        view_height = self.scroll.viewport().height()
        buffer = int(view_height * 0.1)
        vis_top = scroll_y - buffer
        vis_bot = scroll_y + view_height + buffer

        for card in self.cards:
            rect = card.geometry()
            if rect.bottom() >= vis_top and rect.top() <= vis_bot:
                card.set_label_visibility(show_idx, show_name, show_notes)
                if show_notes:
                    card.set_note_text(self.custom_notes.get(card.path, ""))

    # ── Shortcuts ─────────────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        # Undo/Redo are handled centrally in eventFilter — no duplicate registration needed.
        pass

    # ── Sidebar / stash toggles ───────────────────────────────────────────────

    def _toggle_sidebar(self):
        if self.sidebar.isVisible():
            self.sidebar.hide()
            self.sidebar_toggle.setText("›")
        else:
            self.sidebar.show()
            self.sidebar_toggle.setText("‹")

    def _toggle_stash(self):
        self.stash_zone.toggle()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sep(self):
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setStyleSheet("color:#444;")
        return f

    def show_status(self, message):
        self.status_label.setText(f"✓ {message}")
        self._status_timer.start(5000)

    def _cancel_operation(self):
        """Sets the cancellation flag — checked in long-running loops."""
        self._cancelled = True

    def _start_progress(self, total):
        """Shows progress bar and cancel button."""
        self._cancelled = False
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.cancel_btn.setVisible(True)
        self.status_label.hide()

    def _stop_progress(self):
        """Hides progress bar and cancel button."""
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.status_label.show()

    def _update_empty_state(self):
        show = len(self.cards) == 0
        self.empty_state.setVisible(show)
        if show:
            vp = self.scroll.viewport()
            self.empty_state.setGeometry(0, 0, vp.width(), vp.height())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._resize_timer.start(120)
        vp = self.scroll.viewport()
        self.empty_state.setGeometry(0, 0, vp.width(), vp.height())
        for lb in self.findChildren(ui_dialogs.Lightbox):
            lb.setGeometry(self.rect())

    def _zoom_changed(self, _):
        """Handles zoom changes with a lightweight refresh instead of full rebuild."""
        # 1. Update the icon size based on current selection
        new_zoom = self.zoom_box.currentData()
        self.icon_size = utils_workers.zoom_to_px(new_zoom)

        # 2. Tell all cards to resize themselves according to the new zoom level
        for card in self.cards:
            card.update_size(self.icon_size)

        # 3. Schedule a refresh after the layout engine has finished resizing widgets.
        # We use singleShot(0) so this runs immediately after the current event loop finishes.
        QTimer.singleShot(0, self._refresh_after_zoom)
        self._save_settings()

    def _zoom_in(self):
        idx = self.zoom_box.currentIndex()
        if idx < self.zoom_box.count() - 1:
            self.zoom_box.setCurrentIndex(idx + 1)

    def _zoom_out(self):
        idx = self.zoom_box.currentIndex()
        if idx > 0:
            self.zoom_box.setCurrentIndex(idx - 1)

    def _refresh_after_zoom(self):
        """Rebuilds position cache and refreshes visible cards immediately after zoom."""
        self._rebuild_y_cache()
        # This ensures that all newly visible cards get their labels/images instantly.
        self._update_visible_cards()

    def _rebuild_y_cache(self):
        """No longer used in the new robust implementation."""
        pass

    def wheelEvent(self, e):
        # Standard scrolling only (Zooming moved to Numpad keys to avoid conflicts)
        super().wheelEvent(e)

    def _show_about(self):
        for child in self.findChildren(ui_dialogs.AboutDialog):
            child.raise_()
            child.activateWindow()
            return
        ui_dialogs.AboutDialog(self).exec()

    # ── Card management ───────────────────────────────────────────────────────

    def _add_image_internal(self, path, index=None, rebuild=True):
        idx = index if index is not None else len(self.cards)
        card = ui_components.ThumbnailCard(path, idx, self.icon_size, self.thread_pool, self)
        card.clicked.connect(self._on_card_clicked)
        card.note_changed.connect(self.handle_custom_note)

        card.set_label_visibility(
            self.settings_manager.get("show_index", True),
            self.settings_manager.get("show_filename", True),
            self.settings_manager.get("show_notes", True)
        )

        if path in self.custom_notes:
            card.set_note_text(self.custom_notes[path])
        if path in self.temp_colors:
            card.set_color(self.temp_colors[path])

        if index is not None:
            self.cards.insert(index, card)
        else:
            self.cards.append(card)

        if rebuild:
            self._rebuild_flow_completely()
            self._update_count()

        if hasattr(self, "_watcher") and path not in self._watcher.files():
            self._watcher.addPath(path)

        return card

    def _add_images_bulk(self, paths, summary_path=None):
        existing = {c.path for c in self.cards}
        new = [p for p in paths if p not in existing]
        if new:
            self.undo_stack.push(commands.AddImagesCommand(self, new))
        if summary_path:
            self.import_notes_from_summary(summary_path)

    def _add_files_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Importieren", "",
            "Images & Summary (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.txt);;"
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;"
            "Summary Files (*.txt)"
        )
        if not paths:
            return

        image_paths = [p for p in paths if p.lower().endswith(constants.IMAGE_EXTS)]
        summary_paths = [p for p in paths if p.lower().endswith('.txt')]

        if image_paths and not summary_paths:
            folder = os.path.dirname(image_paths[0])
            candidates = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.lower().endswith('.txt')
            ]
            if candidates:
                summary_paths = candidates[:1]

        # Identify the sorter summary by its marker (ignores mapping files etc.)
        summary_file = None
        for sp in summary_paths:
            try:
                with open(sp, 'r', encoding='utf-8') as f:
                    if f.read(30).startswith('STORYBOARD_IMAGESORTER_DATA'):
                        summary_file = sp
                        break
            except Exception:
                pass

        if image_paths:
            self._add_images_bulk(image_paths, summary_path=summary_file)
        elif summary_file:
            self.import_notes_from_summary(summary_file)

    def _open_image(self, path):
        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as ex:
            QMessageBox.warning(self, "Cannot open", str(ex))

    # ── File watcher ──────────────────────────────────────────────────────────

    def _on_file_changed(self, path):
        QTimer.singleShot(400, lambda: self._handle_changed(path))

    def _handle_changed(self, path):
        if os.path.exists(path) and path not in self._watcher.files():
            self._watcher.addPath(path)
        cards = [c for c in self.cards if c.path == path]
        if not cards:
            return
        if self.settings_manager.get("auto_reload", True):
            for card in cards:
                card.load_thumbnail(force=True)
                self._flash_card(card)
        else:
            for card in cards:
                card.mark_changed(True)

    def _flash_card(self, card):
        orig = card.styleSheet()
        card.setStyleSheet("background:#2a1a00;border:2px solid #e8872a;border-radius:5px;")
        QTimer.singleShot(600, lambda: card.setStyleSheet(orig) if not sip.isdeleted(card) else None)

    # ── Lightbox ──────────────────────────────────────────────────────────────

    def _open_lightbox(self):
        if not self.cards:
            return
        sel = [i for i, c in enumerate(self.cards) if c._selected]
        start = sel[0] if sel else 0
        lb = ui_dialogs.Lightbox(self.cards, start, self)
        global_pos = self.mapToGlobal(QPoint(0, 0))
        lb.setGeometry(global_pos.x(), global_pos.y(), self.width(), self.height())
        lb.exec()

    # ── Order / layout ────────────────────────────────────────────────────────

    def _apply_order_by_paths(self, path_list):
        pm = {c.path: c for c in self.cards}
        self.cards = [pm[p] for p in path_list if p in pm]
        for i, c in enumerate(self.cards):
            c.update_index(i)
        self._reorder_flow_widgets()
        self._update_count()

    def _move_cards_by_paths(self, src_paths, dst_index, direction=1):
        if not src_paths:
            return
        old = [c.path for c in self.cards]
        ms = set(src_paths)
        remaining = [c for c in self.cards if c.path not in ms]
        moving = [c for c in self.cards if c.path in ms]
        ip = len(remaining)

        if dst_index < len(self.cards):
            tgt = self.cards[dst_index]
            if tgt.path not in ms:
                ip = next((i for i, c in enumerate(remaining) if c.path == tgt.path), len(remaining))
                if direction == 1:
                    ip += 1
            else:
                if direction == 1:
                    for i in range(dst_index + 1, len(self.cards)):
                        if self.cards[i].path not in ms:
                            ip = next(
                                (j for j, c in enumerate(remaining) if c.path == self.cards[i].path),
                                len(remaining)
                            )
                            break
                else:
                    for i in range(dst_index - 1, -1, -1):
                        if self.cards[i].path not in ms:
                            ip = next(
                                (j for j, c in enumerate(remaining) if c.path == self.cards[i].path),
                                len(remaining)
                            ) + 1
                            break

        new_paths = [c.path for c in remaining[:ip] + moving + remaining[ip:]]
        self.undo_stack.push(commands.MoveCardsCommand(self, old, new_paths))

    def _move_selection_absolute(self, target: str):
        """
        Moves the entire selection block to either the very beginning
        or the very end of the current card list.
        """
        # 1. Identify all currently selected cards
        sel = [c for c in self.cards if c._selected]
        if not sel:
            return

        # 2. Capture current state for Undo
        old_paths = [c.path for c in self.cards]

        # 3. Separate selected paths from the rest (preserving order of non-selected)
        sel_paths = [c.path for c in sel]
        remaining_paths = [c.path for c in self.cards if c.path not in sel_paths]

        # 4. Calculate new order based on target
        if target == "start":
            new_paths = sel_paths + remaining_paths
        else:  # target == "end"
            new_paths = remaining_paths + sel_paths

        # 5. Only execute if the order actually changes
        if new_paths != old_paths:
            self.undo_stack.push(commands.MoveCardsCommand(self, old_paths, new_paths))

    def _move_selected_with_modifier(self, direction):
        """Handles button clicks with optional Ctrl modifier for absolute jumps."""
        mods = QApplication.keyboardModifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            target = "start" if direction == -1 else "end"
            self._move_selection_absolute(target)
        else:
            self._move_selected(direction)

        # Use a small delay to allow the layout engine to settle
        QTimer.singleShot(100, self._refresh_after_move)

    def _refresh_after_move(self):
        """Ensures the UI is visually consistent after a move operation."""
        # 1. Tell the layout to recalculate everything
        self.flow_layout.invalidate()

        # 2. Force a single pass of the event loop to let geometry settle
        QTimer.singleShot(50, self._finalize_move_refresh)

    def _finalize_move_refresh(self):
        """Final step of refresh after layout has settled."""
        # Direct update without relying on a potentially stale cache
        self._update_visible_cards()
        self._update_count()

    def _rebuild_flow_completely(self):
        """Full reconstruction of the layout and cache (used for heavy operations like adding/removing cards)."""
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)
        for idx, card in enumerate(self.cards):
            card.update_index(idx)
            self.flow_layout.addWidget(card)
            card.show()

        # Update cache after full rebuild
        self._rebuild_y_cache()

        self._update_empty_state()
        self._update_window_title()
        self._lazy_timer.start(80)


    def _reorder_flow_widgets(self):
        """
        Smart reorder: repositions existing widgets in the layout without
        destroying and recreating them. Use this for sort/move operations
        where no cards are added or removed — only their order changes.
        This avoids the Qt widget churn that causes lag at >500 cards.

        We bypass addWidget/takeAt entirely and write FlowLayout.items directly.
        This is safe because FlowLayout is our own class and addWidget on an
        already-parented widget is unreliable in Qt6 (may not trigger addItem).
        """
        # Build a lookup from widget to its current QWidgetItem in the layout
        item_map = {item.widget(): item for item in self.flow_layout.items if item.widget()}

        # Replace the items list in-place with the new order — no parent changes, no allocation
        self.flow_layout.items = [item_map[card] for card in self.cards if card in item_map]

        # Update indices and force a layout pass
        for idx, card in enumerate(self.cards):
            card.update_index(idx)

        self.flow_layout.invalidate()
        self.flow_layout.update()

        self._rebuild_y_cache()
        self._update_empty_state()
        self._update_window_title()
        self._lazy_timer.start(80)

    def _update_visible_cards(self):
        """
        Update thumbnails and labels for cards using direct geometry checks.
        This version is robust against layout shifts after moving cards.
        """
        # Get current viewport info
        viewport = self.scroll.viewport()
        if not viewport:
            return

        v_rect = viewport.rect()
        scroll_y = self.scroll.verticalScrollBar().value()

        # The actual visible area in the scroll area (in global/parent coordinates)
        visible_area = v_rect.translated(0, scroll_y)

        # Add a generous buffer to prevent flickering during scrolling
        buffer = 200
        vis_top = visible_area.top() - buffer
        vis_bot = visible_area.bottom() + buffer

        show_idx = self.settings_manager.get("show_index", True)
        show_name = self.settings_manager.get("show_filename", True)
        show_notes = self.settings_manager.get("show_notes", True)

        for card in self.cards:
            # Get the actual position of the card relative to the scroll area
            card_rect = card.geometry()

            # Check if the card is within the expanded visible range
            if (card_rect.bottom() >= vis_top and card_rect.top() <= vis_bot):
                # Card is visible: Load content
                card.load_thumbnail()
                card.set_label_visibility(show_idx, show_name, show_notes)
                if show_notes:
                    card.set_note_text(self.custom_notes.get(card.path, ""))
            else:
                # Card is not visible: Unload to save memory
                card.unload_thumbnail()

    # ── Selection ─────────────────────────────────────────────────────────────

    def _on_card_clicked(self, index):
        """Handles clicking on a card to select it and ensures the canvas gets focus."""
        mods = QApplication.keyboardModifiers()

        if mods & Qt.KeyboardModifier.ShiftModifier and self._last_clicked is not None:
            lo, hi = sorted([self._last_clicked, index])
            add = bool(mods & Qt.KeyboardModifier.ControlModifier)
            for i, c in enumerate(self.cards):
                if lo <= i <= hi:
                    c.set_selected(True)
                elif not add:
                    c.set_selected(False)
            self._last_clicked = index  # update anchor after range selection
        elif mods & Qt.KeyboardModifier.ControlModifier:
            if 0 <= index < len(self.cards):
                self.cards[index].set_selected(not self.cards[index]._selected)
            self._last_clicked = index
        else:
            for i, c in enumerate(self.cards):
                c.set_selected(i == index)
            self._last_clicked = index

        self._update_count()

        # Ensure the LassoContainer receives focus so key events (Ctrl+A etc.) are handled.
        if hasattr(self, 'container'):
            self.container.setFocus()

        # Deactivate stash visual state when clicking a card in the main view.
        self.stash_zone.set_active(False)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            if obj is self:
                self.stash_zone.set_active(False)

        if event.type() == QEvent.Type.KeyPress:
            # Intercept Tab before Qt's focus-navigation consumes it.
            # Must run at app level (QApplication filter) so child widgets never see it.
            key = event.key()
            mods = event.modifiers()
            is_ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
            is_shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)

            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab) and not is_ctrl:
                if QApplication.activeModalWidget() is None:
                    focus_widget = QApplication.focusWidget()
                    if not isinstance(focus_widget, QTextEdit):
                        self._toggle_stash()
                        return True

            # Ignore events not targeting the main window from here on
            if obj is not self:
                return False

            if QApplication.activeModalWidget() is not None:
                return False

            in_stash = self.stash_zone.container.hasFocus()
            focus_widget = QApplication.focusWidget()
            is_typing = isinstance(focus_widget, QTextEdit)

            # --- 1. Global hotkeys (active even while typing) ---
            if is_ctrl and key == Qt.Key.Key_Z:
                self.undo_stack.undo()
                return True
            if is_ctrl and key == Qt.Key.Key_Y:
                self.undo_stack.redo()
                return True
            if is_ctrl and is_shift and key == Qt.Key.Key_Z:
                self.undo_stack.redo()
                return True

            # --- 2. Typing guard ---
            if is_typing:
                return False

            # --- 3. Application hotkeys (not while typing) ---
            if key == Qt.Key.Key_B and not is_ctrl:
                self._toggle_sidebar()
                return True
            if is_ctrl and is_shift and key == Qt.Key.Key_C:
                self._clear_selected_colors()
                return True
            if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal) and not is_ctrl:
                self._zoom_in()
                return True
            if key == Qt.Key.Key_Minus and not is_ctrl:
                self._zoom_out()
                return True
            if key == Qt.Key.Key_F:
                self._scroll_to_selected()
                return True

            # Stash hotkeys
            if in_stash:
                if key == Qt.Key.Key_Home:
                    self.stash_zone.scroll.horizontalScrollBar().setValue(0)
                    return True
                if key == Qt.Key.Key_End:
                    self.stash_zone.scroll.horizontalScrollBar().setValue(
                        self.stash_zone.scroll.horizontalScrollBar().maximum()
                    )
                    return True
                if key == Qt.Key.Key_PageUp:
                    self.stash_zone.scroll.horizontalScrollBar().setValue(
                        self.stash_zone.scroll.horizontalScrollBar().value() - 500
                    )
                    return True
                if key == Qt.Key.Key_PageDown:
                    self.stash_zone.scroll.horizontalScrollBar().setValue(
                        self.stash_zone.scroll.horizontalScrollBar().value() + 500
                    )
                    return True
                if key == Qt.Key.Key_F:
                    self._scroll_to_selected()
                    return True
                if is_ctrl and key == Qt.Key.Key_A:
                    self.stash_zone.container._select_all_stash()
                    return True
                if is_ctrl and key == Qt.Key.Key_D:
                    self.stash_zone.container._deselect_all_stash()
                    return True
                if key == Qt.Key.Key_Delete:
                    sel = [c.path for c in self.stash_zone._cards if c._selected]
                    if sel:
                        self.undo_stack.push(
                            commands.RemoveFromStashCommand(self.stash_zone, sel)
                        )
                    return True

            # Main area hotkeys
            else:
                if key == Qt.Key.Key_Space:
                    self._open_lightbox()
                    return True
                if key == Qt.Key.Key_Home:
                    self.scroll.verticalScrollBar().setValue(0)
                    return True
                if key == Qt.Key.Key_End:
                    self.scroll.verticalScrollBar().setValue(
                        self.scroll.verticalScrollBar().maximum()
                    )
                    return True
                if is_ctrl and key == Qt.Key.Key_A:
                    self._select_all()
                    return True
                if is_ctrl and key == Qt.Key.Key_D:
                    self._deselect_all()
                    return True
                if key == Qt.Key.Key_Delete:
                    self._remove_selected()
                    return True
                if key == Qt.Key.Key_F:
                    self._scroll_to_selected()
                    return True

                if not is_ctrl:
                    if key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
                        self._move_selected(-1)
                        return True
                    if key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
                        self._move_selected(1)
                        return True
                else:
                    if key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
                        self._move_selection_absolute("start")
                        return True
                    if key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
                        self._move_selection_absolute("end")
                        return True

        return super().eventFilter(obj, event)


    def _move_selected(self, direction):
        sel = [i for i, c in enumerate(self.cards) if c._selected]
        if not sel:
            return
        if direction == 1 and max(sel) >= len(self.cards) - 1:
            return
        if direction == -1 and min(sel) <= 0:
            return
        tgt = (max(sel) + 1) if direction == 1 else (min(sel) - 1)
        self._move_cards_by_paths([self.cards[i].path for i in sel], tgt, direction)

    def _remove_selected(self):
        sel = [c for c in self.cards if c._selected]
        if not sel:
            return
        data = [{'path': c.path, 'index': i}
                for i, c in enumerate(self.cards) if c._selected]
        if hasattr(self, '_watcher'):
            for d in data:
                self._watcher.removePath(d['path'])
        self.undo_stack.push(commands.RemoveSelectedCommand(self, data))

    def _deselect_all(self):
        for c in self.cards:
            c.set_selected(False)
        self._last_clicked = None
        self._update_count()

    def _select_all(self):
        for c in self.cards:
            c.set_selected(True)
        self._update_count()

    # ── Color ─────────────────────────────────────────────────────────────────

    def _apply_color_to_selection(self, color_hex: str):
        changes = [
            {'path': c.path, 'old': self.temp_colors.get(c.path), 'new': color_hex}
            for c in self.cards if c._selected
        ]
        if changes:
            self.undo_stack.push(commands.ColorCommand(self, changes))

    def _clear_selected_colors(self):
        changes = [
            {'path': c.path, 'old': self.temp_colors.get(c.path), 'new': None}
            for c in self.cards if c._selected and c.path in self.temp_colors
        ]
        if changes:
            self.undo_stack.push(commands.ColorCommand(self, changes))
            self.show_status(f"Cleared colors from {len(changes)} cards")

    # ── Sort menu ─────────────────────────────────────────────────────────────

    def _show_sort_menu(self):
        """Displays the sorting menu including selection management with visual anchors."""
        menu = QMenu(self)
        menu.setStyleSheet(constants.MENU_STYLE)

        # --- Selection Management ---
        # Using checkmark and empty square for immediate recognition of select/deselect
        menu.addAction("☑ Select All\tCtrl+A", self._select_all)
        menu.addAction("☐ Deselect All\tCtrl+D", self._deselect_all)

        menu.addSeparator()

        # --- Sorting Operations ---
        menu.addAction("🔤 Sort A → Z", lambda: self._sort_by('name_asc'))
        menu.addAction("🔤 Sort Z → A", lambda: self._sort_by('name_desc'))
        menu.addSeparator()
        menu.addAction("🕒 Oldest First", lambda: self._sort_by('date_asc'))
        menu.addAction("🕓 Newest First", lambda: self._sort_by('date_desc'))
        menu.addSeparator()
        menu.addAction("🔄 Reverse Order", lambda: self._sort_by('reverse'))
        menu.addSeparator()
        menu.addAction("🎯 Focus selected\tF", self._scroll_to_selected)

        btn = self.sender()
        if btn:
            menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))


    def _sort_by(self, mode):
        if not self.cards:
            return
        old = [c.path for c in self.cards]
        if mode == 'name_asc':
            nc = sorted(self.cards, key=lambda c: os.path.basename(c.path).lower())
        elif mode == 'name_desc':
            nc = sorted(self.cards, key=lambda c: os.path.basename(c.path).lower(), reverse=True)
        elif mode == 'date_asc':
            nc = sorted(self.cards, key=lambda c: os.path.getmtime(c.path))
        elif mode == 'date_desc':
            nc = sorted(self.cards, key=lambda c: os.path.getmtime(c.path), reverse=True)
        elif mode == 'reverse':
            nc = list(reversed(self.cards))
        else:
            return
        new = [c.path for c in nc]
        if new == old:
            return
        labels = {
            'name_asc': 'Sort A→Z', 'name_desc': 'Sort Z→A',
            'date_asc': 'Sort oldest', 'date_desc': 'Sort newest', 'reverse': 'Reverse'
        }
        self.undo_stack.push(commands.SortCommand(self, old, new, labels[mode]))

    # ── Status / title ────────────────────────────────────────────────────────

    def _update_count(self):
        sel = sum(1 for c in self.cards if c._selected)
        total = len(self.cards)
        self.count_label.setText(
            f"{total} images · {sel} selected" if sel else f"{total} images"
        )

    def _update_window_title(self):
        n = len(self.cards)
        self.setWindowTitle(
            f"Storyboard Imagesorter — {n} image{'s' if n != 1 else ''}" if n else "Storyboard Imagesorter"
        )

    def _scroll_to_selected(self):
        """Scrolls the view to the first selected card (main view or stash)."""
        if self.stash_zone.container.hasFocus():
            for card in self.stash_zone._cards:
                if card._selected:
                    self.stash_zone.scroll.ensureWidgetVisible(card)
                    break
        else:
            for card in self.cards:
                if card._selected:
                    self.scroll.ensureWidgetVisible(card)
                    break

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        """Ensures all settings are saved to disk before exiting."""
        # Sync UI values into the manager first
        self._save_settings()
        # Stop timer and force immediate write
        self.settings_manager._save_timer.stop()
        self.settings_manager.save()
        event.accept()

    # ── Select by color tag ───────────────────────────────────────────────────

    def _select_by_color(self, color: str):
        """
        Selects cards based on their assigned color.
        If the Shift key is held down, it performs an additive selection.
        Otherwise, it replaces the current selection with the matching colors.
        """
        mods = QApplication.keyboardModifiers()
        is_additive = bool(mods & Qt.KeyboardModifier.ShiftModifier)

        if is_additive:
            # Add only the cards with the target color to the current selection
            for card in self.cards:
                if self.temp_colors.get(card.path) == color:
                    card.set_selected(True)
        else:
            # Replace current selection with all cards matching the target color
            for card in self.cards:
                matches_color = self.temp_colors.get(card.path) == color
                card.set_selected(matches_color)

        self._update_count()

    # ── Open the export folder ───────────────────────────────────────────────

    def _open_folder(self, path):
        """Opens the specified directory using the system default file explorer."""
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Error", f"Path is not a directory:\n{path}")
            return

        try:
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as ex:
            QMessageBox.warning(self, "Cannot open folder", str(ex))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    sorter = ImageSorter()
    sorter.show()
    sys.exit(app.exec())
