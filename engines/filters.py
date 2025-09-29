import pandas as pd
from typing import Dict, Any
from .nl import compute_score
from .utils import norm_text


def _apply_range(series: pd.Series, rng):
    if rng is None:
        return pd.Series([True] * len(series), index=series.index)
    lo, hi = rng
    m = pd.Series([True] * len(series), index=series.index)
    if lo is not None:
        m &= series >= lo
    if hi is not None:
        m &= series <= hi
    return m


def filter_df(df: pd.DataFrame, f: Dict[str, Any]) -> pd.DataFrame:
    data = df.copy()
    mask = pd.Series([True] * len(data), index=data.index)

    if f.get("miasto") and "miasto" in data.columns:
        mask &= data["miasto"].astype(str).map(norm_text) == norm_text(f["miasto"])
    if f.get("lokalizacja") and "lokalizacja" in data.columns:
        mask &= data["lokalizacja"].astype(str).map(norm_text) == norm_text(
            f["lokalizacja"]
        )

    for col, key in [
        ("cena", "cena_range"),
        ("metraz", "metraz_range"),
        ("pokoje", "pokoje_range"),
        ("pietro", "pietro_range"),
    ]:
        if col in data.columns:
            mask &= _apply_range(data[col], f.get(key))

    for col in ["balkon", "winda", "garaz"]:
        if f.get(col) is not None and col in data.columns:
            mask &= data[col] == f[col]

    return data[mask].copy()


def add_scores(df: pd.DataFrame, f: Dict[str, Any]) -> pd.DataFrame:
    scores = [compute_score(row.to_dict(), f) for _, row in df.iterrows()]
    out = df.copy()
    out["score"] = scores
    return out


def sort_results(df: pd.DataFrame, f: Dict[str, Any]) -> pd.DataFrame:
    sk = f.get("sort", "score")
    if sk == "cena_asc":
        return df.sort_values(["cena", "id"], ascending=[True, True], na_position="last")
    if sk == "cena_desc":
        return df.sort_values(
            ["cena", "id"], ascending=[False, True], na_position="last"
        )
    if sk == "metraz_asc":
        return df.sort_values(
            ["metraz", "id"], ascending=[True, True], na_position="last"
        )
    if sk == "metraz_desc":
        return df.sort_values(
            ["metraz", "id"], ascending=[False, True], na_position="last"
        )
    cols = [c for c in ["score", "cena", "id"] if c in df.columns]
    asc = [False, True, True][: len(cols)]
    return df.sort_values(cols, ascending=asc, na_position="last")


def filter_and_rank(df: pd.DataFrame, f: Dict[str, Any]) -> pd.DataFrame:
    return (
        sort_results(add_scores(filter_df(df, f), f), f)
        .head(f.get("limit", 50))
        .reset_index(drop=True)
    )


def roommate_alternatives(
    df: pd.DataFrame, f: Dict[str, Any], max_n: int = 5
) -> pd.DataFrame:
    """
    Heurystyka dla współdzielenia:
    - wybierz oferty z >=2 pokojami,
    - policz cenę i metraż per pokój (na osobę),
    - miękko trzymaj się miasta/lokalizacji jeśli zadane,
    - sortuj po najniższej cenie per pokój, potem najlepszym score i całościowej cenie.
    """
    if df.empty:
        return df

    data = df.copy()
    if "pokoje" in data.columns:
        data = data[data["pokoje"].fillna(0) >= 2]
    if data.empty:
        return data

    # Miękkie zawężenie do miasta/lokalizacji (bez braku wyników, ma być użyteczne)
    if f.get("miasto") and "miasto" in data.columns:
        data = data[data["miasto"].astype(str).str.lower() == str(f["miasto"]).lower()]
    if f.get("lokalizacja") and "lokalizacja" in data.columns:
        data = data[
            data["lokalizacja"].astype(str).str.lower()
            == str(f["lokalizacja"]).lower()
        ]

    data = data.copy()
    with pd.option_context("mode.use_inf_as_na", True):
        data["per_room_price"] = (data["cena"] / data["pokoje"]).replace(
            [float("inf")], pd.NA
        )
        data["per_room_area"] = (data["metraz"] / data["pokoje"]).replace(
            [float("inf")], pd.NA
        )

    # Sensowny zakres metrażu pokoju: ~8–20 m²/os.
    if "per_room_area" in data.columns:
        mask = data["per_room_area"].between(8, 20)
        data = data[mask.fillna(True)]

    # Score z istniejącej logiki
    try:
        scored = add_scores(data, f)
    except Exception:
        scored = data
        scored["score"] = 0.0

    sort_cols = []
    if "per_room_price" in scored.columns:
        sort_cols.append(("per_room_price", True))
    sort_cols.append(("score", False))
    if "cena" in scored.columns:
        sort_cols.append(("cena", True))

    by = [c for c, _ in sort_cols]
    asc = [a for _, a in sort_cols]
    scored = scored.sort_values(by=by, ascending=asc, na_position="last")

    return scored.head(max_n).reset_index(drop=True)


