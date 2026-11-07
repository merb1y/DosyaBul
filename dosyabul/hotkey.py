import os
import threading
import time
from dataclasses import dataclass

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
WM_CLOSE = 0x0010
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

WH_KEYBOARD_LL = 13
LLKHF_INJECTED = 0x00000010
KEYEVENTF_KEYUP = 0x0002
EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

VK_SPACE = 0x20
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_S = 0x53
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_MBUTTON = 0x04
VK_MASK = 0xFF

MODIFIER_FLAGS = (
    ("Win", MOD_WIN),
    ("Ctrl", MOD_CONTROL),
    ("Alt", MOD_ALT),
    ("Shift", MOD_SHIFT),
)

KEY_NAMES = {
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x1B: "Esc",
    0x20: "Space", 0x21: "PageUp", 0x22: "PageDown", 0x23: "End",
    0x24: "Home", 0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
    0x2D: "Insert", 0x2E: "Delete",
    VK_LWIN: "Win", VK_RWIN: "Win",
}


def _key_name(code):
    if code in KEY_NAMES:
        return KEY_NAMES[code]
    if 0x30 <= code <= 0x39 or 0x41 <= code <= 0x5A:
        return chr(code)
    if 0x60 <= code <= 0x69:
        return f"Num{code - 0x60}"
    if 0x70 <= code <= 0x87:
        return f"F{code - 0x6F}"
    return f"0x{code:02X}"


def parse_key(name):
    text = (name or "").strip()
    if not text:
        raise ValueError("Tuş adı boş.")
    upper = text.upper()
    for code, label in KEY_NAMES.items():
        if label.casefold() == text.casefold():
            return code
    if len(text) == 1:
        return ord(upper)
    if upper.startswith("NUM") and upper[3:].isdigit():
        return 0x60 + int(upper[3:])
    if upper.startswith("F") and upper[1:].isdigit():
        number = int(upper[1:])
        if 1 <= number <= 24:
            return 0x6F + number
    if upper.startswith("0X"):
        return int(upper, 16)
    raise ValueError(f"Tanınmayan tuş: {name}")


@dataclass(frozen=True)
class HotkeySpec:
    modifiers: int
    key: int

    @property
    def is_solo_win(self) -> bool:
        return (int(self.modifiers) & (MOD_WIN | MOD_CONTROL | MOD_ALT | MOD_SHIFT)) == MOD_WIN and int(self.key) in (VK_LWIN, VK_RWIN)

    def normalized(self):
        modifiers = int(self.modifiers) & (MOD_WIN | MOD_CONTROL | MOD_ALT | MOD_SHIFT)
        key = int(self.key)
        if not modifiers:
            raise ValueError("Kısayolda en az bir değiştirici (Win, Ctrl, Alt, Shift) olmalı.")
        if key <= 0:
            raise ValueError("Kısayol tuşu geçersiz.")
        if modifiers == MOD_WIN and key in (VK_LWIN, VK_RWIN):
            return HotkeySpec(MOD_WIN, VK_LWIN)
        return HotkeySpec(modifiers, key)

    @property
    def label(self):
        return format_hotkey(self)

    @property
    def reserved_by_windows(self):
        return self.modifiers == MOD_WIN and self.key == VK_SPACE


DEFAULT_SPEC = HotkeySpec(MOD_ALT, 0x71)  # Alt + F2
WIN_SOLO_SPEC = HotkeySpec(MOD_WIN, VK_LWIN)


def format_hotkey(spec):
    if spec.is_solo_win:
        return "Win"
    parts = [label for label, flag in MODIFIER_FLAGS if spec.modifiers & flag]
    parts.append(_key_name(spec.key))
    return " + ".join(parts)


def parse_hotkey(text):
    if not text:
        return DEFAULT_SPEC
    modifiers = 0
    key = None
    for chunk in str(text).replace("+", " ").split():
        if not chunk:
            continue
        matched = None
        for label, flag in MODIFIER_FLAGS:
            if label.casefold() == chunk.casefold():
                matched = flag
                break
        if matched is not None:
            modifiers |= matched
        else:
            key = parse_key(chunk)
    if key is None:
        if modifiers == MOD_WIN:
            return WIN_SOLO_SPEC
        raise ValueError("Kısayolda bir tuş bulunamadı.")
    return HotkeySpec(modifiers, key).normalized()


def captured_hotkey(event):
    """Tkinter tuş olayını HotkeySpec'e çevirir (None ise yalnızca değiştirici)."""
    keysym = (event.keysym or "").strip()
    state = int(getattr(event, "state", 0) or 0)
    if keysym in {"Win_L", "Win_R", "Super_L", "Super_R"} and not (state & (0x0004 | 0x0001 | 0x0008)):
        return WIN_SOLO_SPEC
    if keysym in {
        "Win_L", "Win_R", "Super_L", "Super_R", "Shift_L", "Shift_R",
        "Control_L", "Control_R", "Alt_L", "Alt_R", "Alt_Gr", "Caps_Lock", "Num_Lock",
    }:
        return None
    modifiers = 0
    if state & 0x0004:
        modifiers |= MOD_CONTROL
    if state & 0x0001:
        modifiers |= MOD_SHIFT
    if state & 0x0008:
        modifiers |= MOD_ALT
    if getattr(event, "keycode", 0) in (0x5B, 0x5C):
        modifiers |= MOD_WIN
    special = {
        "space": VK_SPACE, "Return": 0x0D, "Escape": 0x1B, "Tab": 0x09,
        "BackSpace": 0x08, "Delete": 0x2E, "Insert": 0x2D, "Home": 0x24, "End": 0x23,
        "Prior": 0x21, "Next": 0x22, "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28,
    }
    if keysym in special:
        key = special[keysym]
    elif len(keysym) == 1 and keysym.isalnum():
        key = ord(keysym.upper())
    elif keysym.startswith("F") and keysym[1:].isdigit() and 1 <= int(keysym[1:]) <= 24:
        key = 0x6F + int(keysym[1:])
    else:
        raise ValueError(f"Bu tuş kısayolda kullanılamıyor: {keysym}")
    return HotkeySpec(modifiers, key).normalized()


class HotkeyService:
    """Ayrı iş parçacığında RegisterHotKey ve (etkinse) Win/Başlat araması kancasını dinler."""

    def __init__(self, callback, spec=DEFAULT_SPEC, *, win_search_override: bool = False, show_callback=None):
        self.callback = callback
        self.show_callback = show_callback or callback
        self.spec = spec.normalized()
        self.win_search_override = bool(win_search_override)
        self.error = None
        self._thread = None
        self._thread_id = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._win_down = False
        self._win_alone = False
        self._last_searchhost_trigger = 0.0

    def start(self):
        if os.name != "nt":
            self.error = "Global kısayol yalnızca Windows'ta destekleniyor."
            return False
        if self.spec.reserved_by_windows:
            self.error = "Bu birleşim Windows dil değiştiricisi tarafından kullanılıyor."
            return False
        self._thread = threading.Thread(target=self._run, daemon=True, name="DosyaBul-Kisayol")
        self._thread.start()
        self._ready.wait(timeout=1.0)
        return self.error is None

    def _run(self):
        import ctypes
        from ctypes import wintypes

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        self._thread_id = kernel32.GetCurrentThreadId()

        user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
        user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
        user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
        user32.GetAsyncKeyState.restype = wintypes.SHORT
        user32.keybd_event.argtypes = (wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t)
        user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.PostMessageW.restype = wintypes.BOOL

        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL

        WINEVENTPROC = ctypes.WINFUNCTYPE(
            None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
            wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD,
        )
        user32.SetWinEventHook.argtypes = (
            wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, WINEVENTPROC,
            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
        )
        user32.SetWinEventHook.restype = wintypes.HANDLE
        user32.UnhookWinEvent.argtypes = (wintypes.HANDLE,)
        user32.UnhookWinEvent.restype = wintypes.BOOL
        user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        )
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

        registered_hotkey = False
        kb_hook = None
        event_hook = None
        kb_proc_ref = None
        event_proc_ref = None

        def send_mask_key():
            user32.keybd_event(VK_MASK, 0, 0, 0)
            user32.keybd_event(VK_MASK, 0, KEYEVENTF_KEYUP, 0)

        def other_modifiers_down() -> bool:
            for vk in (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LBUTTON, VK_RBUTTON, VK_MBUTTON):
                if user32.GetAsyncKeyState(vk) & 0x8000:
                    return True
            return False

        def is_search_host(hwnd) -> bool:
            if not hwnd:
                return False
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return False
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if not handle:
                return False
            try:
                buf = ctypes.create_unicode_buffer(512)
                size = wintypes.DWORD(512)
                if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                    exe = os.path.basename(buf.value).casefold()
                    return exe in ("searchhost.exe", "searchapp.exe", "searchui.exe")
            finally:
                kernel32.CloseHandle(handle)
            return False

        def low_level_kb_proc(n_code, w_param, l_param):
            if n_code >= 0 and l_param:
                kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if not (kb.flags & LLKHF_INJECTED) and kb.vkCode != VK_MASK:
                    is_down = w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    is_up = w_param in (WM_KEYUP, WM_SYSKEYUP)
                    if kb.vkCode in (VK_LWIN, VK_RWIN):
                        if is_down:
                            if not self._win_down:
                                self._win_down = True
                                self._win_alone = not other_modifiers_down()
                        elif is_up:
                            was_solo = self._win_down and self._win_alone and not other_modifiers_down()
                            self._win_down = False
                            self._win_alone = False
                            if was_solo:
                                send_mask_key()
                                res = user32.CallNextHookEx(kb_hook, n_code, w_param, l_param)
                                try:
                                    self.callback()
                                except Exception:
                                    pass
                                return res
                    elif is_down and self._win_down:
                        self._win_alone = False
                        if self.win_search_override and kb.vkCode == VK_S and not other_modifiers_down():
                            send_mask_key()
                            try:
                                self.show_callback()
                            except Exception:
                                pass
                            return 1
            return user32.CallNextHookEx(kb_hook, n_code, w_param, l_param)

        def win_event_proc(_hook, _event, hwnd, id_object, _id_child, _thread, _time):
            if id_object != 0 or not hwnd:
                return
            now = time.monotonic()
            if now - self._last_searchhost_trigger < 0.35:
                return
            if is_search_host(hwnd):
                self._last_searchhost_trigger = now
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                try:
                    self.show_callback()
                except Exception:
                    pass

        try:
            if not self.spec.is_solo_win:
                if not user32.RegisterHotKey(None, 1, self.spec.modifiers, self.spec.key):
                    self.error = f"Kısayol başka bir uygulama tarafından kullanılıyor (hata {ctypes.get_last_error()})."
                    self._ready.set()
                    return
                registered_hotkey = True

            if self.spec.is_solo_win or self.win_search_override:
                kb_proc_ref = HOOKPROC(low_level_kb_proc)
                kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, kb_proc_ref, None, 0)
                if not kb_hook and self.spec.is_solo_win:
                    self.error = f"Win tuşu kancası kurulamadı (hata {ctypes.get_last_error()})."
                    self._ready.set()
                    return

            if self.win_search_override:
                event_proc_ref = WINEVENTPROC(win_event_proc)
                event_hook = user32.SetWinEventHook(
                    EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
                    None, event_proc_ref, 0, 0, WINEVENT_OUTOFCONTEXT,
                )

            self._ready.set()
            message = wintypes.MSG()
            while not self._stop.is_set():
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result in (0, -1):
                    break
                if message.message == WM_HOTKEY:
                    try:
                        self.callback()
                    except Exception:
                        pass
        finally:
            self._ready.set()
            if event_hook:
                user32.UnhookWinEvent(event_hook)
            if kb_hook:
                user32.UnhookWindowsHookEx(kb_hook)
            if registered_hotkey:
                user32.UnregisterHotKey(None, 1)

    def stop(self):
        self._stop.set()
        if os.name == "nt" and self._thread_id:
            try:
                import ctypes
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
