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
# settings_manager.py
# This module provides the SettingsManager class for handling persistent configuration.
# It facilitates loading default values, merging them with saved user settings from a JSON file,
# and providing easy access to application-wide parameters via getter and setter methods.

import os
import json
import platform

class SettingsManager:
    """
    Handles loading, saving, and managing application configuration.
    Everything is encapsulated: directory creation, platform detection,
    and error handling are all handled internally.
    """

    def __init__(self, app_name="Storyboard_Imagesorter", config_filename="sorter_settings.json"):
        self.app_name = app_name
        self.config_filename = config_filename
        self._defaults = {
            "last_export_dir": os.path.join(os.getcwd(), "exports"),
            "gap": 10,
            "zoom_pct": 100,
            "export_prefix": "image_",
            "export_mapping_enabled": False,
            "contact_export_prefix": "Sheet_",
            "contact_cols": 5,
            "contact_thumb": 150,
            "contact_labels": True,
            "contact_notes": False,
            "contact_mode": "grid",
            "contact_images_per_page": 24,
            "auto_reload": True,
            "show_index": True,
            "show_filename": True,
            "show_notes": False,
            "include_summary": False,
            "custom_color": "#ffffff",
            "sidebar_visible": False,
            "stash_visible": False,
            "scroll_zone_alpha": 80,
            "undo_limit": 50,
        }
        self.settings = {}

        # 1. Determine the platform-specific writable directory
        self.config_dir = self._get_config_directory()
        self.config_file = os.path.join(self.config_dir, self.config_filename)

        # 2. Ensure the config directory exists immediately upon instantiation
        os.makedirs(self.config_dir, exist_ok=True)

        # 3. Load settings (or use defaults if no file exists)
        self.load()

    def _get_config_directory(self):
        """
        Internal method to find the correct system directory.
        No external user input required.
        """
        system = platform.system()
        if system == "Windows":
            # Returns C:\Users\<User>\AppData\Roaming\Storyboard_Imagesorter
            base_dir = os.getenv("APPDATA")
            return os.path.join(base_dir, self.app_name) if base_dir else os.getcwd()
        elif system == "Darwin":  # macOS
            return os.path.expanduser(f"~/Library/Application Support/{self.app_name}")
        else:  # Linux / Unix
            base_dir = os.getenv("XDG_CONFIG_HOME")
            if base_dir:
                return os.path.join(base_dir, self.app_name)
            return os.path.expanduser(f"~/.config/{self.app_name}")

    def load(self):
        """Loads settings from the JSON file and merges them with defaults."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                self.settings = {**self._defaults, **saved}
            except Exception as e:
                print(f"Error loading settings: {e}")
                self.settings = self._defaults.copy()
        else:
            self.settings = self._defaults.copy()

    def save(self):
        """Saves the current settings dictionary to the JSON file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        """Returns a setting value by key."""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Sets a setting value."""
        self.settings[key] = value

    def update_export_dir(self, path):
        """
        Updates the last export directory and ensures that directory exists.
        All error handling is internal.
        """
        self.settings["last_export_dir"] = path
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            # If the user provides an invalid/protected path, we don't crash
            pass
