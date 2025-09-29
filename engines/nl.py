import re
from typing import Dict, Any, Optional, Tuple, List
from .utils import norm_text, to_int_safe, safe_range


def _parse_range_generic(text: str) -> Tuple[Optional[int], Optional[int]]:
    t = norm_text(text)
    m = re.search(r"(\d[\d\s\.,]*)\s*[-–—]\s*(\d[\d\s\.,]*)", t)
    if m:
        return safe_range(to_int_safe(m.group(1)), to_int_safe(m.group(2)))
    m = re.search(r"od\s*([0-9][\d\s\.,]*)\s*do\s*([0-9][\d\s\.,]*)", t)
    if m:
        return safe_range(to_int_safe(m.group(1)), to_int_safe(m.group(2)))
    m = re.search(r"od\s*([0-9][\d\s\.,]*)", t)
    if m:
        return (to_int_safe(m.group(1)), None)
    m = re.search(r"do\s*([0-9][\d\s\.,]*)", t)
    if m:
        return (None, to_int_safe(m.group(1)))
    m = re.search(r"([0-9][\d\s\.,]*)", t)
    if m:
        x = to_int_safe(m.group(1))
        return (x, x)
    return (None, None)


def parse_price_range(t: str):
    txt = norm_text(t)
    # „do 900k / do 900 tys / do 900000 zł”
    m = re.search(r"do\s*([0-9][\d\s\.,]*)(?:\s*(mln|mili|tys|k|zł|pln))?", txt)
    if m:
        num = (m.group(1) or "") + (m.group(2) or "")
        return (None, to_int_safe(num))
    # Pojedyncza liczba z jednostką → traktujemy jako max
    m = re.search(r"([0-9][\d\s\.,]*)(?:\s*(mln|mili|tys|k|zł|pln))", txt)
    if m:
        num = (m.group(1) or "") + (m.group(2) or "")
        return (None, to_int_safe(num))
    return (None, None)


def parse_area_range(t: str):
    m = re.search(r"(?:m2|m\u00b2|metraz|metraż|metr).*", norm_text(t))
    return _parse_range_generic(m.group(0) if m else t)


def parse_rooms_range(t: str):
    m = re.search(r"(poko(?:j|je|i).*)", norm_text(t))
    return _parse_range_generic(m.group(1) if m else t)


def parse_floor_range(t: str):
    txt = norm_text(t)
    if "parter" in txt:
        return (0, 0)
    m = re.search(r"(pi[eę]tro.*)", txt)
    return _parse_range_generic(m.group(1) if m else t)


def parse_query(
    q: str, locations: Optional[List[str]] = None, cities: Optional[List[str]] = None
) -> Dict[str, Any]:
    t = norm_text(q)
    res: Dict[str, Any] = {
        "miasto": None,
        "lokalizacja": None,
        "cena_range": None,
        "metraz_range": None,
        "pokoje_range": None,
        "pietro_range": None,
        "balkon": None,
        "winda": None,
        "sort": "score",
        "limit": 50,
        # nowe sygnały:
        "persona": None,
        "roommate_intent": False,
    }

    # Miasto / lokalizacja (słownikami)
    if cities:
        for c in cities:
            if norm_text(c) in t:
                res["miasto"] = c
                break
    if locations:
        for loc in locations:
            ln = norm_text(loc)
            if ln and (
                ln in t
                or re.search(rf"\bna\s+{ln}\b", t)
                or re.search(rf"\bw\s+{ln}\b", t)
            ):
                res["lokalizacja"] = loc
                break

    # Zakresy
    cr = parse_price_range(t)
    res["cena_range"] = None if cr == (None, None) else cr

    ar = parse_area_range(t)
    res["metraz_range"] = None if ar == (None, None) else ar

    if "poko" in t:
        pr = parse_rooms_range(t)
        res["pokoje_range"] = None if pr == (None, None) else pr

    if "piętro" in t or "pietro" in t or "parter" in t:
        fr = parse_floor_range(t)
        res["pietro_range"] = None if fr == (None, None) else fr

    # Booleany
    if "balkon" in t:
        res["balkon"] = False if "bez" in t else True
    if "winda" in t or "windą" in t:
        res["winda"] = False if "bez" in t else True

    # =========================
    # Persony / kategorie użytkownika + roommate intent
    # =========================
    is_single = any(w in t for w in ["singiel", "singla", "singlowe", "singlem", "solo", "dla singla", "dla singli"])
    is_couple = any(w in t for w in ["para", "pary", "dla pary", "we dwoje", "dla dwojga", "małżeństwo", "malzenstwo"])
    is_students = any(w in t for w in ["student", "studenci", "dla studenta", "dla studentów", "dla studentow", "stud"])
    is_family = any(w in t for w in ["rodzina", "rodzinne", "dla rodziny", "dzieci", "2+1", "2+2", "3+1"])

    roommate_words = ["współlokator", "wspollokator", "roommate", "co-living", "coliving", "pokój", "pokoj", "pokojowe", "na pokój"]
    res["roommate_intent"] = any(w in t for w in roommate_words)

    if is_family:
        res["persona"] = "family"
        if res.get("pokoje_range") is None:
            res["pokoje_range"] = (3, 5)
        if res.get("metraz_range") is None:
            res["metraz_range"] = (60, 120)
    elif is_students:
        res["persona"] = "students"
        if res.get("pokoje_range") is None:
            res["pokoje_range"] = (1, 4)
        if res.get("metraz_range") is None:
            res["metraz_range"] = (15, 50)  # wg Twojej wytycznej
    elif is_couple:
        res["persona"] = "couple"
        if res.get("pokoje_range") is None:
            res["pokoje_range"] = (2, 2)
        if res.get("metraz_range") is None:
            res["metraz_range"] = (40, 60)
    elif is_single:
        res["persona"] = "single"
        if res.get("pokoje_range") is None:
            res["pokoje_range"] = (1, 2)
        if res.get("metraz_range") is None:
            res["metraz_range"] = (25, 45)

    # Sort (intencje)
    if "najtańsz" in t or "cena rosn" in t or "po cenie" in t:
        res["sort"] = "cena_asc"
    elif "najdroż" in t or "cena malej" in t:
        res["sort"] = "cena_desc"
    elif "największ" in t or "metraż malej" in t:
        res["sort"] = "metraz_desc"
    elif "najmniejsz" in t or "metraż rosn" in t:
        res["sort"] = "metraz_asc"

    return res


def compute_score(row, f: Dict[str, Any]) -> float:
    # Prostota i stabilność; w razie potrzeby doważymy pod persony na Twoje zlecenie
    score = 0.0
    if f.get("balkon") is not None:
        score += 2.0 if row.get("balkon") == f["balkon"] else 0.0
    if f.get("winda") is not None:
        score += 2.0 if row.get("winda") == f["winda"] else 0.0
    if f.get("miasto") and norm_text(row.get("miasto", "")) == norm_text(f["miasto"]):
        score += 1.5
    if f.get("lokalizacja") and norm_text(row.get("lokalizacja", "")) == norm_text(
        f["lokalizacja"]
    ):
        score += 2.0

    def rs(val, rng, scale=1.0):
        if val is None or rng is None:
            return 0.0
        lo, hi = rng
        if lo is not None and val < lo:
            return max(0.0, 1 - (lo - val) / max(lo, 1)) * scale * 0.5
        if hi is not None and val > hi:
            return max(0.0, 1 - (val - hi) / max(hi, 1)) * scale * 0.5
        return 1.0 * scale

    score += rs(row.get("cena"), f.get("cena_range"), 2.0)
    score += rs(row.get("metraz"), f.get("metraz_range"), 1.5)
    score += rs(row.get("pokoje"), f.get("pokoje_range"), 1.2)
    score += rs(row.get("pietro"), f.get("pietro_range"), 0.8)
    return float(round(score, 4))


def why_match(row, f: Dict[str, Any]) -> List[str]:
    reasons = []
    if f.get("miasto") and row.get("miasto"):
        reasons.append(f"Miasto: {row.get('miasto')}")
    if f.get("lokalizacja") and row.get("lokalizacja"):
        reasons.append(f"Lokalizacja: {row.get('lokalizacja')}")

    def add(name, val, rng, unit=""):
        if rng is None or val is None:
            return
        lo, hi = rng
        if (lo is None or val >= lo) and (hi is None or val <= hi):
            reasons.append(f"{name}: {val}{unit} w zakresie")
        else:
            reasons.append(f"{name}: {val}{unit} blisko zakresu")

    add("Cena", row.get("cena"), f.get("cena_range"), " zł")
    add("Metraż", row.get("metraz"), f.get("metraz_range"), " m²")
    add("Pokoje", row.get("pokoje"), f.get("pokoje_range"))
    add("Piętro", row.get("pietro"), f.get("pietro_range"))
    if f.get("balkon") is not None:
        reasons.append("Balkon: tak" if row.get("balkon") else "Balkon: nie")
    if f.get("winda") is not None:
        reasons.append("Winda: tak" if row.get("winda") else "Winda: nie")
    # persona i roommate tylko jako meta (nie wpływa na pojedynczą kartę w tekście powodów)
    return reasons


