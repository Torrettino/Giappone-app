import streamlit as st
import uuid
import pandas as pd
import requests
from datetime import datetime, date
from sqlalchemy import text

# ═════════════════════════════════════════════════════════════════════
# 1. CONFIGURAZIONE PAGINA (OTTIMIZZATA WIDE & MOBILE)
# ═══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Travel Budget Tracker",
    page_icon="🇯🇵",
    layout="wide"
)

# CSS Personalizzato per la visualizzazione da Smartphone
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

st.title("🇯🇵 Gestione Spese Tokyo")

# ═════════════════════════════════════════════════════════════════════
# 2. CONNESSIONE DATABASE & FUNZIONI DI I/O
# ═════════════════════════════════════════════════════════════════════
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error("Errore di configurazione della connessione. Controlla il file secrets.toml.")
    st.stop()

def load_data_from_supabase():
    """Recupera i dati da Supabase e li formatta con i nomi richiesti dalla Dashboard"""
    try:
        query = """
            SELECT 
                id as "_id", 
                destinatario as "Destinatario", 
                data_inserimento::text as "Data", 
                data_pagamento::text as "Data Pagamento", 
                stato as "Stato", 
                categoria as "Categoria", 
                sorgente as "Sorgente", 
                valuta_originale as "Valuta Originale", 
                importo_orig as "Importo Originale", 
                importo_eur as "Importo EUR", 
                importo_jpy as "Importo JPY", 
                note as "Note" 
            FROM spese_tokyo
            ORDER BY data_inserimento DESC;
        """
        df = conn.query(query, ttl=0)
        if df.empty:
            return []
        return df.to_dict("records")
    except Exception as e:
        st.warning(f"Nessun dato caricato o tabella non ancora pronta: {e}")
        return []

# ═════════════════════════════════════════════════════════════════════
# 3. COSTANTI & SESSION STATE
# ═════════════════════════════════════════════════════════════════════
CATEGORIE = ["Trasporti", "Alloggi", "Cibo", "Shopping", "Altro", "Prelievo ATM", "Ricarica Revolut"]
SORGENTI = ["Carta Credito JPY", "Carta Credito EUR", "Carta Debito EUR", "Wallet Contanti"]
DESTINATARI = ["Famiglia", "Francesco", "Guia", "Matilde"]

if "operazioni" not in st.session_state:
    st.session_state["operazioni"] = load_data_from_supabase()

if "tasso_cambio" not in st.session_state:
    st.session_state["tasso_cambio"] = 165.0

if "quick_presets" not in st.session_state:
    st.session_state["quick_presets"] = {}

if "quick_selected" not in st.session_state:
    st.session_state["quick_selected"] = None

# Automazione: Trasforma Prenotazioni scadute in Spese Effettive
for op in st.session_state["operazioni"]:
    if op.get("Stato") == "Prenotazione" and op.get("Data Pagamento"):
        if pd.to_datetime(op["Data Pagamento"]) <= pd.to_datetime(date.today()):
            op["Stato"] = "Spesa Effettiva"

# ═════════════════════════════════════════════════════════════════════
# 4. UTILITIES & API CAMBIO LIVE
# ═════════════════════════════════════════════════════════════════════
def get_live_rate() -> tuple[float, bool]:
    try:
        r = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=5)
        r.raise_for_status()
        return float(r.json()["rates"]["JPY"]), True
    except Exception:
        return st.session_state["tasso_cambio"], False

def converti(importo: float, valuta: str, tasso: float):
    if valuta == "EUR":
        return importo, importo * tasso
    return importo / tasso, importo

def calcola_saldo_revolut():
    if not st.session_state["operazioni"]:
        return 0
    df_temp = pd.DataFrame(st.session_state["operazioni"])
    ricariche = df_temp[df_temp["Categoria"] == "Ricarica Revolut"]["Importo JPY"].sum()
    spese_rev = df_temp[df_temp["Sorgente"] == "Carta Credito JPY"]["Importo JPY"].sum()
    return ricariche - spese_rev

# ═════════════════════════════════════════════════════════════════════
# 5. SIDEBAR DI CONFIGURAZIONE
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
        else:
            st.error("Impossibile raggiungere l'API.")

    st.divider()
    tab_date, tab_budget, tab_preset = st.tabs(["📅 Date", "💰 Budget", "⚡ Preset"])

    with tab_date:
        st.subheader("Date Viaggio")
        data_inizio = st.date_input("Inizio", value=date(2026, 6, 13), key="d_inizio")
        data_fine = st.date_input("Fine", value=date(2026, 6, 26), key="d_fine")

    with tab_budget:
        st.subheader("Budget e Limiti")
        budget_totale = st.number_input("Budget massimo viaggio (€)", min_value=0.0, value=10000.0, step=100.0)
        st.write("---")
        plafond_cc = st.number_input("Plafond Mensile CC EUR (€)", min_value=0.0, value=3000.0, step=500.0)

    with tab_preset:
        st.subheader("Personalizza Preset Rapidi")
        nome_preset = st.text_input("Nome preset (es: Metro, Sushi)", placeholder="Inserisci il nome...", key="preset_name_input")
        
        if nome_preset:
            col_cat, col_sorg, col_val = st.columns(3)
            with col_cat:
                categoria_preset = st.selectbox("Categoria", CATEGORIE, key="preset_cat_select")
            with col_sorg:
                sorgente_preset = st.selectbox("Sorgente", SORGENTI, key="preset_sorg_select")
            with col_val:
                valuta_preset = st.selectbox("Valuta", ["JPY", "EUR"], key="preset_val_select")
            
            if st.button("➕ Salva Preset", use_container_width=True):
                st.session_state["quick_presets"][nome_preset] = {
                    "categoria": categoria_preset,
                    "sorgente": sorgente_preset,
                    "valuta": valuta_preset
                }
                st.success(f"✅ Preset '{nome_preset}' salvato!")
                st.rerun()

# ═════════════════════════════════════════════════════════════════════
# 6. INSERIMENTO NUOVA OPERAZIONE
# ═════════════════════════════════════════════════════════════════════
st.header("➕ Nuova Operazione")

if st.session_state["quick_presets"]:
    with st.expander("⚡ Preset Rapidi", expanded=False):
        quick_cols = st.columns(2)
        for i, (label, vals) in enumerate(st.session_state["quick_presets"].items()):
            with quick_cols[i % 2]:
                if st.button(label, use_container_width=True, key=f"qt_{i}"):
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
    note = st.text_area("Note / Descrizione", placeholder="Es: Cena sushi...", height=100)

    submitted = st.form_submit_button("🚀 Registra nel Cloud", use_container_width=True)

    if submitted and importo > 0:
        imp_eur, imp_jpy = converti(importo, valuta, tasso_cambio)
        nota_fin = f"[{destinatario}] " + (note if note else "-")
        id_operazione = str(uuid.uuid4())

        query_inserimento = text("""
            INSERT INTO spese_tokyo (
                id, destinatario, data_inserimento, data_pagamento, stato, 
                categoria, sorgente, valuta_originale, importo_orig, 
                importo_eur, importo_jpy, note
            ) VALUES (
                :id, :destinatario, :data_inserimento, :data_pagamento, :stato, 
                :categoria, :sorgente, :valuta_originale, :importo_orig, 
                :importo_eur, :importo_jpy, :note
            );
        """)

        try:
            with conn.session as session:
                session.execute(query_inserimento, {
                    "id": id_operazione, "destinatario": destinatario, "data_inserimento": data_op,
                    "data_pagamento": data_pag, "stato": stato, "categoria": categoria, "sorgente": sorgente,
                    "valuta_originale": valuta, "importo_orig": importo, "importo_eur": round(imp_eur, 4),
                    "importo_jpy": int(round(imp_jpy, 0)), "note": nota_fin
                })
                session.commit()
            st.success("✅ Spesa registrata con successo su Supabase!")
            st.session_state["quick_selected"] = None
            st.session_state["operazioni"] = load_data_from_supabase()
            st.rerun()
        except Exception as err:
            st.error(f"❌ Errore di salvataggio: {err}")

# Bottone Annulla Ultima Operazione direttamente dal DB
if st.session_state["operazioni"]:
    if st.button("⏪ Annulla ultima operazione", use_container_width=True):
        ultima_op_id = st.session_state["operazioni"][0]["_id"]
        try:
            with conn.session as session:
                session.execute(text("DELETE FROM spese_tokyo WHERE id = :id"), {"id": ultima_op_id})
                session.commit()
            st.success("Operazione eliminata!")
            st.session_state["operazioni"] = load_data_from_supabase()
            st.rerun()
        except Exception as e:
            st.error(f"Errore: {e}")

# ═════════════════════════════════════════════════════════════════════
# 7. SEZIONE CONTO REVOLUT
# ═════════════════════════════════════════════════════════════════════
st.divider()
st.header("🏧 Gestione Conto Revolut (¥)")
saldo_revolut = calcola_saldo_revolut()

col_saldo, col_ricarica = st.columns([2, 1])
with col_saldo:
    st.metric("Saldo Attuale Revolut", f"¥ {saldo_revolut:,.0f}")

with col_ricarica:
    if st.button("💰 Registra Ricarica rapida 10k ¥", use_container_width=True):
        try:
            with conn.session as session:
                session.execute(text("""
                    INSERT INTO spese_tokyo (id, destinatario, data_inserimento, data_pagamento, stato, categoria, sorgente, valuta_originale, importo_orig, importo_eur, importo_jpy, note)
                    VALUES (:id, 'Revolut', :data, :data, 'Spesa Effettiva', 'Ricarica Revolut', 'Carta Debito EUR', 'JPY', 10000, :eur, 10000, 'Ricarica Rapida');
                """), {"id": str(uuid.uuid4()), "data": date.today(), "eur": round(10000 / tasso_cambio, 4)})
                session.commit()
            st.success("Ricarica di ¥ 10,000 registrata!")
            st.session_state["operazioni"] = load_data_from_supabase()
            st.rerun()
        except Exception as e:
            st.error(f"Errore: {e}")

# ═════════════════════════════════════════════════════════════════════
# 8. CRUSCOTTO FINANZIARIO & GRAFICI
# ═════════════════════════════════════════════════════════════════════
st.divider()
st.header("📊 Cruscotto Finanziario")

if not st.session_state["operazioni"]:
    st.info("Nessuna operazione ancora registrata nel cloud. Inserisci la prima spesa per sbloccare i grafici!")
    st.stop()

df = pd.DataFrame(st.session_state["operazioni"])
df["Data"] = pd.to_datetime(df["Data"])

spese = df[df["Stato"] == "Spesa Effettiva"]
prenotazioni = df[df["Stato"] == "Prenotazione"]
spese_reali = spese[(spese["Categoria"] != "Prelievo ATM") & (spese["Categoria"] != "Ricarica Revolut")]

tot_spesa_eur = spese_reali["Importo EUR"].sum()
tot_spesa_jpy = spese_reali["Importo JPY"].sum()
tot_pren_eur = prenotazioni["Importo EUR"].sum()
budget_residuo = budget_totale - tot_spesa_eur - tot_pren_eur

# Visualizzazione KPI
k1, k2, k3, k4 = st.columns(4)
k1.metric("Budget Totale", f"€ {budget_totale:,.2f}")
k2.metric("Speso Effettivo", f"€ {tot_spesa_eur:,.2f}", f"¥ {tot_spesa_jpy:,.0f}")
k3.metric("Prenotazioni", f"€ {tot_pren_eur:,.2f}")
k4.metric("💰 Residuo", f"€ {budget_residuo:,.2f}", delta="✅ Ok" if budget_residuo >= 0 else "⚠️ Sforato")

if budget_totale > 0:
    perc_glob = min(max((tot_spesa_eur + tot_pren_eur) / budget_totale, 0.0), 1.0)
    st.write(f"Utilizzo budget globale: {perc_glob*100:.1f}%")
    st.progress(perc_glob)

# Grafici delle Spese
st.subheader("Pie Chart per Categoria")
if not spese_reali.empty:
    rip = spese_reali.groupby("Categoria")["Importo EUR"].sum().reset_index()
    st.bar_chart(rip.set_index("Categoria")["Importo EUR"])

st.subheader("👨‍👩‍👧 Spese per Persona")
rip_persona = spese_reali.groupby("Destinatario")["Importo EUR"].sum().reset_index()
st.dataframe(rip_persona, use_container_width=True, hide_index=True)

# Controllo Plafond Carte
st.subheader("💳 Controllo Plafond Carte")
impegni_cc_eur = df[df["Sorgente"] == "Carta Credito EUR"]["Importo EUR"].sum()
st.metric("Plafond Utilizzato CC EUR", f"€ {impegni_cc_eur:,.2f}", f"Residuo: € {plafond_cc - impegni_cc_eur:,.2f}")
