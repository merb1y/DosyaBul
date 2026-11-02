import os
import threading
from dataclasses import dataclass

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

WM_HOTKEY = 0x0312
VK_SPACE = 0x20

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

    def normalized(self):
        modifiers = int(self.modifiers) & (MOD_WIN | MOD_CONTROL | MOD_ALT | MOD_SHIFT)
        key = int(self.key)
        if not modifiers:
            raise ValueError("Kısayolda en az bir değiştirici (Win, Ctrl, Alt, Shift) olmalı.")
        if key <= 0:
            raise ValueError("Kısayol tuşu geçersiz.")
        return HotkeySpec(modifiers, key)

    @property
    def label(self):
        return format_hotkey(self)

    @property
    def reserved_by_windows(self):
        return self.modifiers == MOD_WIN and self.key == VK_SPACE


DEFAULT_SPEC = HotkeySpec(MOD_ALT, 0x71)  # Alt + F2


def format_hotkey(spec):
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
        raise ValueError("Kısayolda bir tuş bulunamadı.")
    return HotkeySpec(modifiers, key).normalized()


def captured_hotkey(event):
    """Tkinter tuş olayını HotkeySpec'e çevirir (None ise yalnızca değiştirici)."""
    keysym = (event.keysym or "").strip()
    if keysym in {
        "Win_L", "Win_R", "Super_L", "Super_R", "Shift_L", "Shift_R",
        "Control_L", "Control_R", "Alt_L", "Alt_R", "Alt_Gr", "Caps_Lock", "Num_Lock",
    }:
        return None
    modifiers = 0
    state = int(getattr(event, "state", 0) or 0)
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
    """Ayrı iş parçacığında RegisterHotKey ile global kısayolu dinler."""

    def __init__(self, callback, spec=DEFAULT_SPEC):
        self.callback = callback
        self.spec = spec.normalized()
        self.error = None
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        if os.name != "nt":
            self.error = "Global kısayol yalnızca Windows'ta destekleniyor."
            return False
        if self.spec.reserved_by_windows:
            self.error = "Bu birleşim Windows dil değiştiricisi tarafından kullanılıyor."
            return False
        self._thread = threading.Thread(target=self._run, daemon=True, name="DosyaBul-Kisayol")
        self._thread.start()
        self._thread.join(timeout=1.0)
        return self.error is None

    def _run(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
        user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
        if not user32.RegisterHotKey(None, 1, self.spec.modifiers, self.spec.key):
            self.error = f"Kısayol başka bir uygulama tarafından kullanılıyor (hata {ctypes.get_last_error()})."
            return
        try:
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
            user32.UnregisterHotKey(None, 1)

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
