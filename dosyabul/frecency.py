"""Sık ve yakın zamanda açılan öğeleri sıralamada öne çıkaran 'frecency' deposu."""

import json
import os
import tempfile
import time
from pathlib import Path

HALF_LIFE_DAYS = 14.0
MAX_ENTRIES = 2000


class FrecencyStore:
    def __init__(self, path, clock=time.time):
        self.path = Path(path)
        self._clock = clock
        self._data: dict[str, list[float]] = self._load()

    @staticmethod
    def signature(kind: str, target: str) -> str:
        return f"{kind}|{os.path.normcase(target)}"

    def record(self, signature: str) -> None:
        count, _last = self._data.get(signature, [0.0, 0.0])
        self._data[signature] = [self._decayed(signature) + 1.0, self._clock()]
        if len(self._data) > MAX_ENTRIES:
            keep = sorted(self._data, key=self.score, reverse=True)[: MAX_ENTRIES // 2]
            self._data = {key: self._data[key] for key in keep}
        self._save()

    def _decayed(self, signature: str) -> float:
        count, last = self._data.get(signature, [0.0, 0.0])
        if not count:
            return 0.0
        age_days = max(0.0, (self._clock() - last) / 86400.0)
        return count * 0.5 ** (age_days / HALF_LIFE_DAYS)

    def score(self, signature: str) -> float:
        return self._decayed(signature)

    def rank(self, items, signature_of):
        """Skoru olan öğeleri skora göre öne alır; diğerlerinin sırası korunur."""
        items = list(items)
        scored = [(self.score(signature_of(item)), index) for index, item in enumerate(items)]
        if not any(score > 0.05 for score, _ in scored):
            return tuple(items)
        order = sorted(range(len(items)), key=lambda index: (-(scored[index][0] if scored[index][0] > 0.05 else 0.0), index))
        return tuple(items[index] for index in order)

    def _load(self) -> dict[str, list[float]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        if not isinstance(raw, dict):
            return {}
        data = {}
        for key, value in raw.items():
            if isinstance(key, str) and isinstance(value, list) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value):
                data[key] = [float(value[0]), float(value[1])]
        return data

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix="usage-", suffix=".json", dir=self.path.parent)
        except OSError:
            return
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(self._data, stream)
            os.replace(temporary, self.path)
        except OSError:
            try:
                os.unlink(temporary)
            except OSError:
                pass
