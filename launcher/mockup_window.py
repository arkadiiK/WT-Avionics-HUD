"""Module for rendering the real HUD layout in live scale preview mode."""

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QApplication, QWidget

import config
from gui.instruments import InstrumentRenderer
from gui.sms_indicator import SMSIndicator


class HudMockupOverlay(QWidget):
    """Transparent fullscreen overlay using real HUD renderers for preview."""

    MOCK_LOADOUT = {
        "1": "AIM-9L",
        "3": "AIM-7M",
        "5": "AIM-7M",
        "7": "Drop tank",
        "9": "AIM-7M",
        "11": "AIM-7M",
        "13": "AIM-9L",
    }
    MOCK_WARNINGS = {
        "warning": "OVERSPEED",
        "caution": "CHK SPD",
        "advisory": "AIRBRAKE",
    }
    MOCK_AMMO = [{"ammo": 512}]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.telemetry_scale: float = 1.0
        self.sms_scale: float = 1.0

        self.renderer = InstrumentRenderer()
        self.sms_renderer = SMSIndicator()

        self._init_window()

    def _init_window(self) -> None:
        """Configure window flags and fullscreen geometry."""
        window_flags = (
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
                | Qt.WindowType.WindowTransparentForInput
        )
        self.setWindowFlags(window_flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geometry)

    def set_telemetry_scale(self, scale_percent: int) -> None:
        """Update telemetry scale factor from slider percentage."""
        self.telemetry_scale = scale_percent / 100.0
        self.update()

    def set_sms_scale(self, scale_percent: int) -> None:
        """Update SMS panel scale factor from slider percentage."""
        self.sms_scale = scale_percent / 100.0
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Render the actual HUD instruments and SMS panel with scaling."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        self._draw_scaled_telemetry(painter)
        self._draw_scaled_sms(painter)

        painter.end()

    def _draw_scaled_telemetry(self, painter: QPainter) -> None:
        """Render all telemetry instruments scaled from top-left anchor."""
        anchor_x = float(config.X_LEFT_TAPE - config.TAPE_WIDTH)
        anchor_y = float(config.Y_CENTER - (config.TAPE_HEIGHT // 2) - 35)

        painter.save()
        painter.translate(QPointF(anchor_x, anchor_y))
        painter.scale(self.telemetry_scale, self.telemetry_scale)
        painter.translate(QPointF(-anchor_x, -anchor_y))

        painter.setFont(self.renderer.main_font)

        self.renderer.draw_tape(
            painter,
            config.X_LEFT_TAPE,
            config.Y_CENTER,
            config.TAPE_HEIGHT,
            1080.0,
            15.0,
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
            3250.0,
            -10.0,
            False,
            config.STEP_MAIN_ALT,
            config.STEP_MINOR_ALT,
            config.SCALE_ALT,
            config.TREND_SCALE_ALT,
        )

        self.renderer.draw_central_warning_box(
            painter, self.MOCK_WARNINGS, True
        )
        self.renderer.draw_stall_warning(painter, True, True)
        self.renderer.draw_throttle_bar(painter, 105.0, True, True, False)
        self.renderer.draw_g_meter(painter, 4.5)
        self.renderer.draw_mach_indicator(painter, 0.94)
        self.renderer.draw_aoa_indexer(painter, 8.5)
        self.renderer.draw_tas_indicator(painter, 1150.0)
        self.renderer.draw_rad_alt_indicator(painter, 42.0)
        self.renderer.draw_weapon_indicators(painter, self.MOCK_AMMO)

        self._draw_flaps_preview(painter)

        painter.restore()

    def _draw_flaps_preview(self, painter: QPainter) -> None:
        """Render the flaps indicator at its exact telemetry position."""
        flaps_x = config.X_RIGHT_TAPE + 120
        flaps_y = config.Y_CENTER - 190

        painter.save()
        painter.translate(flaps_x, flaps_y)

        color_green = QColor(*config.HUD_COLOR)
        color_bg = QColor(*config.BG_COLOR)

        pen = QPen(color_green)
        pen.setWidthF(2)
        painter.setPen(pen)

        center_y = 42
        start_x = 42
        wing_length = 84
        painter.drawLine(start_x, center_y, start_x + wing_length, center_y)

        painter.drawRect(start_x - 21, center_y - 7, 14, 14)
        painter.fillRect(start_x - 21, center_y - 7, 14, 14, color_green)

        for i in range(2):
            box_x = start_x + wing_length + 7 + (i * 21)
            painter.drawRect(box_x, center_y - 7, 14, 14)
            if i == 0:
                painter.fillRect(box_x, center_y - 7, 14, 14, color_green)

        rect_y = center_y + 25
        text_box_x = start_x - 20
        text_box_width = wing_length + 80
        text_box_height = 35

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color_bg)
        painter.drawRect(text_box_x, rect_y, text_box_width, text_box_height)

        painter.setPen(color_green)
        painter.setFont(QFont(config.FONT_FAMILY, 14, QFont.Weight.Bold))
        text_rect = QRect(text_box_x, rect_y, text_box_width, text_box_height)
        painter.drawText(
            text_rect, Qt.AlignmentFlag.AlignCenter, "COMBAT"
        )

        painter.restore()

    def _draw_scaled_sms(self, painter: QPainter) -> None:
        """Render the SMS weapon panel scaled from top-right anchor."""
        sms_x = float(self.rect().width() - 320)
        sms_y = float(self.rect().height() / 2 - 300)

        anchor_x = sms_x + 265.0
        anchor_y = sms_y - 75.0

        painter.save()
        painter.translate(QPointF(anchor_x, anchor_y))
        painter.scale(self.sms_scale, self.sms_scale)
        painter.translate(QPointF(-anchor_x, -anchor_y))

        seeker_state = {"color": config.HUD_COLOR, "blink": False}

        self.sms_renderer.draw(
            painter=painter,
            center_x=sms_x,
            center_y=sms_y,
            active_loadout=self.MOCK_LOADOUT,
            selected_weapon="AIM-7M",
            seeker_state=seeker_state,
            global_blink=True,
            active_pylons=[3],
            fuel_mass=1837,
            fuel_time_sec=802,
            flares=60,
            chaff=120,
        )

        painter.restore()
