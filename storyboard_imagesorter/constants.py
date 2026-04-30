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
# constants.py
# This module defines global constants and configuration settings for the application.
# It includes MIME types, UI dimension parameters, supported image formats,
# and QSS (Qt Style Sheets) strings used to style menus and main components.


MIME_INTERNAL = "application/x-image-paths"
ZOOM_STEPS = [25, 50, 75, 100, 125, 150, 175, 200]
BASE_SIZE = 200
TOOLBAR_H = 32
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')

# Style constants are now owned by ui_styles.
# Re-exported here so existing callers (constants.MENU_STYLE / constants.APP_STYLE)
# continue to work without modification.
from ui_styles import MENU_STYLE, STYLE_APP as APP_STYLE  # noqa: E402
