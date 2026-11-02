import ctypes
import hashlib
import os
import threading
from ctypes import wintypes

MUTEX_PREFIX = "Local\\DosyaBul-"
WAIT_ABANDONED = 0x00000080


class InstanceGuard:
    """Tek örnek koruması ve mevcut pencereyi öne getirme sinyali."""

    def __init__(self, directory):
        self.directory = str(directory)
        self.acquired = False
        self._handle = None
        self._stop = threading.Event()
        self._activation = threading.Event()
        self._thread = None
        self._name = MUTEX_PREFIX + hashlib.sha1(os.path.abspath(self.directory).casefold().encode("utf-8", "surrogatepass")).hexdigest()
        if os.name != "nt":
            self.acquired = True
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        self._handle = kernel32.CreateMutexW(None, False, self._name)
        last = ctypes.get_last_error()
        self.acquired = last != 183  # ERROR_ALREADY_EXISTS
        if not self.acquired and self._handle:
            kernel32.CloseHandle(self._handle)
            self._handle = None

    def signal_existing(self):
        if os.name != "nt":
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenMutexW(0x00100000, False, self._name)  # SYNCHRONIZE
        if handle:
            try:
                kernel32.ReleaseMutex(handle)
            except Exception:
                pass
            finally:
                kernel32.CloseHandle(handle)

    def start_listening(self):
        return

    def activation_requested(self) -> bool:
        return False

    def close(self):
        if self._handle:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
