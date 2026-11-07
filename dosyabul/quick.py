"""Hesap makinesi, birim çevirici, zamanlayıcı ve hızlı not yardımcıları."""

import ast
import math
import operator
import re
from datetime import datetime
from pathlib import Path

from .query import fold_text

# ---- Hesap makinesi -------------------------------------------------------

_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log10, "ln": math.log, "abs": abs, "round": round,
    "floor": math.floor, "ceil": math.ceil, "exp": math.exp,
}
_CONSTANTS = {"pi": math.pi, "e": math.e}
_MATH_CHARS = re.compile(r"^[\d\s.,+\-*/%^()a-z]+$")
MAX_EXPONENT = 1000


class CalcError(ValueError):
    """İfade hesaplanamadığında yükseltilir."""


def _evaluate(node):
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _evaluate(node.left), _evaluate(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise CalcError("Üs çok büyük.")
        try:
            return _BINARY[type(node.op)](left, right)
        except ZeroDivisionError as error:
            raise CalcError("Sıfıra bölünemez.") from error
        except OverflowError as error:
            raise CalcError("Sayı çok büyük.") from error
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_evaluate(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS and not node.keywords:
        arguments = [_evaluate(argument) for argument in node.args]
        try:
            return _FUNCTIONS[node.func.id](*arguments)
        except (ValueError, TypeError, OverflowError) as error:
            raise CalcError("Fonksiyon bu değerle hesaplanamadı.") from error
    raise CalcError("Desteklenmeyen ifade.")


def format_number(value) -> str:
    if isinstance(value, bool):
        raise CalcError("Desteklenmeyen sonuç.")
    if isinstance(value, complex) or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        raise CalcError("Sonuç tanımsız.")
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    if isinstance(value, float):
        return f"{value:.10g}"
    return str(value)


def calculate(expression: str) -> str:
    """Güvenli biçimde matematik ifadesini değerlendirir ve metin döndürür."""
    text = (expression or "").strip().lower().replace("^", "**").replace("×", "*").replace("÷", "/")
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    if not text or len(text) > 200:
        raise CalcError("İfade boş ya da çok uzun.")
    try:
        tree = ast.parse(text, mode="eval")
    except (SyntaxError, ValueError, MemoryError, RecursionError) as error:
        raise CalcError("İfade anlaşılamadı.") from error
    try:
        return format_number(_evaluate(tree))
    except RecursionError as error:
        raise CalcError("İfade çok karmaşık.") from error


def looks_like_math(text: str) -> bool:
    """Önek olmadan yazılan metnin otomatik hesaplanmaya aday olup olmadığına bakar."""
    value = (text or "").strip().lower()
    if len(value) < 3 or not _MATH_CHARS.match(value):
        return False
    if not any(char.isdigit() for char in value):
        return False
    return bool(re.search(r"\d\s*[-+*/%^]\s*[\d(]|\d\s*\)|\(|[a-z]+\(", value)) and not value.endswith(("+", "-", "*", "/", "^"))


# ---- Birim çevirici -------------------------------------------------------

# kategori -> {birim adları: taban birime çarpan}
_UNITS = {
    "uzunluk": {
        ("m", "metre", "meter"): 1.0, ("km", "kilometre", "kilometer"): 1000.0,
        ("cm", "santimetre", "santimetre"): 0.01, ("mm", "milimetre", "millimeter"): 0.001,
        ("mi", "mil", "mile", "miles"): 1609.344, ("ft", "feet", "foot", "fit"): 0.3048,
        ("in", "inch", "inc", "inç"): 0.0254, ("yd", "yard"): 0.9144,
    },
    "kütle": {
        ("kg", "kilogram", "kilo"): 1.0, ("g", "gram"): 0.001, ("mg", "miligram"): 1e-6,
        ("ton", "t"): 1000.0, ("lb", "lbs", "pound", "libre"): 0.45359237, ("oz", "ons", "ounce"): 0.028349523125,
    },
    "hacim": {
        ("l", "lt", "litre", "liter"): 1.0, ("ml", "mililitre"): 0.001,
        ("gal", "galon", "gallon"): 3.785411784, ("cup", "bardak"): 0.2365882365,
    },
    "veri": {
        ("b", "byte", "bayt"): 1.0, ("kb", "kilobayt", "kilobyte"): 1024.0,
        ("mb", "megabayt", "megabyte"): 1024.0**2, ("gb", "gigabayt", "gigabyte"): 1024.0**3,
        ("tb", "terabayt", "terabyte"): 1024.0**4,
    },
    "süre": {
        ("s", "sn", "saniye", "sec", "second"): 1.0, ("dk", "dakika", "min", "minute"): 60.0,
        ("sa", "saat", "h", "hour"): 3600.0, ("gun", "gün", "day"): 86400.0, ("hafta", "week"): 604800.0,
    },
    "hız": {
        ("m/s",): 1.0, ("km/h", "kmh", "km/sa"): 1000.0 / 3600.0, ("mph",): 0.44704, ("knot", "kt", "dugum"): 0.514444,
    },
    "alan": {
        ("m2", "m²"): 1.0, ("km2", "km²"): 1e6, ("ha", "hektar", "hectare"): 10000.0,
        ("donum", "dönüm"): 1000.0, ("acre", "akre"): 4046.8564224, ("ft2", "ft²"): 0.09290304,
    },
}
_TEMPERATURE = {"c": "c", "celsius": "c", "santigrat": "c", "f": "f", "fahrenheit": "f", "k": "k", "kelvin": "k"}
_UNIT_LOOKUP: dict[str, tuple[str, float]] = {}
for _category, _table in _UNITS.items():
    for _names, _factor in _table.items():
        for _name in _names:
            _UNIT_LOOKUP.setdefault(fold_text(_name), (_category, _factor))

_CONVERT = re.compile(
    r"^\s*([-+]?\d+(?:[.,]\d+)?)\s*([^\d\s]+)\s+(?:(?:to|in|->|=>|>|=|-)\s*)?([^\d\s]+)\s*$",
    re.IGNORECASE,
)


def _to_celsius(value: float, unit: str) -> float:
    if unit == "f":
        return (value - 32) * 5 / 9
    if unit == "k":
        return value - 273.15
    return value


def _from_celsius(value: float, unit: str) -> float:
    if unit == "f":
        return value * 9 / 5 + 32
    if unit == "k":
        return value + 273.15
    return value


def convert_units(text: str) -> str | None:
    """'10 km mi' gibi bir ifadeyi çevirir; anlaşılmazsa None döndürür."""
    match = _CONVERT.match(text or "")
    if not match:
        return None
    number = float(match.group(1).replace(",", "."))
    source, target = fold_text(match.group(2)), fold_text(match.group(3))
    temp_source, temp_target = _TEMPERATURE.get(source), _TEMPERATURE.get(target)
    if temp_source and temp_target:
        result = _from_celsius(_to_celsius(number, temp_source), temp_target)
        return f"{format_number(round(result, 6))} °{temp_target.upper()}"
    found_source, found_target = _UNIT_LOOKUP.get(source), _UNIT_LOOKUP.get(target)
    if not found_source or not found_target or found_source[0] != found_target[0]:
        return None
    result = number * found_source[1] / found_target[1]
    return f"{format_number(float(f'{result:.10g}'))} {match.group(3)}"


# ---- Zamanlayıcı ------------------------------------------------------------

_TIMER_PREFIXES = ("timer", "zamanlayici", "zamanlayıcı", "sayac", "sayaç")
_DURATION = re.compile(r"(\d+(?:[.,]\d+)?)\s*(saat|sa|h|dakika|dk|min|m|saniye|sn|s)(?![a-zA-ZçğıöşüÇĞİÖŞÜ])", re.IGNORECASE)
_UNIT_SECONDS = {"saat": 3600, "sa": 3600, "h": 3600, "dakika": 60, "dk": 60, "min": 60, "m": 60, "saniye": 1, "sn": 1, "s": 1}


def is_timer_prefix(text: str) -> bool:
    words = (text or "").split()
    return bool(words) and words[0].casefold() in _TIMER_PREFIXES


def parse_timer(text: str) -> tuple[int, str] | None:
    """'timer 10m çay' -> (600, 'çay'). Önek yoksa ya da süre anlaşılmazsa None."""
    value = (text or "").strip()
    lowered = value.casefold()
    for prefix in _TIMER_PREFIXES:
        if lowered == prefix or lowered.startswith(prefix + " "):
            rest = value[len(prefix):].strip()
            break
    else:
        return None
    if not rest:
        return None
    bare = re.match(r"^(\d+)(?:\s+(.*))?$", rest)
    if bare:
        seconds = int(bare.group(1)) * 60  # birimsiz sayı dakikadır
        label = (bare.group(2) or "").strip()
    else:
        matches = list(_DURATION.finditer(rest))
        if not matches or matches[0].start() != 0:
            return None
        seconds = 0.0
        end = 0
        for match in matches:
            if rest[end:match.start()].strip():
                break
            seconds += float(match.group(1).replace(",", ".")) * _UNIT_SECONDS[match.group(2).casefold()]
            end = match.end()
        seconds = int(seconds)
        label = rest[end:].strip()
    if seconds <= 0 or seconds > 7 * 86400:
        return None
    return seconds, label


def format_duration(seconds: int) -> str:
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    parts = []
    if hours:
        parts.append(f"{hours} sa")
    if minutes:
        parts.append(f"{minutes} dk")
    if secs or not parts:
        parts.append(f"{secs} sn")
    return " ".join(parts)


# ---- Hızlı notlar -----------------------------------------------------------

_NOTE_PREFIXES = ("n:", "not:", "note:")


def parse_note(text: str) -> str | None:
    """'n: süt al' -> 'süt al'; önek yoksa None, önek boşsa ''."""
    value = (text or "").strip()
    lowered = value.casefold()
    for prefix in _NOTE_PREFIXES:
        if lowered.startswith(prefix):
            return value[len(prefix):].strip()
    return None


def append_note(path, text: str, now: datetime | None = None) -> None:
    path = Path(path)
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"{stamp}  {text.strip()}\n")
