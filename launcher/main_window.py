"""
main_window.py
--------------
The primary entry point and graphical Launcher for the WT Avionics suite.
Manages user settings, configuration windows, system tray integration,
and deploys the background HUD process alongside the game.
"""

import os
import sys
import subprocess
import urllib.request
import json

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QPushButton,
    QCheckBox, QLabel, QSpacerItem, QSizePolicy,
    QSystemTrayIcon, QMenu, QStyle, QDialog, QApplication, QMessageBox
)
from PySide6.QtGui import QCloseEvent, QAction, QDesktopServices
from PySide6.QtCore import Qt, QUrl

from launcher.settings_manager import load_settings, save_settings
from launcher.presets_view import PresetsWindow
from launcher.my_presets_view import MyPresetsWindow
from launcher.colors_view import ColorsWindow
from launcher.settings_view import SettingsWindow
from launcher.instruction_view import InstructionWindow


class LauncherWindow(QMainWindow):
    """
    Main Launcher interface.
    Controls database parsing, active presets, background task delegation,
    and process management (e.g., executing Steam and the HUD overlay).
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("WT Avionics Launcher")
        self.setFixedSize(400, 550)

        self.settings = load_settings()
        self.hud_process = None
        self._is_quitting = False

        self._init_ui()
        self._init_tray()

        self._check_tesseract_installation()
        self._show_startup_instructions()

    def _show_startup_instructions(self):
        """Display instructions."""
        if not self.settings.get("show_startup_guide", True):
            return
        dialog = InstructionWindow(self)
        dialog.exec()

        if dialog.dont_show_again:
            self.settings["show_startup_guide"] = False

            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            settings_path = os.path.join(base_dir, "data", "launcher_settings.json")

            try:
                with open(settings_path, "w", encoding="utf-8") as f:
                    json.dump(self.settings, f, indent=4)
            except Exception as e:
                print(f"[ERROR] [LAUNCHNER] Failed to save launcher_settings.json: {e}")

    def _init_ui(self):
        """Initializes the main layout and buttons for the Launcher."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(30, 30, 30, 30)

        title_label = QLabel("WT AVIONICS")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title_label.font()
        font.setPointSize(18)
        font.setBold(True)
        title_label.setFont(font)
        main_layout.addWidget(title_label)

        self.chk_silent = QCheckBox("Silent Launch (No Launcher)")
        self.chk_silent.setChecked(self.settings.get("silent_launch", False))
        self.chk_silent.stateChanged.connect(self._on_silent_toggled)
        main_layout.addWidget(self.chk_silent)

        spacer = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        main_layout.addItem(spacer)

        btn_presets = QPushButton("Aircraft & Loadouts")
        btn_presets.setMinimumHeight(35)
        btn_presets.clicked.connect(self._open_presets_window)
        main_layout.addWidget(btn_presets)

        btn_detect = QPushButton("Auto-Detect Aircraft")
        btn_detect.setMinimumHeight(35)
        btn_detect.clicked.connect(self._detect_current_plane)
        main_layout.addWidget(btn_detect)

        btn_my_presets = QPushButton("My Presets")
        btn_my_presets.setMinimumHeight(35)
        btn_my_presets.clicked.connect(self._open_my_presets_window)
        main_layout.addWidget(btn_my_presets)

        btn_colors = QPushButton("UI Colors")
        btn_colors.setMinimumHeight(35)
        btn_colors.clicked.connect(self._open_colors_window)
        main_layout.addWidget(btn_colors)

        btn_settings = QPushButton("Settings")
        btn_settings.setMinimumHeight(35)
        btn_settings.clicked.connect(self._open_settings_window)
        main_layout.addWidget(btn_settings)

        btn_donate = QPushButton("☕ Support the Developer")
        btn_donate.setMinimumHeight(35)
        btn_donate.setStyleSheet("""
                            QPushButton { background-color: #f28c28; color: white; font-weight: bold; }
                            QPushButton:hover { background-color: #e07b22; }
                        """)
        btn_donate.clicked.connect(self._open_donation_link)
        main_layout.addWidget(btn_donate)

        main_layout.addSpacing(15)

        btn_launch = QPushButton("LAUNCH")
        btn_launch.setMinimumHeight(55)
        btn_launch.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold; font-size: 16px;")
        btn_launch.clicked.connect(self.launch)
        main_layout.addWidget(btn_launch)

    def _init_tray(self):
        """Initializes the Windows system tray icon and background context menu."""
        self.tray_icon = QSystemTrayIcon(self)
        standard_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(standard_icon)

        tray_menu = QMenu()

        show_action = QAction("Show Launcher", self)
        show_action.triggered.connect(self.show_normal)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit Application", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def _check_tesseract_installation(self):
        """
        Verifies that Tesseract OCR is installed at the expected default path.
        Warns the user if the executable is missing, preventing silent OCR failures later.
        """
        tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if not os.path.exists(tesseract_path):
            QMessageBox.warning(
                self,
                "Missing Dependency: Tesseract OCR",
                f"Tesseract OCR was not found at the expected location:\n"
                f"{tesseract_path}\n\n"
                "The HUD requires Tesseract to read weapon seekers accurately. "
                "Please run the included 'tesseract-ocr-setup.exe' installer, "
                "keep the default installation path, and restart WT Avionics."
            )

    def _on_silent_toggled(self, state):
        """Saves the silent launch preference to the settings file."""
        self.settings["silent_launch"] = self.chk_silent.isChecked()
        save_settings(self.settings)

    def _open_presets_window(self):
        """Opens the full aircraft database explorer."""
        dialog = PresetsWindow(self)
        dialog.exec()

    def _detect_current_plane(self):
        """
        Attempts to automatically detect the currently active aircraft by pinging
        the '/indicators' API endpoint, which remains active even in the hangar.
        """
        try:
            response = urllib.request.urlopen("http://127.0.0.1:8111/indicators", timeout=1)
            data = json.loads(response.read().decode('utf-8'))

            plane_tag = data.get("type", "")

            if plane_tag:
                dialog = PresetsWindow(self)

                if plane_tag in dialog.database:
                    dialog.jump_to_plane(plane_tag)
                    dialog.exec()
                else:
                    QMessageBox.warning(
                        self,
                        "Aircraft Not Found",
                        f"Detected aircraft ID '{plane_tag}', but it is missing from the database.\n"
                        "This aircraft might not be supported yet."
                    )
            else:
                QMessageBox.warning(
                    self,
                    "Detection Failed",
                    "No aircraft ID detected in the API.\nTry selecting the vehicle again in the hangar."
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Connection Error",
                "Could not connect to War Thunder API.\nIs the game running?\n\nDetails: " + str(e)
            )

    def _open_my_presets_window(self):
        """Opens the user's custom loadout manager."""
        dialog = MyPresetsWindow(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_plane_tag:
            preset_dialog = PresetsWindow(self)
            preset_dialog.jump_to_plane(dialog.selected_plane_tag)
            preset_dialog.exec()

    def _open_colors_window(self):
        """Opens the HUD color configuration dialog."""
        dialog = ColorsWindow(self)
        dialog.exec()

    def _open_settings_window(self):
        """Opens the general settings dialog."""
        dialog = SettingsWindow(self)
        dialog.exec()

    def _open_donation_link(self):
        """Opens the default web browser to the project's donation page."""
        url = QUrl("https://ko-fi.com/alice_kojima")
        QDesktopServices.openUrl(url)

    def _is_game_running(self):
        """Verifies if the game's local API server is currently responding."""
        try:
            urllib.request.urlopen("http://127.0.0.1:8111/", timeout=1)
            return True
        except Exception:
            return False

    def _start_background_hud(self):
        """
        Spawns the HUD overlay process independently using the subprocess module.
        Smartly handles both raw Python and compiled .exe environments using the --overlay flag.
        """
        if self.hud_process is not None and self.hud_process.poll() is None:
            print("[INFO] [LAUNCHER] HUD is already running.")
            return

        try:
            env = os.environ.copy()

            if getattr(sys, 'frozen', False):
                # Compiled executable mode (.exe)
                cmd = [sys.executable, "--overlay"]
                cwd = os.path.dirname(sys.executable)
            else:
                # Development mode (Raw Python script)
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                main_script = os.path.join(base_dir, 'main.py')
                cmd = [sys.executable, main_script, "--overlay"]
                cwd = base_dir
                env["PYTHONPATH"] = base_dir

            self.hud_process = subprocess.Popen(cmd, cwd=cwd, env=env)
            print("[INFO] [LAUNCHER] Background HUD deployed successfully.")
        except Exception as e:
            print(f"[ERROR] [LAUNCHER] Critical failure during HUD deployment: {e}")

    def launch(self):
        """
        Executes the main launch sequence: hides the launcher, spawns the HUD,
        and optionally boots the game via Steam protocol if it is not already running.
        """
        self.hide()
        print("[INFO] [LAUNCHER] Initialization sequence started...")

        self._start_background_hud()

        if self._is_game_running():
            print("[INFO] [LAUNCHER] War Thunder is already running. Launching HUD only.")
        else:
            print("[INFO] [LAUNCHER] Game not detected. Dispatching signal to Steam...")
            try:
                os.startfile("steam://run/236390")
            except Exception as e:
                print(f"[ERROR] [LAUNCHER] Steam execution failed: {e}")

    def show_normal(self):
        """Restores the launcher window from the system tray."""
        self.show()
        self.activateWindow()

    def quit_app(self):
        """Terminates the launcher and forcibly kills the child HUD process if active."""
        self._is_quitting = True

        if self.hud_process is not None and self.hud_process.poll() is None:
            print("[INFO] [LAUNCHER] Terminating background HUD process...")
            self.hud_process.kill()
            self.hud_process.wait()

        self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent):
        """Overrides the standard window close behavior to minimize to tray instead."""
        if not self._is_quitting:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "WT Avionics",
                "Launcher is running in the background.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
        else:
            event.accept()
