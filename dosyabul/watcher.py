"""Arka planda kullanıcı klasörlerini (ReadDirectoryChangesW) izleyip SQLite indeksini canlı günceller."""

import ctypes
import os
import threading
from ctypes import wintypes
from pathlib import Path

FILE_LIST_DIRECTORY = 0x0001
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_NOTIFY_CHANGE_FILE_NAME = 0x00000001
FILE_NOTIFY_CHANGE_DIR_NAME = 0x00000002
FILE_NOTIFY_CHANGE_SIZE = 0x00000008
FILE_NOTIFY_CHANGE_LAST_WRITE = 0x00000010

FILE_ACTION_ADDED = 0x00000001
FILE_ACTION_REMOVED = 0x00000002
FILE_ACTION_MODIFIED = 0x00000003
FILE_ACTION_RENAMED_OLD_NAME = 0x00000004
FILE_ACTION_RENAMED_NEW_NAME = 0x00000005


def default_watch_directories() -> tuple[Path, ...]:
    home = Path.home()
    candidates = [
        home / "Desktop",
        home / "Downloads",
        home / "Documents",
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    seen = set()
    result = []
    for folder in candidates:
        try:
            resolved = folder.resolve()
        except OSError:
            continue
        if resolved.is_dir() and resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return tuple(result)


class LiveFileWatcher:
    """Kullanıcının sık değişen klasörlerini izleyip veritabanını anında günceller."""

    def __init__(self, database, directories: tuple[Path, ...] | None = None):
        self.database = database
        self.directories = directories if directories is not None else default_watch_directories()
        self._stop = threading.Event()
        self._handles: list[int] = []
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        if os.name != "nt" or self._threads:
            return
        for directory in self.directories:
            thread = threading.Thread(
                target=self._watch_dir,
                args=(directory,),
                daemon=True,
                name=f"DosyaBul-Watch-{directory.name}",
            )
            self._threads.append(thread)
            thread.start()

    def _watch_dir(self, directory: Path) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = (
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        )
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.ReadDirectoryChangesW.argtypes = (
            wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, wintypes.BOOL,
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID, wintypes.LPVOID,
        )
        kernel32.ReadDirectoryChangesW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

        handle = kernel32.CreateFileW(
            str(directory),
            FILE_LIST_DIRECTORY,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if not handle or handle == wintypes.HANDLE(-1).value:
            return
        self._handles.append(handle)
        buf = ctypes.create_string_buffer(16384)
        bytes_returned = wintypes.DWORD()
        notify_filter = (
            FILE_NOTIFY_CHANGE_FILE_NAME
            | FILE_NOTIFY_CHANGE_DIR_NAME
            | FILE_NOTIFY_CHANGE_SIZE
            | FILE_NOTIFY_CHANGE_LAST_WRITE
        )

        try:
            while not self._stop.is_set():
                ok = kernel32.ReadDirectoryChangesW(
                    handle,
                    ctypes.byref(buf),
                    len(buf),
                    True,
                    notify_filter,
                    ctypes.byref(bytes_returned),
                    None,
                    None,
                )
                if not ok or self._stop.is_set() or bytes_returned.value == 0:
                    break
                offset = 0
                raw = buf.raw[: bytes_returned.value]
                while offset + 12 <= len(raw):
                    next_offset = int.from_bytes(raw[offset : offset + 4], "little")
                    action = int.from_bytes(raw[offset + 4 : offset + 8], "little")
                    name_len = int.from_bytes(raw[offset + 8 : offset + 12], "little")
                    name_bytes = raw[offset + 12 : offset + 12 + name_len]
                    rel_name = name_bytes.decode("utf-16-le", errors="replace")
                    full_path = directory / rel_name
                    try:
                        if action in (FILE_ACTION_REMOVED, FILE_ACTION_RENAMED_OLD_NAME):
                            self.database.remove_path(full_path)
                        elif action in (FILE_ACTION_ADDED, FILE_ACTION_MODIFIED, FILE_ACTION_RENAMED_NEW_NAME):
                            self.database.upsert_path(full_path)
                    except Exception:
                        pass
                    if next_offset == 0:
                        break
                    offset += next_offset
        finally:
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass

    def stop(self) -> None:
        self._stop.set()
        if os.name == "nt" and self._handles:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            CancelIoEx = getattr(kernel32, "CancelIoEx", None)
            for handle in list(self._handles):
                try:
                    if CancelIoEx:
                        CancelIoEx(wintypes.HANDLE(handle), None)
                except Exception:
                    pass
            self._handles.clear()
