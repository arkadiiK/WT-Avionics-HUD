"""
agm_logic.py
------------
Manages combat logic and guidance state machines for Air-to-Ground Missiles (AGM).
Supports TV/IR seeker systems, Laser designation guidance, and Manual (SACLOS/MCLOS) modes.
"""

import time

import config
from core.enums import WeaponState


class BaseAGMGuidance:
    """
    Base class for all air-to-ground missile guidance systems.
    Provides fundamental state management and fire flags.
    """

    def __init__(self):
        self.current_state = WeaponState.OFF
        self.missile_fired_flag = False

    def reset(self):
        """Resets the guidance system to its default state."""
        self.current_state = WeaponState.OFF
        self.missile_fired_flag = False

    def on_fire_press(self, current_time):
        """Handles weapon fire commands."""
        pass

    def update_ocr_text(self, text, current_time, last_fire_press_time):
        """Processes OCR text data from the game display."""
        pass

    def tick(self, current_time):
        """Periodic logic update for state timeouts."""
        pass


class TV_IR_Guidance(BaseAGMGuidance):
    """
    Logic for TV and Infrared guided Air-to-Ground Missiles.
    Tracks seeker states such as searching, tracking, and standby.
    """

    def __init__(self):
        super().__init__()
        self.ignore_ocr_until = 0.0
        self.has_tracking = False
        self.fire_intention_time = 0.0

    def reset(self):
        """Resets TV/IR guidance internal states."""
        super().reset()
        self.ignore_ocr_until = 0.0
        self.has_tracking = False
        self.fire_intention_time = 0.0

    def on_fire_press(self, current_time):
        """Registers intent to fire when a lock is established."""
        if self.current_state == WeaponState.LOCKED:
            self.fire_intention_time = current_time

    def update_ocr_text(self, text, current_time, last_fire_press_time):
        """Updates seeker states based on OCR text analysis."""
        if current_time < self.ignore_ocr_until:
            return

        # 1. Missile launch detection logic
        # If fire was pressed and the seeker text disappears, we confirm the launch.
        if self.has_tracking and self.fire_intention_time > 0:
            if current_time - self.fire_intention_time <= 1.5:
                if not text or "off" in text or "seeker" not in text:
                    self.missile_fired_flag = True
                    self.ignore_ocr_until = current_time + 1.5
                    self.current_state = WeaponState.OFF
                    self.has_tracking = False
                    self.fire_intention_time = 0.0
                    return
            else:
                self.fire_intention_time = 0.0

        # 2. Sticky States
        # The state updates ONLY when the OCR clearly detects a new keyword.
        # If the text is empty (vanished), the code ignores it and keeps the previous state.
        if "tracking" in text:
            self.current_state = WeaponState.LOCKED
            self.has_tracking = True
        elif "searching" in text:
            self.current_state = WeaponState.SEARCHING
        elif "waiting" in text or "seeker: on" in text:
            self.current_state = WeaponState.STANDBY
        elif "off" in text:
            self.current_state = WeaponState.OFF
            self.has_tracking = False
            self.fire_intention_time = 0.0

    def tick(self, current_time):
        """Placeholder for periodic TV/IR ticks."""
        pass


class LaserGuidance(BaseAGMGuidance):
    """
    Logic for Laser-guided Air-to-Ground Missiles and munitions.
    Manages laser designation status and launch sequences.
    """

    def __init__(self):
        super().__init__()
        self.laser_active = False
        self.fire_intention_time = 0.0
        self.ignore_ocr_until = 0.0

    def reset(self):
        """Resets laser guidance parameters."""
        super().reset()
        self.laser_active = False
        self.fire_intention_time = 0.0
        self.ignore_ocr_until = 0.0
        self.current_state = WeaponState.OFF

    def on_fire_press(self, current_time):
        """Registers firing sequence if the laser designator is active."""
        if self.laser_active:
            self.fire_intention_time = current_time

    def update_ocr_text(self, text, current_time, last_fire_press_time):
        """Updates laser designation state using OCR feedback."""
        if current_time < self.ignore_ocr_until:
            return

        # Confirm launch if waiting status appears shortly after firing
        if self.fire_intention_time > 0:
            if current_time - self.fire_intention_time <= 1.0:
                if "waiting" in text:
                    self.missile_fired_flag = True
                    self.laser_active = False
                    self.current_state = WeaponState.OFF
                    self.fire_intention_time = 0.0
                    self.ignore_ocr_until = current_time + 1.0
                    return
            else:
                self.fire_intention_time = 0.0

        if "searching" in text or "waiting" in text:
            self.laser_active = True
            self.current_state = WeaponState.LOCKED
        elif "off" in text:
            self.laser_active = False
            self.current_state = WeaponState.OFF

    def tick(self, current_time):
        """Placeholder for periodic laser ticks."""
        pass


class SACLOS_MCLOS_AGM_Guidance(BaseAGMGuidance):
    """
    Logic for manual command-guided Air-to-Ground weapons (SACLOS/MCLOS).
    Allows immediate deployment without seeker tracking.
    """

    def on_fire_press(self, current_time):
        """Triggers immediate missile release."""
        self.missile_fired_flag = True


class AGMCombatLogic:
    """
    Controller class responsible for managing AGM strategies and routing commands.
    """

    def __init__(self):
        self.last_fire_press_time = 0.0
        self.guidance_mode = "TV_IR"
        self.strategies = {
            "TV_IR": TV_IR_Guidance(),
            "LASER": LaserGuidance(),
            "MANUAL": SACLOS_MCLOS_AGM_Guidance()
        }

    @property
    def active_strategy(self):
        """Returns the currently active guidance strategy."""
        return self.strategies.get(self.guidance_mode, self.strategies["TV_IR"])

    def on_fire_press(self, current_time):
        """Passes fire commands to the active strategy."""
        self.last_fire_press_time = current_time
        self.active_strategy.on_fire_press(current_time)

    def reset(self):
        """Resets the active strategy."""
        self.active_strategy.reset()

    def set_guidance(self, guidance_list):
        """
        Selects the appropriate guidance mode based on weapon characteristics.

        Args:
            guidance_list (list): List of guidance capability strings.
        """
        if "TV" in guidance_list or "IR" in guidance_list:
            self.guidance_mode = "TV_IR"
        elif "Laser" in guidance_list:
            self.guidance_mode = "LASER"
        elif "SACLOS" in guidance_list or "MCLOS" in guidance_list:
            self.guidance_mode = "MANUAL"
        else:
            self.guidance_mode = "TV_IR"

        self.reset()

    def update_ocr_text(self, text):
        """Feeds normalized OCR text into the active strategy."""
        text_lower = text.lower() if text else ""
        current_time = time.time()
        self.active_strategy.update_ocr_text(
            text_lower, current_time, self.last_fire_press_time
        )

    def tick(self):
        """
        Performs regular logic ticks and compiles UI layout states.

        Returns:
            dict: Configuration dictionary for visual HUD elements.
        """
        current_time = time.time()
        self.active_strategy.tick(current_time)

        fired = self.active_strategy.missile_fired_flag
        self.active_strategy.missile_fired_flag = False
        state = self.active_strategy.current_state

        ui_color = None
        ui_blink = False

        if state == WeaponState.STANDBY:
            ui_color = config.FLAPS_TRANSIT_COLOR
            ui_blink = False
        elif state == WeaponState.SEARCHING:
            ui_color = config.FLAPS_TRANSIT_COLOR
            ui_blink = True
        elif state == WeaponState.LOCKED:
            ui_color = config.ERR_COLOR
            ui_blink = False

        return {"color": ui_color, "blink": ui_blink, "fired": fired}