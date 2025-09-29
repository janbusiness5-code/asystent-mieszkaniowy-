import pandas as pd
from typing import Optional, Dict, Any
from .utils import norm_bool

# Mapowanie kolumn CSV → wewnętrzne klucze
COLUMN_MAP = {
    "ID": "id",
    "Miasto": "miasto",
    "Lokalizacja": "lokalizacja",
    "Metraż": "metraz",
    "Metraz": "metraz",
    "Pokoje": "pokoje",
    "Balkon": "balkon",
    "Cena": "cena",
    "Piętro": "pietro",
    "Pietro": "pietro",
    "Winda": "winda",
    # (opcjonalnie) "Garaż": "garaz", "Garaz": "garaz",
}


def _read_csv_robust(path: str) -> pd.DataFrame:
    """
    Odporny loader CSV: wykrywa separator, BOM/UTF-8, CP1250, pomija uszkodzone wiersze.
    """
    attempts = [
        dict(sep=None, engine="python", encoding="utf-8-sig", on_bad_lines="skip"),
        dict(sep=";", engine="python", encoding="utf-8-sig", on_bad_lines="skip"),
        dict(sep=",", engine="python", encoding="utf-8-sig", on_bad_lines="skip"),
        dict(sep=";", engine="python", encoding="cp1250", on_bad_lines="skip"),
        dict(sep=",", engine="python", encoding="cp1250", on_bad_lines="skip"),
        dict(sep=r"[;,]", engine="python", encoding="utf-8-sig", on_bad_lines="skip"),
    ]
    last_err = None
    for kw in attempts:
        try:
            return pd.read_csv(path, **kw)
        except Exception as e:
            last_err = e
    if path.lower().endswith((".xls", ".xlsx")):
        return pd.read_excel(path)
    raise last_err or RuntimeError("Nie udało się wczytać CSV")


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={col: COLUMN_MAP.get(col, col) for col in df.columns}).copy()

    # Booleany
    if "balkon" in df.columns:
        df["balkon"] = df["balkon"].map(lambda v: norm_bool(v) if pd.notna(v) else None)
    if "winda" in df.columns:
        df["winda"] = df["winda"].map(lambda v: norm_bool(v) if pd.notna(v) else None)
    # if "garaz" in df.columns:
    #     df["garaz"] = df["garaz"].map(lambda v: norm_bool(v) if pd.notna(v) else None)

    # Liczbowe
    for col in ["metraz", "pokoje", "cena", "pietro"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Pochodne
    if "cena" in df.columns and "metraz" in df.columns:
        df["cena_m2"] = (df["cena"] / df["metraz"]).round(0)

    # Teksty
    for col in ["miasto", "lokalizacja"]:
        if col in df.columns:
            df[col] = df[col].astype(str)

    return df


def load_csv(path: str = "mieszkania.csv") -> pd.DataFrame:
    return normalize_df(_read_csv_robust(path))


def locations(df: pd.DataFrame):
    return (
        sorted(df["lokalizacja"].dropna().astype(str).unique().tolist())
        if "lokalizacja" in df.columns
        else []
    )


def cities(df: pd.DataFrame):
    return (
        sorted(df["miasto"].dropna().astype(str).unique().tolist())
        if "miasto" in df.columns
        else []
    )


def price_context(row: pd.Series, full_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Kontekst cenowy dla oferty:
    - cena_m2 oferty,
    - średnia m² w mieście i (jeśli możliwe) w lokalizacji,
    - różnice procentowe.
    """
    try:
        r = row.to_dict() if hasattr(row, "to_dict") else dict(row)
        miasto = r.get("miasto")
        lok = r.get("lokalizacja")
        cena_m2 = r.get("cena_m2")

        def _avg(series):
            s = series.dropna()
            return float(s.mean()) if len(s) else None

        avg_city = None
        avg_loc = None
        if "cena_m2" in full_df.columns:
            if miasto:
                avg_city = _avg(full_df.loc[full_df["miasto"] == miasto, "cena_m2"])
            if miasto and lok:
                avg_loc = _avg(
                    full_df.loc[
                        (full_df["miasto"] == miasto)
                        & (full_df["lokalizacja"] == lok),
                        "cena_m2",
                    ]
                )

        def _delta(a, b):
            if a is None or b is None or b == 0:
                return None
            return (a - b) / b * 100.0

        return {
            "city": miasto,
            "lok": lok,
            "cena_m2": cena_m2,
            "avg_city": avg_city,
            "avg_loc": avg_loc,
            "delta_city_pct": _delta(cena_m2, avg_city),
            "delta_loc_pct": _delta(cena_m2, avg_loc),
        }
    except Exception:
        return {
            "city": row.get("miasto") if isinstance(row, dict) else None,
            "lok": row.get("lokalizacja") if isinstance(row, dict) else None,
            "cena_m2": row.get("cena_m2") if isinstance(row, dict) else None,
            "avg_city": None,
            "avg_loc": None,
            "delta_city_pct": None,
            "delta_loc_pct": None,
        }

