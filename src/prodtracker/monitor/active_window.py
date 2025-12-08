# src/prodtracker/monitor/active_window.py
import platform
from typing import Tuple


def get_active_window() -> Tuple[str, str]:
    """
    Returns (window_title, app_name). Best-effort; may be platform-dependent.
    """
    system = platform.system()
    if system == "Windows":
        try:
            # Prefer pywin32 if available, but import dynamically to avoid static-analysis errors.
            import importlib

            win32gui = None
            win32process = None
            psutil = None

            try:
                win32gui = importlib.import_module("win32gui")
                win32process = importlib.import_module("win32process")
            except Exception:
                win32gui = None
                win32process = None

            try:
                psutil = importlib.import_module("psutil")
            except Exception:
                psutil = None

            if win32gui and win32process:
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            else:
                # Fallback using ctypes when pywin32 is not installed
                import ctypes

                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                length = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                pid_c = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_c))
                pid = pid_c.value

            app_name = ""
            if psutil and pid:
                try:
                    proc = psutil.Process(pid)
                    app_name = proc.name()
                except Exception:
                    app_name = ""

            return (title or ""), (app_name or "")
        except Exception:
            return "", ""
    elif system == "Darwin":
        try:
            import importlib

            AppKit = importlib.import_module("AppKit")
            NSWorkspace = getattr(AppKit, "NSWorkspace")
            active = NSWorkspace.sharedWorkspace().frontmostApplication()
            name = active.localizedName()
            # Getting window title needs pyobjc extras; best-effort:
            return name, name
        except Exception:
            return "", ""
    else:  # Linux - X11
        try:
            import subprocess

            out = subprocess.check_output(["xdotool", "getwindowfocus", "getwindowname"], text=True).strip()
            # app name fallback
            return out, out
        except Exception:
            return "", ""
