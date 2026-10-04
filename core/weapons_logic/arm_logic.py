"""
arm_logic.py
------------
Manages the combat logic and state machine for Anti-Radiation Missiles (ARM).
Handles passive radar homing (PRH) activation, fire requests, and OCR-based launch confirmation.
"""

import config
from core.enums import WeaponState


class ARMCombatLogic:
    """
    Controller class for Anti-Radiation Missile guidance.
    Requires a two-step firing process: activation and firing request,
    followed by OCR confirmation to ensure the missile actually left the rail.
    """

    def __init__(self):
        self.is_active = False
        self.latest_text = ""
        self.missile_fired_flag = False
        self.current_state = WeaponState.OFF
        self.guidance_mode = "PRH"
        self.activation_time = 0.0
        # Flag to register that the fire button was pressed a second time
        self.fire_requested = False

    def reset(self):
        """Resets the ARM guidance state machine to its default parameters."""
        self.is_active = False
        self.current_state = WeaponState.OFF
        self.latest_text = ""
        self.missile_fired_flag = False
        self.activation_time = 0.0
        self.fire_requested = False

    def set_guidance(self, guidance_list):
        """
        Sets the guidance mode for the weapon. Defaults to Passive Radar Homing (PRH).

        Args:
            guidance_list (list): List of guidance capabilities.
        """
        self.guidance_mode = "PRH"
        self.reset()

    def on_fire_press(self, current_time):
        """
        Handles the weapon activation and fire request inputs.

        Args:
            current_time (float): Current system time.
        """
        # 1. Activation (First press)
        if not self.is_active:
            self.is_active = True
            self.latest_text = ""
            self.current_state = WeaponState.OFF
            self.activation_time = current_time
            self.fire_requested = False
            print("[INFO] [ARM] Activated.")
            return

        # Buffer of 0.5 seconds to prevent accidental double-clicks (micro-clicks)
        if current_time - self.activation_time < 0.5:
            return

        # 2. Fire Request (Second press)
        # Registers the command but waits for OCR confirmation before concluding the launch.
        if self.is_active:
            self.fire_requested = True
            print("[INFO] [ARM] Fire requested, waiting for OCR confirmation.")

    def update_ocr_text(self, text):
        """
        Processes OCR text to confirm missile launch and update UI seeker states.

        Args:
            text (str): Raw text captured from the game UI.
        """
        if not self.is_active:
            self.current_state = WeaponState.OFF
            return

        if text and text.strip():
            self.latest_text = text.lower()

        # 3. Actual launch confirmation
        # Only checked if the user has requested a fire (second spacebar press)
        if self.fire_requested:
            if any(w in self.latest_text for w in ["wait", "lock", "track", "off"]):
                self.missile_fired_flag = True
                self.is_active = False
                self.fire_requested = False
                self.current_state = WeaponState.OFF
                self.latest_text = ""
                print("[INFO] [ARM] Missile fired.")
                return

        # Continuous state holding for visual feedback
        # Controls the color of the HUD frame regardless of launch status
        if any(w in self.latest_text for w in ["wait", "lock", "track"]):
            self.current_state = WeaponState.LOCKED
        elif "search" in self.latest_text or "seeker" in self.latest_text:
            if self.current_state == WeaponState.OFF:
                self.current_state = WeaponState.SEARCHING

    def tick(self):
        """
        Evaluates the current state and formats the UI response for the HUD.

        Returns:
            dict: Contains UI color, blinking state, and the fired status.
        """
        fired = self.missile_fired_flag
        self.missile_fired_flag = False

        ui_color = None
        ui_blink = False

        if self.current_state == WeaponState.SEARCHING:
            ui_color = config.FLAPS_TRANSIT_COLOR
            ui_blink = True
        elif self.current_state == WeaponState.LOCKED:
            ui_color = config.ERR_COLOR
            ui_blink = False

        return {"color": ui_color, "blink": ui_blink, "fired": fired}