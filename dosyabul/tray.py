"""Windows sistem tepsisi (Shell_NotifyIcon) entegrasyonu."""

import ctypes
import os
import threading
from ctypes import wintypes

WM_APP = 0x8000
WM_TRAY = WM_APP + 1
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NOTIFYICON_VERSION_4 = 4


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


if os.name == "nt":
    _shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
else:
    _shell32 = _user32 = _kernel32 = None


def _setup_api():
    if os.name != "nt":
        return
    _shell32.Shell_NotifyIconW.argtypes = (wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATA))
    _shell32.Shell_NotifyIconW.restype = wintypes.BOOL
    _shell32.ExtractIconExW.restype = wintypes.UINT
    _user32.RegisterClassW.restype = wintypes.ATOM
    _user32.CreateWindowExW.restype = wintypes.HWND
    _user32.CreateWindowExW.argtypes = (
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    )
    _user32.DefWindowProcW.argtypes = (wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t)
    _user32.DefWindowProcW.restype = ctypes.c_ssize_t
    _user32.GetMessageW.argtypes = (ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
    _user32.GetMessageW.restype = ctypes.c_int
    _user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    _kernel32.GetModuleHandleW.restype = wintypes.HMODULE


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t)


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


def load_tray_icon(path=None):
    """Tepside kullanilacak HICON'u yukler (exe veya .ico dosyasindan)."""
    if os.name != "nt":
        return None
    source = path
    if not source:
        import sys
        if getattr(sys, "frozen", False):
            source = sys.executable
        else:
            candidate = os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico")
            source = os.path.abspath(candidate) if os.path.isfile(candidate) else None
    if not source or not os.path.isfile(source):
        return None
    if source.lower().endswith(".ico"):
        LR_LOADFROMFILE = 0x00000010
        IMAGE_ICON = 1
        return _user32.LoadImageW(None, source, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
    large = wintypes.HICON()
    small = wintypes.HICON()
    if _shell32.ExtractIconExW(source, 0, ctypes.byref(large), ctypes.byref(small), 1) > 0:
        if small:
            return small
        return large
    return None


class TrayIcon:
    """Sistem tepsisinde ikon gosterir; tiklamalari callback'e iletir."""

    def __init__(self, tooltip="DosyaBul", on_select=None, on_context=None, icon_handle=None):
        self.tooltip = tooltip
        self._on_select = on_select
        self._on_context = on_context
        self._hicon = icon_handle
        self._hwnd = None
        self._installed = False
        self._thread = None
        self._stop = threading.Event()
        self._wndproc_ref = None

    @property
    def available(self):
        return os.name == "nt" and _shell32 is not None and self._installed

    def start(self):
        if os.name != "nt" or _shell32 is None:
            return False
        self._thread = threading.Thread(target=self._run, daemon=True, name="DosyaBul-Tepsi")
        self._thread.start()
        self._thread.join(timeout=2.0)
        return self._installed

    def _register_class(self, instance):
        wndproc = WNDPROC(self._window_proc)
        self._wndproc_ref = wndproc
        wc = WNDCLASS()
        wc.lpfnWndProc = wndproc
        wc.hInstance = instance
        wc.lpszClassName = "DosyaBulTrayWindow"
        _user32.RegisterClassW(ctypes.byref(wc))
        return wc.lpszClassName

    def _window_proc(self, hwnd, message, wparam, lparam):
        if message == WM_TRAY:
            event = int(lparam) & 0xFFFF
            if event == WM_LBUTTONUP:
                self._dispatch(self._on_select)
            elif event == WM_RBUTTONUP:
                self._dispatch(self._on_context)
            return 0
        if message == 0x0010:
            return 0
        return _user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def _dispatch(self, callback):
        if callback is None:
            return
        try:
            callback()
        except Exception:
            pass

    def _run(self):
        instance = _kernel32.GetModuleHandleW(None)
        class_name = self._register_class(instance)
        hwnd = _user32.CreateWindowExW(
            0, class_name, "DosyaBulTray", 0, 0, 0, 0, 0, None, None, instance, None,
        )
        if not hwnd:
            return
        self._hwnd = hwnd
        self._add_icon(hwnd)
        message = MSG()
        while not self._stop.is_set():
            result = _user32.GetMessageW(ctypes.byref(message), None, 0, 0)
            if result in (0, -1):
                break
            _user32.TranslateMessage(ctypes.byref(message))
            _user32.DispatchMessageW(ctypes.byref(message))
        self._delete_icon()
        _user32.DestroyWindow(hwnd)

    def _data(self, hwnd):
        data = NOTIFYICONDATA()
        data.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        data.hWnd = hwnd
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = WM_TRAY
        data.hIcon = self._hicon or 0
        data.szTip = self.tooltip[:127]
        return data

    def _add_icon(self, hwnd):
        data = self._data(hwnd)
        if not _shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)):
            return
        self._installed = True

    def _delete_icon(self):
        if self._hwnd:
            data = self._data(self._hwnd)
            _shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
        self._installed = False

    def set_tooltip(self, text):
        self.tooltip = text[:127]
        if self._hwnd and self._installed:
            data = self._data(self._hwnd)
            _shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data))

    def stop(self):
        self._stop.set()
        if self._hwnd:
            _user32.PostMessageW(self._hwnd, 0x0012, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)


_setup_api()


