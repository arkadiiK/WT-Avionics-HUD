"""
screen_reader.py
----------------
Captures specific screen regions and performs Optical Character Recognition (OCR).
Used to read the UI state of weapon seekers (e.g., 'TRACKING', 'SEEKER: ON') in real-time.
"""

import time
import cv2
import mss
import numpy as np
import pytesseract
from PySide6.QtCore import QThread, Signal

# Define the path to the Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


class ScreenReader(QThread):
    """
    A background thread that continuously captures a dynamically scaled Region of Interest (ROI),
    processes the image using OpenCV, and extracts text using Tesseract OCR.
    Emits a signal whenever the extracted text changes.
    """
    text_read = Signal(str)

    # Reference resolution and ROI captured on a 2560x1440 display
    BASE_WIDTH = 2560
    BASE_HEIGHT = 1440
    BASE_ROI = {"top": 1097, "left": 691, "width": 789, "height": 155}

    # Target pixel height before passing the crop to Tesseract (155px * 2 on 1440p)
    TARGET_OCR_HEIGHT = 310

    def __init__(self):
        super().__init__()
        self.running = True
        self.last_text = ""
        self.roi: dict[str, int] = {}

    def _calculate_roi(self, monitor: dict[str, int]) -> dict[str, int]:
        """
        Calculates the ROI dynamically using bottom-center anchor scaling
        to support different monitor resolutions and aspect ratios (16:9, 16:10, 21:9).
        """
        screen_w = monitor["width"]
        screen_h = monitor["height"]
        scale = screen_h / self.BASE_HEIGHT

        # Offsets relative to the bottom-center anchor on the reference display
        base_center_x = self.BASE_WIDTH / 2.0
        offset_from_center_x = self.BASE_ROI["left"] - base_center_x
        offset_from_bottom_y = self.BASE_HEIGHT - self.BASE_ROI["top"]

        width = max(1, round(self.BASE_ROI["width"] * scale))
        height = max(1, round(self.BASE_ROI["height"] * scale))
        left = monitor["left"] + round((screen_w / 2.0) + (offset_from_center_x * scale))
        top = monitor["top"] + round(screen_h - (offset_from_bottom_y * scale))

        # Clamp coordinates to stay strictly within primary monitor bounds
        left = max(monitor["left"], min(left, monitor["left"] + screen_w - width))
        top = max(monitor["top"], min(top, monitor["top"] + screen_h - height))

        return {
            "top": top,
            "left": left,
            "width": width,
            "height": height,
        }

    def run(self):
        """
        Main execution loop for the thread.
        Captures the screen, applies image processing, and runs OCR at ~50 Hz.
        """
        # Using a safe and stable configuration for PyTesseract (Assume a single uniform block of text)
        tess_config = '--psm 6'

        with mss.mss() as sct:
            # sct.monitors[1] targets the primary display
            primary_monitor = sct.monitors[1]
            self.roi = self._calculate_roi(primary_monitor)

            while self.running:
                start_time = time.time()
                try:
                    sct_img = sct.grab(self.roi)
                    img = np.array(sct_img)

                    # Image processing for consistent OCR accuracy across resolutions
                    gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
                    ocr_scale = self.TARGET_OCR_HEIGHT / gray.shape[0]
                    gray = cv2.resize(
                        gray,
                        None,
                        fx=ocr_scale,
                        fy=ocr_scale,
                        interpolation=cv2.INTER_CUBIC,
                    )
                    _, thresh = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY_INV)

                    # Extract text, strip whitespace, and normalize to lowercase
                    text = pytesseract.image_to_string(thresh, config=tess_config).strip().lower()

                    if text != self.last_text:
                        self.text_read.emit(text)
                        self.last_text = text

                except Exception as e:
                    print(f"[ERROR] [SCREEN READER] Loop failed: {e}")

                # Aggressive timing optimization targeting ~50 checks per second
                elapsed = time.time() - start_time
                sleep_time = max(0.02 - elapsed, 0.005)
                time.sleep(sleep_time)

    def stop(self):
        """Safely stops the execution loop and waits for the thread to terminate."""
        self.running = False
        self.wait()