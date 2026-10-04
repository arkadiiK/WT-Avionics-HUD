"""
build.py
--------
Automates the packaging of the WT Avionics project into a standalone executable.
Utilizes PyInstaller and includes a post-build cleanup step to ensure
local developer configurations are not distributed to end-users.
"""

import PyInstaller.__main__
import os
import shutil


def clean_build_dirs():
    """Removes obsolete build and distribution directories before compilation."""
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                print(f"[INFO] [BUILD] Removed obsolete '{folder}' directory.")
            except Exception as e:
                print(f"[ERROR] [BUILD] Failed to remove '{folder}': {e}")


def post_build_cleanup():
    """
    Deletes local developer configurations from the final release build.
    Ensures that end-users receive a fresh, default state application.
    """
    files_to_remove = [
        "favorites.json",
        "keybinds.json",
        "user_presets.json",
        "launcher_settings.json"
    ]

    dist_data_dir = os.path.join("dist", "WT_Avionics", "data")

    if os.path.exists(dist_data_dir):
        for file_name in files_to_remove:
            file_path = os.path.join(dist_data_dir, file_name)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"[INFO] [BUILD] Purged personal configuration: {file_name}")
                except Exception as e:
                    print(f"[ERROR] [BUILD] Failed to remove {file_name}: {e}")


def build_app():
    """Executes the PyInstaller sequence and triggers post-build cleanup."""
    clean_build_dirs()
    print("[INFO] [BUILD] Initialization started. Launching PyInstaller...")

    PyInstaller.__main__.run([
        'main.py',                           # Primary entry point
        '--name=WT_Avionics',                # Name of the output executable
        '--windowed',                        # Suppress the console window (GUI mode)
        '--noconfirm',                       # Automatically overwrite existing builds
        '--clean',                           # Clear PyInstaller cache before building

        # Bundle internal directories (format: 'source;destination')
        '--add-data=data;data',
        '--add-data=assets;assets',
    ])

    print("[INFO] [BUILD] PyInstaller compilation finished successfully.")

    # Execute cleanup immediately after a successful build
    post_build_cleanup()

    print("[INFO] [BUILD] Release package is ready in the 'dist/WT_Avionics' directory.")


if __name__ == "__main__":
    build_app()