"""
sms_indicator.py
----------------
Renders the Stores Management System (SMS) visual display.
Draws the aircraft's physical pylon layout, current active loadout, weapon selection highlights,
and header information including fuel mass, remaining time, and countermeasures (flares/chaff).
"""

from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush
from PySide6.QtCore import Qt, QPointF, QRectF
import config
import re


class SMSIndicator:
    """
    Handles the dynamic rendering of the aircraft's external payload and vital resources.
    Features dynamic bounding boxes depending on whether the aircraft is carrying ordnance
    or solely countermeasures/fuel.
    """

    def __init__(self):
        self.color = QColor(*config.HUD_COLOR)
        self.color.setAlpha(220)
        self.bg_color = QColor(*config.BG_COLOR)

        mfd_font_size = max(10, int(config.FONT_SIZE * 0.9))
        self.font = QFont(config.FONT_FAMILY, mfd_font_size, QFont.Bold)

    def draw(self, painter: QPainter, center_x: float, center_y: float, active_loadout: dict,
             selected_weapon: str = None, seeker_state: dict = None, global_blink: bool = True,
             active_pylons=None, fuel_mass=None, fuel_time_sec=None, flares=None, chaff=None):
        """
        Main rendering routine for the SMS block.

        Args:
            painter (QPainter): The active Qt drawing context.
            center_x, center_y (float): Base rendering coordinates.
            active_loadout (dict): The current weapon configuration mapped by pylon index.
            selected_weapon (str): The actively selected weapon name.
            seeker_state (dict): Provides color and blink signals for the active seeker.
            global_blink (bool): Synchronization boolean for flashing UI elements.
            active_pylons (list, optional): List of pylons next in the firing sequence.
            fuel_mass (float, optional): Remaining fuel in kg.
            fuel_time_sec (float, optional): Calculated fuel time remaining.
            flares, chaff (int, optional): Current countermeasure counts.
        """
        has_fuel = fuel_mass is not None and fuel_time_sec is not None
        has_cm = flares is not None or chaff is not None
        has_header = has_fuel or has_cm

        # Check if there is at least one physical weapon equipped on the pylons
        has_weapons = False
        if active_loadout:
            has_weapons = any(w not in ("< Empty >", "< N/A >") for w in active_loadout.values())

        # If neither header nor weapons exist, skip rendering entirely
        if not has_header and not has_weapons:
            return

        painter.save()

        # --- BACKGROUND CALCULATION ---
        bg_width = 530

        # Dynamic height: large box for weapons, compact strip for header only
        if has_weapons:
            bg_height = 220 if has_header else 150
        else:
            bg_height = 40  # Dedicated height strictly for fuel and countermeasures

        bg_x = center_x - (bg_width / 2)
        bg_y = (center_y - 75) if has_header else (center_y - 45)

        # --- DRAW BACKGROUND ---
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.bg_color))
        painter.drawRoundedRect(QRectF(bg_x, bg_y, bg_width, bg_height), 10, 10)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self.color, 2))
        painter.setFont(self.font)

        # --- DRAW HEADER (FUEL & COUNTERMEASURES) ---
        if has_header:
            if has_fuel:
                minutes = int(fuel_time_sec // 60)
                seconds = int(fuel_time_sec % 60)

                if fuel_time_sec <= 0 or minutes > 99:
                    time_str = "--:--"
                else:
                    time_str = f"{minutes:02d}:{seconds:02d}"

                fuel_text = f"FUEL: {int(fuel_mass)} KG  [{time_str}]"
                painter.drawText(bg_x + 15, bg_y + 26, fuel_text)

            if has_cm:
                f_val = flares if flares is not None else 0
                c_val = chaff if chaff is not None else 0
                cm_text = f"FLR {f_val} || {c_val} CHF"

                text_rect = painter.fontMetrics().boundingRect(cm_text)
                cm_x = bg_x + bg_width - text_rect.width() - 15
                painter.drawText(cm_x, bg_y + 26, cm_text)

            # Draw separation line ONLY if weapons are present below the header
            if has_weapons:
                painter.setPen(QPen(self.color, 1))
                painter.drawLine(bg_x, bg_y + 35, bg_x + bg_width, bg_y + 35)
                painter.setPen(QPen(self.color, 2))

        # --- DRAW WEAPONS (IF EQUIPPED) ---
        if has_weapons:
            active_pylon_ints = []
            if active_pylons is not None:
                nums = re.findall(r'\d+', str(active_pylons))
                active_pylon_ints = [int(n) for n in nums]

            active_bg_color = self.color
            is_blinking = False

            if seeker_state:
                ui_color_tuple = seeker_state.get("color")
                if ui_color_tuple:
                    active_bg_color = QColor(*ui_color_tuple)
                is_blinking = seeker_state.get("blink", False)

            w_tip_dy = 90
            w_tip_dx = 240
            root_dx = 45

            c_left = QPointF(center_x - root_dx, center_y)
            c_right = QPointF(center_x + root_dx, center_y)
            tip_left = QPointF(center_x - w_tip_dx, center_y + w_tip_dy)
            tip_right = QPointF(center_x + w_tip_dx, center_y + w_tip_dy)

            painter.drawLine(tip_left, c_left)
            painter.drawLine(c_left, c_right)
            painter.drawLine(c_right, tip_right)

            def draw_pylon(x, y, weapon_name, pylon_idx, is_center=False):
                """Helper function to render an individual pylon crosshair and weapon text."""
                painter.drawLine(x - 8, y, x + 8, y)
                painter.drawLine(x, y - 8, x, y + 8)

                display_name = weapon_name[:10]
                text_rect = painter.fontMetrics().boundingRect(display_name)

                text_x = x - text_rect.width() / 2
                text_y_base = y - 18 if is_center else y + 35

                clean_weapon_name = re.sub(r'^x\d+\s*', '', weapon_name, flags=re.IGNORECASE).strip()

                is_next_to_fire = (pylon_idx in active_pylon_ints)
                is_selected_type = (selected_weapon and selected_weapon == clean_weapon_name)

                padding = 2
                bg_rect = QRectF(text_x - padding, text_y_base - text_rect.height() + padding,
                                 text_rect.width() + padding * 2, text_rect.height() + padding * 2)

                if is_next_to_fire:
                    if is_blinking and not global_blink:
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.setPen(QPen(active_bg_color, 2))
                        painter.drawRect(bg_rect)
                        painter.drawText(text_x, text_y_base, display_name)
                    else:
                        painter.setBrush(QBrush(active_bg_color))
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.drawRect(bg_rect)
                        painter.setPen(QPen(Qt.GlobalColor.black))
                        painter.drawText(text_x, text_y_base, display_name)

                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(self.color, 2))

                elif is_selected_type:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(self.color, 2))
                    painter.drawRect(bg_rect)
                    painter.drawText(text_x, text_y_base, display_name)
                    painter.setPen(QPen(self.color, 2))

                else:
                    painter.drawText(text_x, text_y_base, display_name)

            left_pylons = {}
            right_pylons = {}
            center_pylon = None

            for p_str, weapon in active_loadout.items():
                if not p_str.isdigit():
                    continue

                if weapon in ("< Empty >", "< N/A >"):
                    continue

                idx = int(p_str)
                if 1 <= idx <= 6:
                    left_pylons[idx] = weapon
                elif idx == 7:
                    center_pylon = weapon
                elif idx >= 8:
                    right_pylons[idx] = weapon

            # Distribute left wing pylons
            for idx, weapon in left_pylons.items():
                t = (idx - 1) / 5.0
                px = tip_left.x() + (c_left.x() - tip_left.x()) * t
                py = tip_left.y() + (c_left.y() - tip_left.y()) * t
                draw_pylon(px, py, weapon, pylon_idx=idx)

            # Draw centerline pylon
            if center_pylon:
                draw_pylon(center_x, center_y, center_pylon, pylon_idx=7, is_center=True)

            # Distribute right wing pylons
            for idx, weapon in right_pylons.items():
                max_right = max(13, max(right_pylons.keys()) if right_pylons else 13)
                t = (idx - 8) / float(max_right - 8)

                px = c_right.x() + (tip_right.x() - c_right.x()) * t
                py = c_right.y() + (tip_right.y() - c_right.y()) * t
                draw_pylon(px, py, weapon, pylon_idx=idx)

        painter.restore()