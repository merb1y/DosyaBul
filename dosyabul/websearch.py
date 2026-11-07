import re
import webbrowser
from dataclasses import dataclass
from urllib.parse import quote_plus, urlparse

SEARCH_ENGINES = ("Google", "DuckDuckGo", "Bing")

_ENGINE_URLS = {
    "Google": "https://www.google.com/search?q={}",
    "DuckDuckGo": "https://duckduckgo.com/?q={}",
    "Bing": "https://www.bing.com/search?q={}",
}

_DOMAIN = re.compile(r"^[\w-]+(\.[\w-]+)+([/?#].*)?$", re.UNICODE)
_SAFE_SCHEMES = {"http", "https"}


DEFAULT_SHORTCUTS = {
    "yt": "https://www.youtube.com/results?search_query={}",
    "gh": "https://github.com/search?q={}",
    "tr": "https://translate.google.com/?sl=auto&tl=tr&text={}",
    "en": "https://translate.google.com/?sl=auto&tl=en&text={}",
    "w": "https://tr.wikipedia.org/w/index.php?search={}",
    "maps": "https://www.google.com/maps/search/{}",
    "so": "https://stackoverflow.com/search?q={}",
}


@dataclass(frozen=True)
class WebTarget:
    text: str
    detail: str
    url: str


def clean_shortcuts(value) -> dict:
    """Yalnızca {} içeren http(s) şablonlarını ve tek sözcüklü anahtarları tutar."""
    if not isinstance(value, dict):
        return dict(DEFAULT_SHORTCUTS)
    cleaned = {}
    for key, template in value.items():
        if not isinstance(key, str) or not isinstance(template, str):
            continue
        key = key.strip().casefold()
        if not key or " " in key or template.count("{}") != 1:
            continue
        if urlparse(template.replace("{}", "x")).scheme not in _SAFE_SCHEMES:
            continue
        cleaned[key] = template
    return cleaned


def resolve_web_input(text: str, engine: str = "Google", shortcuts: dict | None = None) -> WebTarget:
    value = (text or "").strip()
    if not value:
        raise ValueError("Web aramasi bos olamaz.")
    if shortcuts:
        key, _, rest = value.partition(" ")
        template = shortcuts.get(key.casefold())
        if template and rest.strip():
            query = rest.strip()
            return WebTarget(query, f"{key.casefold()} ile ara", template.format(quote_plus(query)))
    lowered = value.casefold()
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        if parsed.scheme in _SAFE_SCHEMES and parsed.netloc:
            return WebTarget(value, "Adresi ac", value)
    if "://" in value:
        return WebTarget(value, "Web'de ara", build_search_url(value, engine))
    if _DOMAIN.match(value) and " " not in value:
        return WebTarget(value, "Siteyi ac", "https://" + value)
    return WebTarget(value, "Web'de ara", build_search_url(value, engine))


def build_search_url(text: str, engine: str = "Google") -> str:
    template = _ENGINE_URLS.get(engine, _ENGINE_URLS["Google"])
    return template.format(quote_plus(text))


def open_web(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in _SAFE_SCHEMES:
        return False
    return webbrowser.open(url)
