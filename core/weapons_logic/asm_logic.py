"""
asm_logic.py
------------
Manages combat logic and guidance state machines for Anti-Ship Missiles (ASM/AShM).
Supports Infrared (IR) and Active Radar Homing (ARH) seekers.
"""

import time
import config
from core.enums import WeaponState


class BaseASMLogic:
    """
    Base class for Anti-Ship Missile guidance logic.
    Provides standard state properties and reset mechanisms.
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


class IR_ASM_Guidance(BaseASMLogic):
    """
    Logic for Infrared (IR) guided Anti-Ship Missiles.
    Monitors OCR for tracking, searching, and waiting states to infer launches.
    """

    def __init__(self):
        super().__init__()
        self.was_locked = False

    def reset(self):
        """Resets IR guidance internal states."""
        super().reset()
        self.was_locked = False

    def update_ocr_text(self, text, current_time, last_fire_press_time):
        """Updates seeker states based on OCR text analysis."""
        if "tracking" in text:
            self.current_state = WeaponState.LOCKED
            self.was_locked = True

        elif "searching" in text:
            self.current_state = WeaponState.SEARCHING

        elif "lock waiting" in text or "waiting" in text:
            self.current_state = WeaponState.COOLDOWN

        elif "seeker: on" in text:
            self.current_state = WeaponState.STANDBY

        elif "off" in text or "seeker" not in text:
            if current_time - last_fire_press_time <= 1.5:
                self.missile_fired_flag = True
                print("[INFO] [ASM] IR Anti-Ship Missile FIRED.")

            self.current_state = WeaponState.OFF
            self.was_locked = False

    def tick(self, current_time):
        """Placeholder for periodic IR ticks."""
        pass


class ARH_ASM_Guidance(BaseASMLogic):
    """
    Strict event-driven logic for ARH (Active Radar Homing) missiles.
    Requires a two-stage process: target lock request, followed by a launch command.
    """

    def __init__(self):
        super().__init__()
        self.is_activating = False
        self.activation_time = 0.0
        self.ignore_ocr_until = 0.0

    def reset(self):
        """Resets ARH guidance internal states and timers."""
        super().reset()
        self.is_activating = False
        self.activation_time = 0.0
        self.ignore_ocr_until = 0.0

    def on_fire_press(self, current_time):
        """Processes fire button presses, handling both lock initiation and missile launch."""
        # STAGE 2: Launch (Missile is LOCKED, user presses fire again)
        if self.current_state == WeaponState.LOCKED:
            self.missile_fired_flag = True
            self.current_state = WeaponState.OFF

            # Block OCR for 1.5 seconds to prevent the old 'seeker: on' text
            # from accidentally locking the next missile on the pylon
            self.ignore_ocr_until = current_time + 1.5
            print("[INFO] [ASM] ARH Missile FIRED.")
            return

        # STAGE 1: Lock intent (Missile is OFF, user presses fire for the first time)
        if self.current_state == WeaponState.OFF:
            self.is_activating = True
            self.activation_time = current_time
            print("[INFO] [ASM] ARH Lock requested. Waiting for seeker confirmation...")

    def update_ocr_text(self, text, current_time, last_fire_press_time):
        """Validates lock and launch statuses via OCR parsing."""
        if current_time < self.ignore_ocr_until:
            return

        # Process OCR ONLY if actively waiting for a lock after activation
        if self.is_activating:
            if "seeker: on" in text or "tracking" in text:
                self.current_state = WeaponState.LOCKED
                self.is_activating = False
                print("[INFO] [ASM] ARH Lock CONFIRMED by OCR.")

        # Check for lock loss if the user disables the seeker while locked
        elif self.current_state == WeaponState.LOCKED:
            if "off" in text:
                self.current_state = WeaponState.OFF
                print("[INFO] [ASM] ARH Lock LOST ('off' detected).")

    def tick(self, current_time):
        """Handles timeouts for lock attempts."""
        # Timer check is placed in tick() to ensure it executes even if OCR is silent
        if self.is_activating:
            if current_time - self.activation_time > 2.0:  # 2 second window
                self.is_activating = False
                self.current_state = WeaponState.OFF
                print("[INFO] [ASM] ARH Lock FAILED (Timeout).")


class ASMCombatLogic:
    """
    Controller class responsible for managing ASM guidance strategies and routing commands.
    """

    def __init__(self):
        self.last_fire_press_time = 0.0
        self.guidance_mode = "IR"

        self.strategies = {
            "IR": IR_ASM_Guidance(),
            "ARH": ARH_ASM_Guidance(),
        }

    @property
    def active_strategy(self):
        """Returns the currently active guidance strategy."""
        return self.strategies.get(self.guidance_mode, self.strategies["IR"])

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
        if "ARH" in guidance_list:
            self.guidance_mode = "ARH"
        else:
            self.guidance_mode = "IR"

        print(f"[INFO] [ASM] Guidance mode switched to: {self.guidance_mode}")
        self.reset()

    def update_ocr_text(self, text):
        """Feeds normalized OCR text into the active strategy."""
        text_lower = text.lower() if text else ""
        current_time = time.time()
        self.active_strategy.update_ocr_text(text_lower, current_time, self.last_fire_press_time)

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
        elif state == WeaponState.COOLDOWN:
            ui_color = None
            ui_blink = False

        return {
            "color": ui_color,
            "blink": ui_blink,
            "fired": fired,
        }