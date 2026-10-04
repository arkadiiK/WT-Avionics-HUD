"""
config.py
---------
Global configuration file for the WT Avionics HUD.
Dynamically loads user-defined colors from settings or falls back to default values.
Defines layout constants, typography, and API endpoints for the overlay.
"""

import os

# ==========================================
# SETTINGS INITIALIZATION
# ==========================================
_settings = {}
try:
    # Load user settings to apply custom colors across the HUD
    from launcher.settings_manager import load_settings
    _settings = load_settings()
except Exception as e:
    print(f"[ERROR] [CONFIG] Failed to load settings: {e}")

# ==========================================
# DYNAMIC COLORS (RGB/RGBA Tuples)
# ==========================================
HUD_COLOR = tuple(_settings.get("HUD_COLOR", [0, 255, 50]))
BG_COLOR = tuple(_settings.get("BG_COLOR", [0, 0, 0, 100]))
TREND_COLOR = tuple(_settings.get("TREND_COLOR", [255, 255, 0]))
FLAPS_TRANSIT_COLOR = tuple(_settings.get("FLAPS_TRANSIT_COLOR", [255, 165, 0]))
ERR_COLOR = tuple(_settings.get("ERR_COLOR", [255, 30, 30]))

# ==========================================
# NETWORK & API
# ==========================================
TELEMETRY_URL = "http://127.0.0.1:8111/state"

# ==========================================
# TYPOGRAPHY & HUD LAYOUT CONSTANTS
# ==========================================
FONT_FAMILY = "Consolas"
FONT_SIZE = 15

Y_CENTER = 250
X_LEFT_TAPE = 100
X_RIGHT_TAPE = 290
TAPE_HEIGHT = 374
TAPE_WIDTH = 88

# Speedometer Tape Settings
SCALE_SPD = 3.0
TREND_SCALE_SPD = 1.2
STEP_MAIN_SPD = 50
STEP_MINOR_SPD = 10

# Altimeter Tape Settings
SCALE_ALT = 2.0
TREND_SCALE_ALT = 0.25
STEP_MAIN_ALT = 100
STEP_MINOR_ALT = 20