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
    A background thread that continuously captures a predefined Region of Interest (ROI),
    processes the image using OpenCV, and extracts text using Tesseract OCR.
    Emits a signal whenever the extracted text changes.
    """
    text_read = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.last_text = ""

        # Original coordinates targeting the weapon state UI text
        self.roi = {"top": 1097, "left": 691, "width": 789, "height": 155}

    def run(self):
        """
        Main execution loop for the thread.
        Captures the screen, applies image processing, and runs OCR at ~50 Hz.
        """
        # Using a safe and stable configuration for PyTesseract (Assume a single uniform block of text)
        tess_config = '--psm 6'

        with mss.mss() as sct:
            while self.running:
                start_time = time.time()
                try:
                    sct_img = sct.grab(self.roi)
                    img = np.array(sct_img)

                    # Image processing for better OCR accuracy
                    gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
                    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                    _, thresh = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY_INV)

                    # Extract text, strip whitespace, and normalize to lowercase
                    text = pytesseract.image_to_string(thresh, config=tess_config).strip().lower()

                    if text != getattr(self, 'last_text', None):
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