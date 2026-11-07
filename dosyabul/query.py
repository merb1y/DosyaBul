"""Türkçe karakterleri sadeleştirip arama sorgusunu ayrıştırır ve Rofi tarzı fuzzy eşleşme yapar."""

import shlex


class QueryError(ValueError):
    """Kullanıcı sorgusu ayrıştırılamadığında yükseltilir."""


_TRANSLATION = str.maketrans(
    {
        "ç": "c",
        "Ç": "c",
        "ğ": "g",
        "Ğ": "g",
        "ı": "i",
        "İ": "i",
        "ö": "o",
        "Ö": "o",
        "ş": "s",
        "Ş": "s",
        "ü": "u",
        "Ü": "u",
        "â": "a",
        "î": "i",
        "û": "u",
    }
)

_BOUNDARY_CHARS = frozenset(" -_./\\:()")


def fold_text(value: str) -> str:
    return (value or "").translate(_TRANSLATION).casefold()


def parse_plain_query(text: str) -> tuple[str, ...]:
    """Metni tırnak kurallarına uyarak sözcüklere ayırır."""
    text = (text or "").strip()
    if not text:
        return ()
    try:
        parts = shlex.split(text, posix=False)
    except ValueError as error:
        raise QueryError("Aramada kapanmayan bir tırnak var; tırnağı kapatıp yeniden dene.") from error
    return tuple(part for part in (p.strip('"') for p in parts) if part)


def fuzzy_score(query: str, candidate: str) -> int | None:
    """Rofi tarzı bulanık (fuzzy subsequence) eşleşme puanı döndürür (eşleşmezse None).

    Yüksek puan daha iyi eşleşmeyi gösterir.
    """
    q = fold_text(query).strip()
    if not q:
        return 0
    c = fold_text(candidate)
    if not c:
        return None
    if c == q:
        return 1000
    if c.startswith(q):
        return 900 - min(len(c), 80)
    pos = c.find(q)
    if pos != -1:
        boundary_bonus = 40 if (pos == 0 or c[pos - 1] in _BOUNDARY_CHARS) else 0
        return 750 + boundary_bonus - min(pos * 2, 120) - min(len(c), 80)

    tokens = q.split()
    if len(tokens) > 1 and all(tok in c for tok in tokens):
        return 680 - min(len(c), 80)

    compact_q = "".join(tokens)
    if len(compact_q) < 2:
        return None

    score = 300
    c_idx = 0
    c_len = len(c)
    prev_match = -2
    matched_boundaries = 0
    for ch in compact_q:
        found = c.find(ch, c_idx)
        if found == -1:
            return None
        if found == 0 or c[found - 1] in _BOUNDARY_CHARS:
            score += 35
            matched_boundaries += 1
        elif found == prev_match + 1:
            score += 25
        else:
            gap = found - c_idx
            score -= min(gap * 4, 30)
        prev_match = found
        c_idx = found + 1

    if matched_boundaries == 0 and prev_match - compact_q.find(compact_q[0]) > len(compact_q) * 3:
        return None
    return score - min(c_len, 60)
