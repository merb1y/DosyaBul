"""DosyaBul'dan acilan son uygulama ve komutlari saklar."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

MAX_RECENT = 5


@dataclass(frozen=True)
class LaunchRecord:
    kind: str
    name: str
    target: str
    detail: str = ""

    @property
    def signature(self) -> tuple[str, str]:
        return (self.kind, os.path.normcase(self.target))


class LaunchHistory:
    """En son acilan uygulamalari ve komutlari en yeniden eskiye tutar."""

    def __init__(self, path, limit: int = MAX_RECENT):
        self.path = Path(path)
        self.limit = max(1, int(limit))
        self._entries = self._load()

    def entries(self) -> tuple[LaunchRecord, ...]:
        return self._entries

    def record(self, entry: LaunchRecord) -> None:
        if not entry.target:
            return
        entries = [item for item in self._entries if item.signature != entry.signature]
        entries.insert(0, entry)
        self._entries = tuple(entries[: self.limit])
        self._save()

    def clear(self) -> None:
        self._entries = ()
        self._save()

    def _load(self) -> tuple[LaunchRecord, ...]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return ()
        rows = raw.get("entries") if isinstance(raw, dict) else raw
        if not isinstance(rows, list):
            return ()
        entries = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            kind, name, target = row.get("kind"), row.get("name"), row.get("target")
            if not all(isinstance(value, str) for value in (kind, name, target)):
                continue
            if not target or (kind != "command" and not kind.startswith("app:")):
                continue
            detail = row.get("detail")
            entries.append(LaunchRecord(kind, name, target, detail if isinstance(detail, str) else ""))
            if len(entries) >= self.limit:
                break
        return tuple(entries)

    def _save(self) -> None:
        payload = {"version": 1, "entries": [asdict(entry) for entry in self._entries]}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix="history-", suffix=".json", dir=self.path.parent)
        except OSError:
            return
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary, self.path)
        except OSError:
            try:
                os.unlink(temporary)
            except OSError:
                pass
