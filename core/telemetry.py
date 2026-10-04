"""
telemetry.py
------------
Core background worker for fetching and parsing real-time telemetry from the War Thunder local API.
Handles HTTP requests, advanced fuel consumption calculations using linear regression,
and simulates weapon logic (gun spool-up, cooldowns, ammo counters) in a separate thread.
"""

import time
import requests
import json
import os
import sys
import threading
import re
from collections import deque
from PySide6.QtCore import QThread, Signal

import config
from core.input_manager import InputManager


class TelemetryWorker(QThread):
    """
    Background thread that polls the local game API (127.0.0.1:8111) for telemetry.
    Emits a parsed dictionary of flight and weapon data via Qt Signals.
    """
    data_received = Signal(dict)

    def __init__(self):
        super().__init__()
        self._is_running = True
        self.session = requests.Session()

        self.history_spd = deque()
        self.history_alt = deque()
        self.history_fuel = deque()
        self.smoothed_fuel_time = 0.0  # Variable for smoothing fuel time

        base_dir = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

        try:
            db_path = os.path.join(base_dir, 'data', 'aircraft_db.json')
            with open(db_path, "r", encoding="utf-8") as f:
                self.aircraft_db = json.load(f)
        except Exception as e:
            print(f"[ERROR] [TELEMETRY] Failed to load aircraft_db: {e}")
            self.aircraft_db = {}

        try:
            wpn_path = os.path.join(base_dir, 'data', 'weapons_db.json')
            with open(wpn_path, "r", encoding="utf-8") as f:
                self.weapons_db = json.load(f)
        except Exception as e:
            print(f"[ERROR] [TELEMETRY] Failed to load weapons.json: {e}")
            self.weapons_db = {}

        self.input_manager = InputManager()

        self.weapon_lock = threading.Lock()
        self.current_plane_config = {}
        self.current_plane_tag = None
        self.active_loadout = {}
        self.ammo_state = []
        self.gun_charge = 0.0

        self.preset_flares = None
        self.preset_chaff = None
        self.preset_flare_step = None
        self.preset_chaff_step = None

        self.current_flares = None
        self.current_chaff = None

        self.flare_step = 1
        self.chaff_step = 1

        self.weapon_thread_running = True
        self.weapon_thread = threading.Thread(target=self._weapon_logic_loop, daemon=True)
        self.weapon_thread.start()

    def _fetch_main_preset(self, plane_tag):
        """
        Retrieves the main user preset for a given aircraft tag.

        Args:
            plane_tag (str): The internal ID of the aircraft.

        Returns:
            dict: Active weapons loadout mapped by pylon index.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        presets_path = os.path.join(base_dir, "data", "user_presets.json")

        if not os.path.exists(presets_path):
            self.preset_flares = None
            self.preset_chaff = None
            self.preset_flare_step = None
            self.preset_chaff_step = None
            return {}

        try:
            with open(presets_path, "r", encoding="utf-8") as f:
                presets = json.load(f)

            plane_data = presets.get(plane_tag, {})
            main_preset_name = plane_data.get("_main")

            if main_preset_name and main_preset_name in plane_data:
                preset_data = plane_data[main_preset_name]

                self.preset_flares = preset_data.get("flares")
                self.preset_chaff = preset_data.get("chaff")
                self.preset_flare_step = preset_data.get("flare_step")
                self.preset_chaff_step = preset_data.get("chaff_step")

                raw_pylons = preset_data.get("pylons", {})
                active_weapons = {
                    str(idx): weapon for idx, weapon in raw_pylons.items()
                    if weapon not in ("< Empty >", "< N/A >")
                }
                return active_weapons
        except Exception as e:
            print(f"[WARNING] [TELEMETRY] Failed to parse user_presets.json: {e}")

        self.preset_flares = None
        self.preset_chaff = None
        self.preset_flare_step = None
        self.preset_chaff_step = None
        return {}

    def _get_all_guns(self, config_dict):
        """
        Combines internal guns and equipped gunpods into a single list.

        Args:
            config_dict (dict): The aircraft's configuration dictionary.

        Returns:
            list: A list of dictionaries detailing all equipped guns.
        """
        guns = []

        internal = config_dict.get("internal_gun", [])
        if isinstance(internal, dict):
            internal = [internal]
        guns.extend(internal)

        gunpods = config_dict.get("gunpod_stats", [])
        if isinstance(gunpods, dict):
            gunpods = [gunpods]

        loadout_weapons = [str(w).lower() for w in self.active_loadout.values()]

        for gp in gunpods:
            gp_copy = dict(gp)
            gun_name = gp_copy.get("gun", gp_copy.get("name", ""))

            is_equipped = False
            total_multiplier = 0

            for w in loadout_weapons:
                if gun_name.lower() in w:
                    is_equipped = True
                    match = re.search(r'x(\d+)', w)
                    if match:
                        total_multiplier += int(match.group(1))
                    else:
                        total_multiplier += 1

            if is_equipped:
                if "gun" in gp_copy and "name" not in gp_copy:
                    gp_copy["name"] = gp_copy.pop("gun")

                if total_multiplier > 1 and "max_ammo" in gp_copy:
                    gp_copy["max_ammo"] = float(gp_copy["max_ammo"]) * total_multiplier

                guns.append(gp_copy)

        return guns

    def _get_gun_db_data(self, gun_name):
        """Fetches detailed gun statistics from the weapons database."""
        classes = self.weapons_db.get("WEAPON_CLASSES", {})

        data = classes.get("INTERNAL_GUN", {}).get(gun_name)
        if data:
            return data

        data = classes.get("GUN_PODS", {}).get(gun_name)
        if data:
            return data

        for cat_name, cat_data in classes.items():
            if isinstance(cat_data, dict) and gun_name in cat_data:
                return cat_data[gun_name]

        return {}

    def _weapon_logic_loop(self):
        """
        Dedicated sub-thread for calculating weapon states.
        Handles gun spool-up, ammo depletion, and countermeasure logic at high frequency.
        """
        last_time = time.perf_counter()

        while self.weapon_thread_running:
            try:
                current_time = time.perf_counter()
                dt = current_time - last_time
                last_time = current_time

                is_firing = self.input_manager.is_action_down("primary_fire")
                fire_flares = self.input_manager.is_action_pressed("fire_flares")
                fire_chaff = self.input_manager.is_action_pressed("fire_chaff")

                with self.weapon_lock:
                    if fire_flares and self.current_flares is not None and self.current_flares > 0:
                        self.current_flares -= self.flare_step
                        if self.current_flares < 0:
                            self.current_flares = 0

                    if fire_chaff and self.current_chaff is not None and self.current_chaff > 0:
                        self.current_chaff -= self.chaff_step
                        if self.current_chaff < 0:
                            self.current_chaff = 0

                    guns_list = self._get_all_guns(self.current_plane_config)

                    if not guns_list or len(self.ammo_state) != len(guns_list):
                        time.sleep(0.002)
                        continue

                    first_gun_name = guns_list[0].get("name", "")
                    gun_data = self._get_gun_db_data(first_gun_name)

                    try:
                        charge_rate = float(gun_data.get("shootingCharge", 0.0))
                    except (ValueError, TypeError):
                        charge_rate = 0.0

                    if charge_rate <= 0.0:
                        try:
                            spinup = float(gun_data.get("spinup_time", 0.0))
                            if spinup > 0.0:
                                charge_rate = 1.0 / spinup
                        except (ValueError, TypeError):
                            pass

                    if charge_rate > 0.0:
                        if is_firing:
                            self.gun_charge += dt * charge_rate
                            if self.gun_charge > 1.0:
                                self.gun_charge = 1.0
                        else:
                            self.gun_charge -= dt * (charge_rate * 0.7)
                            if self.gun_charge < 0.0:
                                self.gun_charge = 0.0
                    else:
                        self.gun_charge = 1.0 if is_firing else 0.0

                    for i, gun in enumerate(guns_list):
                        if self.ammo_state[i] <= 0:
                            continue

                        name = gun.get("name", "")
                        current_gun_data = self._get_gun_db_data(name)

                        try:
                            nominal_rof = float(current_gun_data.get("rof_rps", 10.0))
                        except (ValueError, TypeError):
                            nominal_rof = 10.0

                        if charge_rate > 0.0:
                            if self.gun_charge >= 0.95:
                                self.ammo_state[i] -= nominal_rof * dt
                        else:
                            if is_firing:
                                self.ammo_state[i] -= nominal_rof * dt

                        if self.ammo_state[i] < 0:
                            self.ammo_state[i] = 0

            except Exception as e:
                print(f"[ERROR] [TELEMETRY] Weapon loop error: {e}")

            time.sleep(0.002)

    def run(self):
        """
        Main execution loop for the telemetry thread.
        Polls the game's HTTP API continuously.
        """
        indicators_url = config.TELEMETRY_URL.replace("/state", "/indicators")
        map_info_url = config.TELEMETRY_URL.replace("/state", "/map_info.json")

        while self._is_running:
            try:
                response_map = self.session.get(map_info_url, timeout=0.1)

                if response_map.status_code != 200 or not response_map.json().get("valid", False):
                    self.data_received.emit({"valid": False})
                    time.sleep(0.5)
                    continue

                response_state = self.session.get(config.TELEMETRY_URL, timeout=0.1)

                if response_state.status_code == 200:
                    raw_state = response_state.json()

                    try:
                        response_ind = self.session.get(indicators_url, timeout=0.1)
                        raw_ind = response_ind.json() if response_ind.status_code == 200 else {}
                    except requests.exceptions.RequestException:
                        raw_ind = {}

                    combined_data = {**raw_ind, **raw_state}
                    parsed_data = self._parse_and_calculate(combined_data)
                    self.data_received.emit(parsed_data)
                else:
                    self.data_received.emit({"valid": False})

            except requests.exceptions.RequestException:
                self.data_received.emit({"valid": False})
                time.sleep(0.5)

            time.sleep(0.02)

    def _parse_and_calculate(self, raw_data: dict) -> dict:
        """
        Parses raw API data, calculates derived metrics (like fuel consumption via regression),
        and formats the output for the UI overlay.

        Args:
            raw_data (dict): Combined raw JSON from the game's API endpoints.

        Returns:
            dict: Processed and normalized telemetry data.
        """
        if not raw_data or raw_data.get("valid", False) is False:
            self.current_plane_tag = None
            return {"valid": False}

        plane_type = str(raw_data.get("type", "")).lower()

        spd = alt = tas = rad_alt = aoa = g_force = mach = None
        raw_throttles = []
        throttle_pct = 0.0
        is_afterburner = False
        ny_negative = False
        airbrake = 0.0

        fuel_mass = None
        total_fuel_consume = 0.0

        for key, val in raw_data.items():
            key_upper = key.upper()
            key_lower = key.lower()

            if key_lower == "mfuel, kg" or key_lower == "fuel":
                try:
                    fuel_mass = float(val)
                except ValueError:
                    pass
            elif "fuel_consume" in key_lower:
                try:
                    total_fuel_consume += float(val)
                except ValueError:
                    pass

            if "TAS, km/h" in key:
                try:
                    tas = float(val)
                except ValueError:
                    pass
            elif "IAS, km/h" in key:
                try:
                    spd = float(val)
                except ValueError:
                    pass
            elif "H, m" in key:
                try:
                    alt = float(val)
                except ValueError:
                    pass
            elif "AOA, DEG" in key_upper or key_upper == "AOA":
                try:
                    aoa = float(val)
                except ValueError:
                    pass
            elif "NY" in key_upper:
                try:
                    g_force = float(val)
                    if g_force < -3.0:
                        ny_negative = True
                except ValueError:
                    pass
            elif key_upper == "M" or key_upper == "MACH":
                try:
                    mach = float(val)
                except ValueError:
                    pass
            elif "THROTTLE" in key_upper and "%" in key_upper:
                try:
                    raw_throttles.append(float(val))
                except ValueError:
                    pass
            elif key in ["radio_altitude", "altitude_rad", "Hrad", "radio_altimeter"]:
                try:
                    rad_val = float(val)
                    if plane_type.startswith("f-") or plane_type in ["a-10a", "a-10a_late", "av-8a", "av-8c",
                                                                     "harrier"]:
                        rad_alt = rad_val * 0.3048
                    else:
                        rad_alt = rad_val
                except ValueError:
                    pass
            elif "airbrake" in key.lower():
                try:
                    airbrake = float(val) / 100.0
                except ValueError:
                    pass

        if raw_throttles:
            throttle_pct = sum(raw_throttles) / len(raw_throttles)
            if throttle_pct > 100.0:
                is_afterburner = True
            throttle_pct = max(0.0, min(throttle_pct, 120.0))

        current_time = time.time()

        # --- ADVANCED FUEL CALCULATION (LINEAR REGRESSION) ---
        raw_fuel_time_sec = 0

        if fuel_mass is not None:
            self.history_fuel.append((current_time, fuel_mass))

            # Keep history for the last 10 seconds
            while self.history_fuel and current_time - self.history_fuel[0][0] > 10.0:
                self.history_fuel.popleft()

            if total_fuel_consume > 0:
                # If the game provides a direct parameter, use it
                raw_fuel_time_sec = (fuel_mass / total_fuel_consume) * 60
            elif len(self.history_fuel) > 10:
                # Least squares method to smooth telemetry "steps"
                N = len(self.history_fuel)
                t0 = self.history_fuel[0][0]

                sum_t = sum_y = sum_ty = sum_t2 = 0.0

                for t_raw, y in self.history_fuel:
                    t = t_raw - t0  # Normalize time from 0 for float precision
                    sum_t += t
                    sum_y += y
                    sum_ty += t * y
                    sum_t2 += t * t

                denominator = (N * sum_t2) - (sum_t ** 2)

                if denominator != 0:
                    slope = ((N * sum_ty) - (sum_t * sum_y)) / denominator

                    # slope is mass change per second. It should be negative (fuel burning).
                    # Threshold of -0.05 kg/s cuts off micro-noise when the engine is off
                    if slope < -0.05:
                        burn_rate_per_sec = abs(slope)
                        raw_fuel_time_sec = fuel_mass / burn_rate_per_sec

        # Exponential smoothing (Low-pass filter) for visual stability
        if raw_fuel_time_sec > 0:
            if self.smoothed_fuel_time == 0:
                self.smoothed_fuel_time = raw_fuel_time_sec
            else:
                self.smoothed_fuel_time = self.smoothed_fuel_time * 0.95 + raw_fuel_time_sec * 0.05
        else:
            self.smoothed_fuel_time = 0.0

        fuel_time_sec = self.smoothed_fuel_time

        if spd is not None:
            self.history_spd.append((current_time, spd))
        if alt is not None:
            self.history_alt.append((current_time, alt))

        while self.history_spd and current_time - self.history_spd[0][0] > 0.5:
            self.history_spd.popleft()
        while self.history_alt and current_time - self.history_alt[0][0] > 0.5:
            self.history_alt.popleft()

        trend_spd = 0.0
        if len(self.history_spd) > 2:
            hist_dt = self.history_spd[-1][0] - self.history_spd[0][0]
            if hist_dt > 0.2:
                trend_spd = (self.history_spd[-1][1] - self.history_spd[0][1]) / hist_dt

        trend_alt = 0.0
        if len(self.history_alt) > 2:
            hist_dt = self.history_alt[-1][0] - self.history_alt[0][0]
            if hist_dt > 0.2:
                trend_alt = (self.history_alt[-1][1] - self.history_alt[0][1]) / hist_dt

        pull_up_required = False
        if ny_negative and rad_alt is not None and rad_alt < 50.0:
            pull_up_required = True

        raw_flaps = float(raw_data.get("flaps, %", 0.0))
        flaps_val = raw_flaps / 100.0

        raw_gear = raw_data.get("gear", raw_data.get("gear, %", 0.0))
        gear_val = raw_gear / 100.0 if raw_gear > 1.0 else float(raw_gear)
        wing_sweep = float(raw_data.get("wing_sweep_lever", 0.0))

        norm_type = plane_type.replace('-', '_').lower()
        new_config = {}
        for key, cfg in self.aircraft_db.items():
            if key.replace('-', '_').lower() in norm_type:
                new_config = cfg
                break

        with self.weapon_lock:
            self.flare_step = self.preset_flare_step if self.preset_flare_step is not None else new_config.get(
                "flare_step", 1)
            self.chaff_step = self.preset_chaff_step if self.preset_chaff_step is not None else new_config.get(
                "chaff_step", 1)

            if self.current_plane_tag != plane_type:
                self.current_plane_tag = plane_type
                self.active_loadout = self._fetch_main_preset(plane_type)

                self.current_flares = self.preset_flares
                self.current_chaff = self.preset_chaff

                self.current_plane_config = new_config
                guns_list = self._get_all_guns(new_config)
                self.ammo_state = [float(gun.get("max_ammo", 0)) for gun in guns_list]
                self.gun_charge = 0.0
            else:
                guns_list = self._get_all_guns(new_config)
                if self.current_plane_config.get("name") != new_config.get("name"):
                    self.current_plane_config = new_config
                    self.ammo_state = [float(gun.get("max_ammo", 0)) for gun in guns_list]
                    self.gun_charge = 0.0

            is_on_ground = (tas is not None and tas < 5.0) and (alt is not None and alt < 10.0)
            if is_on_ground and not self.input_manager.is_action_down("primary_fire"):
                for i, gun in enumerate(guns_list):
                    if i < len(self.ammo_state) and self.ammo_state[i] < float(gun.get("max_ammo", 0)):
                        self.ammo_state[i] = float(gun.get("max_ammo", 0))

                if self.preset_flares is not None:
                    self.current_flares = self.preset_flares
                if self.preset_chaff is not None:
                    self.current_chaff = self.preset_chaff

            grouped = {}
            for i, gun in enumerate(guns_list):
                if i >= len(self.ammo_state):
                    continue

                name = gun.get("name", "Unknown")
                current = int(self.ammo_state[i])

                if name not in grouped:
                    grouped[name] = 0
                grouped[name] += current

            calculated_ammo = [{"ammo": amount, "name": name} for name, amount in grouped.items()] if grouped else None

        return {
            "valid": True,
            "type": plane_type,
            "flaps": flaps_val,
            "gear": gear_val,
            "airbrake": airbrake,
            "wing_sweep": wing_sweep,
            "spd": spd,
            "alt": alt,
            "tas": tas,
            "rad_alt": rad_alt,
            "trend_spd": trend_spd,
            "trend_alt": trend_alt,
            "aoa": aoa,
            "g_force": g_force,
            "mach": mach,
            "throttle_pct": throttle_pct,
            "is_afterburner": is_afterburner,
            "pull_up_required": pull_up_required,
            "ammo_internal": calculated_ammo,
            "fuel_mass": fuel_mass,
            "fuel_time_sec": fuel_time_sec,
            "flares": self.current_flares,
            "chaff": self.current_chaff
        }

    def stop(self):
        """Signals all loops to stop and safely terminates the thread."""
        self._is_running = False
        self.weapon_thread_running = False
        self.quit()
        self.wait()