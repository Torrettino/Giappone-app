import streamlit as st
import pandas as pd
from datetime import datetime, date
import requests
import uuid

# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Travel Budget Tracker",
    page_icon="🇯🇵",
    layout="centered",   # meglio per mobile
    initial_sidebar_state="collapsed"  # sidebar chiusa di default su mobile
)

st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background:#1e1e2e;
        border-radius:10px;
        padding:12px;
    }
    .stProgress > div > div { border-radius:10px; }
    .block-container { padding-top: 1.5rem; }
    .stButton button { height: 3.2em; }
</style>
""", unsafe_allow_html=True)

st.title("🇯🇵 Gestione Spese Tokyo")

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
if "operazioni" not in st.session_state:
    st.session_state["operazioni"] = []
if "tasso_cambio" not in st.session_state:
    st.session_state["tasso_cambio"] = 165.0

# ══════════════════════════════════════════════════════════════════════════════
# COSTANTI
# ══════════════════════════════════════════════════════════════════════════════
CATEGORIE = [
    "Trasporti", "Metro/Suica", "Shinkansen", "Taxi", 
    "Alloggi", "Cibo", "Ramen", "Sushi", "Konbini", 
    "Shopping", "Duty Free", "Attrazioni", "Onsen", 
    "Altro", "Prelievo ATM"
]

SORGENTI = [
    "Carta Credito JPY", "Carta Credito EUR", 
    "Carta Debito EUR", "Wallet Contanti"
]

PERSONE = ["Famiglia", "Francesco", "Guia", "Matilde"]

# ══════════════════════════════════════════════════════════════════════════════
# FUNZIONI
# ══════════════════════════════════════════════════════════════════════════════
def get_live_rate() -> tuple[float, bool]:
    try:
        r = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=5)
        r.raise_for_status()
        return float(r.json()["rates"]["JPY"]), True
    except Exception:
        return st.session_state["tasso_cambio"], False

def converti(importo: float, valuta: str, tasso: float):
    if valuta == "EUR":
        return importo, round(importo * tasso, 0)
    return round(importo / tasso, 4), importo

def elimina_per_id(ids):
    st.session_state["operazioni"] = [
        op for op in st.session_state["operazioni"] 
        if op.get("_id") not in ids
    ]

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("⚙️ Configurazione")
    
    st.subheader("💱 Tasso EUR→JPY")
    tasso_cambio = st.number_input(
        "1 EUR = X JPY", 
        min_value=1.0, 
        value=float(st.session_state["tasso_cambio"]), 
        step=0.5
    )
    st.session_state["tasso_cambio"] = tasso_cambio
    
    if st.button("🔄 Aggiorna tasso live", use_container_width=True):
        rate, ok = get_live_rate()
        if ok:
            st.session_state["tasso_cambio"] = rate
            st.success(f"Tasso aggiornato: ¥ {rate:.2f}")
            st.rerun()
        else:
            st.error("Impossibile raggiungere l'API.")

    st.divider()
    st.subheader("📅 Date Viaggio")
    data_inizio = st.date_input("Inizio", value=date(2026, 6, 13))
    data_fine = st.date_input("Fine", value=date(2026, 6, 26))

    st.divider()
    st.subheader("🎯 Budget")
    budget_totale = st.number_input("Budget massimo viaggio (€)", min_value=0.0, value=10000.0, step=100.0)
    fondo_revolut = st.number_input("Fondo Revolut (¥)", min_value=0.0, value=250000.0, step=10000.0)
    plafond_cc = st.number_input("Plafond Mensile CC EUR (€)", min_value=0.0, value=3000.0, step=500.0)

    st.divider()
    st.subheader("📂 Backup")
    file_up = st.file_uploader("Ripristina da CSV", type="csv")
    if file_up:
        try:
            df_imp = pd.read_csv(file_up)
            if "_id" not in df_imp.columns:
                df_imp["_id"] = [str(uuid.uuid4()) for _ in range(len(df_imp))]
            existing = {op["_id"] for op in st.session_state["operazioni"]}
            nuovi = [r for r in df_imp.to_dict("records") if r["_id"] not in existing]
            st.session_state["operazioni"].extend(nuovi)
            st.success(f"Importati {len(nuovi)} record")
            st.rerun()
        except Exception as e:
            st.error(f"Errore: {e}")

    if st.session_state["operazioni"]:
        df_exp = pd.DataFrame(st.session_state["operazioni"])
        st.download_button(
            "⬇️ Scarica Backup CSV",
            data=df_exp.to_csv(index=False).encode("utf-8"),
            file_name="spese_tokyo.csv",
            mime="text/csv",
            use_container_width=True
        )

# ══════════════════════════════════════════════════════════════════════════════
# QUICK EXPENSE
# ══════════════════════════════════════════════════════════════════════════════
st.header("➕ Inserimento Rapido")

QUICK_TAGS = {
    "🚇 Metro": ("Metro/Suica", "Wallet Contanti", "JPY", 230),
    "🍜 Ramen": ("Ramen", "Wallet Contanti", "JPY", 1200),
    "🏪 Konbini": ("Konbini", "Wallet Contanti", "JPY", 600),
    "🍣 Sushi": ("Sushi", "Carta Credito JPY", "JPY", 3500),
    "🛍️ Shopping": ("Shopping", "Carta Credito JPY", "JPY", 0),
    "💴 Prelievo": ("Prelievo ATM", "Wallet Contanti", "JPY", 0),
}

cols = st.columns(3)
for i, (label, vals) in enumerate(QUICK_TAGS.items()):
    with cols[i % 3]:
        if st.button(label, use_container_width=True, key=f"qt_{i}"):
            st.session_state["quick"] = vals
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# FORM COMPLETO
# ══════════════════════════════════════════════════════════════════════════════
with st.form("form_ins", clear_on_submit=True):
    st.subheader("Nuova Operazione")
    
    c1, c2 = st.columns(2)
    with c1:
        data_op = st.date_input("Data", date.today())
        stato = st.selectbox("Stato", ["Spesa Effettiva", "Prenotazione"])
        categoria = st.selectbox("Categoria", CATEGORIE)
        persona = st.selectbox("Persona / Gruppo", PERSONE)
    
    with c2:
        sorgente = st.selectbox("Metodo di pagamento", SORGENTI)
        valuta = st.selectbox("Valuta", ["JPY", "EUR"])
        importo = st.number_input("Importo", min_value=0.0, value=0.0, step=100.0, format="%.2f")
        note = st.text_area("Note / Descrizione", placeholder="Es: Cena a Shibuya con vista...", height=100)

    submitted = st.form_submit_button("🚀 Registra Operazione", use_container_width=True)

    if submitted and importo > 0:
        imp_eur, imp_jpy = converti(importo, valuta, st.session_state["tasso_cambio"])
        
        st.session_state["operazioni"].append({
            "_id": str(uuid.uuid4()),
            "Persona": persona,
            "Data": data_op.strftime("%Y-%m-%d"),
            "Data Pagamento": data_op.strftime("%Y-%m-%d") if stato == "Spesa Effettiva" else None,
            "Stato": stato,
            "Categoria": categoria,
            "Sorgente": sorgente,
            "Valuta Originale": valuta,
            "Importo Originale": round(importo, 2),
            "Importo EUR": round(imp_eur, 4),
            "Importo JPY": round(imp_jpy, 0),
            "Note": note
        })
        st.success(f"Registrata spesa di ¥{imp_jpy:,.0f} per {persona}")
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.header("📊 Cruscotto")

if not st.session_state["operazioni"]:
    st.info("Nessuna operazione registrata. Inizia inserendo una spesa.")
    st.stop()

df = pd.DataFrame(st.session_state["operazioni"])
df["Data"] = pd.to_datetime(df["Data"])
df["Data Pagamento"] = pd.to_datetime(df["Data Pagamento"], errors='coerce')

spese = df[df["Stato"] == "Spesa Effettiva"]
spese_reali = spese[spese["Categoria"] != "Prelievo ATM"]

tot_spesa_eur = spese_reali["Importo EUR"].sum()
tot_pren_eur = df[df["Stato"] == "Prenotazione"]["Importo EUR"].sum()
budget_residuo = budget_totale - tot_spesa_eur - tot_pren_eur

k1, k2, k3, k4 = st.columns(4)
k1.metric("Budget Totale", f"€ {budget_totale:,.0f}")
k2.metric("Speso", f"€ {tot_spesa_eur:,.0f}")
k3.metric("Prenotazioni", f"€ {tot_pren_eur:,.0f}")
k4.metric("Residuo", f"€ {budget_residuo:,.0f}", 
          delta="OK" if budget_residuo >= 0 else "Sforato",
          delta_color="normal" if budget_residuo >= 0 else "inverse")

if budget_totale > 0:
    perc = min((tot_spesa_eur + tot_pren_eur) / budget_totale, 1.0)
    st.progress(perc)
    st.caption(f"Utilizzo budget: {perc*100:.1f}%")

# Grafici
col1, col2 = st.columns(2)
with col1:
    st.subheader("Ripartizione per Categoria")
    if not spese_reali.empty:
        cat = spese_reali.groupby("Categoria")["Importo EUR"].sum().sort_values(ascending=False)
        st.bar_chart(cat)

with col2:
    st.subheader("Andamento Giornaliero")
    if not spese_reali.empty:
        daily = spese_reali.groupby("Data")["Importo EUR"].sum()
        st.line_chart(daily)

# Registro
st.divider()
st.subheader("📋 Registro Operazioni")

df_vis = df.copy()
df_vis["Data"] = df_vis["Data"].dt.strftime("%Y-%m-%d")
df_vis.insert(0, "🗑️", False)

edited = st.data_editor(
    df_vis[["🗑️", "Persona", "Data", "Categoria", "Sorgente", "Importo Originale", 
            "Valuta Originale", "Importo EUR", "Note"]],
    use_container_width=True,
    hide_index=True
)

da_eliminare = edited[edited["🗑️"] == True].index.tolist()
if da_eliminare and st.button("🗑️ Elimina selezionate", type="primary"):
    ids_to_delete = df_vis.iloc[da_eliminare]["_id"].tolist()
    elimina_per_id(ids_to_delete)
    st.success("Operazioni eliminate")
    st.rerun()
