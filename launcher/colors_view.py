"""
colors_view.py
--------------
Provides a graphical user interface (GUI) dialog for customizing HUD colors.
Allows users to pick RGB/RGBA values for various HUD elements and saves them to the global settings.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QColorDialog, QFrame
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from launcher.settings_manager import load_settings, save_settings


class ColorsWindow(QDialog):
    """
    Dialog window for configuring and persisting HUD interface colors.
    Includes functionality to pick new colors via native OS dialogs and reset to factory defaults.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HUD Colors Configuration")
        self.setFixedSize(420, 300)

        self.settings = load_settings()

        # Reference (default) colors for the reset functionality
        self.default_colors = {
            "HUD_COLOR": [0, 255, 50],
            "BG_COLOR": [0, 0, 0, 100],
            "TREND_COLOR": [255, 255, 0],
            "FLAPS_TRANSIT_COLOR": [255, 165, 0],
            "ERR_COLOR": [255, 30, 30]
        }

        # Load current colors from settings, falling back to defaults if missing
        self.colors = {
            "HUD_COLOR": self.settings.get("HUD_COLOR", self.default_colors["HUD_COLOR"]),
            "BG_COLOR": self.settings.get("BG_COLOR", self.default_colors["BG_COLOR"]),
            "TREND_COLOR": self.settings.get("TREND_COLOR", self.default_colors["TREND_COLOR"]),
            "FLAPS_TRANSIT_COLOR": self.settings.get("FLAPS_TRANSIT_COLOR", self.default_colors["FLAPS_TRANSIT_COLOR"]),
            "ERR_COLOR": self.settings.get("ERR_COLOR", self.default_colors["ERR_COLOR"])
        }

        self.color_frames = {}
        self._init_ui()

    def _init_ui(self):
        """Initializes the layout and populates the dialog with color picker rows."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._add_color_picker(layout, "Main Text (HUD_COLOR)", "HUD_COLOR")
        self._add_color_picker(layout, "Background (BG_COLOR)", "BG_COLOR", allow_alpha=True)
        self._add_color_picker(layout, "Trend Vectors (TREND_COLOR)", "TREND_COLOR")
        self._add_color_picker(layout, "Transit/Search (TRANSIT)", "FLAPS_TRANSIT_COLOR")
        self._add_color_picker(layout, "Lock/Error (ERR_COLOR)", "ERR_COLOR")

        layout.addStretch()

        btn_layout = QHBoxLayout()

        btn_save = QPushButton("Save & Apply")
        btn_save.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.save_colors)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _add_color_picker(self, parent_layout, label_text, setting_key, allow_alpha=False):
        """
        Creates a UI row containing a label, color preview frame, and control buttons.

        Args:
            parent_layout (QVBoxLayout): The parent layout to append this row to.
            label_text (str): The display name for the setting.
            setting_key (str): The internal dictionary key for the color setting.
            allow_alpha (bool): Whether to enable opacity/alpha channel selection.
        """
        row = QHBoxLayout()

        label = QLabel(label_text)
        label.setMinimumWidth(160)

        # Color preview square
        color_preview = QFrame()
        color_preview.setFixedSize(30, 30)
        color_preview.setStyleSheet(self._get_stylesheet(self.colors[setting_key]))
        self.color_frames[setting_key] = color_preview

        # Pick color button
        btn_pick = QPushButton("Pick")
        btn_pick.setFixedWidth(60)
        btn_pick.clicked.connect(lambda: self._pick_color(setting_key, allow_alpha))

        # Reset to default button
        btn_reset = QPushButton("Reset")
        btn_reset.setFixedWidth(60)
        btn_reset.clicked.connect(lambda: self._reset_color(setting_key))

        row.addWidget(label)
        row.addStretch()
        row.addWidget(color_preview)
        row.addWidget(btn_pick)
        row.addWidget(btn_reset)

        parent_layout.addLayout(row)

    def _get_stylesheet(self, color_list):
        """
        Generates the CSS stylesheet string for the color preview frame.

        Args:
            color_list (list): A list of integers representing RGB or RGBA values.

        Returns:
            str: The formatted CSS string.
        """
        if len(color_list) == 4:
            return f"background-color: rgba({color_list[0]}, {color_list[1]}, {color_list[2]}, {color_list[3]}); border: 1px solid #777;"
        return f"background-color: rgb({color_list[0]}, {color_list[1]}, {color_list[2]}); border: 1px solid #777;"

    def _pick_color(self, setting_key, allow_alpha):
        """
        Opens the native OS color picker dialog and updates the selected color.

        Args:
            setting_key (str): The internal dictionary key for the color setting.
            allow_alpha (bool): Determines if the alpha channel selection UI should be shown.
        """
        initial_color = QColor(*self.colors[setting_key])
        options = QColorDialog.ColorDialogOption.ShowAlphaChannel if allow_alpha else QColorDialog.ColorDialogOption(0)
        color = QColorDialog.getColor(initial_color, self, "Select Color", options=options)

        if color.isValid():
            if allow_alpha:
                self.colors[setting_key] = [color.red(), color.green(), color.blue(), color.alpha()]
            else:
                self.colors[setting_key] = [color.red(), color.green(), color.blue()]

            self.color_frames[setting_key].setStyleSheet(self._get_stylesheet(self.colors[setting_key]))

    def _reset_color(self, setting_key):
        """
        Restores a specific color setting to its default factory value.

        Args:
            setting_key (str): The internal dictionary key for the color setting.
        """
        # list() is used to create a copy, preventing accidental mutation of the default dictionary
        self.colors[setting_key] = list(self.default_colors[setting_key])
        self.color_frames[setting_key].setStyleSheet(self._get_stylesheet(self.colors[setting_key]))

    def save_colors(self):
        """Commits the selected colors to the settings manager and closes the dialog."""
        for k, v in self.colors.items():
            self.settings[k] = v

        save_settings(self.settings)
        self.accept()