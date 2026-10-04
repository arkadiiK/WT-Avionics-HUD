"""
settings_manager.py
-------------------
Handles the persistent storage and retrieval of launcher settings.
Ensures that configuration data is saved safely in the appropriate directory.
"""

import json
import os


def _get_settings_path():
    """Returns absolute path to the settings file to prevent directory conflicts."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_dir = os.path.join(base_dir, "data")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "launcher_settings.json")


def load_settings():
    """Retrieves settings from JSON, returning defaults upon failure."""
    settings_file = _get_settings_path()

    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARNING] [SETTINGS] Failed to load settings: {e}")

    return {"silent_launch": False}


def save_settings(data):
    """Commits settings dictionary to JSON file."""
    settings_file = _get_settings_path()

    try:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"[ERROR] [SETTINGS] Failed to save settings: {e}")