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
# ui_canvas.py
# This module provides UI components for the application's canvas area.

from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QLabel, QVBoxLayout, QLayout, QRubberBand, QApplication,
)
from PyQt6.QtGui import QPainter, QColor, QPen, QCursor
from PyQt6.QtCore import (
    Qt, QPoint, QRect, QSize, pyqtSignal, QTimer
)

import constants

from commands import MoveFromStashCommand, MoveCardsCommand

MIME_INTERNAL = constants.MIME_INTERNAL


# ─── LAYOUT ───────────────────────────────────────────────────────────────────


class FlowLayout(QLayout):
    """
    A custom layout that arranges widgets in a flow from left to right,
    wrapping to the next line when the edge is reached.
    """

    def __init__(self, parent=None, margin=10, spacing=10):
        super().__init__(parent)
        if parent is not None:
            self.setParent(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._spacing = spacing
        self.items = []

    def __del__(self):
        del self.items

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, i):
        if 0 <= i < len(self.items):
            return self.items[i]
        return None

    def takeAt(self, i):
        if 0 <= i < len(self.items):
            return self.items.pop(i)
        return None

    def expandingDirections(self):
        return QLayout.ExpandingDirections(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do_layout(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def setSpacing(self, s):
        self._spacing = s
        self.invalidate()

    def spacing(self):
        return self._spacing

    def minimumSize(self):
        size = QSize()
        for item in self.items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        indicator_buffer = int((self._spacing / 2) + 3)
        left_margin = max(margins.left(), indicator_buffer)
        right_margin = max(margins.right(), indicator_buffer)
        top_margin = margins.top()

        x = rect.left() + left_margin
        y = rect.top() + top_margin
        lh = 0

        for item in self.items:
            if not item.widget():
                continue

            hint = item.sizeHint()
            w, h = hint.width(), hint.height()

            if x + w > rect.right() and x > (rect.left() + left_margin):
                x = rect.left() + left_margin
                y += lh + self._spacing
                lh = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))

            x += w + self._spacing
            lh = max(lh, h)

        return y + lh - rect.y()


# ─── OVERLAYS & CONTAINERS ────────────────────────────────────────────────────

class IndicatorOverlay(QWidget):
    """Paints drag-drop position indicators over the canvas."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.sorter = parent.sorter
        self.container = parent
        self.setStyleSheet("background:transparent;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw drop position indicators
        indicator_color = QColor("#e8872a")
        bar_width = 4
        spacing = self.sorter.current_spacing

        for card in self.sorter.cards:
            if not hasattr(card, '_drop_indicator') or not card._drop_indicator:
                continue

            card_rect = card.geometry()
            if card._drop_indicator == 'left':
                x = card_rect.left() - (spacing / 2) - (bar_width / 2)
            else:
                x = card_rect.right() + (spacing / 2) - (bar_width / 2)
            painter.fillRect(QRect(int(x), card_rect.top(), bar_width, card_rect.height()), indicator_color)

        # Draw scroll zones when drag is active
        if not self.container._is_internal_drag:
            return

        scroll_area = self.container._get_scroll_area()
        if not scroll_area:
            return

        vp = scroll_area.viewport()
        mouse_vp = vp.mapFromGlobal(QCursor.pos())
        zone_h = 80
        vp_h = vp.height()
        w = self.width()
        bar = scroll_area.verticalScrollBar()
        scroll_y = bar.value()
        alpha = self.sorter.settings_manager.get("scroll_zone_alpha", 80)
        alpha_active = min(255, int(alpha * 1.75))

        # Only draw the zone the mouse is currently hovering over
        if mouse_vp.y() < zone_h:
            top_y = scroll_y
            can_scroll = scroll_y > 0
            color = QColor(45, 111, 171, alpha_active) if can_scroll else QColor(60, 60, 60, alpha)
            text_color = QColor(77, 143, 204, 200) if can_scroll else QColor(100, 100, 100, 120)
            painter.fillRect(QRect(0, top_y, w, zone_h), color)
            painter.setPen(text_color)
            painter.drawText(QRect(0, top_y, w, zone_h), Qt.AlignmentFlag.AlignCenter, "▲  Hold Shift for fast scroll")

        elif mouse_vp.y() > vp_h - zone_h:
            bot_y = scroll_y + vp_h - zone_h
            can_scroll = scroll_y < bar.maximum()
            color = QColor(45, 111, 171, alpha_active) if can_scroll else QColor(60, 60, 60, alpha)
            text_color = QColor(77, 143, 204, 200) if can_scroll else QColor(100, 100, 100, 120)
            painter.fillRect(QRect(0, bot_y, w, zone_h), color)
            painter.setPen(text_color)
            painter.drawText(QRect(0, bot_y, w, zone_h), Qt.AlignmentFlag.AlignCenter, "▼  Hold Shift for fast scroll")


class LassoContainer(QWidget):
    """Main canvas widget supporting lasso selection and internal drag-drop reordering."""

    def __init__(self, sorter):
        super().__init__()
        self.sorter = sorter
        self._lasso_origin = None
        self._rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.setStyleSheet("background:#181818;")
        self.setAcceptDrops(True)
        # Allow the container to receive keyboard focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.overlay = IndicatorOverlay(self)
        self.overlay.raise_()
        self._is_internal_drag = False
        self._last_drag_target = (None, None)  # (card, indicator) — skip repaint if unchanged

        self._scroll_timer = QTimer()
        self._scroll_timer.setInterval(20)
        self._scroll_timer.timeout.connect(self._do_scroll)
        self._scroll_direction = 0

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.overlay.resize(self.size())

    def _clear_drop_state(self):
        """Resets all card indicators and styles."""
        self._last_drag_target = (None, None)
        for c in self.sorter.cards:
            c._drag_over = False
            c._drop_indicator = None
            c._apply_style()
        self.overlay.update()

    def _reset_drag_state(self):
        """Resets all drag-related state — called on stale drag detection."""
        self._is_internal_drag = False
        self._scroll_timer.stop()
        self._scroll_direction = 0
        self.unsetCursor()
        self._clear_drop_state()

    def _do_scroll(self):
        """Executes one scroll step in the active direction."""
        scroll_area = self._get_scroll_area()
        if not scroll_area:
            return
        mods = QApplication.keyboardModifiers()
        fast = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        step = 60 if fast else 12
        bar = scroll_area.verticalScrollBar()
        bar.setValue(bar.value() + self._scroll_direction * step)

    def _update_scroll_zones(self):
        """Checks mouse position against viewport edges and starts/stops scrolling."""
        scroll_area = self._get_scroll_area()
        if not scroll_area:
            self._scroll_direction = 0
            self._scroll_timer.stop()
            self.unsetCursor()
            self.overlay.update()
            return

        vp = scroll_area.viewport()
        mouse_vp = vp.mapFromGlobal(QCursor.pos())
        zone = 80
        vp_h = vp.height()

        if mouse_vp.y() < zone:
            self._scroll_direction = -1
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            if not self._scroll_timer.isActive():
                self._scroll_timer.start()
        elif mouse_vp.y() > vp_h - zone:
            self._scroll_direction = 1
            self.setCursor(Qt.CursorShape.SizeVerCursor)
            if not self._scroll_timer.isActive():
                self._scroll_timer.start()
        else:
            self._scroll_direction = 0
            self._scroll_timer.stop()
            self.unsetCursor()

        self.overlay.update()

    def _get_scroll_area(self):
        """Traverses parent hierarchy to find the FileDropScrollArea."""
        parent = self.parent()
        while parent is not None:
            if getattr(parent, "is_file_drop_area", False):
                return parent
            parent = parent.parent()
        return None

    def _find_target(self, pos):
        """
        The Single Source of Truth for target detection.
        Determines which card is under the mouse and whether it's a 'left' or 'right' drop.
        """
        spacing = self.sorter.current_spacing
        for card in self.sorter.cards:
            rect = card.geometry()

            # Case 1: Mouse is within the actual card boundaries.
            if rect.contains(pos):
                # Determine if we are on the left or right half of the card body.
                indicator = 'left' if pos.x() < rect.center().x() else 'right'
                return card, indicator

            # Case 2: Mouse is in the spacing/gap area immediately to the right of the card.
            # We extend the hit zone by the spacing width to ensure a smooth drop experience.
            right_gap_zone = QRect(rect.right(), rect.top(), spacing + 10, rect.height())
            if right_gap_zone.contains(pos):
                return card, 'right'

        return None, None

    def dragEnterEvent(self, e):
        """Handles entering the canvas with a drag."""
        if e.mimeData().hasFormat(MIME_INTERNAL):
            self._is_internal_drag = True
            self._update_scroll_zones()
            e.acceptProposedAction()
        else:
            # Reset stale drag state on any new external drag enter
            self._is_internal_drag = False
            self._scroll_timer.stop()
            self._scroll_direction = 0
            self.overlay.update()
            scroll_area = self._get_scroll_area()
            if scroll_area:
                scroll_area.dragEnterEvent(e)
                e.acceptProposedAction()
            else:
                e.ignore()

    def dragMoveEvent(self, e):
        """Handles the movement of an internal drag to update visual indicators."""
        if e.mimeData().hasFormat(MIME_INTERNAL):
            self._update_scroll_zones()

            pos = e.position().toPoint()
            tgt, indicator = self._find_target(pos)

            # Skip repaint if nothing changed
            if (tgt, indicator) == self._last_drag_target:
                e.acceptProposedAction()
                return

            # Reset only the single previously highlighted card
            prev_tgt, _ = self._last_drag_target
            if prev_tgt is not None:
                prev_tgt._drag_over = False
                prev_tgt._drop_indicator = None
                prev_tgt._apply_style()

            self._last_drag_target = (tgt, indicator)

            if tgt:
                tgt._drag_over = True
                tgt._drop_indicator = indicator
                tgt._apply_style()
                self.overlay.raise_()

            self.overlay.update()
            e.acceptProposedAction()
        else:
            scroll_area = self._get_scroll_area()
            if scroll_area:
                scroll_area.dragMoveEvent(e)
                e.acceptProposedAction()
            else:
                e.ignore()

    def dragLeaveEvent(self, e):
        """Handles leaving the canvas area."""
        scroll_area = self._get_scroll_area()
        vp = scroll_area.viewport() if scroll_area else None
        in_viewport = vp and vp.rect().contains(vp.mapFromGlobal(QCursor.pos()))

        if not in_viewport:
            if self._is_internal_drag:
                self._reset_drag_state()
            else:
                if scroll_area:
                    scroll_area.dragLeaveEvent(e)
                else:
                    e.ignore()

    def dropEvent(self, e):
        """Handles the actual dropping of images for reordering or stashing."""
        self._reset_drag_state()
        self._scroll_direction = 0
        if e.mimeData().hasFormat(MIME_INTERNAL):
            src_data = e.mimeData().data(MIME_INTERNAL).data().decode()
            src_paths = [p for p in src_data.split(",") if p]

            tgt, indicator = self._find_target(e.position().toPoint())

            self._clear_drop_state()
            self._is_internal_drag = False
            e.acceptProposedAction()

            stash_zone_paths = self.sorter.stash_zone._paths
            paths_from_stash = [p for p in src_paths if p in stash_zone_paths]

            if paths_from_stash:
                # CASE 1: Returning from Stash to Main View.
                dst_index = tgt.index if tgt else len(self.sorter.cards)
                self.sorter.undo_stack.push(MoveFromStashCommand(self.sorter, paths_from_stash, dst_index))
            elif tgt and tgt.path not in src_paths:
                # CASE 2: Reordering within the Main View.
                old_paths = [c.path for c in self.sorter.cards]
                remaining = [c.path for c in self.sorter.cards if c.path not in src_paths]

                try:
                    target_idx_in_rem = remaining.index(tgt.path)

                    # If the target was identified as 'right' (via card half or gap),
                    # place it immediately after that card.
                    if indicator == 'right':
                        target_idx_in_rem += 1

                    new_paths = remaining[:target_idx_in_rem] + src_paths + remaining[target_idx_in_rem:]
                    self.sorter.undo_stack.push(MoveCardsCommand(self.sorter, old_paths, new_paths))
                except ValueError:
                    pass
        else:
            # Handle external file drops (text files/images from OS).
            if e.mimeData().hasFormat("text/uri-list"):
                paths = [u.toLocalFile() for u in e.mimeData().urls()]
                txt_files = [p for p in paths if p.lower().endswith('.txt')]
                img_files = [p for p in paths if p.lower().endswith(constants.IMAGE_EXTS)]

                # Find the sorter summary among dropped txt files by checking the marker.
                summary_file = None
                for t in txt_files:
                    try:
                        with open(t, 'r', encoding='utf-8') as f:
                            if f.read(30).startswith('STORYBOARD_IMAGESORTER_DATA'):
                                summary_file = t
                                break
                    except Exception:
                        pass

                if img_files:
                    self.sorter._add_images_bulk(img_files, summary_path=summary_file)
                elif summary_file:
                    self.sorter.import_notes_from_summary(summary_file)

                e.acceptProposedAction()
            else:
                e.ignore()

    def mousePressEvent(self, e):
        """Handles lasso selection start and ensures focus."""
        self.setFocus()

        # Reset any stale drag state (e.g. after Alt+Tab or screenshot tool)
        if self._is_internal_drag:
            self._reset_drag_state()

        is_card = False
        for card in self.sorter.cards:
            if card.geometry().contains(e.pos()):
                is_card = True
                break

        if e.button() == Qt.MouseButton.LeftButton and not is_card:
            self._lasso_origin = e.pos()
            self._rubber.setGeometry(QRect(self._lasso_origin, QSize()))
            self._rubber.show()

    def mouseMoveEvent(self, e):
        """Handles lasso selection drawing."""
        if self._lasso_origin is not None:
            self._rubber.setGeometry(QRect(self._lasso_origin, e.pos()).normalized())

    def mouseReleaseEvent(self, e):
        """Finalizes the lasso selection."""
        if self._lasso_origin is None:
            return

        lasso = QRect(self._lasso_origin, e.pos()).normalized()
        self._lasso_origin = None
        self._rubber.hide()

        if lasso.width() < 4 and lasso.height() < 4:
            for card in self.sorter.cards:
                card.set_selected(False)
            self.sorter._update_count()
            return

        add = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        for card in self.sorter.cards:
            cr = QRect(card.mapTo(self, QPoint(0, 0)), card.size())
            if lasso.intersects(cr):
                card.set_selected(True)
            elif not add:
                card.set_selected(False)
        self.sorter._update_count()

# ─── FILE DROP SCROLL AREA ────────────────────────────────────────────────────

class FileDropScrollArea(QScrollArea):
    """Scroll area that accepts external file drops and emits typed signals."""

    is_file_drop_area = True
    files_dropped = pyqtSignal(list)
    summary_dropped = pyqtSignal(str)

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.setAcceptDrops(True)
        self.sorter = None  # injected by _build_canvas

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat("text/uri-list"):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat("text/uri-list"):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasFormat("text/uri-list"):
            paths = [u.toLocalFile() for u in e.mimeData().urls()]

            img_files = [p for p in paths if p.lower().endswith(constants.IMAGE_EXTS)]
            txt_files = [p for p in paths if p.lower().endswith('.txt')]

            if img_files:
                # Pass summary_path so it is applied after push() completes and all
                # cards are guaranteed to be in self.cards.
                self.sorter._add_images_bulk(img_files, summary_path=txt_files[0] if txt_files else None)
            elif txt_files:
                # No images — cards already present, apply directly.
                self.sorter.import_notes_from_summary(txt_files[0])

            e.acceptProposedAction()
        else:
            super().dropEvent(e)

    def wheelEvent(self, e):
        """Normal scroll = Qt default, Shift+scroll = fast jump (~10 card rows)."""
        if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            bar = self.verticalScrollBar()
            delta = e.angleDelta().y()
            step = 1200  # ~10 card rows at typical card height
            bar.setValue(bar.value() + (-step if delta > 0 else step))
            e.accept()
        else:
            super().wheelEvent(e)


# ─── EMPTY STATE ──────────────────────────────────────────────────────────────


class EmptyState(QWidget):
    """Placeholder widget shown when no images are loaded."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(12)
        icon = QLabel("⬆")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size:52px;color:#777;")
        lay.addWidget(icon)
        txt = QLabel("Drop images here\nor use ＋ Import")
        txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt.setStyleSheet("font-size:14px;color:#999;line-height:1.8;")
        lay.addWidget(txt)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setPen(QPen(QColor("#444"), 2, Qt.PenStyle.DashLine))
        p.drawRoundedRect(self.rect().adjusted(40, 40, -40, -40), 14, 14)
