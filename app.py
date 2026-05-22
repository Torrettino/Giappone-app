import streamlit as st
import uuid
import pandas as pd
import requests
import os
from datetime import datetime, date
from sqlalchemy import text, create_engine

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

st.title("🇯🇵 Gestione Spese Tokyo (Database)")

# ═════════════════════════════════════════════════════════════════════
# 2. CONNESSIONE DATABASE & COSTRUTTORE ENGINE
# ═════════════════════════════════════════════════════════════════════
# Inizializza la connessione nativa di Streamlit
conn = st.connection("postgresql", type="sql")

def get_raw_engine():
    """Genera un engine SQLAlchemy dinamico leggendo i secrets"""
    if "url" in st.secrets["postgresql"]:
        return create_engine(st.secrets["postgresql"]["url"])
    else:
        p = st.secrets["postgresql"]
        return create_engine(f"postgresql://{p['username']}:{p['password']}@{p['host']}:{p['port']}/{p['database']}")

# Automazione Scadenze Prenotazioni direttamente in SQL
try:
    with conn.session as session:
        session.execute(text("""
            UPDATE spese 
            SET "Stato" = 'Spesa Effettiva' 
            WHERE "Stato" = 'Prenotazione' 
              AND "Data Pagamento" <= :oggi
        """), {"oggi": str(date.today())})
        session.commit()
except Exception:
    # Ignora se la tabella non è ancora stata creata/migrata al primo avvio
    pass

# Inizializzazione Session State per memoria temporanea annullamenti
if "ultimo_id" not in st.session_state:
    st.session_state["ultimo_id"] = None

if "tasso_cambio" not in st.session_state:
    st.session_state["tasso_cambio"] = 165.0

if "quick_presets" not in st.session_state:
    st.session_state["quick_presets"] = {}

if "quick_selected" not in st.session_state:
    st.session_state["quick_selected"] = None

# Costanti dell'interfaccia
CATEGORIE = ["Trasporti", "Alloggi", "Cibo", "Shopping", "Altro", "Prelievo ATM", "Ricarica Revolut"]
SORGENTI = ["Carta Credito JPY", "Carta Credito EUR", "Carta Debito EUR", "Wallet Contanti"]
DESTINATARI = ["Famiglia", "Francesco", "Guia", "Matilde"]

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

# ═════════════════════════════════════════════════════════════════════
# 4. SIDEBAR DI CONFIGURAZIONE & PULSANTE DI MIGRAZIONE
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
    tab_date, tab_budget, tab_preset, tab_migrazione = st.tabs(["📅 Date", "💰 Budget", "⚡ Preset", "📦 Migra CSV"])

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

    with tab_migrazione:
        st.subheader("Caricamento Iniziale")
        st.caption("Esegui questo pulsante UNA SOLA VOLTA in locale sul PC per inviare il tuo file CSV a Supabase.")
        
        if st.button("🚀 Riversa CSV nel Database", use_container_width=True):
            CSV_FILE = "spese_tokyo .csv"
            if os.path.exists(CSV_FILE):
                try:
                    with st.spinner("Lettura e conversione file in corso..."):
                        df_csv = pd.read_csv(CSV_FILE)
                        df_csv["Data"] = df_csv["Data"].astype(str)
                        df_csv["Data Pagamento"] = df_csv["Data Pagamento"].astype(str)
                        
                        engine = get_raw_engine()
                        # Carica i dati creando o inserendo records nella tabella 'spese'
                        df_csv.to_sql("spese", engine, if_exists="append", index=False)
                        st.success(f"🔥 Successo! {len(df_csv)} righe migrate su Supabase. Ora l'app è indipendente!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Errore di migrazione: {e}")
            else:
                st.error(f"File '{CSV_FILE}' non trovato nella cartella del progetto.")

# ═════════════════════════════════════════════════════════════════════
# 5. INSERIMENTO NUOVA OPERAZIONE SU DATABASE
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

    submitted = st.form_submit_button("💾 Salva nel Database cloud", use_container_width=True)

    if submitted and importo > 0:
        imp_eur, imp_jpy = converti(importo, valuta, tasso_cambio)
        nota_fin = f"[{destinatario}] " + (note if note else "-")
        nuovo_id = str(uuid.uuid4())
        
        try:
            with conn.session as session:
                query_ins = text("""
                    INSERT INTO spese (_id, "Destinatario", "Data", "Data Pagamento", "Stato", "Categoria", "Sorgente", "Valuta Originale", "Importo Originale", "Importo EUR", "Importo JPY", "Note")
                    VALUES (:id, :dest, :data, :data_p, :stato, :cat, :sorg, :val, :imp, :eur, :jpy, :note)
                """)
                session.execute(query_ins, {
                    "id": nuovo_id, "dest": destinatario, "data": str(data_op), "data_p": str(data_pag),
                    "stato": stato, "cat": categoria, "sorg": sorgente, "val": valuta, "imp": float(importo),
                    "eur": round(imp_eur, 4), "jpy": int(round(imp_jpy, 0)), "note": nota_fin
                })
                session.commit()
            
            st.session_state["ultimo_id"] = nuovo_id
            st.success("✅ Spesa registrata direttamente su Supabase!")
            st.session_state["quick_selected"] = None
            st.rerun()
        except Exception as e:
            st.error(f"Errore di scrittura nel DB: {e}")

# Bottone Annulla Ultima Spesa
if st.session_state["ultimo_id"]:
    if st.button("⏪ Annulla ultima operazione inserita", use_container_width=True):
        try:
            with conn.session as session:
                session.execute(text('DELETE FROM spese WHERE _id = :id'), {"id": st.session_state["ultimo_id"]})
                session.commit()
            st.session_state["ultimo_id"] = None
            st.success("Ultima operazione rimossa dal Database cloud!")
            st.rerun()
        except Exception as e:
            st.error(f"Impossibile rimuovere l'operazione: {e}")

# ═════════════════════════════════════════════════════════════════════
# 6. CRUSCOTTO FINANZIARIO LEGATO A SUPABASE
# ═════════════════════════════════════════════════════════════════════
st.divider()
st.header("📊 Cruscotto Finanziario")

# Scarica i dati in tempo reale dal database
try:
    df = conn.query('SELECT * FROM spese ORDER BY "Data" DESC;', ttl=0)
except Exception as e:
    st.warning("Nessun dato trovato o tabella non ancora pronta su Supabase. Se è il primo avvio, effettua la migrazione dal tab laterale.")
    st.stop()

if df.empty:
    st.info("Il database su Supabase è vuoto. Vai nella barra laterale -> tab 'Migra CSV' per popolarlo.")
    st.stop()

# Calcolo Saldo Revolut dinamico dal DB
ricariche_rev = df[df["Categoria"] == "Ricarica Revolut"]["Importo JPY"].sum()
spese_rev = df[df["Sorgente"] == "Carta Credito JPY"]["Importo JPY"].sum()
saldo_revolut = ricariche_rev - spese_rev

st.subheader("🏧 Stato Conto Revolut (¥)")
col_saldo, col_ricarica = st.columns([2, 1])
col_saldo.metric("Saldo Attuale Revolut", f"¥ {saldo_revolut:,.0f}")

with col_ricarica:
    if st.button("💰 Ricarica rapida 10k ¥", use_container_width=True):
        try:
            with conn.session as session:
                query_ric = text("""
                    INSERT INTO spese (_id, "Destinatario", "Data", "Data Pagamento", "Stato", "Categoria", "Sorgente", "Valuta Originale", "Importo Originale", "Importo EUR", "Importo JPY", "Note")
                    VALUES (:id, 'Revolut', :data, :data, 'Spesa Effettiva', 'Ricarica Revolut', 'Carta Debito EUR', 'JPY', 10000.0, :eur, 10000, 'Ricarica Rapida')
                """)
                session.execute(query_ric, {
                    "id": str(uuid.uuid4()), "data": str(date.today()), "eur": round(10000 / tasso_cambio, 4)
                })
                session.commit()
            st.success("Ricarica da ¥ 10.000 registrata nel cloud!")
            st.rerun()
        except Exception as e:
            st.error(f"Errore ricarica: {e}")

# Filtri statistici per la Dashboard
spese_effettive = df[df["Stato"] == "Spesa Effettiva"]
prenotazioni = df[df["Stato"] == "Prenotazione"]
spese_reali = spese_effettive[(spese_effettive["Categoria"] != "Prelievo ATM") & (spese_effettive["Categoria"] != "Ricarica Revolut")]

tot_spesa_eur = spese_reali["Importo EUR"].sum()
tot_spesa_jpy = spese_reali["Importo JPY"].sum()
tot_pren_eur = prenotazioni["Importo EUR"].sum()
budget_residuo = budget_totale - tot_spesa_eur - tot_pren_eur

# Metriche KPI principali
st.write("")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Budget Totale", f"€ {budget_totale:,.2f}")
k2.metric("Speso Effettivo", f"€ {tot_spesa_eur:,.2f}", f"¥ {tot_spesa_jpy:,.0f}")
k3.metric("Prenotazioni", f"€ {tot_pren_eur:,.2f}")
k4.metric("💰 Residuo", f"€ {budget_residuo:,.2f}", delta="✅ Ok" if budget_residuo >= 0 else "⚠️ Sforato")

if budget_totale > 0:
    perc_glob = min(max((tot_spesa_eur + tot_pren_eur) / budget_totale, 0.0), 1.0)
    st.write(f"Utilizzo budget globale: {perc_glob*100:.1f}%")
    st.progress(perc_glob)

# Grafici di analisi
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

st.subheader("📜 Registro Ultime Operazioni (Live da Supabase)")
st.dataframe(df, use_container_width=True, hide_index=True)
