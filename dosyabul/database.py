"""Arama indeksini SQLite üzerinde tutar."""

import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .models import FileResult, ScanReport, SearchResults
from .query import fold_text

SCHEMA_VERSION = 3
BATCH_SIZE = 2000

CREATE_ROOTS = """
CREATE TABLE IF NOT EXISTS roots (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    last_scan REAL NOT NULL DEFAULT 0
)
"""

CREATE_ITEMS = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    root_id INTEGER NOT NULL REFERENCES roots(id) ON DELETE CASCADE,
    parent TEXT NOT NULL,
    name TEXT NOT NULL,
    folded TEXT NOT NULL,
    path TEXT NOT NULL,
    kind TEXT NOT NULL,
    extension TEXT NOT NULL DEFAULT '',
    size INTEGER NOT NULL DEFAULT 0,
    modified REAL NOT NULL DEFAULT 0
)
"""

CREATE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS items_folded ON items(folded)",
    "CREATE INDEX IF NOT EXISTS items_root ON items(root_id)",
    "CREATE INDEX IF NOT EXISTS items_path ON items(path)",
)

CREATE_META = "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"


@dataclass(frozen=True)
class Root:
    id: int
    path: str
    last_scan: float


class SearchCancelled(Exception):
    """Arama iptal edildiğinde yükseltilir."""


MATCH_TAG = "dosyabul"


def _like_pattern(text: str) -> str:
    escaped = fold_text(text).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class IndexDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._create_schema()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def _create_schema(self):
        with self._lock, self._connection:
            self._connection.execute(CREATE_ROOTS)
            self._connection.execute(CREATE_ITEMS)
            for statement in CREATE_INDEXES:
                self._connection.execute(statement)
            self._connection.execute(CREATE_META)
            self._connection.execute(
                "INSERT INTO meta(key, value) VALUES('schema', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )

    def close(self):
        with self._lock:
            self._connection.close()

    # ---- Root yönetimi -------------------------------------------------

    def add_root(self, path: str | Path) -> Root:
        target = str(Path(path))
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR IGNORE INTO roots(path, last_scan) VALUES(?, 0)", (target,)
            )
            row = self._connection.execute(
                "SELECT id, path, last_scan FROM roots WHERE path = ?", (target,)
            ).fetchone()
        return Root(row["id"], row["path"], row["last_scan"])

    def list_roots(self) -> tuple[Root, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT id, path, last_scan FROM roots ORDER BY path"
            ).fetchall()
        return tuple(Root(row["id"], row["path"], row["last_scan"]) for row in rows)

    def synchronize_drives(self, paths) -> tuple[Root, ...]:
        """Algılanan sürücüleri indekse ekler, kaybolanları temizler."""
        detected = {str(Path(path)) for path in paths}
        with self._lock, self._connection:
            existing = {row["path"]: row["id"] for row in self._connection.execute("SELECT id, path FROM roots")}
            for path in detected - existing.keys():
                self._connection.execute("INSERT INTO roots(path) VALUES(?)", (path,))
            for path, root_id in existing.items():
                if path not in detected:
                    self._connection.execute("DELETE FROM items WHERE root_id = ?", (root_id,))
                    self._connection.execute("DELETE FROM roots WHERE id = ?", (root_id,))
        return self.list_roots()

    def mark_scanned(self, root_id: int, when: float | None = None):
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE roots SET last_scan = ? WHERE id = ?", (when or time.time(), root_id)
            )

    def overview(self):
        with self._lock:
            roots = self._connection.execute("SELECT COUNT(*) AS n FROM roots").fetchone()["n"]
            items = self._connection.execute("SELECT COUNT(*) AS n FROM items").fetchone()["n"]
            last = self._connection.execute("SELECT MAX(last_scan) AS t FROM roots").fetchone()["t"]
        return roots, items, last or 0.0

    def clear_items(self, root_id: int):
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM items WHERE root_id = ?", (root_id,))

    # ---- Tarama --------------------------------------------------------

    def begin_scan(self) -> "ScanWriter":
        return ScanWriter(self)

    def replace_tree_batch(self, root_id: int, batch) -> int:
        """Toplu hâlde taranan öğeleri yazar."""
        rows = [
            (
                root_id,
                str(Path(entry.path).parent),
                entry.name,
                fold_text(entry.name),
                entry.path,
                entry.kind,
                entry.extension,
                entry.size,
                entry.modified,
            )
            for entry in batch
        ]
        if not rows:
            return 0
        with self._lock, self._connection:
            self._connection.executemany(
                "INSERT INTO items(root_id, parent, name, folded, path, kind, extension, size, modified) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                rows,
            )
        return len(rows)

    # ---- Arama ---------------------------------------------------------

    def search(self, parsed, limit: int = 500, cancel=None) -> SearchResults:
        terms = tuple(term for term in (parsed or ()) if term)
        if not terms:
            return SearchResults((), 0, 0, limit)
        clauses = []
        params: list = []
        for term in terms:
            clauses.append("folded LIKE ? ESCAPE '\\'")
            params.append(_like_pattern(term))
        where = " AND ".join(clauses)
        with self._lock:
            total = self._connection.execute(
                f"SELECT COUNT(*) AS n FROM items WHERE {where}", params
            ).fetchone()["n"]
            rows = self._connection.execute(
                f"SELECT id, name, parent, path, kind, extension, size, modified "
                f"FROM items WHERE {where} ORDER BY length(name), name LIMIT ?",
                params + [limit],
            ).fetchall()
        if cancel is not None and cancel.is_set():
            raise SearchCancelled()
        files = tuple(
            FileResult(
                id=row["id"],
                name=row["name"],
                parent=row["parent"],
                path=row["path"],
                kind=row["kind"],
                extension=row["extension"],
                size=row["size"],
                modified=row["modified"],
            )
            for row in rows
        )
        return SearchResults(files, total, len(files), limit)

    def lookup(self, item_id: int) -> FileResult | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT id, name, parent, path, kind, extension, size, modified FROM items WHERE id = ?",
                (item_id,),
            ).fetchone()
        if row is None:
            return None
        return FileResult(
            id=row["id"], name=row["name"], parent=row["parent"], path=row["path"],
            kind=row["kind"], extension=row["extension"], size=row["size"], modified=row["modified"],
        )


class ScanWriter:
    """Taramayı katmanlı yazar; sonunda eski kayıtları temizler."""

    def __init__(self, database: IndexDatabase):
        self.database = database
        self._buffer = []
        self._written = 0
        self._seen = 0

    def add(self, root_id: int, entry):
        self._buffer.append((root_id, entry))
        if len(self._buffer) >= BATCH_SIZE:
            self.flush()

    def flush(self):
        if not self._buffer:
            return
        groups: dict[int, list] = {}
        for root_id, entry in self._buffer:
            groups.setdefault(root_id, []).append(entry)
        for root_id, entries in groups.items():
            self._written += self.database.replace_tree_batch(root_id, entries)
            self._seen += len(entries)
        self._buffer = []

    def finish(self) -> int:
        self.flush()
        return self._written
