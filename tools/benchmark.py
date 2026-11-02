"""Gerçek kullanıcı dosyalarına dokunmadan sentetik indeks hızını ölçer."""

import argparse
import statistics
import tempfile
import time
from pathlib import Path

from dosyabul.database import IndexDatabase
from dosyabul.models import IndexedFile
from dosyabul.query import fold_path, fold_text


def main():
    parser = argparse.ArgumentParser(description="Sentetik dosya indeksi için hız ölçümü.")
    parser.add_argument("--files", type=int, default=20000)
    args = parser.parse_args()
    if not 1 <= args.files <= 1000000:
        parser.error("Dosya sayısı 1 ile 1000000 arasında olmalı.")
    with tempfile.TemporaryDirectory(prefix="dosyabulhiz") as temporary:
        base = Path(temporary)
        folder = base / "Belgeler"
        folder.mkdir()
        database = IndexDatabase(base / "index.sqlite3")
        root = database.add_root(folder)
        started = time.perf_counter()
        batch = []
        for number in range(args.files):
            name = f"Bütçe raporu {number:06d}.pdf" if number % 10 == 0 else f"Proje notları {number:06d}.txt"
            path = str(folder / f"Proje-{number % 100}" / name)
            batch.append(IndexedFile(root.id, path, name, str(Path(path).parent), Path(name).suffix, number * 128, time.time(), fold_text(name), fold_path(path), "benchmark"))
            if len(batch) >= 1000:
                database.upsert_files(batch)
                batch.clear()
        database.upsert_files(batch)
        indexing_seconds = time.perf_counter() - started
        print(f"Sentetik kayıt sayısı: {args.files:,}")
        print(f"İndeks oluşturma: {indexing_seconds:.2f} saniye (disk taraması dahil değil)")
        print(f"İndeks boyutu: {database.path.stat().st_size / 1024**2:.1f} MB")
        for query in ("butce", "raporu 001", "tür:pdf boyut:>1MB", "proje -notlari", "19999"):
            results = [database.search(query) for _ in range(5)]
            median = statistics.median(result.elapsed_ms for result in results)
            print(f"{query!r}: {results[-1].total} sonuç, ortanca {median:.1f} ms")


if __name__ == "__main__":
    main()
