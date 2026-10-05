"""
build.py
--------
Automates the packaging of the WT Avionics project into a standalone executable.
Utilizes PyInstaller and temporarily isolates local developer configurations
so they are completely excluded from the build process.
"""

import PyInstaller.__main__
import os
import shutil

CONFIG_FILES = [
    "favorites.json",
    "keybinds.json",
    "user_presets.json",
    "launcher_settings.json"
]

def clean_build_dirs():
    """Removes obsolete build and distribution directories before compilation."""
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                print(f"[INFO] [BUILD] Removed obsolete '{folder}' directory.")
            except Exception as e:
                print(f"[ERROR] [BUILD] Failed to remove '{folder}': {e}")

def backup_personal_configs():
    """Temporarily moves personal config files out of the data folder before building."""
    if not os.path.exists("temp_backup"):
        os.makedirs("temp_backup")

    for file_name in CONFIG_FILES:
        src = os.path.join("data", file_name)
        dst = os.path.join("temp_backup", file_name)
        if os.path.exists(src):
            shutil.move(src, dst)
            print(f"[INFO] [BUILD] Temporarily backed up: {file_name}")

def restore_personal_configs():
    """Restores personal config files back to the data folder after building."""
    if os.path.exists("temp_backup"):
        for file_name in CONFIG_FILES:
            src = os.path.join("temp_backup", file_name)
            dst = os.path.join("data", file_name)
            if os.path.exists(src):
                shutil.move(src, dst)
                print(f"[INFO] [BUILD] Restored: {file_name}")

        try:
            os.rmdir("temp_backup")
        except OSError:
            pass

def build_app():
    """Executes the PyInstaller sequence safely by isolating user configs."""
    clean_build_dirs()

    print("[INFO] [BUILD] Preparing files...")
    backup_personal_configs()

    try:
        print("[INFO] [BUILD] Launching PyInstaller...")
        PyInstaller.__main__.run([
            'main.py',
            '--name=WT_Avionics',
            '--windowed',
            '--noconfirm',
            '--clean',
            '--add-data=data;data',
            '--add-data=assets;assets',
        ])
        print("[INFO] [BUILD] PyInstaller compilation finished successfully.")
    finally:
        restore_personal_configs()

    print("[INFO] [BUILD] Release package is ready in the 'dist/WT_Avionics' directory.")


if __name__ == "__main__":
    build_app()