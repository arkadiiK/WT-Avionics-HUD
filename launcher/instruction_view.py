"""
instruction_view.py
--------------------
Displays a startup instruction manual
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton, QCheckBox
from PySide6.QtCore import Qt


class InstructionWindow(QDialog):
    """
    A popup dialog window that shows the instruction
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Quick Start Guide')
        self.setFixedSize(450, 700)

        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self.dont_show_again = False

        self._init_ui()

    def _init_ui(self):
        """Initializes the text area and buttons"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.text_box = QTextBrowser()
        self.text_box.setOpenExternalLinks(True)

        self.text_box.setHtml(
            "<h2 style='text-align: center; color: #0079C1;'>Welcome to WT Avionics!</h2>"
            "<p style='font-size: 14px; text-align: center;'>Thank you for downloading—your support means a lot to me! ❤️</p>"

            "<h3 style='color: #333; margin-top: 15px;'>⚠️ Important Notes</h3>"
            "<ul style='font-size: 13px; line-height: 1.6;'>"
            "<li><b>Compatibility:</b> This app is designed exclusively for <b>Jet Aircraft</b>.</li>"
            "<li><b>Radio Altitude:</b> Some aircraft do not output radio altitude telemetry natively. For those that do, the indicator will only appear on your HUD when your altitude is <b>below 50 meters</b>.</li>"
            "<li><b>Fuel Consumption:</b> Fuel flow telemetry can vary by aircraft, causing the remaining time indicator to fluctuate slightly (though it remains broadly accurate).</li>"
            "<li><b>Feedback & Support:</b> You might encounter occasional bugs. If you do, please report them on <a href='https://live.warthunder.com/profile/persistent/9sTP1ltuc/' style='color: #0079C1;'>live.warthunder</a> or reach out via <a href='https://discord.gg/BzBGThseEc' style='color: #0079C1;'>Discord</a>.</li>"
            "</ul>"

            "<h3 style='color: #333; margin-top: 15px;'>🛠️ Quick Start Guide</h3>"
            "<ul style='font-size: 13px; line-height: 1.6;'>"
            "<li><b>In-Game Setup:</b> For the best experience, turn off the default game HUD. Go to <i>Options &rarr; Battle Interface &rarr; HUD &rarr; Minimal</i>.</li>"
            "<li><b>Silent Launch:</b> Enable the top checkbox to bypass the main menu in the future. The app will boot quietly in the background and launch the game automatically.</li>"
            "<li><b>Aircraft Loadouts:</b> Select your country and search for your plane. Use the right-side menu to configure your weapon preset to match your in-game loadout. Save it and set it as your main preset.</li>"
            "<li><b>Auto Detection:</b> Instantly opens the preset configuration for the aircraft you are currently using in-game (works in the hangar as well).</li>"
            "<li><b>My Presets:</b> View and manage all your saved aircraft loadouts.</li>"
            "<li><b>UI Colors:</b> Customize the HUD colors to fit your visual preferences.</li>"
            "<li><b>Settings:</b> Rebind your hotkeys and adjust general preferences (WIP).</li>"
            "</ul>"

            "<p style='font-size: 13px; margin-top: 15px;'>"
            "<b>Support the Project:</b> The orange button is for those who enjoy the app and want to support its development!<br><br>"
            "Once everything is configured, just press the <b>LAUNCH</b> button to start the game. You can always return to this menu by clicking the WT Avionics icon in your Windows System Tray."
            "</p>"
        )
        layout.addWidget(self.text_box)

        self.checkbox_dont_show = QCheckBox("Don't Show Again")
        self.checkbox_dont_show.setStyleSheet("font-size: 13px; color: #333333;")
        self.checkbox_dont_show.toggled.connect(self._on_checkbox_toggled)
        layout.addWidget(self.checkbox_dont_show)

        btn_ok = QPushButton('Got it!')
        btn_ok.setMinimumHeight(35)
        btn_ok.setStyleSheet(
            "QPushButton { background-color: #0079c1; color: white; font-weight: bold; font-size: 14px;}"
            "QPushButton:hover {background-color: #005a93;}"
        )

        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)

    def _on_checkbox_toggled(self, checked: bool):
        """
        Updates the internal state based on checkbox interaction.

        Args:
            checked (bool): The current state of the checkbox.
        """
        self.dont_show_again = checked
