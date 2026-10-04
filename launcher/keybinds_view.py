"""
keybinds_view.py
----------------
Provides a graphical interface for configuring custom hotkeys.
Includes a specialized button class that captures raw keyboard and mouse inputs.
"""

import json
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFormLayout, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

# Default fallback configurations
DEFAULT_KEYBINDS = {
    "primary_fire": ["lmb"],
    "ui_score": ["tab"],
    "ui_chat": ["enter"],
    "ui_menu": ["esc"],
    "ui_map": ["m"],
    "switch_secondary_weapon": ["alt", "2"],
    "fire_secondary_weapon": ["space"],
    "fire_flares": ["alt", "e"],
    "fire_chaff": ["alt", "e"]
}


class KeybindButton(QPushButton):
    """
    Custom QPushButton widget that listens for and captures keyboard and mouse input.
    """
    def __init__(self, initial_bind):
        super().__init__()
        self.current_bind = initial_bind
        self.is_listening = False
        self._update_text()
        self.setMinimumHeight(35)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _update_text(self):
        """Updates the button's visual state based on its listening status."""
        if self.is_listening:
            self.setText("Press any key...")
            self.setStyleSheet("background-color: #E65100; color: white; font-weight: bold; border-radius: 4px;")
        else:
            display_text = " + ".join(self.current_bind).upper() if self.current_bind else "UNBOUND"
            self.setText(display_text)
            self.setStyleSheet("background-color: #333; color: white; font-weight: bold; border-radius: 4px;")

    def mousePressEvent(self, event):
        """Captures mouse clicks for binding or activates listening mode."""
        if not self.is_listening:
            # Enable listening mode
            self.is_listening = True
            self._update_text()
            self.setFocus()
            event.accept()
        else:
            # Capture the specific mouse button pressed
            btn = event.button()
            if btn == Qt.MouseButton.LeftButton:
                self.current_bind = ["lmb"]
            elif btn == Qt.MouseButton.RightButton:
                self.current_bind = ["rmb"]
            elif btn == Qt.MouseButton.MiddleButton:
                self.current_bind = ["mmb"]
            elif btn == Qt.MouseButton.XButton1:
                self.current_bind = ["mouse4"]
            elif btn == Qt.MouseButton.XButton2:
                self.current_bind = ["mouse5"]

            self.is_listening = False
            self._update_text()
            event.accept()

    def keyPressEvent(self, event):
        """Captures keyboard inputs, including complex modifier combinations."""
        if not self.is_listening:
            super().keyPressEvent(event)
            return

        key = event.key()
        modifiers = event.modifiers()

        # Ignore raw Windows system keys
        if key in (Qt.Key.Key_Meta, Qt.Key.Key_Super_L, Qt.Key.Key_Super_R):
            return

        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")

        # Check if the pressed key is strictly a modifier
        is_modifier = key in (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_AltGr)

        # If it's a standard key, register the full bind and close listening mode
        if not is_modifier:
            key_map = {
                Qt.Key.Key_Space: "space",
                Qt.Key.Key_Escape: "esc",
                Qt.Key.Key_Tab: "tab",
                Qt.Key.Key_Return: "enter",
                Qt.Key.Key_Enter: "enter",
                Qt.Key.Key_Backspace: "backspace",
                Qt.Key.Key_Up: "up",
                Qt.Key.Key_Down: "down",
                Qt.Key.Key_Left: "left",
                Qt.Key.Key_Right: "right",
            }

            key_name = key_map.get(key)
            if not key_name:
                key_name = event.text().lower()
                if not key_name:
                    key_name = QKeySequence(key).toString().lower()

            if key_name and key_name not in parts:
                parts.append(key_name)

            self.current_bind = parts
            self.is_listening = False
            self._update_text()
        else:
            # If only a modifier is pressed, update visuals and keep waiting for the main key
            self.current_bind = parts
            self.setText(" + ".join(parts).upper() + " + ...")

        event.accept()

    def keyReleaseEvent(self, event):
        """Cancels listening mode if a modifier is released without pressing a primary key."""
        if not self.is_listening:
            super().keyReleaseEvent(event)
            return

        key = event.key()
        is_modifier = key in (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_AltGr)

        if is_modifier:
            self.is_listening = False
            self._update_text()

        event.accept()

    def focusOutEvent(self, event):
        """Disables listening mode if the widget loses focus."""
        if self.is_listening:
            self.is_listening = False
            self._update_text()
        super().focusOutEvent(event)


class KeybindsWindow(QDialog):
    """
    Dialog window for managing and persisting user keybindings.
    Dynamically generates UI rows for all configured actions.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keybinds Configuration")
        self.setFixedSize(380, 500)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.keybinds_file = os.path.join(base_dir, 'data', 'keybinds.json')

        self.current_keybinds = self._load_keybinds()
        self.buttons = {}

        self._init_ui()

    def _load_keybinds(self):
        """Loads existing keybindings from disk or falls back to defaults."""
        if os.path.exists(self.keybinds_file):
            try:
                with open(self.keybinds_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {k: [p.lower() for p in v] for k, v in data.items()}
            except Exception as e:
                print(f"[WARNING] [KEYBINDS] Failed to parse keybinds.json: {e}")
        return DEFAULT_KEYBINDS.copy()

    def _init_ui(self):
        """Initializes the layout and populates the form with KeybindButtons."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        form_layout = QFormLayout()

        labels = {
            "primary_fire": "Primary Fire",
            "ui_score": "Scoreboard",
            "ui_chat": "Chat",
            "ui_menu": "Menu",
            "ui_map": "Map",
            "switch_secondary_weapon": "Cycle Weapon (HUD)",
            "fire_secondary_weapon": "Fire Weapon (HUD)",
            "fire_flares": "Fire Flares",
            "fire_chaff": "Fire Chaff"
        }

        for key in DEFAULT_KEYBINDS.keys():
            val = self.current_keybinds.get(key, DEFAULT_KEYBINDS[key])
            btn = KeybindButton(val)
            self.buttons[key] = btn
            form_layout.addRow(labels.get(key, key) + ":", btn)

        layout.addLayout(form_layout)

        info_label = QLabel("Click a button, then press any key or mouse button.")
        info_label.setStyleSheet("color: gray; font-style: italic;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)

        layout.addStretch()

        btn_layout = QHBoxLayout()

        btn_save = QPushButton("Save & Apply")
        btn_save.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.save_keybinds)

        btn_reset = QPushButton("Reset Defaults")
        btn_reset.clicked.connect(self.reset_to_defaults)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_reset)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def reset_to_defaults(self):
        """Resets all active buttons to their factory default bindings."""
        for key, val in DEFAULT_KEYBINDS.items():
            if key in self.buttons:
                self.buttons[key].current_bind = val.copy()
                self.buttons[key]._update_text()

    def save_keybinds(self):
        """Writes the configured keybindings to disk and closes the dialog."""
        new_binds = {}
        for key, btn in self.buttons.items():
            new_binds[key] = btn.current_bind

        try:
            os.makedirs(os.path.dirname(self.keybinds_file), exist_ok=True)
            with open(self.keybinds_file, 'w', encoding='utf-8') as f:
                json.dump(new_binds, f, indent=2)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save keybinds:\n{e}")