"""Module for the HUD layout and scale configuration dialog."""

import json
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from launcher.mockup_window import HudMockupOverlay


class HudLayoutWindow(QDialog):
    """Dialog window for adjusting and saving telemetry and SMS scales."""

    MIN_SCALE = 50
    MAX_SCALE = 150
    DEFAULT_SCALE = 100
    SETTINGS_FILENAME = "launcher_settings.json"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("HUD Layout & Scale")
        self.setFixedSize(350, 250)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.settings_path = self._get_settings_path()
        saved_telemetry, saved_sms = self._load_scale_settings()

        self.mockup_overlay = HudMockupOverlay()
        self.mockup_overlay.set_telemetry_scale(saved_telemetry)
        self.mockup_overlay.set_sms_scale(saved_sms)
        self.mockup_overlay.show()

        self._init_ui(saved_telemetry, saved_sms)
        self.finished.connect(self._close_overlay)

    def _get_settings_path(self) -> str:
        """Resolve the absolute path to the launcher settings JSON file."""
        base_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
        return os.path.join(base_dir, "data", self.SETTINGS_FILENAME)

    def _load_scale_settings(self) -> tuple[int, int]:
        """Load saved telemetry and SMS scale percentages from JSON."""
        if not os.path.exists(self.settings_path):
            return self.DEFAULT_SCALE, self.DEFAULT_SCALE

        try:
            with open(self.settings_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            telemetry_val = int(
                data.get("telemetry_scale", self.DEFAULT_SCALE)
            )
            sms_val = int(data.get("sms_scale", self.DEFAULT_SCALE))

            telemetry_val = max(
                self.MIN_SCALE, min(telemetry_val, self.MAX_SCALE)
            )
            sms_val = max(self.MIN_SCALE, min(sms_val, self.MAX_SCALE))
            return telemetry_val, sms_val
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"[WARNING] [LAUNCHER] Failed to load HUD scale: {exc}")
            return self.DEFAULT_SCALE, self.DEFAULT_SCALE

    def _save_scale_settings(self) -> None:
        """Save current slider values to JSON while preserving other keys."""
        data = {}
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as file:
                    loaded = json.load(file)
                    if isinstance(loaded, dict):
                        data = loaded
            except (OSError, json.JSONDecodeError) as exc:
                print(
                    f"[WARNING] [LAUNCHER] Could not read existing "
                    f"settings: {exc}"
                )

        data["telemetry_scale"] = self.slider_telemetry.value()
        data["sms_scale"] = self.slider_sms.value()

        try:
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4)
        except OSError as exc:
            print(f"[ERROR] [LAUNCHER] Failed to save HUD scale: {exc}")

    def _init_ui(self, telemetry_scale: int, sms_scale: int) -> None:
        """Initialize UI components and set initial slider values."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        title = QLabel("Adjust HUD Scale")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # Telemetry Scale Slider
        telemetry_layout = QVBoxLayout()
        self.lbl_telemetry = QLabel(f"Telemetry Scale: {telemetry_scale}%")
        self.slider_telemetry = QSlider(Qt.Orientation.Horizontal)
        self.slider_telemetry.setRange(self.MIN_SCALE, self.MAX_SCALE)
        self.slider_telemetry.setValue(telemetry_scale)
        self.slider_telemetry.valueChanged.connect(
            self._on_telemetry_scale_changed
        )

        telemetry_layout.addWidget(self.lbl_telemetry)
        telemetry_layout.addWidget(self.slider_telemetry)
        layout.addLayout(telemetry_layout)

        # SMS (Weapon) Scale Slider
        sms_layout = QVBoxLayout()
        self.lbl_sms = QLabel(f"Weapon Panel Scale: {sms_scale}%")
        self.slider_sms = QSlider(Qt.Orientation.Horizontal)
        self.slider_sms.setRange(self.MIN_SCALE, self.MAX_SCALE)
        self.slider_sms.setValue(sms_scale)
        self.slider_sms.valueChanged.connect(self._on_sms_scale_changed)

        sms_layout.addWidget(self.lbl_sms)
        sms_layout.addWidget(self.slider_sms)
        layout.addLayout(sms_layout)

        layout.addStretch()

        # Action Buttons Layout
        button_layout = QHBoxLayout()

        btn_reset = QPushButton("Reset")
        btn_reset.setMinimumHeight(35)
        btn_reset.clicked.connect(self._on_reset_clicked)

        btn_save = QPushButton("Save & Close")
        btn_save.setMinimumHeight(35)
        btn_save.clicked.connect(self._on_save_clicked)

        button_layout.addWidget(btn_reset)
        button_layout.addWidget(btn_save)

        layout.addLayout(button_layout)

    def _on_telemetry_scale_changed(self, value: int) -> None:
        """Handle telemetry slider changes and update mockup."""
        self.lbl_telemetry.setText(f"Telemetry Scale: {value}%")
        self.mockup_overlay.set_telemetry_scale(value)

    def _on_sms_scale_changed(self, value: int) -> None:
        """Handle SMS panel slider changes and update mockup."""
        self.lbl_sms.setText(f"Weapon Panel Scale: {value}%")
        self.mockup_overlay.set_sms_scale(value)

    def _on_reset_clicked(self) -> None:
        """Reset both scale sliders to their default values."""
        self.slider_telemetry.setValue(self.DEFAULT_SCALE)
        self.slider_sms.setValue(self.DEFAULT_SCALE)

    def _on_save_clicked(self) -> None:
        """Save scale settings and close the dialog."""
        self._save_scale_settings()
        self.accept()

    def _close_overlay(self) -> None:
        """Safely close and destroy the mockup overlay window."""
        if self.mockup_overlay.isVisible():
            self.mockup_overlay.close()
            self.mockup_overlay.deleteLater()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Ensure overlay is closed when dialog window is closed."""
        self._close_overlay()
        super().closeEvent(event)