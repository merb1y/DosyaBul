"""Bellekte tutulan pano geçmişi (diske yazılmaz) ve Windows pano/yapıştırma yardımcıları."""

import ctypes
import os

from .query import fold_text

MAX_TEXT = 20000
MAX_ENTRIES = 50


class ClipboardHistory:
    def __init__(self, limit: int = MAX_ENTRIES):
        self.limit = max(1, int(limit))
        self._entries: list[str] = []

    def add(self, text: str) -> bool:
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            return False
        if text in self._entries:
            self._entries.remove(text)
        self._entries.insert(0, text)
        del self._entries[self.limit:]
        return True

    def entries(self) -> tuple[str, ...]:
        return tuple(self._entries)

    def search(self, query: str) -> tuple[str, ...]:
        terms = tuple(part for part in fold_text(query).split() if part)
        return tuple(entry for entry in self._entries if all(term in fold_text(entry) for term in terms))

    def clear(self) -> None:
        self._entries.clear()


def sequence_number() -> int:
    """Pano her değiştiğinde artan sayaç; metni okumadan değişim anlaşılır."""
    if os.name != "nt":
        return 0
    try:
        return int(ctypes.windll.user32.GetClipboardSequenceNumber())
    except (OSError, AttributeError):
        return 0


def send_paste() -> None:
    """Etkin pencereye Ctrl+V gönderir."""
    if os.name != "nt":
        return
    user32 = ctypes.windll.user32
    VK_CONTROL, VK_V, KEYUP = 0x11, 0x56, 0x0002
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    user32.keybd_event(VK_V, 0, KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYUP, 0)


def display_text(text: str, limit: int = 90) -> str:
    line = " ⏎ ".join(part.strip() for part in text.strip().splitlines() if part.strip()) or text.strip()
    return line if len(line) <= limit else line[: limit - 1] + "…"
