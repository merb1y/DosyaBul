"""Türkçe karakterleri sadeleştirip arama sorgusunu ayrıştırır."""

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
