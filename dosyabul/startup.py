import os
import subprocess
try:
    import winreg
except ImportError:
    winreg = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "DosyaBul"


def _executable() -> str:
    import sys
    if getattr(sys, "frozen", False):
        return sys.executable
    return f'"{sys.executable}" "{os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "run.py"))}"'


def _command(show_panel: bool = False) -> str:
    import sys
    if getattr(sys, "frozen", False):
        base = f'"{sys.executable}" --background'
    else:
        base = f'"{sys.executable}" "{os.path.abspath(os.path.join(os.path.dirname(__file__), chr(46)+chr(46), chr(114)+chr(117)+chr(110)+chr(46)+chr(112)+chr(121)))}" --background'
    return base


def _run_key():
    return winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ | winreg.KEY_WRITE)


def is_startup_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except OSError:
        return False


def set_startup(enabled: bool, show_panel: bool = False):
    if winreg is None:
        return
    with _run_key() as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command(show_panel))
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
