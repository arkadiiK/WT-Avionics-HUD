"""
enums.py
--------
Contains enumerations used across the project to maintain consistent state definitions.
"""

from enum import Enum


class WeaponState(Enum):
    """
    Defines the various operational states of a weapon's seeker or guidance system.
    Used to determine UI feedback (e.g., color, blinking) on the HUD.
    """
    OFF = 0        # Inactive or no seeker text detected
    STANDBY = 1    # 'seeker: on' or 'waiting' for AGM (Indicates spool-up or standby)
    SEARCHING = 2  # 'seeker: searching' (Indicates active search, usually blinking UI)
    LOCKED = 3     # 'seeker: tracking' (Indicates target lock, usually solid red UI)
    COOLDOWN = 4   # 'seeker: waiting' for AAM (Indicates seeker cooling down / inactive)