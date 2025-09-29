import streamlit as st
import pandas as pd
from typing import Dict, Any, Optional
from .nl import why_match
from .utils import pretty_pln, pretty_m2


def render_offer_card(
    row: pd.Series | Dict[str, Any],
    filters: Optional[Dict[str, Any]] = None,
    show_why: bool = False,
):
    r = row if isinstance(row, dict) else row.to_dict()
    with st.container():
        cols = st.columns([2, 1, 1, 1, 1])
        with cols[0]:
            st.markdown(
                f"**#{int(r.get('id', 0))} – {r.get('miasto','')} • {r.get('lokalizacja','')}**"
            )
        with cols[1]:
            st.metric("Cena", pretty_pln(r.get("cena")))
        with cols[2]:
            st.metric("Metraż", pretty_m2(r.get("metraz")))
        with cols[3]:
            st.metric(
                "Pokoje", int(r.get("pokoje")) if r.get("pokoje") is not None else "-"
            )
        with cols[4]:
            st.metric(
                "Piętro", int(r.get("pietro")) if r.get("pietro") is not None else "-"
            )
        st.caption(
            f"Balkon: {'tak' if r.get('balkon') else 'nie'} • Winda: {'tak' if r.get('winda') else 'nie'} • Cena/m²: {pretty_pln(r.get('cena_m2')) if r.get('cena_m2') is not None else '-'}"
        )
        if "score" in r:
            st.progress(
                min(max(float(r["score"]) / 5.0, 0.0), 1.0),
                text=f"Dopasowanie: {r['score']:.2f}/5",
            )
        if show_why and filters is not None:
            reasons = why_match(r, filters)
            if reasons:
                with st.expander("Dlaczego to pasuje?"):
                    for reason in reasons:
                        st.write("• " + reason)


def render_results(df: pd.DataFrame, f: Dict[str, Any], show_why: bool = False):
    count = len(df)
    if count == 0:
        st.info(
            "❌ Brak wyników dla podanych kryteriów. Zmień zapytanie i spróbuj ponownie."
        )
        return
    st.success(f"✅ Znalazłem {count} ofert.")
    for _, row in df.iterrows():
        render_offer_card(row, filters=f, show_why=show_why)


def render_debug(filters: Dict[str, Any]):
    with st.expander("🔧 Debug – wyłuskanie kryteriów", expanded=False):
        st.json({k: v for k, v in filters.items() if v is not None})


def render_primary_offer(
    row: pd.Series | Dict[str, Any],
    context: Optional[Dict[str, Any]],
    filters: Dict[str, Any],
    show_why: bool = True,
):
    """Karta główna (1 oferta) + kontekst cenowy rynku."""
    render_offer_card(row, filters=filters, show_why=show_why)
    # Pasek porównania do rynku
    if context:
        city = context.get("city")
        loc = context.get("lok")
        p_m2 = context.get("cena_m2")
        avg_city = context.get("avg_city")
        avg_loc = context.get("avg_loc")
        delta_city = context.get("delta_city_pct")
        delta_loc = context.get("delta_loc_pct")

        with st.container():
            st.caption("📊 Kontekst cenowy:")
            cols = st.columns(3)
            with cols[0]:
                st.metric(
                    "Cena/m² oferty",
                    pretty_pln(p_m2) + "/m²" if p_m2 is not None else "-",
                )
            with cols[1]:
                st.metric(
                    f"Śr. m² • {city or '-'}",
                    (pretty_pln(avg_city) + "/m²") if avg_city is not None else "-",
                    f"{delta_city:+.0f}%" if delta_city is not None else None,
                )
            with cols[2]:
                st.metric(
                    f"Śr. m² • {loc or 'lokalizacja'}",
                    (pretty_pln(avg_loc) + "/m²") if avg_loc is not None else "-",
                    f"{delta_loc:+.0f}%" if delta_loc is not None else None,
                )
            if delta_loc is not None:
                note = "powyżej" if delta_loc > 0 else "poniżej"
                st.info(
                    f"Ta oferta jest ~{abs(int(delta_loc))}% {note} średniej dla {loc or 'tej lokalizacji'}."
                )


def render_alternatives(
    df: pd.DataFrame,
    filters: Dict[str, Any],
    show_why: bool = False,
):
    """Lista krótkich kart alternatyw (max 5 przekazujemy z app.py)."""
    for _, row in df.iterrows():
        render_offer_card(row, filters=filters, show_why=show_why)


def render_roommate_alternatives(df: pd.DataFrame, filters: Dict[str, Any]):
    """Krótka lista propozycji do współdzielenia (pokazujemy cenę i metraż per osoba)."""
    if df.empty:
        return
    st.subheader("👥 Propozycje do współdzielenia (roommate matching)")
    for _, row in df.iterrows():
        r = row.to_dict()
        with st.container():
            cols = st.columns([2, 1, 1, 1, 1])
            with cols[0]:
                st.markdown(
                    f"**#{int(r.get('id', 0))} – {r.get('miasto','')} • {r.get('lokalizacja','')}**"
                )
                st.caption("Kandydat do współdzielenia (≥2 pokoje)")
            with cols[1]:
                st.metric("Cena całość", pretty_pln(r.get("cena")))
            with cols[2]:
                st.metric(
                    "Pokoje", int(r.get("pokoje")) if r.get("pokoje") is not None else "-"
                )
            with cols[3]:
                st.metric(
                    "Cena / pokój",
                    pretty_pln(r.get("per_room_price"))
                    if r.get("per_room_price") is not None
                    else "-",
                )
            with cols[4]:
                v = r.get("per_room_area")
                st.metric("m² / pokój", f"{float(v):.0f} m²" if v is not None else "-")


