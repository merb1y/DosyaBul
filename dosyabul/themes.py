"""Rofi rasi temalarindan uyarlanan renk semalari."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    background: str
    surface: str
    text: str
    muted: str
    border: str
    accent: str
    accent_text: str
    category: str

    def with_colors(self, *, accent: str | None = None, border: str | None = None, background: str | None = None, surface: str | None = None, text: str | None = None) -> "Theme":
        """Temayı, verilen renklerle ezerek yeni bir tema döndürür."""
        return Theme(
            name=self.name,
            background=background or self.background,
            surface=surface or self.surface,
            text=text or self.text,
            muted=self.muted,
            border=border or self.border,
            accent=accent or self.accent,
            accent_text=self.accent_text,
            category=accent or self.category,
        )


ACCENT_PRESETS = (
    ("Mavi", "#3F6FF2"),
    ("Mor", "#CBA6F7"),
    ("Yesil", "#A6E3A1"),
    ("Turkuaz", "#89DCEB"),
    ("Kirmizi", "#F38BA8"),
    ("Turuncu", "#FE8019"),
    ("Sari", "#F9E2AF"),
    ("Pembe", "#F5C2E7"),
)


THEMES = {
    "KooL Mocha": Theme(
        name="KooL Mocha",
        background="#17191D",
        surface="#20222A",
        text="#D8DEE9",
        muted="#89919D",
        border="#CBA6F7",
        accent="#3F6FF2",
        accent_text="#FFFFFF",
        category="#CBA6F7",
    ),
    "Nord": Theme(
        name="Nord",
        background="#2E3440",
        surface="#3B4252",
        text="#D8DEE9",
        muted="#7B8699",
        border="#88C0D0",
        accent="#5E81AC",
        accent_text="#ECEFF4",
        category="#88C0D0",
    ),
    "Gruvbox": Theme(
        name="Gruvbox",
        background="#282828",
        surface="#3C3836",
        text="#EBDBB2",
        muted="#A89984",
        border="#FABD2F",
        accent="#D79921",
        accent_text="#282828",
        category="#FE8019",
    ),
    "Tokyo Night": Theme(
        name="Tokyo Night",
        background="#1A1B26",
        surface="#24283B",
        text="#C0CAF5",
        muted="#565F89",
        border="#7AA2F7",
        accent="#3D59A1",
        accent_text="#FFFFFF",
        category="#BB9AF7",
    ),
    "Solarized": Theme(
        name="Solarized",
        background="#002B36",
        surface="#073642",
        text="#93A1A1",
        muted="#586E75",
        border="#268BD2",
        accent="#268BD2",
        accent_text="#FDF6E3",
        category="#B58900",
    ),
}


def resolve(name: str) -> Theme:
    return THEMES.get(name, THEMES["KooL Mocha"])
