from PySide6 import QtCore
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QLabel
)
from PySide6.QtCore import Qt
from launcher.keybinds_view import KeybindsWindow


class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(300, 500)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        title = QLabel("Settings")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        btn_keybinds = QPushButton("Keybinds")
        btn_keybinds.setMinimumHeight(40)
        btn_keybinds.clicked.connect(self._open_keybinds)
        layout.addWidget(btn_keybinds)

        btn_telemetry = QPushButton("Telemetry Settings (WIP)")
        btn_telemetry.setMinimumHeight(40)
        btn_telemetry.setEnabled(False)
        layout.addWidget(btn_telemetry)

        layout.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setMinimumHeight(35)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def _open_keybinds(self):
        dialog = KeybindsWindow(self)
        dialog.exec()
