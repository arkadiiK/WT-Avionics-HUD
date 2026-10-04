"""
aam_logic.py
------------
Handles the combat logic and state machine for Air-to-Air Missiles (AAM).
Supports Infrared (IR), Radar (SARH/ARH), and Manual (MCLOS/SACLOS) guidance systems.
Includes logic for seeker spool-up times, target tracking, and firing cooldowns.
"""

import time
import config
from core.enums import WeaponState


class BaseGuidance:
    """
    Base class for all missile guidance systems.
    Provides common state management, cooldown logic, and user activation locking.
    """

    def __init__(self):
        self.current_state = WeaponState.OFF
        self.missile_fired_flag = False
        self.cooldown_until = 0.0
        self.awaiting_user_activation = True  # Hard lock until the user presses the weapon activation key

    def reset(self):
        """Resets the guidance system to its default, inactive state."""
        self.current_state = WeaponState.OFF
        self.missile_fired_flag = False
        self.cooldown_until = 0.0
        self.awaiting_user_activation = True

    def on_fire_press(self, current_time):
        """
        Handles the weapon activation/fire key press.

        Args:
            current_time (float): Current system time.

        Returns:
            bool: True if the missile was actually fired, False otherwise (e.g., if only activated).
        """
        # 1. Unlock the weapon if it was waiting for initial user activation
        if self.awaiting_user_activation:
            self.awaiting_user_activation = False
            print("[INFO] [AAM] Weapon activated by user! Listening to OCR...")
            return False

        # 2. Fire the missile if already activated and has an active seeker state
        if self.current_state != WeaponState.OFF:
            if current_time >= getattr(self, 'cooldown_until', 0.0):
                self.missile_fired_flag = True
                self.cooldown_until = current_time + 1.5
                self.current_state = WeaponState.OFF

                # Halt the algorithm for the next missile in the queue until manual reactivation
                self.awaiting_user_activation = True
                print("[INFO] [AAM] Missile fired! Next missile strictly locked until button press.")
                return True

        return False

    def update_ocr_text(self, text, current_time, last_fire_press_time):
        """Processes OCR text from the game's UI to update the seeker state."""
        pass

    def tick(self, current_time):
        """Periodic logic update for timeouts or state transitions."""
        pass


class IRGuidance(BaseGuidance):
    """
    Logic for Infrared (IR) guided Air-to-Air Missiles.
    Reacts to 'tracking', 'searching', and 'seeker' OCR keywords.
    """

    def __init__(self):
        super().__init__()
        self.state_end_time = 0.0

    def reset(self):
        """Resets the IR guidance state machine."""
        super().reset()
        self.state_end_time = 0.0

    def on_fire_press(self, current_time):
        """Processes fire input for IR missiles."""
        if super().on_fire_press(current_time):
            self.state_end_time = 0.0

    def update_ocr_text(self, text, current_time, last_fire_press_time):
        """Updates IR seeker state based on OCR text parsing."""
        if self.awaiting_user_activation:
            self.current_state = WeaponState.OFF
            return

        if "tracking" in text:
            self.current_state = WeaponState.LOCKED
            self.state_end_time = current_time + 40.0
        elif "searching" in text:
            self.current_state = WeaponState.SEARCHING
            self.state_end_time = current_time + 40.0
        elif "seeker: on" in text or "seeker" in text:
            self.current_state = WeaponState.STANDBY
            self.state_end_time = current_time + 40.0
        elif "off" in text:
            if self.current_state == WeaponState.LOCKED:
                if current_time - last_fire_press_time <= 1.5:
                    if current_time >= getattr(self, 'cooldown_until', 0.0):
                        self.missile_fired_flag = True
                        self.cooldown_until = current_time + 1.5
                        self.awaiting_user_activation = True
            self.current_state = WeaponState.OFF
            self.state_end_time = 0.0
        elif "waiting" in text:
            self.current_state = WeaponState.COOLDOWN
            self.state_end_time = 0.0
        elif "seeker" not in text:
            # Handles implicit missile launch when the 'seeker' UI disappears quickly
            if self.current_state == WeaponState.LOCKED:
                if current_time - last_fire_press_time <= 1.0:
                    if current_time >= getattr(self, 'cooldown_until', 0.0):
                        self.missile_fired_flag = True
                        self.cooldown_until = current_time + 1.5
                        self.awaiting_user_activation = True
                    self.current_state = WeaponState.OFF
                    self.state_end_time = 0.0

    def tick(self, current_time):
        """Handles automatic timeout for the IR seeker."""
        if self.state_end_time > 0 and current_time > self.state_end_time:
            self.current_state = WeaponState.OFF
            self.state_end_time = 0.0


class RadarGuidance(BaseGuidance):
    """
    Logic for Radar-guided (SARH/ARH) Air-to-Air Missiles.
    Includes specific delay mechanisms for radar warm-up and launch validation.
    """

    def __init__(self):
        super().__init__()
        self.radar_lock_start_time = 0.0
        self.pending_radar_check_time = 0.0

    def reset(self):
        """Resets the radar guidance state machine."""
        super().reset()
        self.radar_lock_start_time = 0.0
        self.pending_radar_check_time = 0.0

    def on_fire_press(self, current_time):
        """Processes fire input for Radar missiles, managing spool-up delays."""
        was_waiting = self.awaiting_user_activation

        if super().on_fire_press(current_time):
            self.radar_lock_start_time = 0.0
            self.pending_radar_check_time = 0.0
            return

        if was_waiting:
            return

        # Timing algorithm to validate radar lock before allowing launch
        if self.radar_lock_start_time > 0:
            elapsed = current_time - self.radar_lock_start_time
            if elapsed <= 5.3:
                self.current_state = WeaponState.OFF
                self.radar_lock_start_time = 0.0
                self.awaiting_user_activation = True
            elif 5.3 < elapsed <= 20.3:
                self.pending_radar_check_time = current_time

    def update_ocr_text(self, text, current_time, last_fire_press_time):
        """Updates Radar seeker state based on OCR text parsing."""
        if self.awaiting_user_activation:
            self.current_state = WeaponState.OFF
            return

        if "seeker: on" in text or "trk" in text or "lock" in text or "tracking" in text:
            if self.pending_radar_check_time > 0:
                self.pending_radar_check_time = 0.0
                self.radar_lock_start_time = current_time
                self.current_state = WeaponState.LOCKED
            elif self.radar_lock_start_time == 0.0:
                self.radar_lock_start_time = current_time
                self.current_state = WeaponState.LOCKED
        elif "off" in text:
            self.current_state = WeaponState.OFF
            self.radar_lock_start_time = 0.0
            self.pending_radar_check_time = 0.0
            self.awaiting_user_activation = True

    def tick(self, current_time):
        """Manages radar state transitions based on time elapsed since lock."""
        if self.radar_lock_start_time > 0:
            elapsed = current_time - self.radar_lock_start_time
            if 5.3 < elapsed <= 20.3:
                if self.current_state == WeaponState.LOCKED:
                    self.current_state = WeaponState.STANDBY
            if self.pending_radar_check_time > 0:
                wait_elapsed = current_time - self.pending_radar_check_time
                if wait_elapsed > 0.8:
                    if current_time >= getattr(self, 'cooldown_until', 0.0):
                        self.missile_fired_flag = True
                        self.cooldown_until = current_time + 1.5
                        self.awaiting_user_activation = True
                    self.current_state = WeaponState.OFF
                    self.pending_radar_check_time = 0.0
                    self.radar_lock_start_time = 0.0
            if elapsed > 20.3:
                self.current_state = WeaponState.OFF
                self.radar_lock_start_time = 0.0
                self.pending_radar_check_time = 0.0
                self.awaiting_user_activation = True


class ManualGuidance(BaseGuidance):
    """
    Logic for Manual/Line-of-Sight (MCLOS/SACLOS) guided weapons.
    Bypasses seeker logic and allows immediate firing upon cooldown expiration.
    """

    def on_fire_press(self, current_time):
        """Fires the weapon immediately without requiring OCR validation."""
        if current_time >= getattr(self, 'cooldown_until', 0.0):
            self.missile_fired_flag = True
            self.cooldown_until = current_time + 1.5
            self.current_state = WeaponState.OFF


class AAMCombatLogic:
    """
    Controller class that routes AAM combat events to the appropriate guidance strategy.
    """

    def __init__(self):
        self.last_fire_press_time = 0.0
        self.guidance_mode = "IR"
        self.strategies = {
            "IR": IRGuidance(),
            "RADAR": RadarGuidance(),
            "MANUAL": ManualGuidance()
        }

    @property
    def active_strategy(self):
        """Returns the currently active guidance strategy object."""
        return self.strategies.get(self.guidance_mode, self.strategies["IR"])

    def on_fire_press(self, current_time):
        """Routes the fire command to the active strategy."""
        self.last_fire_press_time = current_time
        self.active_strategy.on_fire_press(current_time)

    def reset(self):
        """Resets the currently active strategy."""
        self.active_strategy.reset()

    def set_guidance(self, guidance_list):
        """
        Determines and sets the correct guidance mode based on the weapon's capabilities.

        Args:
            guidance_list (list): A list of string tags representing the weapon's guidance types.
        """
        if "SARH" in guidance_list or "ARH" in guidance_list:
            self.guidance_mode = "RADAR"
        elif "MCLOS" in guidance_list or "SACLOS" in guidance_list:
            self.guidance_mode = "MANUAL"
        else:
            self.guidance_mode = "IR"
        self.reset()

    def update_ocr_text(self, text):
        """Passes OCR data to the active strategy for processing."""
        text_lower = text.lower() if text else ""
        current_time = time.time()
        self.active_strategy.update_ocr_text(text_lower, current_time, self.last_fire_press_time)

    def tick(self):
        """
        Executes a logic tick and formats the UI state for the HUD.

        Returns:
            dict: Contains UI color, blinking state, and whether a missile was just fired.
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