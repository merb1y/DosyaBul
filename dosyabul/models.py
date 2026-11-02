"""Arama sonuçlarını taşıyan basit veri modelleri."""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class FileResult:
    id: int
    name: str
    parent: str
    path: str
    kind: str
    extension: str = ""
    size: int = 0
    modified: float = 0.0


@dataclass(frozen=True)
class SearchResults:
    files: Tuple[FileResult, ...]
    total: int
    scanned: int = 0
    limit: int = 500


@dataclass(frozen=True)
class ScanProgress:
    items_seen: int
    current: str = ""


@dataclass(frozen=True)
class ScanReport:
    roots: int = 0
    added: int = 0
    removed: int = 0
    errors: Tuple[str, ...] = ()

    @property
    def skipped(self) -> bool:
        return bool(self.errors)
