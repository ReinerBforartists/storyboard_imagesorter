***

# Storyboard Imagesorter 🖼️

**Organize your storyboard frames and image sequences quickly and visually.**

Storyboard Imagesorter is a lightweight tool designed for artists, animators, and previs professionals. Drag in your image files, sort them into a sequence, tag them with colors, add notes, and export, all without a complex project setup.

---

## 📸 Preview

| First Run | Lightbox View |
| :---: | :---: |
| ![Main Interface](img/empty.jpg) | ![Lightbox](img/lightbox.jpg) |

| Main view | Exported Images |
| :---: | :---: |
| ![Sorting](img/sorting.jpg) | ![Exported](img/export.jpg) |

---

## 🚀 User Guide (Workflow)

### 1. Import your images
* **Drag & Drop:** Drag image files directly into the window, or use the ＋ Import button.
* **Auto-restore:** If the folder you import from already contains a `_sorter_data.txt` file, you can restore colors and notes by importing it.

### 2. Organize your sequence
* **Reorder:** Click and drag any image to a new position.
* **Move Groups:** Select multiple images and use the arrow buttons in the toolbar to shift them left or right.
* **The Stash:** Images that don't belong in your current sequence can be parked in the Stash at the bottom of the window. They stay available and can be returned to the main view at any time.

### 3. Add colors and notes
* **Color tags:** Use the sidebar on the left to quickly tap a color onto your selected images (e.g., Blue for "Close-up", Red for "Action").
* **Notes:** Click 📝 Add Note on any image card to add descriptions, camera angles, or timing info.

### 4. Edit images and see changes live
Double-click an image to open it in your system's default editor. Once you save there, the thumbnail in Imagesorter updates automatically.

### 5. Export and "Save" your work
Use the ↓ Export menu to create a numbered image sequence, a Contact Sheet, or a Storyboard List with your notes alongside the artwork.
> **Your originals are never touched.** Exporting always creates copies in a new folder — your source files stay exactly where they are.

> **Saving your progress:** Every export also writes a `_sorter_data.txt` file next to your images. This file stores all your colors and notes. To reload a previous session, drag that file into the application window.

---

## ⌨️ Keyboard Shortcuts

### Main View
| Shortcut | Action |
| :--- | :--- |
| `Space` | Open / Close Full-screen Lightbox |
| `Ctrl + A` / `Ctrl + D` | Select All / Deselect All |
| `Ctrl + O` | Open Import dialog |
| `Ctrl + Z` / `Ctrl + Y` / `Ctrl + Shift + Z` | Undo / Redo last action |
| `C` | Clear colors from selected images |
| `Delete` | Remove selected images |
| `W` | Move selected images to Stash |
| `←` / `→` (Arrows) | Move selection left or right |
| `Ctrl + ←` / `→` (Arrows) | Move selection to Start / End |
| `F` | Focus view on first selected image |
| `Home` / `Pos 1` | Jump to first image |
| `End` / `Ende` | Jump to last image |
| `Page Up` / `Page Down` | Scroll through images |
| `Tab` | Toggle Stash open / closed |
| `B` | Toggle Sidebar open / closed |
| `+` / `-` | Zoom in / out of the canvas |
| `Scroll` | Scroll through images |
| `Shift + Scroll` | **Fast scroll** through large sequences |
| `Right-Click (Color)` | Select all cards with this color |
| `Shift + Right-Click (Color)` | Add color to current selection |

### Lightbox Mode (Full-screen)
| Shortcut | Action |
| :--- | :--- |
| `Esc` / `Space` | Close Lightbox |
| `←` / `→` (Arrows) | Previous / Next image |
| `Scroll` | Previous / Next image |
| `W` | Move current image to Stash |
| `Delete` | Remove current image |

### Mouse & Interactions
| Shortcut | Action |
| :--- | :--- |
| `Shift + Click` | Extend selection |
| `Ctrl + Click` | Toggle single image selection |
| `Mouse Drag (empty area)` | Rectangle / lasso selection |
| `Drag Image(s)` | Reorder via Drag & Drop |
| `Double-Click` | Open in system viewer |
| `Drag → Stash` | Move to stash |
| `Double-Click Stash` | Return image to main view |


---

## ⚙️ Installation & Execution

### Windows
1. Download `storyboard_imagesorter.zip` from the Releases page.
2. Extract the archive.
3. Run `storyboard_imagesorter.exe` directly — no installation required.

### Linux
A `.deb` package is available on the Releases page. Alternatively, run from source using the instructions below.

### macOS & Linux (Source Distribution)

For Linux there is a Deb available. No macOS binary is available at this time. You can run both from source via a Python virtual environment:

1. **Clone this repository:**
   ```bash
   git clone https://github.com/ReinerBforartists/storyboard_imagesorter
   cd storyboard-imagesorter
   ```

2. **Set up a Virtual Environment (Recommended):**
   ```bash
   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application:**
   ```bash
   cd storyboard_imagesorter
   python storyboard_imagesorter.py
   ```
---

## 🛠️ Technical Specifications

For developers and technical users:

* **Core Stack:** Python 3.10+ and PyQt6.
* **Architecture:** 
    * Implements the **Command Pattern** for a robust Undo/Redo system across all manipulations (sorting, tagging, moving, deleting).
    * Uses a custom **Flow Layout** engine for dynamic image arrangement.
    * Features a background **File Watcher** service to monitor file system changes for real-time thumbnail synchronization.
* **Data Management:** Metadata (colors/notes) is handled via a lightweight text-based exchange format (`_sorter_data.txt`), allowing for easy project reloading without proprietary database overhead.

---

**Feedback and Pull Requests are welcome!**

License: GNU General Public License v3.0 · Copyright © 2026 Reiner Prokein (Haizy Tiles)