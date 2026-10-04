"""
weapon_manager.py
-----------------
Manages the aircraft's secondary weapon loadout, cycle logic, and firing sequences.
Tracks active pylons, filters out non-selectable items (like fuel tanks),
and synchronizes with the user's weapon selection hotkeys.
"""

import keyboard
import json
import os
import re


def _safe_dict(d):
    """
    Safeguard function to ensure a valid dictionary is returned.

    Args:
        d: Input that should be a dictionary.

    Returns:
        dict: The original dictionary, or an empty one if the input is invalid.
    """
    return d if isinstance(d, dict) else {}


class WeaponManager:
    """
    Core class for managing weapon states, cycling through available armaments,
    and determining the correct pylon firing order (outer-to-inner).
    """

    def __init__(self):
        self.available_weapons = []
        self.current_index = -1
        self.cycle_flag = False

        self.excluded_weapon_types = ["FUEL_TANKS", "PODS", "ROCKET_BOOSTERS", "GUN_PODS"]

        self.weapons_db = self._load_weapons_db()
        weapon_classes = self.weapons_db.get("WEAPON_CLASSES", {})

        self.aam_db = _safe_dict(weapon_classes.get("AAM"))
        self.agm_db = _safe_dict(weapon_classes.get("AGM"))
        self.asm_db = _safe_dict(weapon_classes.get("ASM"))
        self.gbu_db = _safe_dict(weapon_classes.get("GUIDED_BOMBS"))
        self.arm_db = _safe_dict(weapon_classes.get("ARM"))

        self.rockets_pods_db = _safe_dict(weapon_classes.get("ROCKETS"))

        self.unguided_db = {
            **_safe_dict(weapon_classes.get("BOMBS_LOW_DRAG")),
            **_safe_dict(weapon_classes.get("BOMBS_HIGH_DRAG")),
            **_safe_dict(weapon_classes.get("NAPALM")),
            **_safe_dict(weapon_classes.get("TORPEDOES")),
            **self.rockets_pods_db,
            **_safe_dict(weapon_classes.get("ROCKETS_SINGULAR"))
        }

        self.excluded_weapons = self._build_excluded_weapons()

        self.active_loadout = {}
        self.plane_firing_order = []

        hotkey_str = self._load_keybind()
        try:
            keyboard.add_hotkey(hotkey_str, self._on_hotkey)
            print(f"[INFO] [WEAPON MANAGER] Global hotkey '{hotkey_str}' bound to Weapon Cycle.")
        except Exception as e:
            print(f"[ERROR] [WEAPON MANAGER] Failed to bind hotkey '{hotkey_str}': {e}. Try running as Administrator.")

    def _load_weapons_db(self):
        """Loads the comprehensive weapons database from JSON."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(base_dir, "data", "weapons_db.json")

        if not os.path.exists(db_path):
            return {}

        try:
            with open(db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] [WEAPON MANAGER] Failed to load weapons_db.json: {e}")
            return {}

    def _build_excluded_weapons(self):
        """Constructs a set of weapon names that should not be selectable in the HUD."""
        excluded_set = set()
        weapon_classes = self.weapons_db.get("WEAPON_CLASSES", {})

        for ex_class in self.excluded_weapon_types:
            if ex_class in weapon_classes:
                for weapon_name in weapon_classes[ex_class].keys():
                    excluded_set.add(weapon_name)

        return excluded_set

    def _load_keybind(self):
        """Loads the specific hotkey for cycling secondary weapons."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        keybinds_path = os.path.join(base_dir, "data", "keybinds.json")

        if not os.path.exists(keybinds_path):
            return "alt+2"

        try:
            with open(keybinds_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            keys_list = data.get("switch_secondary_weapon", ["alt", "2"])
            return "+".join(keys_list).lower()
        except Exception:
            return "alt+2"

    def _on_hotkey(self, *args, **kwargs):
        """Callback for the weapon cycle hotkey."""
        self.cycle_flag = True

    def _is_weapon_selectable(self, weapon_name):
        """
        Determines if a weapon should be included in the cycle list.

        Args:
            weapon_name (str): The raw name of the weapon from the pylon data.

        Returns:
            bool: True if selectable, False if it's empty, N/A, or an excluded type (e.g., fuel tank).
        """
        if weapon_name in ("< Empty >", "< N/A >"):
            return False

        clean_name = re.sub(r'^x\d+\s*', '', weapon_name, flags=re.IGNORECASE)

        if clean_name in self.excluded_weapons:
            return False

        for excluded_item in self.excluded_weapons:
            if clean_name.startswith(excluded_item) or excluded_item in clean_name:
                return False

        return True

    def update_loadout(self, active_loadout, is_spawn=False):
        """
        Updates the internal representation of the aircraft's loadout.
        Calculates the firing order dynamically based on pylon position.

        Args:
            active_loadout (dict): The current state of all pylons.
            is_spawn (bool): If True, forces a complete recalculation of the firing order.
        """
        self.active_loadout = active_loadout
        sorted_pylons = sorted([int(k) for k in active_loadout.keys() if k.isdigit()])

        if is_spawn:
            self.current_index = -1
            self.plane_firing_order = []
            l_ptr = 0
            r_ptr = len(sorted_pylons) - 1

            while l_ptr <= r_ptr:
                self.plane_firing_order.append(sorted_pylons[l_ptr])
                if l_ptr != r_ptr:
                    self.plane_firing_order.append(sorted_pylons[r_ptr])
                l_ptr += 1
                r_ptr -= 1

            # Compile the weapon list strictly in firing order (outer to inner)
            current_unique_weapons = []
            for p_idx in self.plane_firing_order:
                raw_weapon = active_loadout.get(str(p_idx))
                if raw_weapon and self._is_weapon_selectable(raw_weapon):
                    clean_name = re.sub(r'^x\d+\s*', '', raw_weapon, flags=re.IGNORECASE)
                    if clean_name not in current_unique_weapons:
                        current_unique_weapons.append(clean_name)

            self.available_weapons = current_unique_weapons
        else:
            old_selected_weapon = self.get_selected_weapon()

            # Collect remaining weapons on pylons (preserving outer-to-inner priority)
            current_unique_weapons = []
            for p_idx in self.plane_firing_order:
                raw_weapon = active_loadout.get(str(p_idx))
                if raw_weapon and self._is_weapon_selectable(raw_weapon):
                    clean_name = re.sub(r'^x\d+\s*', '', raw_weapon, flags=re.IGNORECASE)
                    if clean_name not in current_unique_weapons:
                        current_unique_weapons.append(clean_name)

            new_available = [w for w in self.available_weapons if w in current_unique_weapons]

            for w in current_unique_weapons:
                if w not in new_available:
                    new_available.append(w)

            self.available_weapons = new_available

            if self.current_index != -1:
                if old_selected_weapon in self.available_weapons:
                    self.current_index = self.available_weapons.index(old_selected_weapon)
                else:
                    if self.available_weapons:
                        if self.current_index >= len(self.available_weapons):
                            self.current_index = 0
                        print(f"[INFO] [WEAPON MANAGER] Auto-switched to {self.get_selected_weapon()}")
                    else:
                        self.current_index = -1

    def process_cycle(self):
        """Processes the cycle flag to switch to the next available weapon."""
        if self.cycle_flag:
            self.cycle_flag = False
            if self.available_weapons:
                self.current_index = (self.current_index + 1) % len(self.available_weapons)
                print(f"[INFO] [WEAPON MANAGER] Selected: {self.get_selected_weapon()}")

    def get_selected_weapon(self):
        """Returns the currently selected weapon name."""
        if 0 <= self.current_index < len(self.available_weapons):
            return self.available_weapons[self.current_index]
        return None

    def _get_weapon_data(self, clean_name, db_dict):
        """Helper to search for weapon data by exact name or substring."""
        clean_name_lower = clean_name.lower().strip()

        for key, data in db_dict.items():
            if key.lower().strip() == clean_name_lower:
                return data

        for raw_key, data in db_dict.items():
            db_clean = re.sub(r'^x\d+\s*', '', raw_key, flags=re.IGNORECASE)
            if db_clean.lower().strip() == clean_name_lower:
                return data

        return None

    def get_weapon_category_and_guidance(self):
        """
        Determines the category and guidance type of the currently selected weapon.

        Returns:
            tuple: (Weapon category string, list of guidance types).
        """
        clean_weapon = self.get_selected_weapon()
        if not clean_weapon:
            return "AAM", []

        aam_data = self._get_weapon_data(clean_weapon, self.aam_db)
        if aam_data is not None:
            return "AAM", aam_data.get("guidance", [])

        agm_data = self._get_weapon_data(clean_weapon, self.agm_db)
        if agm_data is not None:
            return "AGM", agm_data.get("guidance", [])

        asm_data = self._get_weapon_data(clean_weapon, self.asm_db)
        if asm_data is not None:
            return "ASM", asm_data.get("guidance", [])

        gbu_data = self._get_weapon_data(clean_weapon, self.gbu_db)
        if gbu_data is not None:
            return "GBU", gbu_data.get("guidance", [])

        arm_data = self._get_weapon_data(clean_weapon, self.arm_db)
        if arm_data is not None:
            return "ARM", arm_data.get("guidance", [])

        unguided_data = self._get_weapon_data(clean_weapon, self.unguided_db)
        if unguided_data is not None:
            return "UNGUIDED", []

        return "UNGUIDED", []

    def get_active_pylons(self, clean_weapon_name):
        """Public accessor for finding which pylons will fire next for a specific weapon."""
        return self._get_pylons_to_fire(clean_weapon_name)

    def _get_pylons_to_fire(self, clean_weapon_name):
        """
        Calculates exactly which pylon(s) will be fired next.
        Handles paired firing for rocket pods and balanced asymmetric loadouts.

        Args:
            clean_weapon_name (str): The name of the weapon to query.

        Returns:
            list: String indices of the pylons queued for the next launch.
        """
        if not clean_weapon_name:
            return []

        matching_pylons = []
        for p_idx in self.plane_firing_order:
            str_idx = str(p_idx)
            raw_weapon = self.active_loadout.get(str_idx)

            if raw_weapon:
                clean_name = re.sub(r'^x\d+\s*', '', raw_weapon, flags=re.IGNORECASE)
                if clean_name.lower().strip() == clean_weapon_name.lower().strip():
                    match = re.match(r'^x(\d+)\s*', raw_weapon, flags=re.IGNORECASE)
                    count = int(match.group(1)) if match else 1
                    matching_pylons.append({"str_idx": str_idx, "count": count})

        if not matching_pylons:
            return []

        is_pod = False
        weapon_data = self._get_weapon_data(clean_weapon_name, self.rockets_pods_db)

        if weapon_data is not None:
            val = weapon_data.get("is_pod", True)
            if isinstance(val, str):
                is_pod = val.strip().lower() in ["true", "1", "yes", "y"]
            else:
                is_pod = bool(val)

        if is_pod:
            return [p['str_idx'] for p in matching_pylons][:2]
        else:
            best_pylon = matching_pylons[0]

            # Rebalancing logic for asymmetric loadouts (e.g., unequal bomb counts per wing)
            if len(matching_pylons) > 1:
                p1 = matching_pylons[0]
                p2 = matching_pylons[1]

                idx1 = self.plane_firing_order.index(int(p1['str_idx']))
                idx2 = self.plane_firing_order.index(int(p2['str_idx']))

                if idx2 == idx1 + 1 and idx1 % 2 == 0:
                    if p2['count'] > p1['count']:
                        best_pylon = p2

            return [best_pylon['str_idx']]

    def fire_current_weapon(self):
        """
        Executes the firing logic for the currently selected weapon.
        Decrements counts on active pylons and updates the global loadout state.
        """
        active_weapon_clean = self.get_selected_weapon()
        if not active_weapon_clean:
            return

        target_pylons = self._get_pylons_to_fire(active_weapon_clean)

        for target_str_idx in target_pylons:
            raw_weapon = self.active_loadout[target_str_idx]
            match = re.match(r'^x(\d+)\s*', raw_weapon, flags=re.IGNORECASE)

            if match:
                count = int(match.group(1))
                if count > 1:
                    new_count = count - 1
                    if new_count == 1:
                        self.active_loadout[target_str_idx] = active_weapon_clean
                    else:
                        self.active_loadout[target_str_idx] = f"x{new_count} {active_weapon_clean}"
                    print(f"[INFO] [WEAPON MANAGER] Pylon {target_str_idx} fired. {new_count} left.")
                else:
                    del self.active_loadout[target_str_idx]
                    print(f"[INFO] [WEAPON MANAGER] Pylon {target_str_idx} empty.")
            else:
                del self.active_loadout[target_str_idx]
                print(f"[INFO] [WEAPON MANAGER] Pylon {target_str_idx} empty.")

        if target_pylons:
            self.update_loadout(self.active_loadout, is_spawn=False)