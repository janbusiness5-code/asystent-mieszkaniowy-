import re
import unicodedata
from typing import Optional, Tuple, Any


def strip_accents(text: str) -> str:
    if text is None:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def norm_text(text: str) -> str:
    return strip_accents(text or "").lower().strip()


def to_int_safe(x, default: Optional[int] = None) -> Optional[int]:
    try:
        if x is None or (isinstance(x, float) and (x != x)):  # NaN
            return default
        if isinstance(x, (int, float)):
            return int(round(float(x)))
        s = str(x).strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
        m = re.search(r"(\d+(?:\.\d+)?)", s)
        if not m:
            return default
        num = float(m.group(1))
        if re.search(r"(mln|mili|m\b)", s):
            num *= 1_000_000
        elif re.search(r"(tys|k\b)", s):
            num *= 1_000
        return int(round(num))
    except Exception:
        return default


def to_float_safe(x, default: Optional[float] = None) -> Optional[float]:
    try:
        if x is None or (isinstance(x, float) and (x != x)):
            return default
        return float(str(x).replace(" ", "").replace("\u00a0", "").replace(",", "."))
    except Exception:
        return default


def norm_bool(val) -> Optional[bool]:
    if val is None:
        return None
    s = norm_text(str(val))
    truthy = {
        "t", "true", "tak", "yes", "y", "1", "z", "jest", "ma", "posiada", "with",
        "z balkonem", "z winda", "z windą",
    }
    falsy = {
        "f", "false", "nie", "no", "n", "0", "bez", "brak",
        "bez balkonu", "bez windy", "bez windą",
    }
    if s in truthy:
        return True
    if s in falsy:
        return False
    if "bez" in s:
        return False
    if "z " in s or "ma " in s:
        return True
    return None


def safe_range(min_v, max_v) -> Optional[Tuple[Optional[float], Optional[float]]]:
    if min_v is None and max_v is None:
        return None
    if (min_v is not None) and (max_v is not None) and min_v > max_v:
        min_v, max_v = max_v, min_v
    return (min_v, max_v)


def clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))


def pretty_pln(x: Any) -> str:
    try:
        return f"{int(float(x)):,} zł".replace(",", " ")
    except Exception:
        return str(x)


def pretty_m2(x: Any) -> str:
    try:
        return f"{float(x):.0f} m²"
    except Exception:
        return str(x)


