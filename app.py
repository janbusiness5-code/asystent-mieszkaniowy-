import streamlit as st
import pandas as pd
from engines import data as data_eng
from engines import nl as nl_eng
from engines import filters as filt_eng
from engines import ui as ui_eng
from engines import answers as ans_eng

st.set_page_config(page_title="Asystent Mieszkaniowy", page_icon="🏠", layout="wide")

@st.cache_data(show_spinner=False)
def load_data_cached(path: str = "mieszkania.csv") -> pd.DataFrame:
    return data_eng.load_csv(path)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("🏠 Asystent Mieszkaniowy")
st.caption("Naturalne zapytania → dopasowane oferty mieszkań")

df = load_data_cached()

# === Sidebar: ustawienia odpowiedzi ===
with st.sidebar:
    st.markdown('### ⚙️ Ustawienia odpowiedzi')
    style = st.selectbox('Styl odpowiedzi', ['zwięzły', 'konsultant', 'handlowy', 'techniczny'], index=0)
    length = st.select_slider('Długość odpowiedzi', options=['krótka', 'średnia', 'dłuższa'], value='krótka')
    temperature = st.slider('Kreatywność (temperature)', 0.0, 1.0, 0.3, 0.1)
    show_why = st.checkbox("Pokaż 'dlaczego pasuje?'", value=True)
    allow_llm = st.checkbox('Użyj modelu językowego (jeśli dostępny)', value=True)

# === Główne pole zapytania ===
user_input = st.text_input(
    "💬 Opisz, czego szukasz (np. *\"Poznań, Jeżyce, 60–80 m², do 800k, z balkonem, do 3 piętra\"*)"
)

if user_input:
    # historia rozmowy
    st.session_state.chat_history.append(("Ty", user_input))

    # Status z krokami (jeśli dostępny), w przeciwnym razie spinner
    if hasattr(st, "status"):
        with st.status("🧠 Analizuję…", expanded=False) as status:
            status.update(label="Parsuję zapytanie")
            filters = nl_eng.parse_query(user_input, locations=data_eng.locations(df), cities=data_eng.cities(df))

            status.update(label="Filtruję i rankuję")
            results = filt_eng.filter_and_rank(df, filters)

            status.update(label="Generuję odpowiedź", state="running")
            summary, src = ans_eng.generate_answer(
                filters, results, top_k=3, style=style, allow_llm=allow_llm,
                length=length, temperature=temperature
            )
            status.update(label="Gotowe ✅", state="complete")
    else:
        with st.spinner('🧠 Analizuję kryteria i dobieram oferty...'):
            filters = nl_eng.parse_query(user_input, locations=data_eng.locations(df), cities=data_eng.cities(df))
            results = filt_eng.filter_and_rank(df, filters)
            summary, src = ans_eng.generate_answer(
                filters, results, top_k=3, style=style, allow_llm=allow_llm,
                length=length, temperature=temperature
            )

    # zapis do historii i render
    st.session_state.chat_history.append(("Bot", summary))
    st.markdown(summary)
    ui_eng.render_debug(filters)
    ui_eng.render_results(results, filters, show_why=show_why)

# === Sidebar: historia ===
with st.sidebar:
    st.markdown("### 🧠 Historia rozmowy")
    for who, msg in st.session_state.chat_history[-10:]:
        st.markdown(f"**{who}:** {msg}")
    st.caption("Źródło odpowiedzi: " + ("LLM" if 'src' in locals() and src=='llm' else "fallback"))
    st.divider()
    st.caption("Tip: *od/do, m², pokoje, piętro, balkon, winda, najtańsze/największe*")
