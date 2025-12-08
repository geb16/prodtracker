# screenshot.py
import time
from pathlib import Path

import pyautogui

SCREEN_DIR = Path("screenshots")


def take_screenshot(prefix="ss"):
    """
    Takes a screenshot and saves it in the 'screenshots' directory.
    Automatically creates the directory if it does not exist.

    Returns:
        str: Path to the saved screenshot
    """
    # Ensure the directory exists
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)

    # Generate timestamped filename
    ts = int(time.time())
    file_path = SCREEN_DIR / f"{prefix}_{ts}.png"

    # Capture and save screenshot
    img = pyautogui.screenshot()
    img.save(file_path)

    return str(file_path)
