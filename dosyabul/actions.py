"""Dosya açma ve klasörde gösterme işlemleri."""

import os
import subprocess

EXECUTABLE_EXTENSIONS = {
    "exe", "com", "bat", "cmd", "msi", "ps1", "psm1", "vbs", "vbe", "js", "jse", "wsf", "wsh", "scr", "cpl", "reg",
}


def configure_windows():
    """Windows'ta DPI farkindaligini acar."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def open_item(path: str):
    os.startfile(path)


def reveal_file(path: str):
    if os.path.isfile(path):
        subprocess.Popen(["explorer", "/select,", path])
    else:
        subprocess.Popen(["explorer", path])
