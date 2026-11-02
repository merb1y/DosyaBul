"""Paketlenmiş EXE'yi geçici örnek verilerle açıp güvenli biçimde kapatır."""

import argparse
import ctypes
import json
import os
import subprocess
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

from dosyabul.database import IndexDatabase


def clean_environment():
    environment = os.environ.copy()
    for name in (
        "_PYI_APPLICATION_HOME_DIR", "_PYI_ARCHIVE_FILE", "_PYI_PARENT_PROCESS_LEVEL",
        "_PYI_SPLASH_IPC", "TCL_LIBRARY", "TK_LIBRARY", "TCLLIBPATH",
    ):
        environment.pop(name, None)
    return environment


class ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
    ]


def process_family(pid):
    kernel = ctypes.windll.kernel32
    kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
    kernel.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessEntry))
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError()
    parents = {}
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        available = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while available:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            available = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    family = {pid}
    while True:
        children = {child for child, parent in parents.items() if parent in family}
        if children <= family:
            return family
        family |= children


def visible_windows(pids):
    user = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = (callback_type, wintypes.LPARAM)
    user.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user.IsWindowVisible.argtypes = (wintypes.HWND,)
    user.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    windows = []

    @callback_type
    def collect(hwnd, _parameter):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user.IsWindowVisible(hwnd):
            length = user.GetWindowTextLengthW(hwnd)
            title = ctypes.create_unicode_buffer(length + 1)
            user.GetWindowTextW(hwnd, title, length + 1)
            windows.append((hwnd, title.value))
        return True

    user.EnumWindows(collect, 0)
    return windows


def wait_for_window(process, expected_title):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        for candidate, title in visible_windows(process_family(process.pid)):
            if "başlatılamadı" in title or "tamamlanamadı" in title:
                raise RuntimeError(f"EXE hata penceresi gösterdi: {title}")
            if title == expected_title:
                return candidate
        try:
            code = process.wait(timeout=0.05)
        except subprocess.TimeoutExpired:
            continue
        raise RuntimeError(f"EXE beklenen pencereyi oluşturmadan kapandı. Çıkış kodu: {code}")
    raise TimeoutError(f"EXE 30 saniye içinde bu pencereyi açmadı: {expected_title}")


def close_window(hwnd):
    user = ctypes.windll.user32
    user.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    if not user.PostMessageW(hwnd, 0x0010, 0, 0):
        raise ctypes.WinError()


def press_global_hotkey(label="Ctrl + Shift + Space"):
    user = ctypes.windll.user32
    KEYUP = 0x0002
    combinations = {
        "Win + Alt + Space": (0x5B, 0x12, 0x20),
        "Ctrl + Shift + Space": (0x11, 0x10, 0x20),
    }
    keys = combinations[label]
    for key in keys:
        user.keybd_event(key, 0, 0, 0)
    for key in reversed(keys):
        user.keybd_event(key, 0, KEYUP, 0)


def wait_until(predicate, message, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise TimeoutError(message)


def window_metrics(hwnd):
    user = ctypes.windll.user32
    user.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
    rectangle = wintypes.RECT()
    if not user.GetWindowRect(hwnd, ctypes.byref(rectangle)):
        raise ctypes.WinError()
    style = user.GetWindowLongW(hwnd, -16)
    extended = user.GetWindowLongW(hwnd, -20)
    return rectangle.right - rectangle.left, rectangle.bottom - rectangle.top, style, extended


def main():
    parser = argparse.ArgumentParser(description="Windows EXE başlangıç ve kapanış kontrolü.")
    parser.add_argument("exe", type=Path, help="Kontrol edilecek DosyaBul.exe yolu.")
    arguments = parser.parse_args()
    if os.name != "nt":
        parser.error("Bu kontrol yalnızca Windows'ta çalışır.")
    executable = arguments.exe.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="dosyabulexe") as temporary:
        base = Path(temporary)
        folder = base / "Örnek sürücü"
        folder.mkdir()
        (folder / "İş Belgeleri").mkdir()
        (folder / "Bütçe 2026.pdf").write_bytes(b"test")
        (folder / "Çalışma notları.txt").write_text("örnek", encoding="utf-8")
        data_directory = base / "veri"
        data_directory.mkdir()
        (data_directory / "settings.json").write_text(json.dumps({
            "hotkey": "Ctrl + Shift + Space",
            "terminal_directory": str(base),
        }), encoding="utf-8")
        database = IndexDatabase(data_directory / "index.sqlite3")
        command = [str(executable), "--data-dir", str(data_directory), "--test-drive", str(folder)]
        environment = clean_environment()
        process = subprocess.Popen(command + ["--background"], env=environment)
        processes = [process]
        try:
            time.sleep(1)
            if visible_windows(process_family(process.pid)):
                raise RuntimeError("--background ile başlatılan panel görünür durumda.")
            press_global_hotkey()
            hwnd = wait_for_window(process, "DosyaBul")
            width, height, style, extended = window_metrics(hwnd)
            if width > 480 or height > 380:
                raise RuntimeError(f"Boş Rofi paneli fazla büyük: {width}x{height}")
            if style & 0x00C00000:
                raise RuntimeError("Rofi panelinde Windows başlık çubuğu var.")
            if not extended & 0x00000080:
                raise RuntimeError("Rofi paneli araç penceresi olarak işaretlenmedi.")
            try:
                process.wait(timeout=0.4)
            except subprocess.TimeoutExpired:
                pass
            else:
                raise RuntimeError("Ana pencere açıldıktan hemen sonra EXE kapandı.")
            for _, title in visible_windows(process_family(process.pid)):
                if "başlatılamadı" in title or "tamamlanamadı" in title:
                    raise RuntimeError(f"EXE hata penceresi gösterdi: {title}")
            wait_until(lambda: database.search("butce").total == 1, "Otomatik indeksleme tamamlanmadı.")
            press_global_hotkey()
            wait_until(lambda: not visible_windows(process_family(process.pid)), "Genel kısayol paneli gizlemedi.", timeout=5)
            duplicate = subprocess.Popen(command, env=environment)
            processes.append(duplicate)
            if duplicate.wait(timeout=10) != 0:
                raise RuntimeError("İkinci örnek düzgün kapanmadı.")
            if process.poll() is not None:
                raise RuntimeError("İkinci örnek asıl uygulamayı kapattı.")
            hwnd = wait_for_window(process, "DosyaBul")
            close_window(hwnd)
            code = process.wait(timeout=10)
            if code != 0:
                raise RuntimeError(f"EXE hatalı çıkış kodu döndürdü: {code}")
            log = data_directory / "dosyabul.log"
            if log.exists() and log.stat().st_size:
                raise RuntimeError("EXE hata günlüğü oluşturdu:\n" + log.read_text(encoding="utf-8"))
            folders = database.search("İş Belgeleri")
            if not folders.files or folders.files[0].kind != "directory":
                raise RuntimeError("Klasörler otomatik indekslenmedi.")
            if len(database.list_roots()) != 1 or database.list_roots()[0].path != str(folder):
                raise RuntimeError("Kontrol, örnek sürücü kapsamının dışına çıktı.")
            print("EXE kontrolü başarılı: arka plan, değiştirilebilir kısayol, kompakt Rofi paneli, dosya indeksi ve tek örnek doğrulandı.")
        finally:
            for child in reversed(processes):
                if child.poll() is None:
                    # Yalnızca bu kontrolün başlattığı süreç ağacı sonlandırılır.
                    subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True, check=False)
                    child.wait(timeout=10)


if __name__ == "__main__":
    main()
