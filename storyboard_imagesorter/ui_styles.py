# ui_styles.py
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

# ui_styles.py
# Centralized design system and QSS presets for Storyboard Imagesorter.
# All UI styling should reference this module to ensure visual consistency.

# ─── Design Tokens ───────────────────────────────────────────────────────────

# Backgrounds
BG_DARK = "#181818"
BG_SURFACE = "#252525"
BG_INPUT = "#2a2a2a"
BG_HOVER = "#333333"
BG_ACTIVE = "#172d4e"
BG_DISABLED = "#1e1e1e"

# Text Colors
TEXT_PRIMARY = "#d0d0d0"
TEXT_SECONDARY = "#999999"
TEXT_DISABLED = "#555555"
TEXT_ACCENT = "#4d8fcc"
TEXT_SUCCESS = "#4caf50"
TEXT_WARNING = "#e8872a"
TEXT_DANGER = "#e74c3c"

# Borders
BORDER_DEFAULT = "#383838"
BORDER_INPUT = "#404040"
BORDER_FOCUS = "#2d6fab"

# Accents & Status
ACCENT_PRIMARY = "#2d6fab"
ACCENT_SUCCESS = "#1a6b3a"
ACCENT_WARNING = "#e8872a"
ACCENT_DANGER = "#8a2020"

# Spacing & Sizing
SPACING_UNIT = 4
BORDER_RADIUS = 4
BUTTON_MIN_HEIGHT = 28
BUTTON_PADDING = "4px 18px"
INPUT_PADDING = "2px 8px"
LABEL_MARGIN = 2

# Typography
FONT_FAMILY = "Arial"
FONT_SIZE_SMALL = 10
FONT_SIZE_NORMAL = 12
FONT_SIZE_LARGE = 14
FONT_SIZE_HEADER = 17


# ─── QSS Generator Functions ─────────────────────────────────────────────────

def style_button(
    default_bg: str = BG_INPUT,
    hover_bg: str = BG_HOVER,
    text_color: str = TEXT_PRIMARY,
    border_color: str = BORDER_INPUT,
    min_height: int = BUTTON_MIN_HEIGHT,
    padding: str = BUTTON_PADDING,
    font_size: int = FONT_SIZE_NORMAL,
    font_weight: str = "normal",
    is_primary: bool = False,
    is_danger: bool = False
) -> str:
    """Generates a unified QPushButton stylesheet."""
    if is_primary:
        bg, hover_bg, border, text = ACCENT_PRIMARY, "#245a9e", BORDER_FOCUS, "#d0e8ff"
    elif is_danger:
        bg, hover_bg, border, text = "#c0392b", "#e74c3c", "#a93226", "#ffffff"
    else:
        bg, hover_bg, border, text = default_bg, hover_bg, border_color, text_color

    return (
        f"QPushButton{{background:{bg};color:{text};border:1px solid {border};"
        f"border-radius:{BORDER_RADIUS}px;padding:{padding};min-height:{min_height}px;"
        f"font-size:{font_size}px;font-family:{FONT_FAMILY};font-weight:{font_weight};}}"
        f"QPushButton:hover{{background:{hover_bg};}}"
        f"QPushButton:disabled{{background:{BG_DISABLED};color:{TEXT_DISABLED};border-color:{BORDER_DEFAULT};}}"
    )


def style_input(
    bg: str = BG_INPUT,
    border: str = BORDER_INPUT,
    text: str = TEXT_PRIMARY,
    placeholder: str = "#888888",
    radius: int = BORDER_RADIUS,
    padding: str = INPUT_PADDING,
    min_height: int = BUTTON_MIN_HEIGHT
) -> str:
    """Generates a unified QLineEdit/QSpinBox/QComboBox stylesheet."""
    return (
        f"QLineEdit,QSpinBox,QComboBox{{background:{bg};color:{text};border:1px solid {border};"
        f"border-radius:{radius}px;padding:{padding};min-height:{min_height}px;font-size:{FONT_SIZE_NORMAL}px;font-family:{FONT_FAMILY};}}"
        f"QLineEdit::placeholder,QSpinBox::placeholder,QComboBox::placeholder{{color:{placeholder};}}"
    )


def style_label(
    text_color: str = TEXT_PRIMARY,
    bg: str = "transparent",
    font_size: int = FONT_SIZE_NORMAL,
    font_weight: str = "normal",
    margin: int = LABEL_MARGIN
) -> str:
    """Generates a unified QLabel stylesheet."""
    return f"QLabel{{background:{bg};color:{text_color};font-size:{font_size}px;font-family:{FONT_FAMILY};font-weight:{font_weight};margin:{margin}px;}}"


def style_separator(color: str = BORDER_DEFAULT, height: int = 1, margin: int = 4) -> str:
    """Generates a unified QFrame separator stylesheet."""
    return f"QFrame{{background:{color};border:none;min-height:{height}px;margin:{margin}px 0;}}"


def style_scrollbar(bg: str = BG_DARK, handle: str = "#333333", width: int = 7) -> str:
    """Generates a unified QScrollBar stylesheet."""
    return (
        f"QScrollBar:vertical{{background:{bg};width:{width}px;margin:0px;}}"
        f"QScrollBar::handle:vertical{{background:{handle};border-radius:3px;min-height:24px;}}"
        f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0px;}}"
    )


# ─── Predefined Widget Styles ────────────────────────────────────────────────

STYLE_BUTTON_DEFAULT = style_button()
STYLE_BUTTON_PRIMARY = style_button(is_primary=True)
STYLE_BUTTON_DANGER = style_button(is_danger=True)
STYLE_BUTTON_SECONDARY = style_button(default_bg=BG_SURFACE, hover_bg=BG_HOVER, border_color=BORDER_DEFAULT)

STYLE_INPUT = style_input()
STYLE_INPUT_LIGHT = style_input(bg=BG_SURFACE)

STYLE_LABEL_PRIMARY = style_label(text_color=TEXT_PRIMARY)
STYLE_LABEL_SECONDARY = style_label(text_color=TEXT_SECONDARY)
STYLE_LABEL_ACCENT = style_label(text_color=TEXT_ACCENT, font_weight="bold")

STYLE_SEPARATOR = style_separator()
STYLE_SCROLLBAR = style_scrollbar()
STYLE_SCROLLBAR_STASH = style_scrollbar(bg=BG_SURFACE, handle="#444444", width=6)

# ─── Global Application Styles ───────────────────────────────────────────────

STYLE_APP = """
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

MENU_STYLE = (
    "QMenu{background:#252525;color:#d0d0d0;border:1px solid #383838;"
    "border-radius:6px;padding:4px;}"
    "QMenu::item{padding:6px 18px;border-radius:4px;}"
    "QMenu::item:selected{background:#2d6fab;}"
    "QMenu::separator{height:1px;background:#383838;margin:4px 8px;}"
)

# ─── Toggle / Checkable Button Styles ────────────────────────────────────────

STYLE_TOGGLE_ACTIVE = (
    f"QPushButton{{background:{BG_ACTIVE};color:{TEXT_ACCENT};"
    f"border:1px solid {BORDER_FOCUS};padding:5px 10px;text-align:left;"
    f"font-size:{FONT_SIZE_SMALL}px;border-radius:{BORDER_RADIUS}px;}}"
)
STYLE_TOGGLE_INACTIVE = (
    f"QPushButton{{background:{BG_INPUT};color:{TEXT_PRIMARY};"
    f"border:1px solid {BORDER_DEFAULT};padding:5px 10px;text-align:left;"
    f"font-size:{FONT_SIZE_SMALL}px;border-radius:{BORDER_RADIUS}px;}}"
)

# ─── Dialog Styles ────────────────────────────────────────────────────────────

STYLE_DIALOG_BASE = f"background:{BG_SURFACE};color:{TEXT_PRIMARY};border-radius:{BORDER_RADIUS}px;"

STYLE_TABLE = (
    f"QTableWidget{{background:{BG_SURFACE};border:1px solid {BORDER_DEFAULT};"
    f"gridline-color:#2e2e2e;}}"
    f"QHeaderView::section{{background:{BG_INPUT};color:#ccc;border:none;padding:4px;}}"
    f"QTableWidget::item{{padding:3px 6px;}}"
)

STYLE_COLLISION_WARN = (
    f"background:#3a1010;color:#ff7070;border:1px solid #7a2020;"
    f"border-radius:{BORDER_RADIUS}px;padding:4px 8px;font-size:{FONT_SIZE_SMALL}px;"
)

# ─── Toolbar Button Helper ────────────────────────────────────────────────────

def style_toolbar_btn(bg: str, hover: str, icon: bool = False) -> str:
    """Generates a standardized toolbar button stylesheet (replaces utils_workers._btn)."""
    from constants import TOOLBAR_H
    w = f"min-width:{TOOLBAR_H}px;" if icon else "min-width:78px;"
    pad = "0px 6px" if icon else "0px 11px"
    fs = "16px" if icon else "12px"
    return (
        f"QPushButton{{background:{bg};color:#e0e0e0;border:none;"
        f"padding:{pad};border-radius:{BORDER_RADIUS}px;"
        f"min-height:{TOOLBAR_H}px;{w}font-size:{fs};font-weight:500;}}"
        f"QPushButton:hover{{background:{hover};}}"
        f"QPushButton:disabled{{background:#222;color:#3a3a3a;}}"
    )

# ─── Card Styles ──────────────────────────────────────────────────────────────

STYLE_CARD_DEFAULT  = f"background:{BG_SURFACE};border:2px solid {BORDER_INPUT};border-radius:5px;"
STYLE_CARD_SELECTED = f"background:{BG_ACTIVE};border:2px solid {ACCENT_PRIMARY};border-radius:5px;"
STYLE_CARD_DRAGOVER = f"background:#1e3d6e;border:2px solid {TEXT_ACCENT};border-radius:5px;"
STYLE_CARD_CHANGED  = f"background:{BG_SURFACE};border:2px solid {ACCENT_WARNING};border-radius:5px;"

STYLE_COLOR_BAR_EMPTY = f"background-color:{BORDER_INPUT};border:none;"

STYLE_NOTE_EDITOR = (
    f"QTextEdit{{background:{BG_INPUT};color:#eee;border:1px solid {BORDER_INPUT};"
    f"border-radius:{BORDER_RADIUS}px;font-size:{FONT_SIZE_NORMAL}px;padding:4px;}}"
    f"QScrollBar:vertical{{background:{BG_INPUT};width:8px;margin:0px;}}"
    f"QScrollBar::handle:vertical{{background:#444;min-height:20px;border-radius:4px;}}"
    f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0px;}}"
)

STYLE_RELOAD_BTN = (
    f"QPushButton{{background:{ACCENT_WARNING};color:#fff;border:none;border-radius:11px;"
    f"font-size:13px;font-weight:bold;padding:0;}}"
    f"QPushButton:hover{{background:#ff9f35;}}"
)

def style_note_toggle_btn(font_size: int) -> str:
    return (
        f"QPushButton{{background:{BG_HOVER};color:#aaa;border:1px solid {BORDER_INPUT};"
        f"border-radius:{BORDER_RADIUS}px;font-size:{font_size}px;padding:2px 6px;text-align:left;}}"
        f"QPushButton:hover{{background:#444;color:#fff;}}"
    )

def style_card_label(font_size: int) -> str:
    return f"background-color:{BG_INPUT};color:white;border:none;font-size:{font_size}px;"

# ─── Stash Styles ─────────────────────────────────────────────────────────────

STYLE_STASH_HEADER_INACTIVE = f"QFrame{{background:#1a1a1a;border-top:1px solid {BORDER_DEFAULT};}}"
STYLE_STASH_HEADER_ACTIVE   = f"QFrame{{background:{BG_SURFACE};border-top:1px solid {BORDER_DEFAULT};}}"
STYLE_STASH_CONTAINER       = f"background:{BG_DARK};"  # slightly different from main bg
STYLE_STASH_SCROLL = (
    f"QScrollArea{{border:none;background:#141414;}}"
    f"QScrollBar:horizontal{{background:#141414;height:6px;}}"
    f"QScrollBar::handle:horizontal{{background:{BG_HOVER};border-radius:3px;}}"
    f"QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0;}}"
)
STYLE_STASH_EMPTY_HINT = f"color:{TEXT_SECONDARY};font-size:{FONT_SIZE_SMALL}px;"

def style_stash_action_btn(hover_color: str = TEXT_ACCENT) -> str:
    return (
        f"QPushButton{{background:transparent;color:{TEXT_SECONDARY};border:none;"
        f"font-size:{FONT_SIZE_SMALL}px;padding:0 4px;}}"
        f"QPushButton:hover{{color:{hover_color};}}"
    )

# ─── Sidebar Styles ───────────────────────────────────────────────────────────

STYLE_SIDEBAR_TOGGLE = (
    f"QPushButton{{background:{BG_SURFACE};color:{TEXT_SECONDARY};"
    f"border:1px solid {BORDER_DEFAULT};border-left:none;"
    f"border-top-right-radius:{BORDER_RADIUS}px;border-bottom-right-radius:{BORDER_RADIUS}px;"
    f"font-size:12px;}}"
    f"QPushButton:hover{{background:{BG_HOVER};color:white;"
    f"border-left:1px solid {TEXT_ACCENT};}}"
)

# ─── Progress / Status Bar ────────────────────────────────────────────────────

STYLE_PROGRESS_BAR = (
    f"QProgressBar{{background-color:{BG_INPUT};border:1px solid {BORDER_INPUT};"
    f"border-radius:{BORDER_RADIUS}px;}}"
    f"QProgressBar::chunk{{background-color:{ACCENT_PRIMARY};border-radius:2px;}}"
)
STYLE_CANCEL_BTN_SMALL = (
    f"QPushButton{{background:#5a1a1a;color:#e0e0e0;border:none;"
    f"padding:0 8px;border-radius:{BORDER_RADIUS}px;font-size:11px;font-weight:500;}}"
    f"QPushButton:hover{{background:{ACCENT_DANGER};}}"
)
STYLE_STATUS_LABEL  = f"color:{TEXT_ACCENT};font-size:{FONT_SIZE_NORMAL}px;font-weight:bold;min-width:150px;"
STYLE_COUNT_LABEL   = f"font-size:11px;color:{TEXT_SECONDARY};min-width:95px;"
STYLE_ZOOM_LABEL    = f"font-size:11px;color:{TEXT_SECONDARY};"

# ─── Lightbox overlay button styles (semi-transparent, on dark backdrop) ─────

STYLE_LB_REMOVE = (
    f"QPushButton{{background:rgba(160,40,40,200);color:#ffffff;"
    f"border:1px solid rgba(220,80,80,180);border-radius:{BORDER_RADIUS}px;"
    f"font-size:13px;font-weight:500;padding:4px 14px;}}"
    f"QPushButton:hover{{background:rgba(220,60,60,230);border-color:rgba(255,120,120,220);}}"
    f"QPushButton:disabled{{background:rgba(50,50,50,160);color:rgba(120,120,120,200);border-color:rgba(80,80,80,120);}}"
)
STYLE_LB_STASH = (
    f"QPushButton{{background:rgba(30,80,160,200);color:#ffffff;"
    f"border:1px solid rgba(60,120,210,180);border-radius:{BORDER_RADIUS}px;"
    f"font-size:13px;font-weight:500;padding:4px 14px;}}"
    f"QPushButton:hover{{background:rgba(50,110,200,230);border-color:rgba(100,160,255,220);}}"
    f"QPushButton:disabled{{background:rgba(50,50,50,160);color:rgba(120,120,120,200);border-color:rgba(80,80,80,120);}}"
)

# ─── Toolbar Action Button Presets ───────────────────────────────────────────
# Named by semantic role so callers never hardcode hex colours.

def _TB(bg, hover, icon=False):
    """Internal shorthand used only in this module for toolbar presets."""
    return style_toolbar_btn(bg, hover, icon)

STYLE_TB_ADD    = _TB("#1a6b3a", "#1f8348")   # green  — add / import
STYLE_TB_REMOVE = _TB("#7a2020", "#a32828")   # red    — remove / delete
STYLE_TB_EXPORT = _TB("#1a4a6b", "#1f5f8a")   # blue   — export
STYLE_TB_SORT   = _TB("#3a2a5a", "#4e3a78")   # purple — sort
STYLE_TB_NAV    = _TB("#252535", "#32324a", True)   # neutral icon — nav/undo
STYLE_TB_UTIL   = _TB("#1e1e1e", "#2e2e2e", True)   # dark icon   — gear/info


STYLE_TB_NAV    = _TB("#252535", "#32324a", True)   # neutral icon — nav/undo
STYLE_TB_UTIL   = _TB("#1e1e1e", "#2e2e2e", True)   # dark icon   — gear/info

# ─── Sidebar-Specific Button Styles ─────────────────────────────────────────
# Unified presets for the color sidebar to maintain visual consistency.

STYLE_SIDEBAR_ICON = (
    f"QPushButton{{background:{BG_INPUT};color:#e0e0e0;border:1px solid {BORDER_INPUT};"
    f"border-radius:3px;padding:0px;font-size:11px;min-height:20px;}}"
    f"QPushButton:hover{{background:{BG_HOVER};border-color:{BORDER_FOCUS};}}"
)

STYLE_SIDEBAR_CLEAR = (
    f"QPushButton{{background:{BG_INPUT};color:{TEXT_DANGER};border:1px solid {BORDER_INPUT};"
    f"border-radius:4px;padding:0px;font-size:18px;font-weight:bold;min-height:32px;}}"
    f"QPushButton:hover{{background:#3a2a2a;border-color:{TEXT_DANGER};}}"
)

