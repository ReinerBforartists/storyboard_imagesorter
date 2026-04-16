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


from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QColorDialog
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


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

        # Professional color palette (10 preset colors)
        self.palette = [
            "#e74c3c", "#3498db", "#2ecc71", "#f1c40f", "#9b59b6",
            "#1abc9c", "#e67e22", "#95a5a6", "#ffffff", "#000000"
        ]

        # Color names for tooltips
        self.palette_names = [
            "Red", "Blue", "Green", "Yellow", "Purple",
            "Teal", "Orange", "Gray", "White", "Black"
        ]

        # Create palette buttons
        for color, name in zip(self.palette, self.palette_names):
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{name}  —  click to apply to selected")
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

        layout.addSpacing(15)

        # Custom Color Picker Button
        self.picker_btn = QPushButton("🎨")
        self.picker_btn.setFixedSize(32, 32)
        self.picker_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.picker_btn.setToolTip("Custom color picker  —  click to apply to selected")
        self._update_picker_style()
        self.picker_btn.clicked.connect(self._open_color_dialog)
        layout.addWidget(self.picker_btn)

        # Clear Colors Button (Placed below the picker)
        self.clear_btn = QPushButton("∅")
        self.clear_btn.setFixedSize(32, 32)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setToolTip("Clear colors from selected (Ctrl+Shift+C)")
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

    def _update_picker_style(self):
        """Updates the appearance of the picker button based on the active custom color."""
        if self._current_custom_color:
            # Show current color as background with white border
            self.picker_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self._current_custom_color};
                    color: white;
                    border: 2px solid white;
                    border-radius: 4px;
                    font-size: 16px;
                }}
                QPushButton:hover {{
                    border: 2px solid #4d8fcc;
                }}
            """)
        else:
            # Default state
            self.picker_btn.setStyleSheet("""
                QPushButton {
                    background: #2a2a2a;
                    color: white;
                    border: 1px solid #444;
                    border-radius: 4px;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background: #3a3a3a;
                    border: 1px solid #4d8fcc;
                }
            """)

    def _open_color_dialog(self):
        """Opens the standard system color dialog and updates visual feedback."""
        start_color = QColor(self._current_custom_color) if self._current_custom_color else QColor("#ffffff")
        color = QColorDialog.getColor(start_color, self, "Select Custom Color")

        if color.isValid():
            new_color_hex = color.name()
            self._current_custom_color = new_color_hex

            # Update the main application (will be saved to disk on exit)
            self.sorter.custom_color = new_color_hex

            self.sorter._apply_color_to_selection(new_color_hex)
            self._update_picker_style()
