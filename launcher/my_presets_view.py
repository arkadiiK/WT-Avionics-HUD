"""
my_presets_view.py
------------------
Manages the user's saved presets view, displaying custom loadouts categorized by aircraft.
Allows quick navigation to a specific aircraft's configuration panel.
"""

import json
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget,
    QTreeWidgetItem, QPushButton, QLabel
)
from PySide6.QtCore import Qt


class MyPresetsWindow(QDialog):
    """
    Dialog window that displays all custom weapon presets saved by the user.
    Parses both the global aircraft database and the user's local saves.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("My Saved Presets")
        self.resize(400, 500)
        self.selected_plane_tag = None

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.user_presets_path = os.path.join(base_dir, "data", "user_presets.json")
        self.db_path = os.path.join(base_dir, "data", "aircraft_db.json")

        self._init_ui()
        self._load_data()

    def _init_ui(self):
        """Initializes the user interface, including the tree view and navigation buttons."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        lbl = QLabel("Your Presets")
        font = lbl.font()
        font.setPointSize(16)
        font.setBold(True)
        lbl.setFont(font)
        layout.addWidget(lbl)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("font-size: 14px; padding: 5px;")
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

        btn_layout = QHBoxLayout()
        btn_open = QPushButton("Go to Selected Aircraft")
        btn_open.setMinimumHeight(40)
        btn_open.setMinimumWidth(150)
        btn_open.setStyleSheet("background-color: #5c9ddb; color: white; font-weight: bold; border-radius: 4px;")
        btn_open.clicked.connect(self._on_open_clicked)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_open)
        layout.addLayout(btn_layout)

    def _load_data(self):
        """
        Loads aircraft data and user presets from disk, populating the tree widget.
        Highlights the currently active main preset for each aircraft.
        """
        db = {}
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    db = json.load(f)
            except Exception as e:
                print(f"[ERROR] [MY PRESETS] Failed to load aircraft DB: {e}")

        if not os.path.exists(self.user_presets_path):
            return

        presets = {}
        try:
            with open(self.user_presets_path, "r", encoding="utf-8") as f:
                presets = json.load(f)
        except Exception as e:
            # If the file is empty (0 bytes) or corrupted, abort loading gracefully
            print(f"[WARNING] [MY PRESETS] user_presets.json is empty or invalid. Skipping. ({e})")
            return

        for plane_tag, plane_presets in presets.items():
            # Filter out the internal system key "_main"
            real_presets = {k: v for k, v in plane_presets.items() if k != "_main"}
            if not real_presets:
                continue

            plane_name = db.get(plane_tag, {}).get("name", plane_tag)

            plane_item = QTreeWidgetItem([plane_name])
            plane_item.setData(0, Qt.UserRole, plane_tag)
            font = plane_item.font(0)
            font.setBold(True)
            plane_item.setFont(0, font)

            for preset_name in sorted(real_presets.keys()):
                is_main = (plane_presets.get("_main") == preset_name)
                display_name = f"⭐ {preset_name}" if is_main else f"  • {preset_name}"

                preset_item = QTreeWidgetItem([display_name])
                preset_item.setData(0, Qt.UserRole, plane_tag)
                plane_item.addChild(preset_item)

            self.tree.addTopLevelItem(plane_item)

        self.tree.expandAll()

    def _on_item_double_clicked(self, item, column):
        """Handler for double-click events on the tree widget."""
        self._on_open_clicked(item)

    def _on_open_clicked(self, item=None):
        """Handler for the 'Go to Selected Aircraft' button to navigate to the presets view."""
        item = self.tree.currentItem()
        if item:
            self.selected_plane_tag = item.data(0, Qt.UserRole)
            self.accept()