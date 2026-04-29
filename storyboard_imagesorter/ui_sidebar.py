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
# ui_sidebar.py
# This module defines the ColorSidebar widget.
# It provides a vertical interface featuring a preset color palette,
# a custom color selection tool, and functionality to clear applied colors,
# enabling rapid visual tagging of images within the application.


from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QColorDialog, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


def _make_separator():
    """Creates a horizontal separator line for visual grouping."""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFixedHeight(1)
    sep.setStyleSheet("background: #333; border: none; margin: 2px 0px;")
    return sep


class ColorSidebar(QWidget):
    """
    Vertical sidebar containing a color palette and a custom color picker.
    Provides fast access to colors for selecting image groups.
    """

    def __init__(self, sorter, initial_color="#ffffff"):
        super().__init__()
        self.sorter = sorter
        # Set the starting color from the passed argument
        self._current_custom_color = initial_color
        self._setup_ui()

    def _setup_ui(self):
        # Narrow width for a professional look
        self.setFixedWidth(50)
        self.setStyleSheet("background:#141414; border-right: 1px solid #333;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 10, 5, 10)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # High-contrast palette (10 colors) optimized for Dark Theme
        self.palette = [
            "#ff0000",  # Red
            "#00ff33",  # Green
            "#2979FF",  # Blue
            "#FFFF00",  # Yellow
            "#f032e6",  # Magenta
            "#FF9100",  # Orange
            "#00ffff",  # Cyan
            "#996600",  # Brown
            "#999999",  # Grey
            "#FFFFFF",  # White
        ]

        self.palette_names = [
            "Red", "Green", "Blue",
            "Yellow", "Magenta", "Orange",
            "Cyan", "Brown", "Grey", "White"
        ]

        # Create palette buttons
        for color, name in zip(self.palette, self.palette_names):
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, c=color: self.sorter._select_by_color(c))
            btn.setToolTip(
                f"{name}\n"
                f"Left click — apply to selected\n"
                f"Right click — select all cards with this color\n"
                f"Shift+right click — add to current selection"
            )
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border: 1px solid #444;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border: 1px solid white;
                }}
            """)
            btn.clicked.connect(lambda checked, c=color: self.sorter._apply_color_to_selection(c))
            layout.addWidget(btn)

        # --- Separator: palette / custom color ---
        layout.addWidget(_make_separator())

        # Create a sub-layout for the custom color group to remove spacing between them
        custom_group_layout = QVBoxLayout()
        custom_group_layout.setSpacing(0)  # No gap between custom button and picker
        custom_group_layout.setContentsMargins(0, 0, 0, 0)

        # Custom Color Button
        self.custom_color_btn = QPushButton()
        self.custom_color_btn.setFixedSize(32, 32)
        self.custom_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_color_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.custom_color_btn.customContextMenuRequested.connect(
            lambda pos: self.sorter._select_by_color(self._current_custom_color)
        )
        self.custom_color_btn.clicked.connect(
            lambda: self.sorter._apply_color_to_selection(self._current_custom_color)
        )
        self._update_custom_color_btn_style()
        custom_group_layout.addWidget(self.custom_color_btn)

        # Open Picker Button
        self.open_picker_btn = QPushButton("🎨")
        self.open_picker_btn.setFixedSize(32, 20)
        self.open_picker_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_picker_btn.setToolTip("Open color picker to set the custom color")
        self.open_picker_btn.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: white;
                border: 1px solid #444;
                border-radius: 3px;
                font-size: 11px;
                padding: 0px;
            }
            QPushButton:hover {
                background: #3a3a3a;
                border: 1px solid #4d8fcc;
            }
        """)
        self.open_picker_btn.clicked.connect(self._open_color_dialog)
        custom_group_layout.addWidget(self.open_picker_btn)

        # Add the sub-layout to the main layout
        layout.addLayout(custom_group_layout)

        # --- Separator: custom color / clear ---
        layout.addWidget(_make_separator())

        # Clear Colors Button
        self.clear_btn = QPushButton("∅")
        self.clear_btn.setFixedSize(32, 32)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setToolTip("Clear color tags from selected\nC")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: #2a2a2a;
                color: #e74c3c;
                border: 1px solid #444;
                border-radius: 4px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: #3a2a2a;
                border: 1px solid #e74c3c;
            }
        """)
        self.clear_btn.clicked.connect(self.sorter._clear_selected_colors)
        layout.addWidget(self.clear_btn)


    def _update_custom_color_btn_style(self):
        """Updates the appearance of the custom color button to reflect the current custom color."""
        color = self._current_custom_color or "#ffffff"
        self.custom_color_btn.setToolTip(
            f"Custom color: {color}\n"
            f"Left click — apply to selected\n"
            f"Right click — select all cards with this color\n"
            f"Shift+right click — add to current selection"
        )
        self.custom_color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: 2px solid #888;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid white;
            }}
        """)

    def _open_color_dialog(self):
        """Opens the standard system color dialog and updates the custom color button.
        Does NOT automatically apply the color to the current selection."""
        start_color = QColor(self._current_custom_color) if self._current_custom_color else QColor("#ffffff")
        color = QColorDialog.getColor(start_color, self, "Select Custom Color")

        if color.isValid():
            new_color_hex = color.name()
            self._current_custom_color = new_color_hex

            # Persist to settings (will be saved to disk on exit)
            self.sorter.custom_color = new_color_hex
            self.sorter.settings_manager.set("custom_color", new_color_hex)
            self.sorter.settings_manager.request_save()

            self._update_custom_color_btn_style()
