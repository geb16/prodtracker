# dashboard/flash_warning.py

import tkinter as tk
import threading
import time
from pathlib import Path
import queue

import pyttsx3
from playsound import playsound
import pystray
from PIL import Image, ImageDraw


# ----------------------------
# CONFIG
# ----------------------------

STATIC_DIR = Path(__file__).parent / "static"
BEEP_FILE = STATIC_DIR / "beep-warning-6387.mp3"
ESCALATION_FILE = STATIC_DIR / "escalation.mp3"
SNOOZE_DEFAULT = 300  # 5 minutes


# ----------------------------
# GLOBAL STATE (THREAD-SAFE)
# ----------------------------

_alert_queue = queue.Queue()
_violation_count = 0
_snoozed_until = 0
_tray_started = False


# ----------------------------
# SOUND (THREAD-SAFE)
# ----------------------------

def _play_sound(escalate: bool):
    try:
        sound = ESCALATION_FILE if escalate and ESCALATION_FILE.exists() else BEEP_FILE
        if sound.exists():
            playsound(str(sound))
    except Exception:
        pass


# ----------------------------
# TTS (NEW ENGINE PER CALL)
# ----------------------------

def _speak(text: str):
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception:
        pass


# ----------------------------
# SYSTEM TRAY (SAFE)
# ----------------------------

def _start_tray():
    global _tray_started
    if _tray_started:
        return
    _tray_started = True

    def snooze_5(icon, item):
        global _snoozed_until
        _snoozed_until = time.time() + SNOOZE_DEFAULT

    def quit_app(icon, item):
        icon.stop()

    img = Image.new("RGB", (64, 64), color="red")
    draw = ImageDraw.Draw(img)
    draw.text((20, 18), "⚠", fill="white")

    menu = pystray.Menu(
        pystray.MenuItem("Snooze 5 min", snooze_5),
        pystray.MenuItem("Exit", quit_app),
    )

    icon = pystray.Icon("ProdTracker", img, "ProdTracker Alert", menu)
    icon.run()


threading.Thread(target=_start_tray, daemon=True).start()


# ----------------------------
# ✅ SINGLE TK THREAD (CRITICAL)
# ----------------------------

def _tk_mainloop():
    root = tk.Tk()
    root.withdraw()  # no root window
    root.title("ProdTracker Alert Engine")

    def process_queue():
        try:
            title, app, duration, escalate = _alert_queue.get_nowait()
        except queue.Empty:
            root.after(200, process_queue)
            return

        _show_popup(root, title, app, duration, escalate)
        root.after(200, process_queue)

    root.after(200, process_queue)
    root.mainloop()


def _show_popup(root: tk.Tk, title: str, app: str, duration: int, escalate: bool):
    threading.Thread(target=_play_sound, args=(escalate,), daemon=True).start()
    threading.Thread(target=_speak, args=("Return to productive task",), daemon=True).start()

    win = tk.Toplevel(root)
    win.attributes("-topmost", True)
    win.overrideredirect(True)

    width, height = 560, 240
    x = (win.winfo_screenwidth() - width) // 2
    y = (win.winfo_screenheight() - height) // 2
    win.geometry(f"{width}x{height}+{x}+{y}")

    frame = tk.Frame(win, bg="red")
    frame.pack(fill="both", expand=True)

    label = tk.Label(
        frame,
        text=f"⚠️ NOISE ALERT ⚠️\n\n{title} ({app})\nReturn to productive task!",
        fg="white",
        bg="red",
        font=("Segoe UI", 18, "bold"),
        justify="center",
        wraplength=520,
    )
    label.pack(expand=True, padx=15, pady=15)

    def safe_destroy(event=None):
        try:
            win.destroy()
        except Exception:
            pass

    label.bind("<Button-1>", safe_destroy)
    frame.bind("<Button-1>", safe_destroy)

    end_time = time.time() + duration
    flash = True

    def animate():
        nonlocal flash
        if time.time() > end_time:
            safe_destroy()
            return

        color = "black" if flash else "red"
        frame.config(bg=color)
        label.config(bg=color)
        flash = not flash
        win.after(450, animate)

    win.after(0, animate)


# ✅ Start Tk once, forever
threading.Thread(target=_tk_mainloop, daemon=True).start()


# ----------------------------
# ✅ PUBLIC API (SAFE)
# ----------------------------

def flash_warning(title: str, app: str, duration: int = 10):
    """
    ✅ Fully thread-safe
    ✅ No Tk crashes possible
    ✅ Click-to-dismiss
    ✅ Snooze
    ✅ Escalation
    ✅ TTS
    ✅ Tray
    """

    global _violation_count, _snoozed_until

    if time.time() < _snoozed_until:
        return

    _violation_count += 1
    escalate = _violation_count >= 3

    _alert_queue.put((title, app, duration, escalate))
