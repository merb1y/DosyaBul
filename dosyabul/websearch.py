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


@dataclass(frozen=True)
class WebTarget:
    text: str
    detail: str
    url: str


def resolve_web_input(text: str, engine: str = "Google") -> WebTarget:
    value = (text or "").strip()
    if not value:
        raise ValueError("Web aramasi bos olamaz.")
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
