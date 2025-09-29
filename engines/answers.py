from __future__ import annotations

import os
from typing import Dict, Any, Optional, Tuple
import pandas as pd

from .utils import pretty_pln, pretty_m2

# -----------------------------
# Opcjonalny backend LLM
# -----------------------------
def _try_llm(prompt: str, temperature: float = 0.3) -> Optional[str]:
    """
    Próbujemy użyć modelu językowego *jeśli* użytkownik skonfigurował środowisko.
    Obsługiwani providerzy: openai, ollama.
    """
    provider = os.getenv("LLM_PROVIDER", "").lower()
    api_key = os.getenv("LLM_API_KEY", "")
    try:
        if provider == "openai":
            from openai import OpenAI
            if not api_key:
                return None
            client = OpenAI(api_key=api_key)
            model = os.getenv("LLM_MODEL", "gpt-4o-mini")
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Jesteś asystentem nieruchomości. Odpowiadasz krótko, konkretnie, po polsku."},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
            )
            return completion.choices[0].message.content.strip()
        elif provider == "ollama":
            import ollama
            model = os.getenv("LLM_MODEL", "llama3")
            r = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": "Jesteś asystentem nieruchomości. Odpowiadasz krótko, konkretnie, po polsku."},
                    {"role": "user", "content": prompt},
                ],
                # jeśli Twoja wersja klienta wspiera temperature:
                # options={"temperature": temperature}
            )
            return (r.get("message", {}) or {}).get("content", "").strip() or None
    except Exception:
        return None
    return None

# -----------------------------
# Fallbackowy summarizer (bez LLM)
# -----------------------------
def _fmt_row_short(r: pd.Series | Dict[str, Any]) -> str:
    d = r if isinstance(r, dict) else r.to_dict()
    parts = []
    if d.get("miasto"):
        parts.append(str(d["miasto"]))
    if d.get("lokalizacja"):
        parts.append(str(d["lokalizacja"]))
    head = " • ".join(parts) if parts else f"ID {d.get('id','-')}"
    cena = pretty_pln(d.get("cena"))
    metraz = pretty_pln(d.get("metraz")).replace(" zł", " m²") if d.get("metraz") is not None else "-"
    pokoje = f"{int(d['pokoje'])} pokoje" if d.get("pokoje") is not None else ""
    pietro = f"piętro {int(d['pietro'])}" if d.get("pietro") is not None else ""
    extras_core = ", ".join([p for p in [pokoje, pietro] if p])
    bools = []
    if d.get("balkon") is not None:
        bools.append("balkon" if d["balkon"] else "bez balkonu")
    if d.get("winda") is not None:
        bools.append("winda" if d["winda"] else "bez windy")
    extras = (extras_core + (", " if extras_core and bools else "") + ", ".join(bools)).strip(", ").strip()
    cm2 = f" • {pretty_pln(d.get('cena_m2'))}/m²" if d.get("cena_m2") is not None else ""
    return f"- **{head}** — {metraz}, {cena}{cm2}" + (f" ({extras})" if extras else "")

def _human_range(rng, unit: str) -> str:
    if not rng: return ""
    lo, hi = rng
    if lo and hi and lo == hi: return f"{lo} {unit}"
    if lo and hi: return f"{lo}–{hi} {unit}"
    if lo and not hi: return f"od {lo} {unit}"
    if not lo and hi: return f"do {hi} {unit}"
    return ""

def _suggest_refinements(filters: Dict[str, Any], df: pd.DataFrame) -> str:
    tips = []
    if not df.empty and len(df) > 5 and filters.get("sort") != "cena_asc":
        tips.append("możesz posortować po cenie (najtańsze) – wpisz *najtańsze*")
    if filters.get("cena_range") and "cena" in df.columns and df["cena"].notna().any():
        lo = filters["cena_range"][0] or 0
        if df["cena"].min() > lo:
            tips.append("podnieś górny limit ceny albo usuń filtr ceny")
    if filters.get("metraz_range") and "metraz" in df.columns and df["metraz"].notna().any():
        lo = filters["metraz_range"][0] or 0
        if df["metraz"].max() < lo:
            tips.append("zmniejsz dolny limit metrażu")
    if filters.get("balkon") is True and "balkon" in df.columns and (~df["balkon"]).sum() > 0:
        tips.append("jeśli balkon nie jest konieczny, usuń ten filtr — zwiększy to liczbę wyników")
    if not tips:
        tips.append("doprecyzuj: *pokoje 2-3*, *piętro do 3*, *Jeżyce* itp.")
    return "💡 Wskazówka: " + " • ".join(tips)

def summarize_results(filters: Dict[str, Any], df: pd.DataFrame, top_k: int = 3) -> str:
    if df.empty:
        return "Nie znalazłem ofert spełniających te kryteria. Spróbuj poluzować budżet lub zakres metrażu, albo usuń jeden z filtrów (np. balkon/winda)."
    hdr = []
    if filters.get("miasto"): hdr.append(filters["miasto"])
    if filters.get("lokalizacja"): hdr.append(filters["lokalizacja"])
    if filters.get("metraz_range"): hdr.append(_human_range(filters["metraz_range"], "m²"))
    if filters.get("pokoje_range"): hdr.append(_human_range(filters["pokoje_range"], "pokoje"))
    if filters.get("cena_range"): hdr.append(_human_range(filters["cena_range"], "zł"))
    if filters.get("pietro_range"): hdr.append(_human_range(filters["pietro_range"], "piętro"))
    if filters.get("balkon") is True: hdr.append("z balkonem")
    if filters.get("balkon") is False: hdr.append("bez balkonu")
    if filters.get("winda") is True: hdr.append("z windą")
    if filters.get("winda") is False: hdr.append("bez windy")

    header = " | ".join(hdr) if hdr else "Dopasowane oferty"
    lines = [f"**{header}**"]
    rows = df.head(top_k).to_dict(orient="records")
    for r in rows:
        lines.append(_fmt_row_short(r))

    try:
        stats = []
        if "cena" in df.columns and df["cena"].notna().any():
            stats.append(f"cena: {pretty_pln(int(df['cena'].min()))} – {pretty_pln(int(df['cena'].max()))}")
        if "metraz" in df.columns and df["metraz"].notna().any():
            stats.append(f"metraż: {int(df['metraz'].min())}-{int(df['metraz'].max())} m²")
        if stats:
            lines.append("Zakres w wynikach: " + " • ".join(stats))
    except Exception:
        pass

    lines.append(_suggest_refinements(filters, df))
    return "\n".join(lines)

# -----------------------------
# Public API
# -----------------------------
def _build_prompt(filters: Dict[str, Any], df: pd.DataFrame, top_k: int, style: str, length: str) -> str:
    tone = {
        "zwięzły": "krótko, konkretnie, zero marketingu",
        "konsultant": "empatycznie i klarownie, ale rzeczowo",
        "handlowy": "zachęcająco, ale bez przesady; nadal rzeczowo",
        "techniczny": "suche fakty i liczby, jak raport",
    }.get(style, "krótko i konkretnie")
    max_words = {"krótka": 80, "średnia": 140, "dłuższa": 220}.get(length, 120)
    parts = [f"Odpowiedz po polsku (maks ~{max_words} słów), styl: {tone}."]
    parts.append("Kryteria: " + str({k: v for k, v in filters.items() if v is not None}))
    rows = df.head(top_k).to_dict(orient="records")
    lines = [_fmt_row_short(r) for r in rows]
    parts.append("Kandydaci:\n" + "\n".join(lines))
    parts.append("W treści zawrzyj: 1) jednozdaniowy nagłówek dopasowany do kryteriów; 2) listę 2–3 najlepszych; 3) 1 wskazówkę co doprecyzować.")
    return "\n".join(parts)

def generate_answer(
    filters: Dict[str, Any],
    df: pd.DataFrame,
    top_k: int = 3,
    style: str = "zwięzły",
    allow_llm: bool = True,
    length: str = "krótka",
    temperature: float = 0.3,
) -> Tuple[str, str]:
    """
    Zwraca (tekst_odpowiedzi, źródło): źródło to 'llm' lub 'fallback'.
    """
    prompt = _build_prompt(filters, df, top_k, style, length)
    llm_out = _try_llm(prompt, temperature=temperature) if allow_llm else None
    if llm_out:
        return llm_out, "llm"
    return summarize_results(filters, df, top_k=top_k), "fallback"

