"""
instruments.py
--------------
Renders flight instruments, tapes (speed, altitude), G-meter, Mach indicator,
AoA indexer, weapon indicators, and warnings using Qt Painter primitives.
"""

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPainter, QPen, QBrush, QPolygon, QFont, QColor
import config


class InstrumentRenderer:
    """
    Handles all graphical rendering operations for the HUD instrumentation,
    ensuring pixel-perfect alignment and dynamic color states.
    """
    def __init__(self):
        # Fonts
        self.main_font = QFont(config.FONT_FAMILY, config.FONT_SIZE, QFont.Weight.Bold)
        self.error_font = QFont(config.FONT_FAMILY, 11, QFont.Weight.Bold)
        self.bottom_indicators_font = QFont(config.FONT_FAMILY, 11, QFont.Weight.ExtraBold)

        # Colors unpacked from config
        self.hud_color = QColor(*config.HUD_COLOR)
        self.bg_color = QColor(*config.BG_COLOR)
        self.trend_color = QColor(*config.TREND_COLOR)
        self.err_color = QColor(*config.ERR_COLOR)
        self.critical_color = QColor(*config.ERR_COLOR)

        # AoA Indexer specific colors (dynamic)
        self.aoa_red = QColor(*config.ERR_COLOR)
        self.aoa_yellow = QColor(*config.FLAPS_TRANSIT_COLOR)
        self.aoa_green = QColor(*config.HUD_COLOR)

        # Unified layout constants for pixel-perfect alignment
        self.inner_tick_left = config.X_LEFT_TAPE + 20
        self.inner_tick_right = config.X_RIGHT_TAPE - 20
        self.shared_padding = -10

    def draw_tape(self, painter: QPainter, x_pos: int, y_center: int, tape_height: int,
                  current_value: float, trend_value: float, is_left_side: bool,
                  step_main: int, step_minor: int, scale_factor: float, trend_scale: float):
        """Renders vertical sliding parameter tapes (e.g., speed, altitude) along with trend arrows."""
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.bg_color))
        bg_x = x_pos - config.TAPE_WIDTH if is_left_side else x_pos
        painter.drawRect(bg_x, y_center - tape_height // 2, config.TAPE_WIDTH, tape_height)

        pen = QPen(self.hud_color)
        pen.setWidth(2)
        painter.setPen(pen)

        val_for_scale = current_value if current_value is not None else 0.0
        min_val = int((val_for_scale - (tape_height / 2 / scale_factor)) // step_minor * step_minor)
        max_val = int((val_for_scale + (tape_height / 2 / scale_factor)) // step_minor * step_minor)

        for value in range(min_val - step_minor, max_val + step_minor * 2, step_minor):
            y_pos = y_center - (value - val_for_scale) * scale_factor

            if abs(y_pos - y_center) <= tape_height / 2:
                if value % step_main == 0:
                    line_start = x_pos - 20 if is_left_side else x_pos
                    line_end = x_pos if is_left_side else x_pos + 20
                    painter.drawLine(line_start, int(y_pos), line_end, int(y_pos))

                    text_x = x_pos - 70 if is_left_side else x_pos + 25
                    painter.drawText(text_x, int(y_pos) + 6, str(value))
                else:
                    line_start = x_pos - 10 if is_left_side else x_pos
                    line_end = x_pos if is_left_side else x_pos + 10
                    painter.drawLine(line_start, int(y_pos), line_end, int(y_pos))

        if current_value is not None:
            visual_length = trend_value * trend_scale * 2.5
            if abs(visual_length) > 0.0:
                painter.setBrush(QBrush(self.trend_color))
                painter.setPen(Qt.PenStyle.NoPen)

                arrow_x = x_pos
                if visual_length > 120:
                    visual_length = 120
                if visual_length < -120:
                    visual_length = -120

                start_y = y_center
                tip_y = int(start_y - visual_length)

                if visual_length > 0:
                    arrow_path = QPolygon([
                        QPoint(arrow_x, tip_y),
                        QPoint(arrow_x + 6, tip_y + 10),
                        QPoint(arrow_x + 2, tip_y + 10),
                        QPoint(arrow_x + 2, start_y),
                        QPoint(arrow_x - 2, start_y),
                        QPoint(arrow_x - 2, tip_y + 10),
                        QPoint(arrow_x - 6, tip_y + 10)
                    ])
                else:
                    arrow_path = QPolygon([
                        QPoint(arrow_x, tip_y),
                        QPoint(arrow_x + 6, tip_y - 10),
                        QPoint(arrow_x + 2, tip_y - 10),
                        QPoint(arrow_x + 2, start_y),
                        QPoint(arrow_x - 2, start_y),
                        QPoint(arrow_x - 2, tip_y - 10),
                        QPoint(arrow_x - 6, tip_y - 10)
                    ])
                painter.drawPolygon(arrow_path)

        self._draw_pointer(painter, x_pos, y_center, current_value, is_left_side)

    def _draw_pointer(self, painter: QPainter, x: int, y: int, value: float, is_left_side: bool):
        """Renders the value pointer box alongside a specific tape."""
        box_width = 65
        box_height = 30

        if is_left_side:
            box_x = x + 10
            poly_box = QPolygon([
                QPoint(box_x, y - box_height // 2), QPoint(box_x + box_width, y - box_height // 2),
                QPoint(box_x + box_width, y + box_height // 2), QPoint(box_x, y + box_height // 2),
                QPoint(box_x - 10, y)
            ])
            text_x = box_x + 5
        else:
            box_x = x - box_width - 10
            poly_box = QPolygon([
                QPoint(box_x, y - box_height // 2), QPoint(box_x + box_width, y - box_height // 2),
                QPoint(box_x + box_width + 10, y), QPoint(box_x + box_width, y + box_height // 2),
                QPoint(box_x, y + box_height // 2)
            ])
            text_x = box_x + 10

        painter.setBrush(QBrush(QColor(0, 0, 0)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(poly_box)

        if value is None:
            painter.setPen(QPen(self.err_color, 2))
            painter.setFont(self.error_font)
            painter.drawText(text_x + 10, y + 6, "ERR")
            painter.setFont(self.main_font)
        else:
            painter.setPen(QPen(self.hud_color, 2))
            painter.drawText(text_x, y + 6, str(int(value)))

    def draw_throttle_bar(self, painter: QPainter, throttle_pct: float, is_thrust_exceeded: bool, has_ab: bool,
                          has_wep: bool):
        """Renders the engine throttle level bar."""
        left_bound = config.X_LEFT_TAPE - config.TAPE_WIDTH
        right_bound = config.X_RIGHT_TAPE + config.TAPE_WIDTH

        bar_x = left_bound
        bar_width = right_bound - left_bound
        bar_height = 24

        tape_top_y = config.Y_CENTER - (config.TAPE_HEIGHT // 2)
        bar_y = tape_top_y - 35

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.bg_color))
        painter.drawRect(bar_x, bar_y, bar_width, bar_height)

        if throttle_pct is None:
            return

        fill_color = QColor(self.hud_color.red(), self.hud_color.green(), self.hud_color.blue(), 100)
        painter.setBrush(QBrush(fill_color))
        clamped_pct = max(0.0, min(throttle_pct, 100.0))
        fill_width = int(bar_width * (clamped_pct / 100.0))
        painter.drawRect(bar_x, bar_y, fill_width, bar_height)

        outline_color = self.critical_color if is_thrust_exceeded else self.hud_color
        text_color = self.critical_color if is_thrust_exceeded else self.hud_color

        text = f"{int(throttle_pct)}%"
        if is_thrust_exceeded:
            if has_ab:
                text = "A/B"
            elif has_wep:
                text = "WEP"
            else:
                text = "MAX"

        painter.setPen(QPen(outline_color, 2))
        for pct in [0.25, 0.50, 0.75]:
            tick_x = bar_x + int(bar_width * pct)
            painter.drawLine(tick_x, bar_y, tick_x, bar_y + 6)
            painter.drawLine(tick_x, bar_y + bar_height - 6, tick_x, bar_y + bar_height)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(bar_x, bar_y, bar_width, bar_height)

        painter.setPen(QPen(text_color, 2))
        painter.setFont(self.main_font)
        text_rect = QRect(bar_x, bar_y, bar_width - 8, bar_height)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text)

    def draw_central_warning_box(self, painter: QPainter, warnings_data: dict = None, blink_state: bool = True):
        """Renders centralized aircraft warnings, cautions, and advisories."""
        if warnings_data is None:
            warnings_data = {}

        box_x = self.inner_tick_left + self.shared_padding
        box_width = (self.inner_tick_right - self.inner_tick_left) - (self.shared_padding * 2)

        box_height = 80
        box_y = config.Y_CENTER - 119

        warnings_rect = QRect(box_x, box_y, box_width, box_height)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.bg_color))
        painter.drawRect(warnings_rect)

        border_color = QColor(self.hud_color)
        border_color.setAlpha(50)
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(warnings_rect)

        row_h = box_height // 3

        separator_color = QColor(200, 200, 200, 60)
        painter.setPen(QPen(separator_color, 1))
        painter.drawLine(box_x, box_y + row_h, box_x + box_width, box_y + row_h)
        painter.drawLine(box_x, box_y + row_h * 2, box_x + box_width, box_y + row_h * 2)

        rect_warn = QRect(box_x, box_y, box_width, row_h)
        rect_caut = QRect(box_x, box_y + row_h, box_width, row_h)
        rect_adv = QRect(box_x, box_y + row_h * 2, box_width, row_h)

        painter.setFont(self.main_font)

        warning_txt = warnings_data.get("warning")
        if warning_txt:
            if blink_state:
                painter.setPen(QPen(self.err_color, 2))
                painter.drawText(rect_warn, Qt.AlignmentFlag.AlignCenter, warning_txt)

        caution_txt = warnings_data.get("caution")
        if caution_txt:
            painter.setPen(QPen(QColor(*config.FLAPS_TRANSIT_COLOR), 2))
            painter.drawText(rect_caut, Qt.AlignmentFlag.AlignCenter, caution_txt)

        advisory_txt = warnings_data.get("advisory")
        if advisory_txt:
            painter.setPen(QPen(self.hud_color, 2))
            painter.drawText(rect_adv, Qt.AlignmentAngle if False else Qt.AlignmentFlag.AlignCenter, advisory_txt)

    def draw_g_meter(self, painter: QPainter, g_force: float):
        """Renders the current vertical acceleration (G-force) counter."""
        g_box_width = 78
        g_box_x = self.inner_tick_left + self.shared_padding

        pointer_bottom_y = config.Y_CENTER + 15
        g_box_y = pointer_bottom_y + 10

        g_rect = QRect(g_box_x, g_box_y, g_box_width, 35)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.bg_color))
        painter.drawRect(g_rect)

        if g_force is None:
            painter.setPen(QPen(self.err_color, 2))
            painter.setFont(self.error_font)
            painter.drawText(g_rect, Qt.AlignmentFlag.AlignCenter, "ERR")
            painter.setFont(self.main_font)
        else:
            current_g_color = self.critical_color if (g_force > 7.0 or g_force < -3.0) else self.hud_color
            sign = "-" if g_force < 0 else " "
            g_str = f"{sign}{abs(g_force):.1f} G"

            painter.setPen(QPen(current_g_color, 2))
            painter.drawText(g_rect, Qt.AlignmentFlag.AlignCenter, g_str)

    def draw_mach_indicator(self, painter: QPainter, mach: float):
        """Renders the aircraft's current Mach number indicator."""
        mach_box_width = 78
        mach_box_x = self.inner_tick_left + self.shared_padding

        pointer_bottom_y = config.Y_CENTER + 15
        g_box_y = pointer_bottom_y + 10
        mach_box_y = g_box_y + 35 + 5

        mach_rect = QRect(mach_box_x, mach_box_y, mach_box_width, 30)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.bg_color))
        painter.drawRect(mach_rect)

        if mach is None:
            painter.setPen(QPen(self.err_color, 2))
            painter.setFont(self.error_font)
            painter.drawText(mach_rect, Qt.AlignmentFlag.AlignCenter, "M ERR")
            painter.setFont(self.main_font)
        else:
            painter.setPen(QPen(self.hud_color, 2))
            painter.setFont(self.main_font)
            painter.drawText(mach_rect, Qt.AlignmentFlag.AlignCenter, f"M:{mach:.2f}")

    def draw_aoa_indexer(self, painter: QPainter, aoa: float):
        """Renders the Angle of Attack (AoA) indexer display elements."""
        aoa_box_width = 40
        aoa_box_x = self.inner_tick_right - self.shared_padding - aoa_box_width
        center_x = aoa_box_x + (aoa_box_width // 2)

        pointer_bottom_y = config.Y_CENTER + 15
        tape_bottom_y = config.Y_CENTER + (config.TAPE_HEIGHT // 2)

        aoa_box_y = pointer_bottom_y + 5
        aoa_box_height = tape_bottom_y - aoa_box_y

        aoa_rect = QRect(aoa_box_x, aoa_box_y, aoa_box_width, aoa_box_height)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.bg_color))
        painter.drawRect(aoa_rect)

        if aoa is None:
            painter.setPen(QPen(self.err_color, 2))
            painter.setFont(self.bottom_indicators_font)
            painter.drawText(aoa_rect, Qt.AlignmentFlag.AlignCenter, "ERR")
            painter.setFont(self.main_font)
        else:
            state = 0
            if aoa > 15:
                state = 1
            elif aoa > 10:
                state = 2
            elif aoa > 5:
                state = 3
            elif aoa > 0:
                state = 4
            else:
                state = 5

            def apply_glow(color, active_state, current_state):
                c = QColor(color)
                c.setAlpha(255 if active_state == current_state else 30)
                painter.setBrush(QBrush(c))

            scale_y = aoa_box_height / 160.0

            def scaled_y(original_y):
                return int(aoa_box_y + (original_y * scale_y))

            apply_glow(self.aoa_red, 1, state)
            painter.drawPolygon(QPolygon([
                QPoint(center_x - 12, scaled_y(10)), QPoint(center_x - 6, scaled_y(10)),
                QPoint(center_x, scaled_y(25)), QPoint(center_x + 6, scaled_y(10)),
                QPoint(center_x + 12, scaled_y(10)), QPoint(center_x, scaled_y(35))
            ]))

            pen = QPen(QColor(self.aoa_yellow.red(), self.aoa_yellow.green(), self.aoa_yellow.blue(),
                              255 if state == 2 else 30))
            pen.setWidth(4)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(center_x - 10, scaled_y(45), 20, int(20 * scale_y), 15 * 16, 150 * 16)
            painter.drawArc(center_x - 10, scaled_y(45), 20, int(20 * scale_y), 195 * 16, 150 * 16)
            painter.setPen(Qt.PenStyle.NoPen)

            apply_glow(self.aoa_yellow, 3, state)
            painter.drawPolygon(QPolygon([
                QPoint(center_x - 12, scaled_y(100)), QPoint(center_x - 6, scaled_y(100)),
                QPoint(center_x, scaled_y(85)), QPoint(center_x + 6, scaled_y(100)),
                QPoint(center_x + 12, scaled_y(100)), QPoint(center_x, scaled_y(75))
            ]))

            apply_glow(self.aoa_yellow, 4, state)
            painter.drawPolygon(QPolygon([
                QPoint(center_x, scaled_y(110)),
                QPoint(center_x - 10, scaled_y(130)),
                QPoint(center_x + 10, scaled_y(130))
            ]))

            apply_glow(self.aoa_green, 5, state)
            painter.drawRect(center_x - 12, scaled_y(140), 24, int(8 * scale_y))

    def draw_tas_indicator(self, painter: QPainter, tas: float):
        """Renders the True Airspeed (TAS) digital text indicator."""
        tape_bottom_y = config.Y_CENTER + (config.TAPE_HEIGHT // 2)
        box_y = tape_bottom_y + 10

        center_x = config.X_LEFT_TAPE - (config.TAPE_WIDTH // 2)
        tas_rect = QRect(center_x - 40, box_y, 80, 30)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.bg_color))
        painter.drawRect(tas_rect)

        if tas is None:
            painter.setPen(QPen(self.err_color, 2))
            painter.setFont(self.bottom_indicators_font)
            painter.drawText(tas_rect, Qt.AlignmentFlag.AlignCenter, "TAS ERR")
            painter.setFont(self.main_font)
        else:
            painter.setPen(QPen(self.hud_color, 2))
            painter.setFont(self.bottom_indicators_font)
            painter.drawText(tas_rect, Qt.AlignmentFlag.AlignCenter, f"TAS: {int(tas)}")
            painter.setFont(self.main_font)

    def draw_rad_alt_indicator(self, painter: QPainter, radio_alt: float):
        """Renders the Radar Altimeter (RALT) digital text indicator."""
        tape_bottom_y = config.Y_CENTER + (config.TAPE_HEIGHT // 2)
        box_y = tape_bottom_y + 10

        center_x = config.X_RIGHT_TAPE + (config.TAPE_WIDTH // 2)
        rad_rect = QRect(center_x - 40, box_y, 80, 30)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self.bg_color))
        painter.drawRect(rad_rect)

        painter.setPen(QPen(self.critical_color, 2))
        painter.setFont(self.bottom_indicators_font)
        painter.drawText(rad_rect, Qt.AlignmentFlag.AlignCenter, f"RALT: {int(radio_alt)}")
        painter.setFont(self.main_font)

    def draw_stall_warning(self, painter: QPainter, is_stalling: bool, blink_state: bool):
        """Renders the flashing stall warning banner when critical limits are reached."""
        if not is_stalling or not blink_state:
            return

        box_x = self.inner_tick_left
        box_width = self.inner_tick_right - self.inner_tick_left

        rect_y = config.Y_CENTER - 180
        stall_rect = QRect(box_x, rect_y, box_width, 50)

        stall_font = QFont(config.FONT_FAMILY, 32, QFont.Weight.Black)
        painter.setFont(stall_font)

        painter.setPen(QPen(self.err_color, 3))
        painter.drawText(stall_rect, Qt.AlignmentFlag.AlignCenter, "STALL")
        painter.setFont(self.main_font)

    def draw_weapon_indicators(self, painter: QPainter, ammo_data: list):
        """Renders ammunition counters and weapon status boxes."""
        if not ammo_data:
            return

        box_width = 55
        box_height = 22
        spacing = 8

        num_boxes = len(ammo_data)
        total_width = (num_boxes * box_width) + ((num_boxes - 1) * spacing)

        center_x = (config.X_LEFT_TAPE + config.X_RIGHT_TAPE) // 2
        start_x = center_x - (total_width // 2)

        box_y = config.Y_CENTER - 142
        painter.setFont(self.bottom_indicators_font)

        for i, gun_group in enumerate(ammo_data):
            ammo_count = gun_group.get("ammo", 0)

            rect_x = start_x + i * (box_width + spacing)
            rect = QRect(rect_x, box_y, box_width, box_height)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self.bg_color))
            painter.drawRect(rect)

            border_color = QColor(self.hud_color)
            border_color.setAlpha(80)
            painter.setPen(QPen(border_color, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)

            if ammo_count <= 0:
                painter.setPen(QPen(self.critical_color, 2))
                text = "EMPTY"
            else:
                painter.setPen(QPen(self.hud_color, 2))
                text = str(ammo_count)

            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.setFont(self.main_font)