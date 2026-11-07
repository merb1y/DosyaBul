"""DosyaBul'a sabitlenen uygulamalar (pinned.json) ve Windows sağ tık menüsü kaydı."""

import json
import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .applications import ResultItem

MAX_HOME_PINS = 8

_CONTEXT_MENU_KEYS = (
    r"Software\Classes\exefile\shell\DosyaBulPin",
    r"Software\Classes\lnkfile\shell\DosyaBulPin",
    r"Software\Classes\InternetShortcut\shell\DosyaBulPin",
    r"Software\Classes\SystemFileAssociations\.exe\shell\DosyaBulPin",
    r"Software\Classes\SystemFileAssociations\.lnk\shell\DosyaBulPin",
)


@dataclass(frozen=True)
class PinnedItem:
    name: str
    target: str
    kind: str = "app:shortcut"
    added_at: float = 0.0

    def to_result_item(self, index: int = 0) -> ResultItem:
        return ResultItem(
            key=f"pin:{index}:{self.target.casefold()}",
            name=self.name,
            detail="Sabitlendi",
            kind=self.kind,
            target=self.target,
        )


def infer_pin_kind(path: str | Path) -> str:
    p = Path(path)
    if p.is_dir():
        return "directory"
    ext = p.suffix.casefold()
    if ext in (".lnk", ".url", ".appref-ms"):
        return "app:shortcut"
    if ext in (".exe", ".bat", ".cmd", ".com"):
        return "app:exe"
    return "file"


def infer_pin_name(path: str | Path) -> str:
    p = Path(path)
    stem = p.stem if p.suffix else p.name
    if stem.lower().endswith("-gui") and len(stem) > 4:
        stem = stem[:-4]
    return stem


class PinStore:
    """Sabitlenen uygulamaları en son eklenen en başta olacak şekilde saklar."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._last_mtime: float = -1.0
        self._cached: tuple[PinnedItem, ...] = ()

    def load(self) -> tuple[PinnedItem, ...]:
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            self._cached = ()
            self._last_mtime = -1.0
            return ()
        if mtime == self._last_mtime and self._cached:
            return self._cached
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return ()
        if not isinstance(raw, list):
            return ()
        items: list[PinnedItem] = []
        seen: set[str] = set()
        for row in raw:
            if not isinstance(row, dict):
                continue
            target = str(row.get("target") or "").strip()
            name = str(row.get("name") or "").strip()
            if not target or not name:
                continue
            norm = target.casefold()
            if norm in seen:
                continue
            seen.add(norm)
            kind = str(row.get("kind") or infer_pin_kind(target))
            added_at = float(row.get("added_at") or 0.0)
            items.append(PinnedItem(name=name, target=target, kind=kind, added_at=added_at))
        self._cached = tuple(items)
        self._last_mtime = mtime
        return self._cached

    def recent(self, limit: int = MAX_HOME_PINS) -> tuple[PinnedItem, ...]:
        """En son sabitlenen `limit` (varsayılan 8) uygulamayı döndürür."""
        return self.load()[: max(1, int(limit))]

    def is_pinned(self, target: str | Path) -> bool:
        norm = str(target).strip().casefold()
        return any(item.target.casefold() == norm for item in self.load())

    def pin(self, target: str | Path, name: str | None = None, kind: str | None = None) -> PinnedItem:
        target_str = str(target).strip().strip('"')
        if not target_str:
            raise ValueError("Sabitlenecek hedef boş.")
        resolved_name = (name or "").strip() or infer_pin_name(target_str)
        resolved_kind = (kind or "").strip() or infer_pin_kind(target_str)
        new_item = PinnedItem(
            name=resolved_name,
            target=target_str,
            kind=resolved_kind,
            added_at=time.time(),
        )
        norm = target_str.casefold()
        existing = [item for item in self.load() if item.target.casefold() != norm]
        updated = [new_item] + existing
        self._save(updated)
        return new_item

    def unpin(self, target: str | Path) -> bool:
        norm = str(target).strip().strip('"').casefold()
        existing = list(self.load())
        filtered = [item for item in existing if item.target.casefold() != norm]
        if len(filtered) == len(existing):
            return False
        self._save(filtered)
        return True

    def _save(self, items: list[PinnedItem]) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix="pinned-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump([asdict(item) for item in items], stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self._cached = tuple(items)
            try:
                self._last_mtime = self.path.stat().st_mtime
            except OSError:
                pass
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise


def default_executable_command() -> tuple[str, str]:
    """(komut_öneki, ikon_yolu) döndürür."""
    installed = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "Programs" / "DosyaBul" / "DosyaBul.exe"
    if installed.is_file():
        return f'"{installed}"', f'"{installed}",0'
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        return f'"{exe}"', f'"{exe}",0'
    run_py = Path(__file__).resolve().parent.parent / "run.py"
    py = Path(sys.executable).resolve()
    return f'"{py}" "{run_py}"', f'"{py}",0'


def register_context_menu(exe_path: str | Path | None = None) -> bool:
    """Windows Gezgini sağ tık menüsüne 'DosyaBul'a sabitle' seçeneğini ekler."""
    if os.name != "nt":
        return False
    import winreg

    if exe_path is not None:
        exe_str = str(Path(exe_path).resolve())
        cmd_prefix = f'"{exe_str}"'
        icon_val = f'"{exe_str}",0'
    else:
        cmd_prefix, icon_val = default_executable_command()

    command_str = f'{cmd_prefix} --pin "%1"'
    try:
        for base_key in _CONTEXT_MENU_KEYS:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base_key) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "DosyaBul'a sabitle")
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon_val)
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base_key + r"\command") as cmd_key:
                winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command_str)
        return True
    except OSError:
        return False


def unregister_context_menu() -> None:
    """Windows Gezgini sağ tık menüsünden 'DosyaBul'a sabitle' seçeneğini kaldırır."""
    if os.name != "nt":
        return
    import winreg

    for base_key in _CONTEXT_MENU_KEYS:
        for sub in (base_key + r"\command", base_key):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
            except OSError:
                pass
