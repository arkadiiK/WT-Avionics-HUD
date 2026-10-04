"""
input_manager.py
----------------
Handles hardware-level keyboard and mouse input capture using the Win32 API.
Operates passively without global hooks to ensure compatibility with anti-cheat systems.
"""

import ctypes
import json
import os
import sys
import time


class InputManager:
    """
    Manages user input mapping, state tracking, and cooldowns.
    Uses virtual key codes (VK) to check hardware states securely.
    """
    VK_MAP = {
        # Mouse
        "LMB": 0x01, "RMB": 0x02, "MMB": 0x04,
        "MOUSE4": 0x05, "MOUSE5": 0x06, "XMB1": 0x05, "XMB2": 0x06,

        # Modifiers
        "SHIFT": 0x10, "LSHIFT": 0xA0, "RSHIFT": 0xA1,
        "CTRL": 0x11, "LCTRL": 0xA2, "RCTRL": 0xA3,
        "ALT": 0x12, "LALT": 0xA4, "RALT": 0xA5,

        # Controls
        "SPACE": 0x20, "SPACEBAR": 0x20,
        "TAB": 0x09, "ENTER": 0x0D,
        "ESC": 0x1B, "ESCAPE": 0x1B,
        "BACKSPACE": 0x08,
        "CAPSLOCK": 0x14, "CAPS": 0x14,
        "TILDE": 0xC0, "`": 0xC0, "~": 0xC0,

        # Arrows
        "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,

        # Numpad
        "NUM0": 0x60, "NUM1": 0x61, "NUM2": 0x62, "NUM3": 0x63, "NUM4": 0x64,
        "NUM5": 0x65, "NUM6": 0x66, "NUM7": 0x67, "NUM8": 0x68, "NUM9": 0x69,

        # Misc
        "M": 0x4D
    }

    _previous_states = {}
    _last_trigger_time = {}

    def __init__(self):
        self.user32 = ctypes.windll.user32

        # Map alphabetical keys (A-Z)
        for i in range(65, 91):
            self.VK_MAP[chr(i)] = i

        # Map numerical keys (0-9)
        for i in range(48, 58):
            self.VK_MAP[chr(i)] = i

        self.keybinds = {}
        self._load_keybinds()

    def _load_keybinds(self):
        """Loads user-defined keybindings from a JSON configuration file."""
        self.keybinds = {
            "primary_fire": ["LMB"],
            "ui_score": ["TAB"],
            "switch_secondary_weapon": ["ALT", "2"],
            "fire_secondary_weapon": ["SPACE"],
            "fire_flares": ["ALT", "E"],
            "fire_chaff": ["ALT", "E"]
        }

        base_dir = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

        try:
            path = os.path.join(base_dir, 'data', 'keybinds.json')
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    self.keybinds.update(json.load(f))
        except Exception as e:
            print(f"[ERROR] [INPUT] Failed to load keybinds.json: {e}")

    def is_wt_foreground(self):
        """
        Checks if War Thunder is the currently active (focused) window.
        Filters out browsers and IDEs that might have matching title strings.

        Returns:
            bool: True if the game is focused, False otherwise.
        """
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return False

        length = self.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        self.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        if "War Thunder" in title:
            for bad in ["Google Chrome", "YouTube", "Discord", "PyCharm", "Idea"]:
                if bad in title:
                    return False
            return True

        return False

    def _check_raw_action(self, action_name: str) -> bool:
        """
        Checks the raw hardware state of all keys mapped to a specific action.

        Args:
            action_name (str): The internal name of the action to verify.

        Returns:
            bool: True if all required keys for the action are currently held down.
        """
        keys = self.keybinds.get(action_name, [])

        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split('+')]

        if not keys:
            return False

        for key_str in keys:
            vk_code = self.VK_MAP.get(key_str.upper())
            # 0x8000 checks the most significant bit, which indicates the key is currently pressed
            if not vk_code or not (self.user32.GetAsyncKeyState(vk_code) & 0x8000):
                return False

        return True

    def is_game_ui_active(self):
        """
        Checks if the in-game UI (like the scoreboard) is active.

        Returns:
            bool: True if the UI keybind is currently held.
        """
        return self._check_raw_action("ui_score")

    def is_action_down(self, action_name: str) -> bool:
        """
        Checks if an action is continuously held down.

        Args:
            action_name (str): The name of the action.

        Returns:
            bool: True if held, False otherwise or if the game is unfocused.
        """
        if not self.is_wt_foreground() or self.is_game_ui_active():
            return False
        return self._check_raw_action(action_name)

    def is_action_pressed(self, action_name: str) -> bool:
        """
        Checks if an action was just pressed (single trigger with cooldown).
        Ideal for weapon releases and countermeasures to prevent spamming.

        Args:
            action_name (str): The name of the action.

        Returns:
            bool: True on the exact frame the action completes its cooldown and is pressed.
        """
        if not self.is_wt_foreground() or self.is_game_ui_active():
            InputManager._previous_states[action_name] = False
            return False

        is_down = self._check_raw_action(action_name)
        was_down = InputManager._previous_states.get(action_name, False)

        InputManager._previous_states[action_name] = is_down

        if is_down and not was_down:
            current_time = time.time()
            last_time = InputManager._last_trigger_time.get(action_name, 0.0)

            # Dynamic cooldown: 20ms for weapons/countermeasures (allows spam), 150ms for UI actions
            if action_name in ["fire_secondary_weapon", "fire_flares", "fire_chaff"]:
                cooldown = 0.02
            else:
                cooldown = 0.15

            if current_time - last_time > cooldown:
                InputManager._last_trigger_time[action_name] = current_time
                return True

        return False