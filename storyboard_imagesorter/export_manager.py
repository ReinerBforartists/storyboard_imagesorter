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
# export_manager.py
# Handles all import/export operations: image export, contact sheet rendering,
# and summary file parsing. Called by ImageSorter but contains no Qt window state.

import os
import re
import shutil
import math

from PyQt6.QtWidgets import (
    QFileDialog, QDialog, QMessageBox, QMenu, QApplication
)
from PyQt6.QtGui import QImage, QPainter, QColor, QFont, QFontMetrics
from PyQt6.QtCore import Qt, QPoint

import constants
import utils_workers
import ui_dialogs


class ExportManager:
    """
    Mixin that provides export and import methods to ImageSorter.
    Expects self to be an ImageSorter instance (accesses self.cards,
    self.custom_notes, self.temp_colors, self.settings_manager, etc.)
    """

    # ── Import ────────────────────────────────────────────────────────────────

    def import_notes_from_summary(self, summary_file_path):
        """
        Parses a summary .txt file and restores notes and color tags
        for any matching images currently loaded.
        """
        if not os.path.exists(summary_file_path):
            self.show_status("File not found!")
            return

        new_notes = {}
        new_colors = {}

        try:
            with open(summary_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            blocks = re.findall(r"(?s)FILE:\s*(.*?)\n(.*?)(?=FILE:|$)", content)

            for filename, block in blocks:
                filename = filename.strip()

                color_match = re.search(r"COLOR:\s*(#[a-fA-F0-9]{6})", block)
                if color_match:
                    new_colors[filename] = color_match.group(1)

                note_match = re.search(r"NOTE:\s*(.*?)(?=\n-|$)", block, re.DOTALL)
                if note_match:
                    note_text = note_match.group(1).strip()
                    if note_text:
                        new_notes[filename] = note_text

            import_count = 0
            color_count = 0
            total_cards = len(self.cards)

            # Show progress bar if we have many cards to process
            show_bar = total_cards > 20
            if show_bar:
                self.progress_bar.setMaximum(total_cards)
                self.progress_bar.setValue(0)
                self.progress_bar.setVisible(True)
                self.status_label.hide()

            for idx, card in enumerate(self.cards):
                base_name = os.path.basename(card.path)

                if base_name in new_notes:
                    text = new_notes[base_name]
                    self.custom_notes[card.path] = text
                    card.set_note_text(text)
                    import_count += 1

                if base_name in new_colors:
                    color = new_colors[base_name]
                    self.temp_colors[card.path] = color
                    card.set_color(color)
                    color_count += 1

                if show_bar:
                    self.progress_bar.setValue(idx + 1)
                    QApplication.processEvents()

            if show_bar:
                self.progress_bar.setVisible(False)
                self.status_label.show()

            if import_count == 0 and color_count == 0:
                self.show_status("No matching images found")
            else:
                self.show_status(f"Imported: {import_count} notes, {color_count} colors")
                self._rebuild_flow_completely()

        except Exception as e:
            print(f"Import Error: {e}")
            self.show_status("Import failed")

    # ── Export menu ───────────────────────────────────────────────────────────

    def _show_export_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(constants.MENU_STYLE)
        menu.addAction("Export images…", self._export_images)
        menu.addAction("Export contact sheet…", self._export_contact_sheet)
        btn = self.sender()
        menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))

    # ── Image export ──────────────────────────────────────────────────────────

    def _export_images(self):
        """
        Copies images to a folder with sequential names.
        Optionally writes a summary file (notes/colors) and a name-mapping file.
        """
        from PyQt6.QtWidgets import QApplication
        if not self.cards:
            return

        mapping_pref = self.settings_manager.get("export_mapping_enabled", False)

        dlg = ui_dialogs.ExportPreviewDialog(
            self.cards, self,
            initial_prefix=self.saved_export_prefix,
            mapping_enabled=mapping_pref
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        prefix = dlg.get_prefix()
        self.saved_export_prefix = prefix
        mapping_requested = dlg.get_mapping_enabled()
        self.settings_manager.set("export_mapping_enabled", mapping_requested)
        self._save_settings()

        folder = QFileDialog.getExistingDirectory(self, "Select Export Folder", self.last_export_dir)
        if not folder:
            return
        self.last_export_dir = folder
        self._save_last_dir(folder)

        digits = len(str(len(self.cards)))
        filenames = [
            f"{prefix}{str(i + 1).zfill(digits)}{os.path.splitext(c.path)[1]}"
            for i, c in enumerate(self.cards)
        ]

        try:
            collisions = [f for f in filenames if f in os.listdir(folder)]
        except OSError:
            collisions = []

        if collisions:
            reply = QMessageBox.question(
                self, "Files exist",
                f"{len(collisions)} file(s) already exist. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Show progress bar in header
        self.status_label.hide()
        self.progress_bar.setMaximum(len(self.cards))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        QApplication.processEvents()

        summary_entries = []
        mapping_entries = []

        for i, card in enumerate(self.cards):
            # Update progress bar
            self.progress_bar.setValue(i + 1)
            QApplication.processEvents()

            dest_img_path = os.path.join(folder, filenames[i])
            try:
                # Using load_image_safely to ensure the file is stable before copying
                img_check = utils_workers.load_image_safely(card.path)
                if not img_check.isNull():
                    shutil.copy2(card.path, dest_img_path)

                    mapping_entries.append({
                        'new': filenames[i],
                        'old': os.path.basename(card.path)
                    })

                    note_text = self.custom_notes.get(card.path, "").strip()
                    color_hex = getattr(card, "_color", None)

                    if note_text or color_hex:
                        summary_entries.append({
                            'filename': filenames[i],
                            'note': note_text,
                            'color': color_hex
                        })
            except Exception as e:
                print(f"Error exporting {card.path}: {e}")

        # Write summary file (only if notes/colors exist)
        if summary_entries:
            summary_path = os.path.join(folder, f"{prefix}_sorter_data.txt")
            try:
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write("STORYBOARD NOTES & COLOR SUMMARY\n")
                    f.write("=" * 35 + "\n\n")
                    for entry in summary_entries:
                        f.write(f"FILE: {entry['filename']}\n")
                        if entry['color']:
                            f.write(f"COLOR: {entry['color']}\n")
                        if entry['note']:
                            f.write(f"NOTE: {entry['note']}\n")
                        f.write("-" * 20 + "\n")
            except Exception as e:
                print(f"Error creating summary file: {e}")

        # Write mapping file (only if requested)
        if mapping_requested:
            mapping_path = os.path.join(folder, f"{prefix}_name_mapping.txt")
            try:
                with open(mapping_path, 'w', encoding='utf-8') as f:
                    f.write("FILENAME MAPPING (EXPORT <-> ORIGINAL)\n")
                    f.write("=" * 40 + "\n\n")
                    for entry in mapping_entries:
                        f.write(f"{entry['new']} -> {entry['old']}\n")
                self.show_status("Mapping file created.")
            except Exception as e:
                print(f"Error creating mapping file: {e}")

        msg = "Export complete."
        if summary_entries and mapping_requested:
            msg += " (Summary & Mapping included)"
        elif summary_entries:
            msg += " (Summary included)"
        elif mapping_requested:
            msg += " (Mapping included)"

        # Hide progress bar and show the final success message in the label
        self.progress_bar.setVisible(False)
        self.show_status(msg)

    # ── Contact sheet export ──────────────────────────────────────────────────

    def _export_contact_sheet(self):
        """Renders paginated contact sheets as PNG files (grid or list layout)."""
        from PyQt6.QtWidgets import QApplication
        if not self.cards:
            return

        dlg = ui_dialogs.ContactSheetDialog(
            self.cards,
            self,
            initial_prefix=self.saved_contact_prefix,
            init_cols=self.saved_contact_cols,
            init_thumb=self.saved_contact_thumb,
            init_labels=self.saved_contact_labels,
            init_notes=self.saved_contact_notes,
            init_mode=self.settings_manager.get("contact_mode", "grid"),
            init_per_page=self.settings_manager.get("contact_images_per_page", 24)
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        prefix = dlg.get_prefix()
        self.saved_contact_prefix = prefix
        self.saved_contact_cols = dlg.get_cols()
        self.saved_contact_thumb = dlg.get_thumb_size()
        self.saved_contact_labels = dlg.get_labels_enabled()
        self.saved_contact_notes = dlg.get_notes_enabled()

        self.settings_manager.set("contact_export_prefix", prefix)
        self.settings_manager.set("contact_mode", dlg.get_mode())
        self.settings_manager.set("contact_images_per_page", dlg.get_per_page())
        self._save_settings()

        folder = QFileDialog.getExistingDirectory(self, "Select Export Folder", self.last_export_dir)
        if not folder:
            return
        self.last_export_dir = folder
        self._save_last_dir(folder)

        mode = dlg.get_mode()
        cols = self.saved_contact_cols if mode == "grid" else 1
        thumb_sz = self.saved_contact_thumb
        show_lbl = self.saved_contact_labels
        show_note = self.saved_contact_notes
        per_page = dlg.get_per_page()

        pad = 10
        font = QFont("Arial", 9)
        font_bold = QFont("Arial", 10, QFont.Weight.Bold)
        char_limit = 1000

        card_chunks = [
            self.cards[i:i + per_page] for i in range(0, len(self.cards), per_page)
        ]

        # Collision check
        expected_filenames = []
        for chunk_idx in range(len(card_chunks)):
            suffix = "grid" if mode == "grid" else "list"
            expected_filenames.append(
                os.path.join(folder, f"{prefix}_{suffix}_{chunk_idx + 1:02d}.png")
            )

        collisions = [f for f in expected_filenames if os.path.exists(f)]
        if collisions:
            reply = QMessageBox.question(
                self, "Files exist",
                f"{len(collisions)} file(s) already exist. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Show progress bar in header
        self.status_label.hide()
        self.progress_bar.setMaximum(len(card_chunks))
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        QApplication.processEvents()

        total_pages = len(card_chunks)

        for chunk_idx, chunk in enumerate(card_chunks):
            # Update progress bar
            self.progress_bar.setValue(chunk_idx + 1)
            QApplication.processEvents()

            if mode == "grid":
                dest_path = expected_filenames[chunk_idx]
                sheet = self._render_grid_sheet(chunk, cols, thumb_sz, show_lbl, show_note, pad, font, char_limit)
            else:
                dest_path = expected_filenames[chunk_idx]
                sheet = self._render_list_sheet(chunk, thumb_sz, show_lbl, show_note, pad, font, font_bold, char_limit)

            sheet.save(dest_path)

        # Hide progress bar and show the final success message in the label
        self.progress_bar.setVisible(False)
        self.show_status(f"Exported {len(self.cards)} images in {total_pages} sheet(s)")

    def _render_grid_sheet(self, chunk, cols, thumb_sz, show_lbl, show_note, pad, font, char_limit):
        """Renders one page of a grid-layout contact sheet and returns a QImage."""
        num_cards = len(chunk)
        rows = math.ceil(num_cards / cols)
        row_heights = []

        for r in range(rows):
            row_cards = chunk[r * cols: (r + 1) * cols]
            max_text_h = 0
            for card in row_cards:
                note = self.custom_notes.get(card.path, "").strip()[:char_limit]
                if show_note and note:
                    fm = QFontMetrics(font)
                    rect = fm.boundingRect(
                        0, 0, thumb_sz + pad, 10000,
                        Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft,
                        note
                    )
                    max_text_h = max(max_text_h, rect.height())
            label_h = 35 if show_lbl else 0
            row_heights.append(thumb_sz + label_h + max_text_h + pad)

        sheet_width = cols * (thumb_sz + pad) + pad
        sheet_height = sum(row_heights) + pad
        sheet = QImage(sheet_width, sheet_height, QImage.Format.Format_RGB32)
        sheet.fill(QColor("#1a1a1a"))
        painter = QPainter(sheet)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for i, card in enumerate(chunk):
            r, c = divmod(i, cols)
            x = pad + c * (thumb_sz + pad)
            y = pad + sum(row_heights[:r]) if r > 0 else pad

            img = utils_workers.load_image_safely(card.path)
            if not img.isNull():
                thumb = img.scaled(
                    thumb_sz, thumb_sz,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                painter.drawImage(x + (thumb_sz - thumb.width()) // 2, y, thumb)

            curr_y = y + thumb_sz + 4
            if show_lbl:
                painter.setPen(QColor("#eee"))
                painter.setFont(font)
                fname = os.path.basename(card.path)
                painter.drawText(x, curr_y, thumb_sz, 20, Qt.AlignmentFlag.AlignCenter, fname)
                curr_y += 22

            if show_note:
                note = self.custom_notes.get(card.path, "").strip()[:char_limit]
                if note:
                    painter.setPen(QColor("#bbb"))
                    painter.setFont(font)
                    painter.drawText(
                        x, curr_y, thumb_sz, 1000,
                        Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop,
                        note
                    )

        painter.end()
        return sheet

    def _render_list_sheet(self, chunk, thumb_sz, show_lbl, show_note, pad, font, font_bold, char_limit):
        """Renders one page of a list-layout contact sheet and returns a QImage."""
        text_internal_gap = 12
        sheet_width = thumb_sz + pad + 600
        rows_data = []

        for card in chunk:
            note = self.custom_notes.get(card.path, "").strip()[:char_limit]
            fname = os.path.basename(card.path)
            f_h = 25 if show_lbl else 0
            n_h = 0
            if show_note and note:
                fm = QFontMetrics(font)
                rect = fm.boundingRect(
                    0, 0, 600, 10000,
                    Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft,
                    note
                )
                n_h = rect.height()

            effective_gap = text_internal_gap if (f_h > 0 and n_h > 0) else 0
            text_block_h = f_h + effective_gap + n_h if (f_h > 0 or n_h > 0) else 0
            total_row_h = max(thumb_sz, text_block_h)

            rows_data.append({
                'card': card, 'total_h': total_row_h, 'fname': fname,
                'note': note, 'f_h': f_h, 'n_h': n_h, 'gap': effective_gap
            })

        sheet_height = sum(r['total_h'] + pad for r in rows_data) + pad
        sheet = QImage(sheet_width, sheet_height, QImage.Format.Format_RGB32)
        sheet.fill(QColor("#1a1a1a"))
        painter = QPainter(sheet)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        curr_y = pad
        for r_data in rows_data:
            img = utils_workers.load_image_safely(r_data['card'].path)
            if not img.isNull():
                thumb = img.scaled(
                    thumb_sz, thumb_sz,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                painter.drawImage(pad, curr_y, thumb)

            text_x = pad + thumb_sz + pad
            temp_y = curr_y

            if show_lbl:
                painter.setPen(QColor("#eee"))
                painter.setFont(font_bold)
                painter.drawText(
                    text_x, temp_y + 20, 600, r_data['f_h'],
                    Qt.AlignmentFlag.AlignLeft, r_data['fname']
                )
                temp_y += r_data['f_h'] + r_data['gap']

            if show_note and r_data['note']:
                painter.setPen(QColor("#bbb"))
                painter.setFont(font)
                painter.drawText(
                    text_x, temp_y, 600, r_data['n_h'],
                    Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop,
                    r_data['note']
                )

            curr_y += r_data['total_h'] + pad

        painter.end()
        return sheet
