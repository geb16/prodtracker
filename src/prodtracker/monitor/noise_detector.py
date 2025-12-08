# src/prodtracker/monitor/noise_detector.py
import time
from datetime import datetime
from src.prodtracker.monitor.active_window import get_active_window
from src.prodtracker.monitor.screenshot import take_screenshot
from src.prodtracker.blocker import hosts_blocker
from src.prodtracker.db.session import SessionLocal
from src.prodtracker.db.models import Event

# Words that flag likely distractions
DISTRACTION_KEYWORDS = ["youtube", "shorts", "tiktok", "instagram", "facebook", "reddit", "x.com"]

def check_for_noise():
    """
    Returns (is_noise, title, app_name)
    """
    title, app = get_active_window()
    title_l = title.lower()
    app_l = app.lower()

    # Browsers likely used for distraction
    browser_like = any(a in app_l for a in ["chrome", "firefox", "edge", "brave"])
    if browser_like and any(k in title_l for k in DISTRACTION_KEYWORDS):
        return True, title, app
    return False, title, app


def background_monitor_and_block(interval: int = 5):
    """Continuously monitor active window and block noise events."""
    while True:
        now = datetime.utcnow()
        is_noise, title, app_name = check_for_noise()
        db = SessionLocal()

        try:
            screenshot_path = None
            if is_noise:
                try:
                    screenshot_path = take_screenshot(prefix="noise")
                    hosts_blocker.block_domains()
                except Exception:
                    pass

            ev = Event(
                timestamp=now,
                event_type="noise" if is_noise else "signal",
                window_title=title,
                app_name=app_name,
                productive=not is_noise,
                screenshot_path=screenshot_path,
            )
            db.add(ev)
            db.commit()
        finally:
            db.close()

        # Restore domains at midnight UTC
        if now.hour == 23 and now.minute >= 59:
            hosts_blocker.unblock_all()

        time.sleep(interval)

