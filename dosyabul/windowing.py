"""Rofi benzeri pencerenin etkin monitorde konumlandirilmasi ve Windows stili."""

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkArea:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def active_work_area(root, monitor_mode: str = "Fare imlecinin ekrani") -> WorkArea:
    if os.name != "nt":
        return WorkArea(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetForegroundWindow.restype = wintypes.HWND
    user.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
    user.MonitorFromWindow.restype = wintypes.HANDLE
    user.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
    user.MonitorFromPoint.argtypes = (wintypes.POINT, wintypes.DWORD)
    user.MonitorFromPoint.restype = wintypes.HANDLE
    user.GetMonitorInfoW.argtypes = (wintypes.HANDLE, ctypes.POINTER(MONITORINFO))
    monitor = None
    if monitor_mode == "Ana ekran":
        monitor = user.MonitorFromPoint(wintypes.POINT(0, 0), 1)
    elif monitor_mode == "Etkin pencerenin ekrani":
        foreground = user.GetForegroundWindow()
        monitor = user.MonitorFromWindow(foreground, 2) if foreground else None
    else:
        point = wintypes.POINT()
        if user.GetCursorPos(ctypes.byref(point)):
            monitor = user.MonitorFromPoint(point, 2)
    if not monitor:
        monitor = user.MonitorFromPoint(wintypes.POINT(0, 0), 1)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(info)
    return WorkArea(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())


def popup_geometry(root, height: int, width: int = 480, position: str = "Orta", monitor_mode: str = "Fare imlecinin ekrani") -> tuple[int, int, int, int]:
    area = active_work_area(root, monitor_mode)
    width = min(max(320, int(width)), max(320, area.width - 32))
    height = min(height, max(100, area.height - 32))
    margin = 24
    horizontal = "orta"
    vertical = "orta"
    words = position.casefold().split()
    if "sol" in words:
        horizontal = "sol"
    elif "sag" in words or "sağ" in words:
        horizontal = "sag"
    if "ust" in words or "üst" in words:
        vertical = "ust"
    elif "alt" in words:
        vertical = "alt"

    x = {
        "sol": area.left + margin,
        "orta": area.left + (area.width - width) // 2,
        "sag": area.right - margin - width,
    }[horizontal]
    y = {
        "ust": area.top + margin,
        "orta": area.top + (area.height - height) // 2,
        "alt": area.bottom - margin - height,
    }[vertical]
    return width, height, x, y


def apply_popup_style(root):
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", 0.97)
    except Exception:
        pass
    root.update_idletasks()
    if os.name != "nt":
        return
    hwnd = root.winfo_id()
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.GetParent.argtypes = (wintypes.HWND,)
    user.GetParent.restype = wintypes.HWND
    parent = user.GetParent(hwnd)
    if parent:
        hwnd = parent
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_APPWINDOW = 0x00040000
    get_style = user.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user.GetWindowLongW
    set_style = user.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user.SetWindowLongW
    get_style.argtypes = (wintypes.HWND, ctypes.c_int)
    get_style.restype = ctypes.c_ssize_t
    set_style.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
    set_style.restype = ctypes.c_ssize_t
    style = get_style(hwnd, GWL_EXSTYLE)
    set_style(hwnd, GWL_EXSTYLE, (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)
    try:
        dwm = ctypes.WinDLL("dwmapi")
        preference = ctypes.c_int(2)  # DWMWCP_ROUND: yuvarlatilmis Rofi paneli
        dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(preference), ctypes.sizeof(preference))
        border = ctypes.c_uint(0x005A4E4A)  # COLORREF, koyu gri cerceve
        dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(border), ctypes.sizeof(border))
    except (AttributeError, OSError):
        pass


def activate_window(root):
    root.deiconify()
    root.lift()
    root.attributes("-topmost", True)
    root.update_idletasks()
    if os.name == "nt":
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.GetParent.argtypes = (wintypes.HWND,)
        user.GetParent.restype = wintypes.HWND
        hwnd = root.winfo_id()
        hwnd = user.GetParent(hwnd) or hwnd
        user.ShowWindow(hwnd, 5)
        user.BringWindowToTop(hwnd)
        user.SetForegroundWindow(hwnd)
    root.focus_force()
