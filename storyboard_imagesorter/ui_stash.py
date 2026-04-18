from PyQt6 import sip  # WICHTIG: Für die Sicherheitsprüfung
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QScrollArea,
    QLabel, QPushButton, QFrame, QRubberBand, QApplication,
)
from PyQt6.QtGui import (
    QPixmap, QDrag, QPainter
)
from PyQt6.QtCore import Qt, QMimeData, QPoint, QRect, QSize, pyqtSignal

import constants
from utils_workers import WorkerSignals, ImageLoadWorker
from commands import MoveToStashCommand, MoveFromStashCommand, ClearStashCommand, RemoveFromStashCommand

MIME_INTERNAL = constants.MIME_INTERNAL
MIME_STASH = "application/x-stash-paths"


# ─── HORIZONTAL SCROLL AREA WITH MOUSEWHEEL SUPPORT ──────────────────────────

class StashScrollArea(QScrollArea):
    """QScrollArea that redirects vertical wheel events to horizontal scrolling.

    Normal scroll  →  scroll by one card width (~90px)
    Shift + scroll →  scroll by ~10 card widths (fast jump for large stashes)
    """

    CARD_STEP = 92          # roughly card width + spacing
    FAST_MULTIPLIER = 10    # Shift+scroll jump factor

    def wheelEvent(self, e):
        delta = e.angleDelta().y()
        if delta == 0:
            super().wheelEvent(e)
            return

        bar = self.horizontalScrollBar()
        fast = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        step = self.CARD_STEP * (self.FAST_MULTIPLIER if fast else 1)
        bar.setValue(bar.value() + (-step if delta > 0 else step))
        e.accept()


# ─── STASH HEADER ─────────────────────────────────────────────────────────────

class StashHeader(QFrame):
    """The clickable header of the stash zone that handles focus activation."""

    def __init__(self, stash_zone):
        super().__init__()
        self.stash_zone = stash_zone

    def mousePressEvent(self, e):
        # Clicking anywhere on the header activates the stash and gives it focus
        if e.button() == Qt.MouseButton.LeftButton:
            self.stash_zone.set_active(True)
            self.stash_zone.container.setFocus()


# ─── STASH CONTAINER (inner drag-drop widget) ─────────────────────────────────

class StashContainer(QWidget):
    """Inner container for the stash scroll area; handles lasso and drop events."""

    def __init__(self, stash_zone):
        super().__init__()
        self.stash_zone = stash_zone
        self._lasso_origin = None
        self._rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.setAcceptDrops(True)
        # Allow the container to receive keyboard focus
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("background:#141414;")
        self.setMinimumHeight(10)

    def _select_all_stash(self):
        """Selects all cards currently in the stash."""
        for card in self.stash_zone._cards:
            card.set_selected(True)
        self.stash_zone._update_label()

    def _deselect_all_stash(self):
        """Deselects all cards currently in the stash."""
        for card in self.stash_zone._cards:
            card.set_selected(False)
        self.stash_zone._update_label()

    def _card_at(self, pos):
        child = self.childAt(pos)
        while child and not hasattr(child, 'path'):
            child = child.parent()
        if hasattr(child, 'path') and child.__class__.__name__ == "StashCard":
            return child
        return None

    def mousePressEvent(self, e):
        # Clicking in the container (on cards or empty space) activates the stash and gives focus
        self.stash_zone.set_active(True)
        self.setFocus()

        if e.button() == Qt.MouseButton.LeftButton and not self._card_at(e.pos()):
            self._lasso_origin = e.pos()
            self._rubber.setGeometry(QRect(self._lasso_origin, QSize()))
            self._rubber.show()

    def mouseMoveEvent(self, e):
        if self._lasso_origin is not None:
            self._rubber.setGeometry(QRect(self._lasso_origin, e.pos()).normalized())

    def mouseReleaseEvent(self, e):
        if self._lasso_origin is None:
            return

        lasso = QRect(self._lasso_origin, e.pos()).normalized()
        self._lasso_origin = None
        self._rubber.hide()

        add = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        for card in self.stash_zone._cards:
            cr = QRect(card.mapTo(self, QPoint(0, 0)), card.size())
            if lasso.intersects(cr):
                card.set_selected(True)
            elif not add:
                card.set_selected(False)

        # FIX: Always update the label after a selection change (lasso or click in empty space)
        self.stash_zone._update_label()

    def keyPressEvent(self, e):
        """Handles Ctrl+A, Ctrl+D, and Delete for the stash container."""
        if e.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if e.key() == Qt.Key.Key_A:
                self._select_all_stash()
                e.accept()
                return
            if e.key() == Qt.Key.Key_D:
                self._deselect_all_stash()
                e.accept()
                return

        if e.key() == Qt.Key.Key_Delete:
            sel = [c.path for c in self.stash_zone._cards if c._selected]
            if sel:
                self.stash_zone.sorter.undo_stack.push(
                    RemoveFromStashCommand(self.stash_zone, sel)
                )
            e.accept()
            return

        super().keyPressEvent(e)


    def dragEnterEvent(self, e):
        if (e.mimeData().hasFormat(MIME_INTERNAL) or
                e.mimeData().hasFormat(MIME_STASH)):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if (e.mimeData().hasFormat(MIME_INTERNAL) or
                e.mimeData().hasFormat(MIME_STASH)):
            e.acceptProposedAction()

    def dropEvent(self, e):
        if e.mimeData().hasFormat(MIME_INTERNAL):
            src_data = e.mimeData().data(MIME_INTERNAL).data().decode()
            src_paths = [p for p in src_data.split(",") if p]

            stash_zone_paths = self.stash_zone._paths
            new_paths = [p for p in src_paths if p not in stash_zone_paths]

            if new_paths:
                self.stash_zone.sorter.undo_stack.push(
                    MoveToStashCommand(self.stash_zone.sorter, new_paths)
                )

            e.acceptProposedAction()
        else:
            super().dropEvent(e)

# ─── STASH CARD ───────────────────────────────────────────────────────────────

class StashCard(QFrame):
    """Thumbnail card used inside the stash panel."""

    clicked = pyqtSignal(str)

    def __init__(self, path, size, thread_pool, stash_zone):
        super().__init__()
        self.path = path
        self._size = size
        self.thread_pool = thread_pool
        self.stash_zone = stash_zone
        self._worker = None
        self._selected = False
        self._color = None
        self.drag_start_pos = None
        self.setAcceptDrops(True)

        # Prevent card from stealing focus so Container can handle shortcuts
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._setup_ui()
        self.load_thumbnail()

    def _setup_ui(self):
        """Initializes the UI components for the stash card."""
        sz = self._size
        self.setFixedSize(sz + 12, sz + 10)
        self._apply_style()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setFixedSize(sz, sz)
        lay.addWidget(self.img_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.color_bar = QFrame()
        self.color_bar.setFixedHeight(3)
        self.color_bar.setFixedWidth(sz)
        self.color_bar.setVisible(False)
        lay.addWidget(self.color_bar, 0, Qt.AlignmentFlag.AlignHCenter)

    def _apply_style(self):
        """Applies selection and base card styles."""
        bg = "#252525"
        border = "#404040"

        if self._selected:
            bg = "#172d4e"
            border = "#2d6fab"
        elif self._color:
            bg = "#252525"
            border = "#404040"

        self.setStyleSheet(f"background:{bg}; border:2px solid {border}; border-radius:5px;")

    def set_selected(self, sel):
        """Sets the selection state of the card."""
        self._selected = sel
        self._apply_style()

    def set_color(self, color_hex: str | None):
        """Sets the color tag and manages the visibility of the color bar."""
        self._color = color_hex
        if color_hex:
            self.color_bar.setVisible(True)
            self.color_bar.setStyleSheet(f"background-color: {color_hex}; border: none;")
        else:
            self.color_bar.setVisible(False)

        self._apply_style()

    def load_thumbnail(self):
        self.unload_thumbnail()
        self._load_id = getattr(self, '_load_id', 0) + 1
        current_id = self._load_id

        sig = WorkerSignals()
        sig.finished.connect(lambda path, img: self._on_loaded(path, img, current_id))
        self._worker = ImageLoadWorker(self.path, self._size, sig)
        self.thread_pool.start(self._worker)

    def unload_thumbnail(self):
        """Cancels the worker and cleans up references."""
        if self._worker:
            self._worker.cancelled = True
            self._worker = None
        try:
            # Clear pixmap if still existing
            self.img_label.clear()
        except (RuntimeError, AttributeError):
            pass

    def _on_loaded(self, path, image, load_id):
        if sip.isdeleted(self):
            return
        if load_id != self._load_id:
            return
        try:
            if self.img_label:
                scaled_pixmap = QPixmap.fromImage(image.scaled(
                    self._size, self._size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))
                self.img_label.setPixmap(scaled_pixmap)
        except (RuntimeError, AttributeError):
            pass

    def mousePressEvent(self, e):
        """Handles initial mouse press for drag operations and focus activation."""
        if e.button() == Qt.MouseButton.LeftButton:
            # Notify the stash zone that it is now active via a click
            self.stash_zone.set_active(True)
            # Give container focus so shortcuts work
            self.stash_zone.container.setFocus()
            self.drag_start_pos = e.pos()

    def mouseReleaseEvent(self, e):
        """Handles mouse release to trigger a click or start a drag."""
        if e.button() == Qt.MouseButton.LeftButton:
            if self.drag_start_pos is None:
                return

            if (e.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
                self.clicked.emit(self.path)
            self.drag_start_pos = None

    def mouseDoubleClickEvent(self, e):
        """Returns the card to the main view on double-click."""
        if e.button() == Qt.MouseButton.LeftButton:
            self.stash_zone.return_to_main([self.path])

    def mouseMoveEvent(self, e):
        """Handles drag and drop reordering within or from the stash."""
        if not (e.buttons() & Qt.MouseButton.LeftButton) or self.drag_start_pos is None:
            return
        if (e.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        sel = [c.path for c in self.stash_zone._cards if c._selected]
        if self.path not in sel:
            sel = [self.path]

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MIME_STASH, ",".join(sel).encode())
        mime.setData(MIME_INTERNAL, ",".join(sel).encode())
        drag.setMimeData(mime)

        px = self.img_label.pixmap()
        if not px or px.isNull():
            px = QPixmap(64, 64)
            px.fill(Qt.GlobalColor.transparent)

        count = len(sel)
        if count > 1:
            off = min(count - 1, 3) * 3
            preview = QPixmap(64 + off, 64 + off)
            preview.fill(Qt.GlobalColor.transparent)
            p = QPainter(preview)
            for i in range(min(count, 4)):
                p.setOpacity(0.5 + 0.5 * (i == min(count, 4) - 1))
                o = (min(count, 4) - 1 - i) * 3
                p.drawPixmap(o, o, px.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio))
            p.end()
            drag.setPixmap(preview)
        else:
            drag.setPixmap(px.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio))

        drag.setHotSpot(QPoint(32, 32))
        drag.exec(Qt.DropAction.MoveAction)


# ─── STASH ZONE ───────────────────────────────────────────────────────────────

class StashZone(QWidget):
    """Collapsible stash panel shown at the bottom of the workspace."""

    STASH_THUMB = 80
    HEADER_H = 28

    def __init__(self, sorter, initial_expanded=False):
        super().__init__()
        self.sorter = sorter
        self._paths: list[str] = []
        self._cards: list[StashCard] = []
        self._expanded = initial_expanded
        self._last_clicked: str | None = None
        # Reference to the container will be set during _setup_ui
        self.container = None
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("background:#141414;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Use the custom StashHeader which handles click activation
        self.header = StashHeader(self)
        self.header.setFixedHeight(self.HEADER_H)
        self.header.setStyleSheet("QFrame{background:#1a1a1a;border-top:1px solid #333;}")
        h_lay = QHBoxLayout(self.header)
        h_lay.setContentsMargins(8, 0, 8, 0)
        h_lay.setSpacing(6)

        self.clear_btn = QPushButton("✕ Clear Stash")
        self.clear_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#bbb;border:none;"
            "font-size:10px;padding:0 4px;}"
            "QPushButton:hover{color:#c0392b;}"
        )
        self.clear_btn.clicked.connect(self._on_clear)
        h_lay.addWidget(self.clear_btn)

        self.return_btn = QPushButton("↑ Return selected")
        self.return_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#bbb;border:none;"
            "font-size:10px;padding:0 4px;}"
            "QPushButton:hover{color:#4d8fcc;}"
        )
        self.return_btn.clicked.connect(self._return_selected)
        h_lay.addWidget(self.return_btn)

        self.remove_btn = QPushButton("✕ Remove")
        self.remove_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#bbb;border:none;"
            "font-size:10px;padding:0 4px;}"
            "QPushButton:hover{color:#c0392b;}"
        )
        self.remove_btn.clicked.connect(self._remove_selected)
        h_lay.addWidget(self.remove_btn)

        h_lay.addStretch()

        self.toggle_btn = QPushButton("▲  Stash  (0)")
        self.toggle_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#bbb;border:none;"
            "font-size:11px;text-align:right;padding:0;}"
            "QPushButton:hover{color:#eee;}"
        )
        self.toggle_btn.setToolTip("Toggle Stash (Tab)")
        self.toggle_btn.clicked.connect(self.toggle)
        h_lay.addWidget(self.toggle_btn)

        root.addWidget(self.header)

        self.scroll = StashScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea{border:none;background:#141414;}"
            "QScrollBar:horizontal{background:#141414;height:6px;}"
            "QScrollBar::handle:horizontal{background:#333;border-radius:3px;}"
            "QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0;}"
        )

        self.container = StashContainer(self)
        flow = QHBoxLayout(self.container)
        flow.setContentsMargins(8, 6, 8, 6)
        flow.setSpacing(6)
        flow.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.flow = flow

        self.empty_hint = QLabel("Drop images here  ·  double-click to return")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint.setStyleSheet("color:#999; font-size:11px;")
        self.flow.addWidget(self.empty_hint)

        self.scroll.setWidget(self.container)
        self.scroll.setFixedHeight(self.STASH_THUMB + 44)
        self.scroll.setVisible(self._expanded)
        root.addWidget(self.scroll)

        self._update_label()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_active(self, active: bool):
        """Changes the header brightness to indicate focus state."""
        if active:
            # Slightly brighter background for active state (Luminance shift)
            self.header.setStyleSheet("QFrame{background:#252525;border-top:1px solid #333;}")
        else:
            # Original dark background for inactive state
            self.header.setStyleSheet("QFrame{background:#1a1a1a;border-top:1px solid #333;}")

    def _on_card_clicked(self, path):
        mods = QApplication.keyboardModifiers()
        cards_by_path = {c.path: c for c in self._cards}
        card = cards_by_path.get(path)
        if not card:
            return

        if mods & Qt.KeyboardModifier.ShiftModifier and self._last_clicked:
            paths = [c.path for c in self._cards]
            if self._last_clicked in paths and path in paths:
                lo = min(paths.index(self._last_clicked), paths.index(path))
                hi = max(paths.index(self._last_clicked), paths.index(path))
                add = bool(mods & Qt.KeyboardModifier.ControlModifier)
                for i, c in enumerate(self._cards):
                    if lo <= i <= hi:
                        c.set_selected(True)
                    elif not add:
                        c.set_selected(False)
        elif mods & Qt.KeyboardModifier.ControlModifier:
            card.set_selected(not card._selected)
            self._last_clicked = path
        else:
            # Single click behavior (as requested, doesn't toggle via same click)
            for c in self._cards:
                c.set_selected(c.path == path)
            self._last_clicked = path
        self._update_label()

    def _return_selected(self):
        sel = [c.path for c in self._cards if c._selected]
        if sel:
            self.return_to_main(sel)

    def _remove_selected(self):
        sel = [c.path for c in self._cards if c._selected]
        if sel:
            self.sorter.undo_stack.push(RemoveFromStashCommand(self, sel))

    def toggle(self):
        self._expanded = not self._expanded
        self.scroll.setVisible(self._expanded)
        self._update_label()

    def _update_label(self):
        arrow = "▼" if self._expanded else "▲"
        n = len(self._paths)
        sel = sum(1 for c in self._cards if c._selected)
        label = f"{arrow}  Stash  ({n})" if not sel else f"{arrow}  Stash  ({n}  ·  {sel} selected)"
        self.toggle_btn.setText(label)
        self.empty_hint.setVisible(n == 0)

    def add_paths(self, paths):
        existing = set(self._paths)
        for p in paths:
            if p not in existing:
                self._paths.append(p)
                card = StashCard(p, self.STASH_THUMB, self.sorter.thread_pool, self)
                card.clicked.connect(self._on_card_clicked)

                if p in self.sorter.temp_colors:
                    card.set_color(self.sorter.temp_colors[p])

                self._cards.append(card)
                self.flow.addWidget(card)
                existing.add(p)
        self._update_label()
        if not self._expanded:
            self.toggle()

    def _remove_path(self, path):
        if path in self._paths:
            idx = self._paths.index(path)
            self._paths.pop(idx)
            card = self._cards.pop(idx)
            self.flow.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._update_label()

    def return_to_main(self, paths):
        self.sorter.undo_stack.push(MoveFromStashCommand(self.sorter, paths))

    def _on_clear(self):
        if not self._paths:
            return
        self.sorter.undo_stack.push(ClearStashCommand(self.sorter))

    def _clear_no_undo(self):
        for card in self._cards:
            self.flow.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()
        self._paths.clear()
        self._update_label()
