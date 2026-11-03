"""Baslat menusu, UWP ve temel Windows uygulamalarini arar ve baslatir."""

import hashlib
import json
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

from .query import fold_text

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
TERMINAL_CHOICES = ("WezTerm", "Windows Terminal", "PowerShell")


@dataclass(frozen=True)
class Application:
    key: str
    name: str
    target: str
    launch_kind: str
    detail: str = "Uygulama"
    keywords: str = ""
    priority: int = 100

    @property
    def search_key(self) -> str:
        return fold_text(f"{self.name} {self.keywords} {self.target}")



@dataclass(frozen=True)
class ResultItem:
    key: str
    name: str
    detail: str
    kind: str
    target: str
    extension: str = ""
    category: str = ""

    @property
    def path(self):
        return self.target


@dataclass(frozen=True)
class LauncherResults:
    items: tuple[ResultItem, ...]
    total: int


def _key(kind: str, target: str) -> str:
    digest = hashlib.sha1(f"{kind}\0{target}".encode("utf-8", "surrogatepass")).hexdigest()
    return digest


def find_wezterm() -> str | None:
    candidates = [shutil.which("wezterm-gui.exe")]
    program_files = os.environ.get("ProgramFiles")
    local = os.environ.get("LOCALAPPDATA")
    home = Path.home()
    if program_files:
        candidates.append(str(Path(program_files) / "WezTerm" / "wezterm-gui.exe"))
    if local:
        candidates.append(str(Path(local) / "Programs" / "WezTerm" / "wezterm-gui.exe"))
    candidates.append(str(home / "scoop" / "apps" / "wezterm" / "current" / "wezterm-gui.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))
    if local:
        packages = Path(local) / "Microsoft" / "WinGet" / "Packages"
        if packages.is_dir():
            try:
                for candidate in packages.glob("*wezterm*/*/wezterm-gui.exe"):
                    if candidate.is_file():
                        return str(candidate)
            except OSError:
                pass
    return None


def builtin_applications() -> tuple[Application, ...]:
    definitions = []
    wezterm = find_wezterm()
    windows_terminal = shutil.which("wt.exe")
    if wezterm:
        definitions.append(("WezTerm", wezterm, "exe", "terminal konsol komut satiri powershell", 0))
    if windows_terminal:
        definitions.append(("Windows Terminal", windows_terminal, "exe", "terminal konsol komut satiri cmd powershell", 100))
    definitions.extend((
        ("PowerShell", "powershell.exe", "exe", "terminal konsol kabuk", 100),
        ("Komut Istemi", "cmd.exe", "exe", "terminal konsol command prompt", 100),
        ("Dosya Gezgini", "explorer.exe", "exe", "dosyalar klasor explorer", 100),
        ("Not Defteri", "notepad.exe", "exe", "notepad metin editor", 100),
        ("Gorev Yoneticisi", "taskmgr.exe", "exe", "islemler performans task manager", 100),
        ("Denetim Masasi", "control.exe", "exe", "control panel sistem", 100),
        ("Windows Ayarlari", "ms-settings:", "uri", "ayarlar settings sistem", 100),
        ("Hesap Makinesi", "calculator:", "uri", "calculator calc hesap", 100),
    ))
    apps = []
    relocatable = {"explorer.exe", "notepad.exe", "cmd.exe", "powershell.exe", "taskmgr.exe", "control.exe"}
    for name, target, kind, keywords, priority in definitions:
        if kind != "exe" or target in {wezterm, windows_terminal} or shutil.which(target) or target.lower() in relocatable:
            apps.append(Application(_key(kind, target), name, target, kind, keywords=keywords, priority=priority))
    return tuple(apps)


def start_menu_directories() -> tuple[Path, ...]:
    directories = []
    appdata = os.environ.get("APPDATA")
    programdata = os.environ.get("PROGRAMDATA")
    if appdata:
        directories.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if programdata:
        directories.append(Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return tuple(directories)


def scan_start_menu(directories=None) -> tuple[Application, ...]:
    applications = []
    for directory in directories or start_menu_directories():
        if not directory.is_dir():
            continue
        try:
            for path in directory.rglob("*"):
                try:
                    if path.is_file() and path.suffix.casefold() in {".lnk", ".url", ".appref-ms"}:
                        applications.append(Application(_key("shortcut", str(path)), path.stem, str(path), "shortcut", keywords=str(path.parent)))
                except OSError:
                    continue
        except OSError:
            continue
    return tuple(applications)


def query_start_apps(runner=subprocess.run) -> tuple[Application, ...]:
    if os.name != "nt":
        return ()
    script = "$OutputEncoding=[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"
    try:
        completed = runner(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=20, creationflags=CREATE_NO_WINDOW, check=False,
        )
        if completed.returncode or not completed.stdout.strip():
            return ()
        raw = json.loads(completed.stdout.lstrip("\ufeff"))
        rows = raw if isinstance(raw, list) else [raw]
        return tuple(
            Application(_key("appid", row["AppID"]), row["Name"], row["AppID"], "appid")
            for row in rows if isinstance(row, dict) and row.get("Name") and row.get("AppID")
        )
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, json.JSONDecodeError):
        return ()


class ApplicationIndex:
    def __init__(self):
        self._lock = threading.Lock()
        self._applications = builtin_applications()

    def refresh(self, *, directories=None, include_start_apps: bool = True):
        # Kurulu uygulamalar once gelir: ayni ada sahip yeni kurulan bir program,
        # yerlesik komut tanimi tarafindan golgelenmemeli.
        candidates = list(scan_start_menu(directories))
        if include_start_apps:
            candidates.extend(query_start_apps())
        candidates.extend(builtin_applications())
        unique = {}
        for app in candidates:
            signature = fold_text(app.name)
            existing = unique.get(signature)
            if existing is None:
                unique[signature] = app
            elif app.priority < existing.priority:
                # Ayni isimde kurulu hedef korunur, en iyi siralama onceligi tasinir.
                unique[signature] = replace(existing, priority=app.priority)
        ordered = tuple(sorted(unique.values(), key=lambda app: (fold_text(app.name), app.target.casefold())))
        with self._lock:
            self._applications = ordered

    def search(self, text: str, limit: int = 30) -> tuple[Application, ...]:
        terms = tuple(part for part in fold_text(text).split() if part)
        if not terms:
            return ()
        with self._lock:
            applications = self._applications
        matches = []
        full = " ".join(terms)
        for app in applications:
            key = app.search_key
            if all(term in key for term in terms):
                name = fold_text(app.name)
                exact = 0 if name == full else 1
                match = 0 if name == full else 1 if name.startswith(full) else 2 if full in name else 3
                rank = (exact, app.priority, match, len(name), name)
                matches.append((rank, app))
        matches.sort(key=lambda pair: pair[0])
        return tuple(app for _, app in matches[:limit])

    def all(self) -> tuple[Application, ...]:
        with self._lock:
            return self._applications


def launch_application(application) -> None:
    kind = application.launch_kind if isinstance(application, Application) else application.kind.removeprefix("app:")
    target = application.target
    if kind == "shortcut":
        os.startfile(target)
    elif kind == "appid":
        subprocess.Popen([str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "explorer.exe"), "shell:AppsFolder\\" + target])
    elif kind == "uri":
        os.startfile(target)
    else:
        subprocess.Popen([target])


def launch_terminal_command(command: str, directory: str, terminal_application: str = "WezTerm") -> None:
    command = command.strip()
    if not command:
        raise ValueError("Calistirilacak komut bos.")
    directory = directory if os.path.isdir(directory) else str(Path.home())
    powershell = shutil.which("pwsh.exe") or shutil.which("powershell.exe") or "powershell.exe"
    if terminal_application == "WezTerm":
        wezterm = find_wezterm()
        if not wezterm:
            raise FileNotFoundError("WezTerm bulunamadi. Ayarlardan baska bir terminal sec.")
        subprocess.Popen(
            [wezterm, "start", "--cwd", directory, "--", powershell, "-NoExit", "-Command", command],
            cwd=directory, creationflags=CREATE_NO_WINDOW,
        )
        return
    if terminal_application == "Windows Terminal":
        terminal = shutil.which("wt.exe")
        if not terminal:
            raise FileNotFoundError("Windows Terminal bulunamadi.")
        subprocess.Popen([terminal, "-d", directory, powershell, "-NoExit", "-Command", command], cwd=directory)
        return
    subprocess.Popen([powershell, "-NoExit", "-Command", command], cwd=directory)
