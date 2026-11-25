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
    Enforces a sequential state machine:
    Activation -> STANDBY ('seeker:on') -> SEARCHING ('seeker: searching') -> LOCKED ('seeker:tracking') -> Fire.
    Resets cleanly on 'seeker:off' (after seeker activation) or per-stage timeout without triggering a launch.
    """

    STAGE_TIMEOUT = 40.0  # Maximum duration (in seconds) allowed for a single stage

    def __init__(self):
        super().__init__()
        self.state_end_time = 0.0

    def reset(self):
        """Resets the IR guidance state machine to its default inactive state."""
        super().reset()
        self.state_end_time = 0.0

    def on_fire_press(self, current_time):
        """
        Handles activation and launch key presses for IR missiles.
        Unlocks OCR listening on first press; fires only when state is LOCKED.
        """
        # 1. Activate seeker and start waiting for 'seeker:on'
        if self.awaiting_user_activation:
            self.awaiting_user_activation = False
            self.current_state = WeaponState.OFF
            self.state_end_time = current_time + self.STAGE_TIMEOUT
            print("[INFO] [AAM-IR] Weapon activated by user! Listening to OCR...")
            return False

        # 2. Fire missile ONLY after reaching LOCKED state
        if self.current_state == WeaponState.LOCKED:
            if current_time >= getattr(self, 'cooldown_until', 0.0):
                self.missile_fired_flag = True
                self.cooldown_until = current_time + 1.5
                self.current_state = WeaponState.OFF
                self.state_end_time = 0.0
                self.awaiting_user_activation = True
                print("[INFO] [AAM-IR] Missile fired! Next missile locked until button press.")
                return True

        return False

    def update_ocr_text(self, text, current_time, last_fire_press_time):
        """Updates IR seeker state sequentially based on OCR text parsing."""
        if self.awaiting_user_activation:
            self.current_state = WeaponState.OFF
            return

        # Normalize spacing after colons to match both 'seeker:on' and 'seeker: on'
        normalized_text = text.replace(": ", ":")

        # Interruption check: reset only if the seeker was already active and then turned off.
        # Ignoring 'seeker:off' while still in WeaponState.OFF prevents stale HUD frames
        # right after missile launch from canceling the new activation press.
        if "seeker:off" in normalized_text:
            if self.current_state != WeaponState.OFF:
                print("[INFO] [AAM-IR] Seeker turned off ('seeker:off'). Returning to default state.")
                self.reset()
            return

        # Stage 1: Seeker:on -> STANDBY
        if "seeker:on" in normalized_text:
            if self.current_state == WeaponState.OFF:
                self.current_state = WeaponState.STANDBY
                self.state_end_time = current_time + self.STAGE_TIMEOUT

        # Stage 2: Seeker: Searching -> SEARCHING
        elif "seeker:searching" in normalized_text:
            if self.current_state in (WeaponState.OFF, WeaponState.STANDBY):
                self.current_state = WeaponState.SEARCHING
                self.state_end_time = current_time + self.STAGE_TIMEOUT

        # Stage 3: Seeker:tracking -> LOCKED
        elif "seeker:tracking" in normalized_text:
            if self.current_state in (WeaponState.OFF, WeaponState.STANDBY, WeaponState.SEARCHING):
                self.current_state = WeaponState.LOCKED
                self.state_end_time = current_time + self.STAGE_TIMEOUT

    def tick(self, current_time):
        """Handles automatic timeout if any single stage takes too long."""
        if not self.awaiting_user_activation and self.state_end_time > 0.0:
            if current_time > self.state_end_time:
                print("[INFO] [AAM-IR] Stage timeout exceeded. Resetting to default state.")
                self.reset()


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
