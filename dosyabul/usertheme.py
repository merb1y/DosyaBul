"""Rofi 'config.rasi' benzeri kullanıcı yapılandırması (theme.json).

Tüm anahtarlar isteğe bağlıdır; geçersiz değerler sessizce yok sayılır.
"""

import json
from dataclasses import replace
from pathlib import Path

from .settings import MODE_CHOICES, clean_color
from .themes import THEMES, Theme

COLOR_KEYS = ("background", "surface", "text", "muted", "border", "accent", "accent_text", "category")
ENTRY_ACTIONS = ("run", "terminal", "url", "path")

EXAMPLE = """{
  "_not": "Kullanmadıklarını sil. Renkler ayarlarda Kaydet'e basınca; font, çerçeve, başlık, kip ve girdiler uygulamayı yeniden başlatınca uygulanır.",

  "extends": "KooL Mocha",

  "background": "#17191D",
  "surface": "#20222A",
  "text": "#D8DEE9",
  "muted": "#89919D",
  "border": "#CBA6F7",
  "accent": "#3F6FF2",
  "accent_text": "#FFFFFF",
  "category": "#CBA6F7",

  "font": "Cascadia Code",
  "border_width": 2,
  "header_height": 54,
  "placeholder": "Ara…",
  "mode_chip": true,
  "modes": ["Tümü", "Uygulamalar", "Dosyalar", "Komutlar", "Web", "Pencereler", "Pano", "Emoji", "Sistem", "Betikler"],

  "entries": [
    {"name": "Proje klasörüm", "path": "C:\\\\Users", "keywords": "klasor proje"},
    {"name": "GitHub", "url": "https://github.com", "keywords": "kod git"},
    {"name": "Sistem güncelle", "terminal": "winget upgrade --all", "keywords": "update guncelle"}
  ]
}
"""


def theme_path(data_dir) -> Path:
    return Path(data_dir) / "theme.json"


def _read(path) -> dict:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def load_overrides(path) -> dict[str, str]:
    """Yalnızca renk anahtarlarını döndürür."""
    raw = _read(path)
    colors = {}
    for key in COLOR_KEYS:
        value = raw.get(key)
        if isinstance(value, str) and clean_color(value):
            colors[key] = clean_color(value)
    return colors


def _entries(raw) -> list[dict]:
    result = []
    if not isinstance(raw, list):
        return result
    for row in raw[:200]:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"].strip():
            continue
        actions = [(key, row[key]) for key in ENTRY_ACTIONS if isinstance(row.get(key), str) and row[key].strip()]
        if len(actions) != 1:
            continue
        keywords = row.get("keywords")
        result.append({
            "name": row["name"].strip(),
            "action": actions[0][0],
            "value": actions[0][1].strip(),
            "keywords": keywords if isinstance(keywords, str) else "",
        })
    return result


def _int(value, low, high):
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return max(low, min(high, value))


def load_config(path) -> dict:
    """Doğrulanmış tüm yapılandırmayı döndürür; olmayan anahtar sonuçta da yoktur."""
    raw = _read(path)
    config: dict = {"colors": load_overrides(path), "entries": _entries(raw.get("entries"))}
    if raw.get("extends") in THEMES:
        config["extends"] = raw["extends"]
    if isinstance(raw.get("font"), str) and raw["font"].strip():
        config["font"] = raw["font"].strip()
    for key, low, high in (("border_width", 0, 8), ("header_height", 30, 100)):
        value = _int(raw.get(key), low, high)
        if value is not None:
            config[key] = value
    if isinstance(raw.get("placeholder"), str) and raw["placeholder"].strip():
        config["placeholder"] = raw["placeholder"].strip()[:60]
    if isinstance(raw.get("mode_chip"), bool):
        config["mode_chip"] = raw["mode_chip"]
    modes = raw.get("modes")
    if isinstance(modes, list):
        ordered = []
        for mode in modes:
            if mode in MODE_CHOICES and mode not in ordered:
                ordered.append(mode)
        if ordered:
            config["modes"] = ordered
    return config


def apply_overrides(theme: Theme, overrides: dict[str, str]) -> Theme:
    return replace(theme, **overrides) if overrides else theme


def ensure_example(path) -> Path:
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(EXAMPLE, encoding="utf-8")
    return path
