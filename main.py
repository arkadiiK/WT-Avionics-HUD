"""
main.py
-------
The primary entry point for the WT Avionics application.
Initializes the Qt application, checks user settings for silent launch preferences,
and routes execution to either the Launcher or the HUD Overlay based on arguments.
"""

import sys
import signal
from PySide6.QtWidgets import QApplication


def main():
    """
    Initializes the application environment.
    Uses argument routing to cleanly switch between Launcher mode and Overlay mode,
    ensuring compatibility with PyInstaller compiled executables.
    """
    # --- SMART ENTRY POINT SWITCH ---
    # If the process is spawned with the --overlay flag, bypass the launcher and run the HUD.
    if "--overlay" in sys.argv:
        from gui.overlay import run_overlay
        run_overlay()
        return

    # Standard Launcher execution path
    from launcher.main_window import LauncherWindow
    from launcher.settings_manager import load_settings

    app = QApplication(sys.argv)

    launcher = LauncherWindow()
    settings = load_settings()

    if settings.get("silent_launch", False):
        print("[INFO] [MAIN] Silent Launch active. Skipping main window.")
        launcher.launch()
    else:
        launcher.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    # Ensure the application terminates immediately upon receiving an interrupt signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()