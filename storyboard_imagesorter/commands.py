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
# commands.py
# This module implements the command pattern for an image sorting application.
# It contains various subclasses of QUndoCommand that encapsulate specific
# user actions—such as adding, deleting, moving to stash, or color-tagging images.
# These classes enable full undo and redo functionality within the
# application's undo stack.

from PyQt6.QtGui import QUndoCommand
from PyQt6.QtWidgets import QApplication


class AddImagesCommand(QUndoCommand):
    def __init__(self, sorter, new_paths):
        super().__init__("Add Images")
        self.sorter = sorter
        self.new_paths = new_paths
        self.added_cards = []  # Store actual card objects

    def redo(self):
        self.added_cards = []
        total = len(self.new_paths)

        # Show progress bar if adding a significant number of images
        show_bar = total > 5
        if show_bar:
            self.sorter.progress_bar.setMaximum(total)
            self.sorter.progress_bar.setValue(0)
            self.sorter.progress_bar.setVisible(True)
            self.sorter.status_label.hide()

        for i, p in enumerate(self.new_paths):
            # Add cards without triggering layout rebuild for every single item
            card = self.sorter._add_image_internal(p, rebuild=False)
            self.added_cards.append(card)

            if show_bar:
                self.sorter.progress_bar.setValue(i + 1)
                # Only process events every few items to avoid slowing down the worker threads
                if (i + 1) % 5 == 0 or (i + 1) == total:
                    QApplication.processEvents()

        # Single rebuild after all items are added to the list
        self.sorter._rebuild_flow_completely()
        self.sorter._update_count()

        if show_bar:
            self.sorter.progress_bar.setVisible(False)
            self.sorter.status_label.show()

    def undo(self):
        for card in self.added_cards:
            if card in self.sorter.cards:
                self.sorter.cards.remove(card)
                card.setParent(None)
                card.deleteLater()
        self.added_cards = []
        self.sorter._rebuild_flow_completely()
        self.sorter._update_count()


class RemoveSelectedCommand(QUndoCommand):
    def __init__(self, sorter, data):
        super().__init__("Remove Selection")
        self.sorter = sorter
        # We store the card objects and their original index
        self.deleted_items = []
        for item in data:
            card = next((c for c in sorter.cards if c.path == item['path']), None)
            if card:
                self.deleted_items.append({'card': card, 'index': item['index']})

    def redo(self):
        # 1. Remove the paths from the list
        paths_to_remove = {item['card'].path for item in self.deleted_items}
        self.sorter.cards = [c for c in self.sorter.cards if c.path not in paths_to_remove]

        # 2. Only hide and detach cards from the layout, DO NOT delete them!
        for item in self.deleted_items:
            item['card'].hide()
            item['card'].setParent(None)

        self.sorter._rebuild_flow_completely()
        self.sorter._update_count()

    def undo(self):
        # 1. Re-insert the cards into the list at the correct position
        # We sort by index in descending order so that insertion does not shift indices
        for item in sorted(self.deleted_items, key=lambda x: x['index'], reverse=True):
            card = item['card']
            idx = item['index']
            self.sorter.cards.insert(idx, card)
            card.show()

        # 2. Update UI
        self.sorter._rebuild_flow_completely()
        self.sorter._update_count()


class MoveToStashCommand(QUndoCommand):
    """Moves cards from the main view into the stash — fully undoable."""

    def __init__(self, sorter, paths):
        super().__init__("Move to Stash")
        self.sorter = sorter
        self.items = []
        for path in paths:
            for i, c in enumerate(sorter.cards):
                if c.path == path:
                    self.items.append({'card': c, 'index': i, 'path': path})
                    break

    def redo(self):
        paths = {it['path'] for it in self.items}
        self.sorter.cards = [c for c in self.sorter.cards if c.path not in paths]
        for it in self.items:
            it['card'].hide()
            it['card'].setParent(None)
        self.sorter._rebuild_flow_completely()
        self.sorter._update_count()
        self.sorter.stash_zone.add_paths([it['path'] for it in self.items])

    def undo(self):
        for it in self.items:
            self.sorter.stash_zone._remove_path(it['path'])
        for it in sorted(self.items, key=lambda x: x['index']):
            idx = min(it['index'], len(self.sorter.cards))
            card = it['card']
            card.show()
            self.sorter.cards.insert(idx, card)
        self.sorter._rebuild_flow_completely()
        self.sorter._update_count()


class MoveFromStashCommand(QUndoCommand):
    """Returns cards from the stash back into the main view — fully undoable."""

    def __init__(self, sorter, paths, insert_index=None):
        super().__init__("Return from Stash")
        self.sorter = sorter
        self.paths = list(paths)
        self.insert_index = insert_index  # None = append
        self.added_cards = []  # track card objects so undo can hide, not delete

    def redo(self):
        self.added_cards = []
        for p in self.paths:
            self.sorter.stash_zone._remove_path(p)

        existing = {c.path for c in self.sorter.cards}
        for p in self.paths:
            if p not in existing:
                # Add card without triggering layout rebuild every time
                card = self.sorter._add_image_internal(p, self.insert_index, rebuild=False)
                self.added_cards.append(card)
                existing.add(p)

        # Single rebuild after all cards are restored
        self.sorter._rebuild_flow_completely()
        self.sorter._update_count()

    def undo(self):
        paths_set = set(self.paths)
        self.sorter.cards = [c for c in self.sorter.cards if c.path not in paths_set]
        for card in self.added_cards:
            card.hide()
            card.setParent(None)
        self.sorter._rebuild_flow_completely()
        self.sorter._update_count()
        self.sorter.stash_zone.add_paths(self.paths)


class ClearStashCommand(QUndoCommand):
    """Clears all cards from the stash — fully undoable."""

    def __init__(self, sorter):
        super().__init__("Clear Stash")
        self.sorter = sorter
        self.saved_paths = list(sorter.stash_zone._paths)

    def redo(self):
        self.sorter.stash_zone._clear_no_undo()

    def undo(self):
        self.sorter.stash_zone.add_paths(self.saved_paths)


class MoveCardsCommand(QUndoCommand):
    def __init__(self, sorter, old_paths, new_paths):
        super().__init__("Move")
        self.sorter = sorter
        self.old = old_paths
        self.new = new_paths

    def redo(self):
        self.sorter._apply_order_by_paths(self.new)

    def undo(self):
        self.sorter._apply_order_by_paths(self.old)


class SortCommand(QUndoCommand):
    def __init__(self, sorter, old_paths, new_paths, label):
        super().__init__(label)
        self.sorter = sorter
        self.old = old_paths
        self.new = new_paths

    def redo(self):
        self.sorter._apply_order_by_paths(self.new)

    def undo(self):
        self.sorter._apply_order_by_paths(self.old)


class ColorCommand(QUndoCommand):
    """Applies or clears color tags on a set of cards — fully undoable."""

    def __init__(self, sorter, changes):
        # changes: list of {'path': str, 'old': str|None, 'new': str|None}
        super().__init__("Color Tag")
        self.sorter = sorter
        self.changes = changes

    def redo(self):
        for ch in self.changes:
            self.sorter.temp_colors.pop(ch['path'], None)
            if ch['new']:
                self.sorter.temp_colors[ch['path']] = ch['new']
            card = next((c for c in self.sorter.cards if c.path == ch['path']), None)
            if card:
                card.set_color(ch['new'])

    def undo(self):
        for ch in self.changes:
            self.sorter.temp_colors.pop(ch['path'], None)
            if ch['old']:
                self.sorter.temp_colors[ch['path']] = ch['old']
            card = next((c for c in self.sorter.cards if c.path == ch['path']), None)
            if card:
                card.set_color(ch['old'])


class RemoveFromStashCommand(QUndoCommand):
    """Removes specific images from the stash."""

    def __init__(self, stash_zone, paths):
        super().__init__("Remove from Stash")
        self.stash_zone = stash_zone
        self.paths = list(paths)

    def redo(self):
        for p in self.paths:
            self.stash_zone._remove_path(p)

    def undo(self):
        self.stash_zone.add_paths(self.paths)


