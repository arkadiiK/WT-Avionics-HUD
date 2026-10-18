"""
overlay.py
----------
Main controller for the HUD overlay.
Manages the transparent, frameless window, coordinates telemetry data updates,
handles weapon logic state machines, and drives the central rendering loop.
"""

import ctypes
import difflib
import json
import os
import sys
import time

from PySide6.QtCore import QPointF, Qt, QTimer, Slot
from PySide6.QtGui import QCloseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QApplication, QWidget

import config
from core.input_manager import InputManager
from core.screen_reader import ScreenReader
from core.telemetry import TelemetryWorker
from core.weapon_manager import WeaponManager
from core.weapons_logic.aam_logic import AAMCombatLogic
from core.weapons_logic.agm_logic import AGMCombatLogic
from core.weapons_logic.arm_logic import ARMCombatLogic
from core.weapons_logic.asm_logic import ASMCombatLogic
from core.weapons_logic.gbu_logic import GBUCombatLogic
from core.weapons_logic.unguided_logic import UnguidedCombatLogic
from gui.flaps_indicator import FlapsIndicator
from gui.instruments import InstrumentRenderer
from gui.sms_indicator import SMSIndicator


class OverlayWidget(QWidget):
    """
    Transparent Qt widget that acts as the primary canvas for the HUD.
    Operates without focusing to avoid interfering with game input.
    """

    SETTINGS_FILENAME = "launcher_settings.json"
    MIN_SCALE = 50
    MAX_SCALE = 150
    DEFAULT_SCALE = 100

    def __init__(self) -> None:
        super().__init__()
        self.user32 = ctypes.windll.user32

        # Server state and Alt-Tab grace timer
        self.server_active = False
        self.signal_lost_time = 0.0
        self.should_draw = False

        self.telemetry_scale, self.sms_scale = self._load_scale_settings()

        self.renderer = InstrumentRenderer()
        self._setup_window_properties()

        self.aircraft_db = self._load_parsed_db()
        self.current_plane_id = ""
        self.current_plane_tag = None
        self.active_loadout = {}
        self.current_plane_config = {}
        self.cached_flap_stages = []

        self.flaps_ui = FlapsIndicator(self)
        self._apply_flaps_transform()

        self.sms_renderer = SMSIndicator()
        self.weapon_manager = WeaponManager()

        self.input_manager = InputManager()
        self.prev_fire_state = False
        self.prev_cycle_state = False

        # Weapon combat logic modules
        self.aam_logic = AAMCombatLogic()
        self.agm_logic = AGMCombatLogic()
        self.asm_logic = ASMCombatLogic()
        self.unguided_logic = UnguidedCombatLogic()
        self.gbu_logic = GBUCombatLogic()
        self.arm_logic = ARMCombatLogic()

        self.active_logic = self.aam_logic
        self.last_ocr_text = ""

        # Screen OCR reader
        self.screen_reader = ScreenReader()
        self.screen_reader.text_read.connect(self._on_seeker_text_received)
        self.screen_reader.start()

        self.seeker_ui_state = {
            "color": None,
            "blink": False,
            "fired": False,
        }
        self.last_selected_weapon = None

        # Telemetry (target values)
        self.target_airspeed = None
        self.target_altitude = None
        self.target_tas = None
        self.target_radio_alt = None
        self.target_trend_spd = 0.0
        self.target_trend_alt = 0.0
        self.target_aoa = None
        self.target_g_force = None
        self.target_mach = None
        self.target_throttle_pct = 0.0
        self.is_afterburner = False

        # Telemetry (displayed values for smoothing)
        self.displayed_airspeed = None
        self.displayed_altitude = None
        self.displayed_tas = None
        self.displayed_radio_alt = None
        self.displayed_trend_spd = 0.0
        self.displayed_trend_alt = 0.0
        self.displayed_aoa = None
        self.displayed_g_force = None
        self.displayed_mach = None
        self.displayed_throttle_pct = 0.0

        # Aircraft state
        self.ammo_internal = None
        self.fuel_mass = None
        self.fuel_time_sec = 0.0
        self.flares = None
        self.chaff = None
        self.target_gear = 0.0
        self.target_airbrake = 0.0
        self.target_flaps = 0.0

        self.is_gear_broken = False
        self.gear_warning_frames = 0
        self.is_flaps_broken = False
        self.flaps_warning_frames = 0

        # UI animations
        self.blink_state = True
        self.blink_counter = 0
        self.cycle_counter = 0
        self.warning_cycle_index = 0

        self.win32_check_counter = 0
        self.is_wt_foreground = False
        self.game_was_found = False
        self.game_missing_ticks = 0

        self._setup_data_integration()

        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self._game_loop)
        self.render_timer.start(16)

    def _get_base_dir(self) -> str:
        """Resolve the base directory of the project."""
        base_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        if not os.path.exists(os.path.join(base_dir, "data")):
            base_dir = os.path.dirname(os.path.abspath(__file__))
        return base_dir

    def _load_scale_settings(self) -> tuple[float, float]:
        """Load telemetry and SMS scale factors from launcher settings."""
        settings_path = os.path.join(
            self._get_base_dir(), "data", self.SETTINGS_FILENAME
        )
        if not os.path.exists(settings_path):
            return 1.0, 1.0

        try:
            with open(settings_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            tel_pct = int(data.get("telemetry_scale", self.DEFAULT_SCALE))
            sms_pct = int(data.get("sms_scale", self.DEFAULT_SCALE))

            tel_pct = max(self.MIN_SCALE, min(tel_pct, self.MAX_SCALE))
            sms_pct = max(self.MIN_SCALE, min(sms_pct, self.MAX_SCALE))
            return tel_pct / 100.0, sms_pct / 100.0
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"[WARNING] [OVERLAY] Failed to load HUD scale: {exc}")
            return 1.0, 1.0

    def _apply_flaps_transform(self) -> None:
        """Position and scale the flaps widget relative to telemetry anchor."""
        anchor_x = config.X_LEFT_TAPE - config.TAPE_WIDTH
        anchor_y = config.Y_CENTER - (config.TAPE_HEIGHT // 2) - 35

        base_flaps_x = config.X_RIGHT_TAPE + 120
        base_flaps_y = config.Y_CENTER - 190

        scaled_x = int(
            anchor_x + (base_flaps_x - anchor_x) * self.telemetry_scale
        )
        scaled_y = int(
            anchor_y + (base_flaps_y - anchor_y) * self.telemetry_scale
        )

        self.flaps_ui.set_scale(self.telemetry_scale)
        self.flaps_ui.move(scaled_x, scaled_y)

    def _setup_window_properties(self) -> None:
        """Configure widget to be transparent, frameless, and click-through."""
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

    def _setup_data_integration(self) -> None:
        """Initialize background telemetry worker and connect its signals."""
        self.telemetry_worker = TelemetryWorker()
        self.telemetry_worker.data_received.connect(self.update_data)
        self.telemetry_worker.start()

    def _load_parsed_db(self) -> dict:
        """Load the aircraft database from the JSON file."""
        try:
            is_frozen = getattr(sys, "frozen", False)
            base_dir = (
                sys._MEIPASS if is_frozen else self._get_base_dir()
            )
            db_path = os.path.join(base_dir, "data", "aircraft_db.json")
            with open(db_path, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception as exc:
            print(f"[ERROR] [OVERLAY] Loading database failed: {exc}")
            return {}

    def _fetch_main_preset(self, plane_tag: str) -> dict:
        """Retrieve the active user preset loadout for the current aircraft."""
        presets_path = os.path.join(
            self._get_base_dir(), "data", "user_presets.json"
        )

        if not os.path.exists(presets_path):
            return {}

        try:
            with open(presets_path, "r", encoding="utf-8") as file:
                presets = json.load(file)
            plane_data = presets.get(plane_tag, {})
            main_preset_name = plane_data.get("_main")

            if main_preset_name and main_preset_name in plane_data:
                raw_pylons = plane_data[main_preset_name].get("pylons", {})
                active_weapons = {
                    str(idx): weapon
                    for idx, weapon in raw_pylons.items()
                    if weapon not in ("< Empty >", "< N/A >")
                }
                return active_weapons
        except Exception as exc:
            print(
                f"[WARNING] [OVERLAY] Failed to parse "
                f"user_presets.json: {exc}"
            )

        return {}

    @Slot(str)
    def _on_seeker_text_received(self, text: str) -> None:
        """Receive OCR text and route it to the active weapon logic."""
        self.last_ocr_text = text
        self.active_logic.update_ocr_text(text)

    @Slot(dict)
    def update_data(self, data: dict) -> None:
        """Receive parsed telemetry data and update target states."""
        if not data.get("valid", False):
            if self.server_active:
                if self.signal_lost_time == 0.0:
                    self.signal_lost_time = time.time()
                elif time.time() - self.signal_lost_time > 3.0:
                    self.server_active = False
                    self.flaps_ui.hide()
            return

        self.signal_lost_time = 0.0

        just_spawned = not self.server_active
        self.server_active = True

        self.target_airspeed = data.get("spd")
        self.target_altitude = data.get("alt")
        self.target_tas = data.get("tas")
        self.target_radio_alt = data.get("rad_alt")
        self.target_trend_spd = data.get("trend_spd", 0.0)
        self.target_trend_alt = data.get("trend_alt", 0.0)
        self.target_aoa = data.get("aoa")
        self.target_g_force = data.get("g_force")
        self.target_mach = data.get("mach")
        self.target_throttle_pct = data.get("throttle_pct", 0.0)
        self.is_afterburner = data.get("is_afterburner", False)
        self.ammo_internal = data.get("ammo_internal")
        self.fuel_mass = data.get("fuel_mass")
        self.fuel_time_sec = data.get("fuel_time_sec", 0.0)
        self.flares = data.get("flares")
        self.chaff = data.get("chaff")

        self.target_airbrake = data.get(
            "airbrake", data.get("airbrake, %", 0.0)
        )
        self.target_gear = data.get("gear", 0.0)
        self.target_flaps = data.get("flaps", 0.0)
        active_plane_id = data.get("type", "")

        if (
                active_plane_id != self.current_plane_id or just_spawned
        ) and active_plane_id:
            self.current_plane_id = active_plane_id
            self.current_plane_tag = active_plane_id
            self.active_loadout = self._fetch_main_preset(
                self.current_plane_tag
            )
            self.weapon_manager.update_loadout(
                self.active_loadout, is_spawn=True
            )

            self.aam_logic.reset()
            self.agm_logic.reset()
            self.asm_logic.reset()
            self.unguided_logic.reset()
            self.gbu_logic.reset()
            self.arm_logic.reset()
            self.last_selected_weapon = None

            found_config = self.aircraft_db.get(self.current_plane_id)
            if not found_config:
                norm_api = self.current_plane_id.replace("-", "_").lower()
                for db_key, db_config in self.aircraft_db.items():
                    if db_key.replace("-", "_").lower() == norm_api:
                        found_config = db_config
                        break

            if not found_config:
                db_keys = list(self.aircraft_db.keys())
                matches = difflib.get_close_matches(
                    self.current_plane_id, db_keys, n=1, cutoff=0.6
                )
                if matches:
                    found_config = self.aircraft_db[matches[0]]

            self.current_plane_config = found_config or {}
            self.cached_flap_stages = []

            if "flaps_config" in self.current_plane_config:
                flaps_cfg = self.current_plane_config["flaps_config"]
                self.cached_flap_stages = sorted(
                    [int(k) for k in flaps_cfg.keys() if int(k) > 0]
                )

        if (
                hasattr(self, "current_plane_config")
                and "flaps_config" in self.current_plane_config
        ):
            self.flaps_ui.update_data(
                self.target_flaps,
                self.current_plane_config["flaps_config"],
            )
        else:
            self.flaps_ui.hide()

    def _safe_lerp(
            self,
            current: float | None,
            target: float | None,
            factor: float,
    ) -> float | None:
        """Perform linear interpolation with None-safety for UI smoothing."""
        if target is None:
            return None
        if current is None:
            return target
        return current + (target - current) * factor

    def _get_flap_vne(self) -> float | None:
        """Retrieve the Velocity Never Exceed for deployed flap stage."""
        if (
                not hasattr(self, "cached_flap_stages")
                or not self.cached_flap_stages
                or self.target_flaps < 0.01
        ):
            return None

        current_pct = self.target_flaps * 100
        flaps_cfg = self.current_plane_config.get("flaps_config", {})
        active_limit = None

        for stage in self.cached_flap_stages:
            limit = flaps_cfg[str(stage)].get("vne")
            if limit:
                active_limit = limit
            if current_pct <= stage:
                break

        return active_limit

    def _get_active_warnings(self) -> dict:
        """Analyze telemetry to generate warnings, cautions, and advisories."""
        warnings = {"warning": None, "caution": None, "advisory": None}

        if (
                getattr(self, "current_plane_config", None) is None
                or self.target_airspeed is None
        ):
            return warnings

        spd = self.target_airspeed
        vne = self.current_plane_config.get("vne")
        gear_vne = self.current_plane_config.get("gear_vne")
        flap_limit = self._get_flap_vne()

        active_warnings = []
        if vne and spd >= vne:
            active_warnings.append("OVERSPEED")
        if flap_limit and spd >= flap_limit and not self.is_flaps_broken:
            active_warnings.append("FLAP LIMIT")
        if (
                gear_vne
                and self.target_gear > 0.01
                and spd >= gear_vne
                and not self.is_gear_broken
        ):
            active_warnings.append("GEAR LIMIT")

        if active_warnings:
            idx = self.warning_cycle_index % len(active_warnings)
            warnings["warning"] = active_warnings[idx]

        active_cautions = []
        if "OVERSPEED" not in active_warnings:
            if vne and vne * 0.90 <= spd < vne:
                active_cautions.append("CHK SPD")
            if (
                    flap_limit
                    and flap_limit * 0.90 <= spd < flap_limit
                    and not self.is_flaps_broken
                    and "FLAP LIMIT" not in active_warnings
            ):
                active_cautions.append("CHK FLAP")
            if (
                    gear_vne
                    and self.target_gear > 0.01
                    and gear_vne * 0.90 <= spd < gear_vne
                    and not self.is_gear_broken
                    and "GEAR LIMIT" not in active_warnings
            ):
                active_cautions.append("CHK GEAR")

        if active_cautions:
            idx = self.warning_cycle_index % len(active_cautions)
            warnings["caution"] = active_cautions[idx]

        active_advisories = []
        if self.target_gear > 0.01 and not self.is_gear_broken:
            if (
                    "GEAR LIMIT" not in active_warnings
                    and "CHK GEAR" not in active_cautions
            ):
                active_advisories.append("GEAR DOWN")

        airbrake_active = False
        if isinstance(self.target_airbrake, bool):
            airbrake_active = self.target_airbrake
        elif (
                isinstance(self.target_airbrake, (int, float))
                and self.target_airbrake > 0.01
        ):
            airbrake_active = True

        if airbrake_active:
            active_advisories.append("AIRBRAKE")

        if active_advisories:
            idx = self.warning_cycle_index % len(active_advisories)
            warnings["advisory"] = active_advisories[idx]

        return warnings

    def _game_loop(self) -> None:
        """
        Main 16ms execution loop.
        Handles input tracking, weapon logic ticks, UI lerping, and game state.
        """
        current_time = time.time()

        cycle_pressed = self.input_manager.is_action_pressed(
            "switch_secondary_weapon"
        )
        if cycle_pressed and not self.prev_cycle_state:
            self.weapon_manager.cycle_flag = True
        self.prev_cycle_state = cycle_pressed

        fire_pressed = self.input_manager.is_action_pressed(
            "fire_secondary_weapon"
        )
        if fire_pressed and not self.prev_fire_state:
            self.active_logic.on_fire_press(current_time)
            self.active_logic.update_ocr_text(self.last_ocr_text)

        self.prev_fire_state = fire_pressed

        if self.weapon_manager.cycle_flag:
            self.aam_logic.reset()
            self.agm_logic.reset()
            self.asm_logic.reset()
            self.unguided_logic.reset()
            self.gbu_logic.reset()
            self.arm_logic.reset()

        self.weapon_manager.process_cycle()
        current_weapon = self.weapon_manager.get_selected_weapon()

        if current_weapon != getattr(self, "last_selected_weapon", None):
            self.aam_logic.reset()
            self.agm_logic.reset()
            self.asm_logic.reset()
            self.unguided_logic.reset()
            self.gbu_logic.reset()
            self.arm_logic.reset()

            category, guidance_list = (
                self.weapon_manager.get_weapon_category_and_guidance()
            )

            if category == "AAM":
                self.active_logic = self.aam_logic
            elif category == "AGM":
                self.active_logic = self.agm_logic
            elif category in ["ASM", "ASHM"]:
                self.active_logic = self.asm_logic
            elif category == "GBU":
                self.active_logic = self.gbu_logic
            elif category == "UNGUIDED":
                self.active_logic = self.unguided_logic
            elif category == "ARM":
                self.active_logic = self.arm_logic
            else:
                self.active_logic = self.aam_logic

            self.active_logic.set_guidance(guidance_list)
            self.last_selected_weapon = current_weapon

        seeker_state = self.active_logic.tick()
        self.seeker_ui_state = seeker_state

        if seeker_state.get("fired"):
            self.weapon_manager.fire_current_weapon()
            self.active_logic.reset()

        # Game state tracking (auto-termination & focus)
        self.win32_check_counter += 1
        if self.win32_check_counter >= 15:
            self.win32_check_counter = 0

            game_hwnd = self.user32.FindWindowW("DagorWClass", None)
            is_game_running = game_hwnd != 0
            fg_hwnd = self.user32.GetForegroundWindow()
            self.is_wt_foreground = False

            if fg_hwnd:
                if fg_hwnd == game_hwnd:
                    self.is_wt_foreground = True
                else:
                    pid = ctypes.c_ulong()
                    self.user32.GetWindowThreadProcessId(
                        fg_hwnd, ctypes.byref(pid)
                    )
                    kernel32 = ctypes.windll.kernel32
                    h_process = kernel32.OpenProcess(0x1000, False, pid)
                    if h_process:
                        exe_path = ctypes.create_unicode_buffer(260)
                        size = ctypes.c_ulong(260)
                        if kernel32.QueryFullProcessImageNameW(
                                h_process, 0, exe_path, ctypes.byref(size)
                        ):
                            if "aces.exe" in exe_path.value.lower():
                                self.is_wt_foreground = True
                                is_game_running = True
                        kernel32.CloseHandle(h_process)

            if is_game_running:
                self.game_was_found = True
                self.game_missing_ticks = 0
            elif self.game_was_found:
                self.game_missing_ticks += 1
                if self.game_missing_ticks >= 5:
                    print(
                        "[INFO] [OVERLAY] War Thunder closed. "
                        "Auto-terminating HUD."
                    )
                    QApplication.quit()

        if (
                not self.is_wt_foreground
                or not self.server_active
                or self.signal_lost_time > 0.0
        ):
            self.should_draw = False
            self.flaps_ui.allow_draw = False
            self.flaps_ui.update()
            self.update()
            return

        self.should_draw = True
        self.flaps_ui.allow_draw = True
        self.raise_()

        if (
                getattr(self, "current_plane_config", None)
                and self.target_airspeed is not None
        ):
            gear_vne = self.current_plane_config.get("gear_vne")
            if self.target_gear < 0.01:
                self.is_gear_broken = False
                self.gear_warning_frames = 0
            elif gear_vne and self.target_gear > 0.01:
                if self.target_airspeed >= gear_vne:
                    if not self.is_gear_broken:
                        self.gear_warning_frames += 1
                        if self.gear_warning_frames >= 600:
                            self.is_gear_broken = True
                else:
                    self.gear_warning_frames = 0

            flap_limit = self._get_flap_vne()
            if self.target_flaps < 0.01:
                self.is_flaps_broken = False
                self.flaps_warning_frames = 0
            elif flap_limit:
                if self.target_airspeed >= flap_limit:
                    if not self.is_flaps_broken:
                        self.flaps_warning_frames += 1
                        if self.flaps_warning_frames >= 600:
                            self.is_flaps_broken = True
                else:
                    self.flaps_warning_frames = 0

        self.displayed_airspeed = self._safe_lerp(
            self.displayed_airspeed, self.target_airspeed, 0.15
        )
        self.displayed_altitude = self._safe_lerp(
            self.displayed_altitude, self.target_altitude, 0.15
        )
        self.displayed_tas = self._safe_lerp(
            self.displayed_tas, self.target_tas, 0.15
        )

        if (
                self.target_radio_alt is not None
                and self.target_radio_alt <= 50.0
        ):
            self.displayed_radio_alt = self._safe_lerp(
                self.displayed_radio_alt, self.target_radio_alt, 0.2
            )
        else:
            self.displayed_radio_alt = None

        self.displayed_aoa = self._safe_lerp(
            self.displayed_aoa, self.target_aoa, 0.2
        )
        self.displayed_g_force = self._safe_lerp(
            self.displayed_g_force, self.target_g_force, 0.25
        )
        self.displayed_mach = self._safe_lerp(
            self.displayed_mach, self.target_mach, 0.2
        )
        self.displayed_trend_spd += (
                                            self.target_trend_spd - self.displayed_trend_spd
                                    ) * 0.1
        self.displayed_trend_alt += (
                                            self.target_trend_alt - self.displayed_trend_alt
                                    ) * 0.1
        self.displayed_throttle_pct = self._safe_lerp(
            self.displayed_throttle_pct, self.target_throttle_pct, 0.2
        )

        if (
                abs(self.displayed_throttle_pct - self.target_throttle_pct)
                < 0.5
        ):
            self.displayed_throttle_pct = self.target_throttle_pct
        if (
                not self.is_afterburner
                and 99.0 <= self.displayed_throttle_pct <= 100.0
        ):
            self.displayed_throttle_pct = 100.0

        self.blink_counter += 1
        if self.blink_counter >= 15:
            self.blink_state = not self.blink_state
            self.blink_counter = 0

        self.cycle_counter += 1
        if self.cycle_counter >= 120:
            self.warning_cycle_index += 1
            self.cycle_counter = 0

        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Render the scaled HUD components onto the transparent widget."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Source
        )
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver
        )

        if not self.should_draw:
            painter.end()
            return

        # =========================================================
        # 1. TELEMETRY RENDERING (SCALED FROM TOP-LEFT ANCHOR)
        # =========================================================
        tel_anchor_x = float(config.X_LEFT_TAPE - config.TAPE_WIDTH)
        tel_anchor_y = float(
            config.Y_CENTER - (config.TAPE_HEIGHT // 2) - 35
        )

        painter.save()
        painter.translate(QPointF(tel_anchor_x, tel_anchor_y))
        painter.scale(self.telemetry_scale, self.telemetry_scale)
        painter.translate(QPointF(-tel_anchor_x, -tel_anchor_y))

        painter.setFont(self.renderer.main_font)

        self.renderer.draw_tape(
            painter,
            config.X_LEFT_TAPE,
            config.Y_CENTER,
            config.TAPE_HEIGHT,
            self.displayed_airspeed,
            self.displayed_trend_spd,
            True,
            config.STEP_MAIN_SPD,
            config.STEP_MINOR_SPD,
            config.SCALE_SPD,
            config.TREND_SCALE_SPD,
        )
        self.renderer.draw_tape(
            painter,
            config.X_RIGHT_TAPE,
            config.Y_CENTER,
            config.TAPE_HEIGHT,
            self.displayed_altitude,
            self.displayed_trend_alt,
            False,
            config.STEP_MAIN_ALT,
            config.STEP_MINOR_ALT,
            config.SCALE_ALT,
            config.TREND_SCALE_ALT,
        )

        warnings_data = self._get_active_warnings()
        self.renderer.draw_central_warning_box(
            painter, warnings_data, self.blink_state
        )

        is_stalling = False
        force_solid = False
        if (
                self.target_aoa is not None
                and self.target_airspeed is not None
        ):
            if self.target_aoa >= 22.0 or self.target_aoa <= -30.0:
                is_stalling = True
                if self.target_airspeed >= 300.0:
                    force_solid = True
            if self.target_airspeed < 50.0:
                is_stalling = False

        active_blink_state = True if force_solid else self.blink_state
        self.renderer.draw_stall_warning(
            painter, is_stalling, active_blink_state
        )

        if getattr(self, "current_plane_config", None):
            has_ab = self.current_plane_config.get(
                "has_afterburner", False
            )
            has_wep = self.current_plane_config.get("has_wep", False)
            self.renderer.draw_throttle_bar(
                painter,
                self.displayed_throttle_pct,
                self.is_afterburner,
                has_ab,
                has_wep,
            )

        self.renderer.draw_g_meter(painter, self.displayed_g_force)
        self.renderer.draw_mach_indicator(painter, self.displayed_mach)
        self.renderer.draw_aoa_indexer(painter, self.displayed_aoa)
        self.renderer.draw_tas_indicator(painter, self.displayed_tas)

        if self.displayed_radio_alt is not None:
            self.renderer.draw_rad_alt_indicator(
                painter, self.displayed_radio_alt
            )

        if self.ammo_internal is not None:
            self.renderer.draw_weapon_indicators(
                painter, self.ammo_internal
            )

        painter.restore()

        # =========================================================
        # 2. SMS PANEL RENDERING (SCALED FROM TOP-RIGHT ANCHOR)
        # =========================================================
        selected_weapon_clean = self.weapon_manager.get_selected_weapon()
        sms_x = float(self.rect().width() - 320)
        sms_y = float(self.rect().height() / 2 - 300)

        sms_anchor_x = sms_x + 265.0
        sms_anchor_y = sms_y - 75.0

        painter.save()
        painter.translate(QPointF(sms_anchor_x, sms_anchor_y))
        painter.scale(self.sms_scale, self.sms_scale)
        painter.translate(QPointF(-sms_anchor_x, -sms_anchor_y))

        active_pylons = self.weapon_manager.get_active_pylons(
            selected_weapon_clean
        )

        try:
            try:
                self.sms_renderer.draw(
                    painter,
                    sms_x,
                    sms_y,
                    self.weapon_manager.active_loadout,
                    selected_weapon_clean,
                    self.seeker_ui_state,
                    self.blink_state,
                    active_pylons,
                    self.fuel_mass,
                    self.fuel_time_sec,
                    self.flares,
                    self.chaff,
                )
            except TypeError:
                self.sms_renderer.draw(
                    painter,
                    sms_x,
                    sms_y,
                    self.weapon_manager.active_loadout,
                    selected_weapon_clean,
                    self.seeker_ui_state,
                    self.blink_state,
                    None,
                    self.fuel_mass,
                    self.fuel_time_sec,
                    self.flares,
                    self.chaff,
                )
        except Exception as exc:
            print(f"[ERROR] [OVERLAY] sms_indicator.py crashed! {exc}")

        painter.restore()
        painter.end()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Terminate background threads and keyboard hooks upon exit."""
        try:
            import keyboard

            keyboard.unhook_all()
        except Exception:
            pass

        if hasattr(self, "telemetry_worker"):
            self.telemetry_worker.stop()
        if hasattr(self, "screen_reader"):
            self.screen_reader.stop()

        super().closeEvent(event)


def run_overlay() -> None:
    """Initialize the QApplication and execute OverlayWidget standalone."""
    import signal

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    hud = OverlayWidget()
    hud.showFullScreen()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_overlay()
