"""
flaps_indicator.py
------------------
GUI component responsible for rendering the aircraft's flaps and slats state.
Handles API noise through value snapping and provides visual feedback (blinking)
during mechanical transitions.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QFont, QPen
from PySide6.QtCore import Qt, QTimer, QRect

import config


class FlapsIndicator(QWidget):
    """
    Widget that displays the current flap and slat configuration.
    Features mechanical transition animations (blinking) and dynamic stage rendering based on the aircraft's database profile.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(210, 140)

        # State variables
        self.current_flaps_api = 0.0
        self.config = {}

        # Calculated variables
        self.normalized_val = 0
        self.snapped_val = 0  # Value with API jitter removed
        self.active_stage_key = "0"  # Exact key of the current aerodynamic stage
        self.is_transit = False
        self.text_label = ""
        self.flaps_stages = []
        self.has_slats = False

        # Timer for blinking
        self.blink_state = True
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.toggle_blink)
        self.blink_timer.start(500)

    def toggle_blink(self):
        """Handles blinking logic during flap transitions."""
        if self.is_transit:
            self.blink_state = not self.blink_state
            self.update()
        else:
            self.blink_state = True

    def update_data(self, api_flaps, aircraft_config):
        """
        Parses raw API data against the aircraft's specific flaps configuration.
        Applies logic to snap floating-point API values to discrete aerodynamic stages.

        Args:
            api_flaps (float): Raw flap extension percentage from the game API (0.0 to 1.0).
            aircraft_config (dict): Aerodynamic configuration dict for the current aircraft.
        """
        self.current_flaps_api = api_flaps
        self.config = aircraft_config

        if not self.config:
            self.hide()
            return

        self.show()

        # 1. Base Normalization (0.0 to 100)
        self.normalized_val = int(round(api_flaps * 100))
        self.snapped_val = self.normalized_val

        self.has_slats = False
        self.flaps_stages = []

        # FIRST PASS: Collect aerodynamic stages
        for k, v in self.config.items():
            val_int = int(k)

            if v.get("slats", False):
                self.has_slats = True

            if val_int > 0 and v.get("flaps", True):
                self.flaps_stages.append(val_int)

        self.flaps_stages = sorted(self.flaps_stages)
        sorted_keys = sorted([int(k) for k in self.config.keys()])

        self.is_transit = True
        self.text_label = "FLAPS"

        # Default stage key (if in transit, fallback to the last passed stage)
        passed_stages = [k for k in sorted_keys if self.normalized_val >= k]
        self.active_stage_key = str(passed_stages[-1]) if passed_stages else "0"

        # SECOND PASS: Determine current stage based on proximity (Snapping)
        for i, stage_int in enumerate(sorted_keys):
            stage_str = str(stage_int)
            stage_data = self.config[stage_str]
            label_str = stage_data.get("label", "")

            # Dynamic tolerance (e.g., F-16 with stages at 99 and 100 requires strict 0.5 tolerance)
            distances = []
            if i > 0:
                distances.append(abs(stage_int - sorted_keys[i - 1]))
            if i < len(sorted_keys) - 1:
                distances.append(abs(stage_int - sorted_keys[i + 1]))

            min_dist = min(distances) if distances else 10
            tolerance = 0.5 if min_dist < 5 else 3.0

            # If within tolerance of a known stage, snap the values
            if abs(self.normalized_val - stage_int) <= tolerance:
                self.is_transit = False
                self.text_label = label_str
                self.blink_state = True
                self.snapped_val = stage_int  # Perfect value without API jitter
                self.active_stage_key = stage_str  # Exact key
                break

        self.update()

    def paintEvent(self, event):
        """Renders the graphical representation of flaps, slats, and transition labels."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        if not getattr(self, 'allow_draw', True) or not self.config:
            painter.end()
            return

        color_green = QColor(*config.HUD_COLOR)
        color_orange = QColor(*config.FLAPS_TRANSIT_COLOR)
        color_bg = QColor(*config.BG_COLOR)

        current_color = color_orange if self.is_transit else color_green

        pen = QPen(current_color)
        pen.setWidthF(2)
        painter.setPen(pen)

        center_y = 42
        start_x = 42
        wing_length = 84
        painter.drawLine(start_x, center_y, start_x + wing_length, center_y)

        # Render Slats (Leading Edge - Left Side)
        if self.has_slats:
            current_slats_active = self.config.get(self.active_stage_key, {}).get("slats", False)
            painter.drawRect(start_x - 21, center_y - 7, 14, 14)
            if current_slats_active:
                painter.fillRect(start_x - 21, center_y - 7, 14, 14, current_color)

        # Render Flaps stages (Trailing Edge - Right Side)
        num_stages = len(self.flaps_stages)
        if num_stages > 0:
            box_width = 14
            spacing = 7
            for i, stage in enumerate(self.flaps_stages):
                box_x = start_x + wing_length + 7 + (i * (box_width + spacing))
                painter.drawRect(box_x, center_y - 7, box_width, 14)

                # Pure threshold comparison based on snapped values
                if self.snapped_val >= stage:
                    painter.fillRect(box_x, center_y - 7, box_width, 14, current_color)

        # Hide text box if flaps are fully UP and not moving
        if self.text_label == "UP" and not self.is_transit:
            return

        # Render Text Box
        rect_y = center_y + 25
        text_box_x = start_x - 20
        text_box_width = wing_length + 80
        text_box_height = 35

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color_bg)
        painter.drawRect(text_box_x, rect_y, text_box_width, text_box_height)

        if not self.is_transit or self.blink_state:
            painter.setPen(current_color)
            painter.setFont(QFont(config.FONT_FAMILY, 14, QFont.Weight.Bold))
            text_rect = QRect(text_box_x, rect_y, text_box_width, text_box_height)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, str(self.text_label))