import streamlit as st
import uuid
import pandas as pd
import requests
import os
from datetime import datetime, date

# ═════════════════════════════════════════════════════════════════════
# 1. CONFIGURAZIONE PAGINA & STILE
# ═════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Travel Budget Tracker",
    page_icon="🇯🇵",
    layout="wide"
)

st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background:#1e1e2e;
        border-radius:10px;
        padding:12px;
    }
    .stProgress > div > div {
        border-radius:10px;
    }
    .block-container {
        padding-top: 1.5rem;
    }
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
            max-width: 100%;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.75rem;
        }
    }
</style>
""", unsafe_allow_html=True)

st.title("🇯🇵 Gestione Spese Tokyo (Locale)")

# ═════════════════════════════════════════════════════════════════════
# 2. GESTIONE FILE CSV LOCALE
# ═════════════════════════════════════════════════════════════════════
CSV_FILE = "spese_tokyo .csv"

def load_local_data():
    """Carica i dati dal file CSV locale o crea un DataFrame vuoto se non esiste"""
    if os.path.exists(CSV_FILE):
        try:
            df = pd.read_csv(CSV_FILE)
            # Forza la corretta formattazione delle date
            df["Data"] = df["Data"].astype(str)
            df["Data Pagamento"] = df["Data Pagamento"].astype(str)
            return df
        except Exception as e:
            st.error(f"Errore nel caricamento del CSV: {e}")
    
    # Se il file non esiste, crea la struttura standard
    return pd.DataFrame(columns=[
        "_id", "Destinatario", "Data", "Data Pagamento", "Stato", 
        "Categoria", "Sorgente", "Valuta Originale", "Importo Originale", 
        "Importo EUR", "Importo JPY", "Note"
    ])

def save_local_data(df):
    """Salva i dati direttamente nel file CSV locale"""
    try:
        df.to_csv(CSV_FILE, index=False)
    except Exception as e:
        st.error(f"Impossibile salvare il file CSV locale: {e}")

# Inizializzazione Session State con i dati del CSV
if "df_spese" not in st.session_state:
    st.session_state["df_spese"] = load_local_data()

if "tasso_cambio" not in st.session_state:
    st.session_state["tasso_cambio"] = 165.0

if "quick_presets" not in st.session_state:
    st.session_state["quick_presets"] = {}

if "quick_selected" not in st.session_state:
    st.session_state["quick_selected"] = None

# Costanti costanti dell'interfaccia
CATEGORIE = ["Trasporti", "Alloggi", "Cibo", "Shopping", "Altro", "Prelievo ATM", "Ricarica Revolut"]
SORGENTI = ["Carta Credito JPY", "Carta Credito EUR", "Carta Debito EUR", "Wallet Contanti"]
DESTINATARI = ["Famiglia", "Francesco", "Guia", "Matilde"]

# Automazione Scadenze Prenotazioni
df_temp = st.session_state["df_spese"]
modificato = False
for idx, row in df_temp.iterrows():
    if row["Stato"] == "Prenotazione" and pd.notna(row["Data Pagamento"]):
        try:
            if pd.to_datetime(row["Data Pagamento"]) <= pd.to_datetime(date.today()):
                df_temp.at[idx, "Stato"] = "Spesa Effettiva"
                modificato = True
        except:
            pass
if modificato:
    save_local_data(df_temp)

# ═════════════════════════════════════════════════════════════════════
# 3. UTILITIES & API CAMBIO LIVE
# ═════════════════════════════════════════════════════════════════════
def get_live_rate() -> tuple[float, bool]:
    try:
        r = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=5)
        r.raise_for_status()
        return float(r.json()["rates"]["JPY"]), True
    except:
        return st.session_state["tasso_cambio"], False

def converti(importo: float, valuta: str, tasso: float):
    if valuta == "EUR":
        return importo, importo * tasso
    return importo / tasso, importo

def calcola_saldo_revolut():
    df = st.session_state["df_spese"]
    if df.empty:
        return 0
    ricariche = df[df["Categoria"] == "Ricarica Revolut"]["Importo JPY"].sum()
    spese_rev = df[df["Sorgente"] == "Carta Credito JPY"]["Importo JPY"].sum()
    return ricariche - spese_rev

# ═════════════════════════════════════════════════════════════════════
# 4. SIDEBAR DI CONFIGURAZIONE & UTILITY
# ═════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("⚙️ Configurazione")
    st.subheader("💱 Tasso EUR→JPY")

    tasso_cambio = st.number_input(
        "1 EUR = X JPY",
        min_value=1.0,
        value=float(st.session_state["tasso_cambio"]),
        step=0.5,
        key="input_tasso"
    )
    st.session_state["tasso_cambio"] = tasso_cambio

    if st.button("🔄 Aggiorna tasso live", use_container_width=True):
        rate, ok = get_live_rate()
        if ok:
            st.session_state["tasso_cambio"] = rate
            st.success(f"Tasso aggiornato: ¥ {rate:.2f}")
            st.rerun()

    st.divider()
    tab_date, tab_budget, tab_preset, tab_export = st.tabs(["📅 Date", "💰 Budget", "⚡ Preset", "💾 Esporta"])

    with tab_date:
        st.subheader("Date Viaggio")
        data_inizio = st.date_input("Inizio", value=date(2026, 6, 13))
        data_fine = st.date_input("Fine", value=date(2026, 6, 26))

    with tab_budget:
        st.subheader("Budget e Limiti")
        budget_totale = st.number_input("Budget massimo viaggio (€)", min_value=0.0, value=10000.0, step=100.0)
        st.write("---")
        plafond_cc = st.number_input("Plafond Mensile CC EUR (€)", min_value=0.0, value=3000.0, step=500.0)

    with tab_preset:
        st.subheader("Preset Rapidi")
        nome_preset = st.text_input("Nome preset (es: Metro, Caffè)", key="p_name")
        if nome_preset:
            c1, c2, c3 = st.columns(3)
            with c1: cp_cat = st.selectbox("Cat", CATEGORIE)
            with c2: cp_sorg = st.selectbox("Sorg", SORGENTI)
            with c3: cp_val = st.selectbox("Val", ["JPY", "EUR"])
            if st.button("➕ Salva Preset", use_container_width=True):
                st.session_state["quick_presets"][nome_preset] = {"categoria": cp_cat, "sorgente": cp_sorg, "valuta": cp_val}
                st.rerun()

    with tab_export:
        st.subheader("Salvataggio Manuale")
        st.caption("Se usi l'app su cloud, scarica il CSV aggiornato prima di chiudere la sessione!")
        csv_buffer = st.session_state["df_spese"].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Scarica Backup CSV",
            data=csv_buffer,
            file_name="spese_tokyo .csv",
            mime="text/csv",
            use_container_width=True
        )

# ═════════════════════════════════════════════════════════════════════
# 5. INSERIMENTO NUOVA OPERAZIONE
# ═════════════════════════════════════════════════════════════════════
st.header("➕ Nuova Operazione")

if st.session_state["quick_presets"]:
    with st.expander("⚡ Preset Rapidi", expanded=False):
        quick_cols = st.columns(2)
        for i, (label, vals) in enumerate(st.session_state["quick_presets"].items()):
            with quick_cols[i % 2]:
                if st.button(label, use_container_width=True, key=f"qp_{i}"):
                    st.session_state["quick_selected"] = vals
                    st.rerun()

q = st.session_state["quick_selected"]

with st.form("form_ins", clear_on_submit=True):
    data_op = st.date_input("Data Inserimento", date.today())
    stato = st.selectbox("Stato", ["Spesa Effettiva", "Prenotazione"])
    data_pag = st.date_input("Data Addebito Automatico", date.today())

    cat_idx = CATEGORIE.index(q["categoria"]) if q and q.get("categoria") in CATEGORIE else 0
    categoria = st.selectbox("Categoria", CATEGORIE, index=cat_idx)

    sorg_idx = SORGENTI.index(q["sorgente"]) if q and q.get("sorgente") in SORGENTI else 0
    sorgente = st.selectbox("Sorgente", SORGENTI, index=sorg_idx)

    val_idx = ["JPY", "EUR"].index(q["valuta"]) if q and q.get("valuta") else 0
    valuta = st.selectbox("Valuta", ["JPY", "EUR"], index=val_idx)

    importo = st.number_input("Importo", min_value=0.0, value=0.0, step=1.0, format="%.2f")
    destinatario = st.selectbox("Destinatario Spesa", DESTINATARI)
    note = st.text_area("Note / Descrizione", placeholder="Inserisci dettagli...", height=80)

    submitted = st.form_submit_button("💾 Salva nel File Locale", use_container_width=True)

    if submitted and importo > 0:
        imp_eur, imp_jpy = converti(importo, valuta, tasso_cambio)
        nota_fin = f"[{destinatario}] " + (note if note else "-")
        
        # Crea la nuova riga
        nuova_spesa = pd.DataFrame([{
            "_id": str(uuid.uuid4()), "Destinatario": destinatario, "Data": str(data_op),
            "Data Pagamento": str(data_pag), "Stato": stato, "Categoria": categoria, "Sorgente": sorgente,
            "Valuta Originale": valuta, "Importo Originale": importo, "Importo EUR": round(imp_eur, 4),
            "Importo JPY": int(round(imp_jpy, 0)), "Note": nota_fin
        }])
        
        # Unisci e salva nel file CSV
        st.session_state["df_spese"] = pd.concat([nuova_spesa, st.session_state["df_spese"]], ignore_index=True)
        save_local_data(st.session_state["df_spese"])
        
        st.success("✅ Spesa registrata nel file locale!")
        st.session_state["quick_selected"] = None
        st.rerun()

# Bottone Elimina Ultima Spesa
if not st.session_state["df_spese"].empty:
    if st.button("⏪ Annulla ultima operazione inserita", use_container_width=True):
        st.session_state["df_spese"] = st.session_state["df_spese"].iloc[1:].reset_index(drop=True)
        save_local_data(st.session_state["df_spese"])
        st.success("Ultima operazione rimossa con successo!")
        st.rerun()

# ═════════════════════════════════════════════════════════════════════
# 6. SEZIONE CONTO REVOLUT
# ═════════════════════════════════════════════════════════════════════
st.divider()
st.header("🏧 Gestione Conto Revolut (¥)")
saldo_revolut = calcola_saldo_revolut()

col_saldo, col_ricarica = st.columns([2, 1])
with col_saldo:
    st.metric("Saldo Attuale Revolut", f"¥ {saldo_revolut:,.0f}")

with col_ricarica:
    if st.button("💰 Ricarica rapida 10k ¥", use_container_width=True):
        nuova_ricarica = pd.DataFrame([{
            "_id": str(uuid.uuid4()), "Destinatario": "Revolut", "Data": str(date.today()),
            "Data Pagamento": str(date.today()), "Stato": "Spesa Effettiva", "Categoria": "Ricarica Revolut",
            "Sorgente": "Carta Debito EUR", "Valuta Originale": "JPY", "Importo Originale": 10000.0,
            "Importo EUR": round(10000 / tasso_cambio, 4), "Importo JPY": 10000, "Note": "Ricarica Rapida"
        }])
        st.session_state["df_spese"] = pd.concat([nuova_ricarica, st.session_state["df_spese"]], ignore_index=True)
        save_local_data(st.session_state["df_spese"])
        st.success("Ricarica da ¥ 10.000 inserita!")
        st.rerun()

# ═════════════════════════════════════════════════════════════════════
# 7. CRUSCOTTO FINANZIARIO & GRAFICI
# ═════════════════════════════════════════════════════════════════════
st.divider()
st.header("📊 Cruscotto Finanziario")

df = st.session_state["df_spese"]

if df.empty:
    st.info("Nessuna spesa presente nel file CSV.")
    st.stop()

# Filtri per i calcoli finanziari
spese_effettive = df[df["Stato"] == "Spesa Effettiva"]
prenotazioni = df[df["Stato"] == "Prenotazione"]
spese_reali = spese_effettive[(spese_effettive["Categoria"] != "Prelievo ATM") & (spese_effettive["Categoria"] != "Ricarica Revolut")]

tot_spesa_eur = spese_reali["Importo EUR"].sum()
tot_spesa_jpy = spese_reali["Importo JPY"].sum()
tot_pren_eur = prenotazioni["Importo EUR"].sum()
budget_residuo = budget_totale - tot_spesa_eur - tot_pren_eur

# Metriche KPI
k1, k2, k3, k4 = st.columns(4)
k1.metric("Budget Totale", f"€ {budget_totale:,.2f}")
k2.metric("Speso Effettivo", f"€ {tot_spesa_eur:,.2f}", f"¥ {tot_spesa_jpy:,.0f}")
k3.metric("Prenotazioni", f"€ {tot_pren_eur:,.2f}")
k4.metric("💰 Residuo", f"€ {budget_residuo:,.2f}", delta="✅ Ok" if budget_residuo >= 0 else "⚠️ Sforato")

if budget_totale > 0:
    perc_glob = min(max((tot_spesa_eur + tot_pren_eur) / budget_totale, 0.0), 1.0)
    st.write(f"Utilizzo budget globale: {perc_glob*100:.1f}%")
    st.progress(perc_glob)

# Grafici e Tabelle di Controllo
st.subheader("Ripartizione Spese per Categoria (€)")
if not spese_reali.empty:
    rip_cat = spese_reali.groupby("Categoria")["Importo EUR"].sum().reset_index()
    st.bar_chart(rip_cat.set_index("Categoria")["Importo EUR"])

st.subheader("👨‍👩‍👧 Riepilogo Spese per Persona")
rip_pers = spese_reali.groupby("Destinatario")["Importo EUR"].sum().reset_index()
st.dataframe(rip_pers, use_container_width=True, hide_index=True)

st.subheader("💳 Controllo Plafond Carte")
impegni_cc_eur = df[df["Sorgente"] == "Carta Credito EUR"]["Importo EUR"].sum()
st.metric("Plafond Utilizzato CC EUR", f"€ {impegni_cc_eur:,.2f}", f"Residuo: € {plafond_cc - impegni_cc_eur:,.2f}")

st.subheader("📜 Registro Ultime Operazioni")
st.dataframe(df, use_container_width=True, hide_index=True)
