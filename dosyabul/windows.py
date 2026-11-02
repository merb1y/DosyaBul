"""Acik pencereleri listeler ve one getirir (Rofi window kipi)."""

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass


@dataclass(frozen=True)
class OpenWindow:
    handle: int
    title: str
    process: str
    pid: int


if os.name == "nt":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    _enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
else:
    user32 = None
    _enum_proc = None

SKIP_TITLES = {"", "Program Manager", "Settings", "Windows Input Experience"}
SKIP_CLASSES = {"Progman", "Shell_TrayWnd", "Windows.UI.Core.CoreWindow", "ApplicationFrameWindow"}


def list_windows() -> tuple[OpenWindow, ...]:
    if os.name != "nt":
        return ()
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    found = []

    @_enum_proc
    def collect(hwnd, _parameter):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        if title.value in SKIP_TITLES:
            return True
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, 256)
        if class_name.value in SKIP_CLASSES:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        found.append(OpenWindow(int(hwnd), title.value, class_name.value, pid.value))
        return True

    user32.EnumWindows(collect, 0)
    return tuple(found)


def focus_window(handle: int) -> bool:
    if os.name != "nt":
        return False
    user32.ShowWindow(handle, 9)  # SW_RESTORE
    return bool(user32.SetForegroundWindow(handle))


def close_window(handle: int) -> bool:
    if os.name != "nt":
        return False
    user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    return bool(user32.PostMessageW(handle, 0x0010, 0, 0))
