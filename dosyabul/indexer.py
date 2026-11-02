"""Sürücüleri gezerek dosya adlarını indeksler."""

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .database import IndexDatabase
from .models import ScanProgress, ScanReport

SKIP_NAMES = {
    "$recycle.bin",
    "system volume information",
    "windows.old",
    "$windows.~bt",
    "$windows.~ws",
    "recovery",
    "perflogs",
}
SKIP_PATHS = {"\\", "\\windows\\winsxs"}


@dataclass(frozen=True)
class Entry:
    name: str
    path: str
    kind: str
    extension: str = ""
    size: int = 0
    modified: float = 0.0


def _entry_for(path: Path, stat_result) -> Entry:
    is_directory = path.is_dir()
    return Entry(
        name=path.name,
        path=str(path),
        kind="directory" if is_directory else "file",
        extension="" if is_directory else path.suffix.casefold().lstrip("."),
        size=0 if is_directory else stat_result.st_size,
        modified=stat_result.st_mtime,
    )


class Indexer:
    def __init__(self, database: IndexDatabase):
        self.database = database
        self._visited = 0

    def scan(self, roots, cancel: threading.Event, progress=None) -> ScanReport:
        writer = self.database.begin_scan()
        added = 0
        errors = []
        for root in roots:
            try:
                added += self._scan_root(root, cancel, writer, progress)
            except OSError as error:
                errors.append(f"{root.path}: {error}")
            finally:
                writer.flush()
            self.database.mark_scanned(root.id)
        return ScanReport(roots=len(roots), added=added, removed=0, errors=tuple(errors))

    def _scan_root(self, root, cancel, writer, progress) -> int:
        stack = [Path(root.path)]
        while stack:
            if cancel.is_set():
                return writer.finish()
            folder = stack.pop()
            try:
                with os.scandir(folder) as scanner:
                    for item in scanner:
                        if cancel.is_set():
                            return writer.finish()
                        name = item.name
                        if name.casefold() in SKIP_NAMES:
                            continue
                        try:
                            is_dir = item.is_dir(follow_symlinks=False)
                            stat_result = item.stat()
                        except OSError:
                            continue
                        path = Path(item.path)
                        writer.add(root.id, _entry_for(path, stat_result))
                        self._visited += 1
                        if is_dir and not item.is_symlink():
                            stack.append(path)
                        if progress is not None and self._visited % 400 == 0:
                            progress(ScanProgress(self._visited, str(folder)))
            except OSError:
                continue
        return writer.finish()
