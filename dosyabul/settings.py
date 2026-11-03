import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .applications import TERMINAL_CHOICES
from .hotkey import DEFAULT_SPEC, HotkeySpec, format_hotkey, parse_hotkey
from .websearch import SEARCH_ENGINES

ROW_CHOICES = (5, 7, 10, 12)
POSITION_CHOICES = (
    "Üst sol", "Üst orta", "Üst sağ",
    "Orta sol", "Orta", "Orta sağ",
    "Alt sol", "Alt orta", "Alt sağ",
)
MONITOR_CHOICES = ("Fare imlecinin ekranı", "Ana ekran", "Etkin pencerenin ekranı")
MODE_CHOICES = ("Tümü", "Uygulamalar", "Dosyalar", "Komutlar", "Web", "Pencereler")
THEME_CHOICES = ("KooL Mocha", "Nord", "Gruvbox", "Tokyo Night", "Solarized")


def clean_color(value: str) -> str:
    """"#RRGGBB" biçiminde geçerli bir renk döndürür; geçersizse boş metin."""
    text = (value or "").strip()
    if not text:
        return ""
    if not text.startswith("#"):
        text = "#" + text
    if len(text) == 7 and all(ch in "0123456789abcdefABCDEF" for ch in text[1:]):
        return text.upper()
    return ""


@dataclass
class AppSettings:
    hotkey: str = format_hotkey(DEFAULT_SPEC)
    hotkey_modifiers: int = DEFAULT_SPEC.modifiers
    hotkey_key: int = DEFAULT_SPEC.key
    visible_rows: int = 10
    opacity: int = 97
    panel_width: int = 600
    panel_position: str = "Orta"
    monitor_mode: str = "Fare imlecinin ekranı"
    search_engine: str = "Google"
    hide_on_focus_loss: bool = True
    refresh_on_start: bool = False
    show_on_startup: bool = False
    search_files: bool = True
    search_apps: bool = True
    search_commands: bool = True
    search_windows: bool = True
    terminal_application: str = "WezTerm"
    terminal_directory: str = ""
    font_size: int = 15
    row_scale: int = 140
    theme: str = "KooL Mocha"
    accent_color: str = ""
    default_mode: str = "Uygulamalar"
    confirm_executables: bool = True
    minimize_to_tray: bool = True
    settings_version: int = 2

    @property
    def hotkey_spec(self) -> HotkeySpec:
        return HotkeySpec(self.hotkey_modifiers, self.hotkey_key).normalized()

    def normalized(self) -> "AppSettings":
        try:
            spec = self.hotkey_spec
        except (TypeError, ValueError):
            spec = DEFAULT_SPEC
        return AppSettings(
            hotkey=format_hotkey(spec),
            hotkey_modifiers=spec.modifiers,
            hotkey_key=spec.key,
            visible_rows=self.visible_rows if self.visible_rows in ROW_CHOICES else 10,
            opacity=max(85, min(100, int(self.opacity))),
            panel_width=max(320, min(800, int(self.panel_width))),
            panel_position=self.panel_position if self.panel_position in POSITION_CHOICES else "Orta",
            monitor_mode=self.monitor_mode if self.monitor_mode in MONITOR_CHOICES else "Fare imlecinin ekranı",
            search_engine=self.search_engine if self.search_engine in SEARCH_ENGINES else "Google",
            hide_on_focus_loss=bool(self.hide_on_focus_loss),
            refresh_on_start=bool(self.refresh_on_start),
            show_on_startup=bool(self.show_on_startup),
            search_files=bool(self.search_files),
            search_apps=bool(self.search_apps),
            search_commands=bool(self.search_commands),
            search_windows=bool(self.search_windows),
            terminal_application=self.terminal_application if self.terminal_application in TERMINAL_CHOICES else "WezTerm",
            terminal_directory=self.terminal_directory if os.path.isdir(self.terminal_directory) else str(Path.home()),
            font_size=max(9, min(24, int(self.font_size))),
            row_scale=max(80, min(200, int(self.row_scale))),
            theme=self.theme if self.theme in THEME_CHOICES else "KooL Mocha",
            accent_color=clean_color(self.accent_color),
            default_mode=self.default_mode if self.default_mode in MODE_CHOICES else "Uygulamalar",
            confirm_executables=bool(self.confirm_executables),
            minimize_to_tray=bool(self.minimize_to_tray),
            settings_version=2,
        )


class SettingsStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings(terminal_directory=str(Path.home()))
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Ayar dosyasının kökü nesne olmalı.")
            if "hotkey_modifiers" not in raw or "hotkey_key" not in raw:
                try:
                    migrated = parse_hotkey(raw.get("hotkey", format_hotkey(DEFAULT_SPEC)))
                except (TypeError, ValueError):
                    migrated = DEFAULT_SPEC
                raw["hotkey_modifiers"] = migrated.modifiers
                raw["hotkey_key"] = migrated.key
            allowed = AppSettings.__dataclass_fields__.keys()
            settings = AppSettings(**{key: raw[key] for key in allowed if key in raw}).normalized()
            if "settings_version" not in raw and settings.default_mode == "Tümü":
                # 1.9: ana sayfa artık yalnızca uygulama arıyor; dosya araması ayrı kipte.
                settings = replace(settings, default_mode="Uygulamalar")
            return settings
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return AppSettings(terminal_directory=str(Path.home()))

    def save(self, settings: AppSettings) -> AppSettings:
        settings = settings.normalized()
        descriptor, temporary = tempfile.mkstemp(prefix="settings-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(asdict(settings), stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        return settings
