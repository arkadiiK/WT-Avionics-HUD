"""
unguided_logic.py
-----------------
Manages combat logic for unguided weapons such as dumb bombs and unguided rockets.
Provides instant fire response without relying on seeker states or OCR feedback.
"""


class UnguidedCombatLogic:
    """
    Controller class for unguided munitions.
    Bypasses any guidance logic to trigger immediate weapon release.
    """

    def __init__(self):
        self.missile_fired_flag = False

    def on_fire_press(self, current_time):
        """
        Registers an immediate fire command upon button press.

        Args:
            current_time (float): Current system time.
        """
        self.missile_fired_flag = True
        print("[INFO] [UNGUIDED] Weapon DROPPED/FIRED.")

    def reset(self):
        """Resets the firing flag to its default state."""
        self.missile_fired_flag = False

    def set_guidance(self, guidance_list):
        """
        Sets the guidance mode. Always defaults to unguided logic.

        Args:
            guidance_list (list): List of guidance capabilities (unused here).
        """
        print("[INFO] [UNGUIDED] Switched to UNGUIDED mode.")
        self.reset()

    def update_ocr_text(self, text):
        """Placeholder for OCR text processing, unused for unguided weapons."""
        pass

    def tick(self):
        """
        Executes a logic tick and formats the UI state for the HUD.

        Returns:
            dict: Contains UI color, blinking state, and the fired status.
        """
        fired = self.missile_fired_flag
        self.missile_fired_flag = False
        return {"color": None, "blink": False, "fired": fired}