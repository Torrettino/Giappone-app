import streamlit as st
import uuid
import pandas as pd
import requests
import os
from datetime import datetime, date, timedelta
from sqlalchemy import text, create_engine

# ═════════════════════════════════════════════════════════════════════
# 1. CONFIGURAZIONE PAGINA & STILE
# ═════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="🇯🇵 Tokyo Trip",
    page_icon="🇯🇵",
    layout="centered"   # MOBILE: centered è meglio di wide su telefono
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
        padding-top: 1rem;
        padding-left: 0.75rem;
        padding-right: 0.75rem;
        max-width: 700px;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.8rem;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.1rem;
    }
    .stAlert {
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🇯🇵 Tokyo Trip Tracker")

# ═════════════════════════════════════════════════════════════════════
# 2. CONNESSIONE DATABASE
# ═════════════════════════════════════════════════════════════════════
# secrets.toml → [connections.postgresql]
# url = "postgresql://postgres.XXX:PASSWORD@aws-1-eu-central-1.pooler.supabase.com:6543/postgres"

conn = st.connection("postgresql", type="sql")

def get_raw_engine():
    """Engine SQLAlchemy per operazioni bulk (migrazione CSV). Usa sempre il pooler porta 6543."""
    secrets = st.secrets["connections"]["postgresql"]
    if "url" in secrets:
        url = secrets["url"]
    else:
        url = f"postgresql://{secrets['username']}:{secrets['password']}@{secrets['host']}:{secrets['port']}/{secrets['database']}"
    return create_engine(url)

# Automazione scadenze prenotazioni
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
    pass

# ═════════════════════════════════════════════════════════════════════
# 3. SESSION STATE
# ═════════════════════════════════════════════════════════════════════
if "ultimo_id" not in st.session_state:
    st.session_state["ultimo_id"] = None
if "tasso_cambio" not in st.session_state:
    st.session_state["tasso_cambio"] = 165.0
if "quick_presets" not in st.session_state:
    st.session_state["quick_presets"] = {}
if "quick_selected" not in st.session_state:
    st.session_state["quick_selected"] = None

# Costanti
CATEGORIE   = ["Trasporti", "Alloggi", "Cibo", "Shopping", "Altro", "Prelievo ATM", "Ricarica Revolut"]
SORGENTI    = ["Carta Credito JPY", "Carta Credito EUR", "Carta Debito EUR", "Wallet Contanti"]
DESTINATARI = ["Famiglia", "Francesco", "Guia", "Matilde"]

DATA_INIZIO_VIAGGIO = date(2026, 6, 13)
DATA_FINE_VIAGGIO   = date(2026, 6, 26)
SOGLIA_REVOLUT_LOW  = 5000   # ¥ — avviso saldo basso

# ═════════════════════════════════════════════════════════════════════
# 4. UTILITIES
# ═════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600)   # Cache 1 ora — non chiama l'API a ogni refresh
def get_live_rate_cached() -> tuple[float, bool]:
    try:
        r = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=5)
        r.raise_for_status()
        return float(r.json()["rates"]["JPY"]), True
    except Exception:
        return 165.0, False

def converti(importo: float, valuta: str, tasso: float):
    if valuta == "EUR":
        return importo, importo * tasso
    return importo / tasso, importo

# ═════════════════════════════════════════════════════════════════════
# 5. SIDEBAR
# ═════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("⚙️ Configurazione")

    # Tasso di cambio
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
        st.cache_data.clear()
        rate, ok = get_live_rate_cached()
        if ok:
            st.session_state["tasso_cambio"] = rate
            st.success(f"Tasso aggiornato: ¥ {rate:.2f}")
            st.rerun()
        else:
            st.warning("API non raggiungibile, tasso invariato.")

    st.divider()
    tab_budget, tab_preset, tab_migrazione = st.tabs(["💰 Budget", "⚡ Preset", "📦 Migra CSV"])

    with tab_budget:
        st.subheader("Budget e Limiti")
        budget_totale = st.number_input("Budget massimo viaggio (€)", min_value=0.0, value=10000.0, step=100.0)
        plafond_cc    = st.number_input("Plafond CC EUR giugno (€)",  min_value=0.0, value=3000.0,  step=500.0)

    with tab_preset:
        st.subheader("Preset Rapidi")
        nome_preset = st.text_input("Nome preset (es: Metro, Caffè)", key="p_name")
        if nome_preset:
            c1, c2, c3 = st.columns(3)
            with c1: cp_cat  = st.selectbox("Cat",  CATEGORIE, key="pc_cat")
            with c2: cp_sorg = st.selectbox("Sorg", SORGENTI,  key="pc_sorg")
            with c3: cp_val  = st.selectbox("Val",  ["JPY", "EUR"], key="pc_val")
            if st.button("➕ Salva Preset", use_container_width=True):
                st.session_state["quick_presets"][nome_preset] = {
                    "categoria": cp_cat, "sorgente": cp_sorg, "valuta": cp_val
                }
                st.rerun()
        if st.session_state["quick_presets"]:
            st.divider()
            st.caption("Preset salvati:")
            for nome in list(st.session_state["quick_presets"].keys()):
                col_n, col_x = st.columns([4, 1])
                col_n.write(f"• {nome}")
                if col_x.button("✕", key=f"del_{nome}"):
                    del st.session_state["quick_presets"][nome]
                    st.rerun()

    with tab_migrazione:
        st.subheader("Caricamento Iniziale")
        st.caption("Esegui UNA SOLA VOLTA in locale per importare il CSV storico su Supabase.")
        if st.button("🚀 Riversa CSV nel Database", use_container_width=True):
            CSV_FILE = "spese_tokyo .csv"
            if os.path.exists(CSV_FILE):
                engine = None
                try:
                    with st.spinner("Migrazione in corso..."):
                        df_csv = pd.read_csv(CSV_FILE)
                        df_csv["Data"]           = df_csv["Data"].astype(str)
                        df_csv["Data Pagamento"] = df_csv["Data Pagamento"].astype(str)
                        engine = get_raw_engine()
                        df_csv.to_sql("spese", engine, if_exists="append", index=False)
                        st.success(f"🔥 {len(df_csv)} righe migrate!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Errore di migrazione: {e}")
                finally:
                    if engine is not None:
                        engine.dispose()
            else:
                st.error(f"File '{CSV_FILE}' non trovato.")

# ═════════════════════════════════════════════════════════════════════
# 6. INSERIMENTO SPESA — sempre in cima, espanso
# ═════════════════════════════════════════════════════════════════════
with st.expander("➕ Registra spesa", expanded=True):

    # Preset rapidi — sempre visibili, non dentro un expander annidato
    if st.session_state["quick_presets"]:
        st.caption("⚡ Preset rapidi")
        quick_cols = st.columns(3)
        for i, (label, vals) in enumerate(st.session_state["quick_presets"].items()):
            with quick_cols[i % 3]:
                if st.button(label, use_container_width=True, key=f"qp_{i}"):
                    st.session_state["quick_selected"] = vals
                    st.rerun()
        st.write("")

    q = st.session_state["quick_selected"]

    with st.form("form_ins", clear_on_submit=True):
        col_d1, col_d2 = st.columns(2)
        with col_d1: data_op  = st.date_input("Data",           date.today())
        with col_d2: stato    = st.selectbox("Stato",           ["Spesa Effettiva", "Prenotazione"])

        data_pag = st.date_input("Data Addebito", date.today())

        col_c, col_s = st.columns(2)
        with col_c:
            cat_idx  = CATEGORIE.index(q["categoria"]) if q and q.get("categoria") in CATEGORIE else 0
            categoria = st.selectbox("Categoria", CATEGORIE, index=cat_idx)
        with col_s:
            sorg_idx  = SORGENTI.index(q["sorgente"]) if q and q.get("sorgente") in SORGENTI else 0
            sorgente  = st.selectbox("Sorgente",  SORGENTI,  index=sorg_idx)

        col_v, col_i = st.columns(2)
        with col_v:
            val_idx = ["JPY", "EUR"].index(q["valuta"]) if q and q.get("valuta") else 0
            valuta  = st.selectbox("Valuta", ["JPY", "EUR"], index=val_idx)
        with col_i:
            importo = st.number_input("Importo", min_value=0.0, value=0.0, step=1.0, format="%.2f")

        destinatario = st.selectbox("Per chi?", DESTINATARI)
        note         = st.text_area("Note", placeholder="Descrizione...", height=70)

        submitted = st.form_submit_button("💾 Salva", use_container_width=True)

        if submitted and importo > 0:
            imp_eur, imp_jpy = converti(importo, valuta, tasso_cambio)
            nota_fin  = f"[{destinatario}] " + (note if note else "-")
            nuovo_id  = str(uuid.uuid4())
            try:
                with conn.session as session:
                    session.execute(text("""
                        INSERT INTO spese (
                            _id, "Destinatario", "Data", "Data Pagamento", "Stato",
                            "Categoria", "Sorgente", "Valuta Originale", "Importo Originale",
                            "Importo EUR", "Importo JPY", "Note"
                        ) VALUES (
                            :id, :dest, :data, :data_p, :stato,
                            :cat, :sorg, :val, :imp, :eur, :jpy, :note
                        )
                    """), {
                        "id": nuovo_id, "dest": destinatario,
                        "data": str(data_op), "data_p": str(data_pag),
                        "stato": stato, "cat": categoria, "sorg": sorgente,
                        "val": valuta, "imp": float(importo),
                        "eur": round(imp_eur, 4), "jpy": int(round(imp_jpy, 0)),
                        "note": nota_fin
                    })
                    session.commit()
                st.session_state["ultimo_id"] = nuovo_id
                st.session_state["quick_selected"] = None
                st.success("✅ Spesa salvata!")
                st.rerun()
            except Exception as e:
                st.error(f"Errore di scrittura nel DB: {e}")

# Annulla ultima spesa
if st.session_state["ultimo_id"]:
    if st.button("⏪ Annulla ultima operazione", use_container_width=True):
        try:
            with conn.session as session:
                session.execute(
                    text('DELETE FROM spese WHERE _id = :id'),
                    {"id": st.session_state["ultimo_id"]}
                )
                session.commit()
            st.session_state["ultimo_id"] = None
            st.success("Operazione rimossa.")
            st.rerun()
        except Exception as e:
            st.error(f"Impossibile rimuovere: {e}")

# ═════════════════════════════════════════════════════════════════════
# 7. CARICAMENTO DATI
# ═════════════════════════════════════════════════════════════════════
st.divider()

try:
    df = conn.query('SELECT * FROM spese ORDER BY "Data" DESC;', ttl=0)
except Exception:
    st.warning("Tabella non trovata o connessione assente. Effettua la migrazione dalla sidebar.")
    st.stop()

if df.empty:
    st.info("Nessuna spesa registrata. Usa il form qui sopra per iniziare.")
    st.stop()

# ═════════════════════════════════════════════════════════════════════
# 8. CRUSCOTTO PRINCIPALE
# ═════════════════════════════════════════════════════════════════════
st.header("📊 Cruscotto")

# Filtri base
spese_effettive = df[df["Stato"] == "Spesa Effettiva"]
prenotazioni    = df[df["Stato"] == "Prenotazione"]
spese_reali     = spese_effettive[
    ~spese_effettive["Categoria"].isin(["Prelievo ATM", "Ricarica Revolut"])
]

tot_spesa_eur = spese_reali["Importo EUR"].sum()
tot_spesa_jpy = spese_reali["Importo JPY"].sum()
tot_pren_eur  = prenotazioni["Importo EUR"].sum()
budget_residuo = budget_totale - tot_spesa_eur - tot_pren_eur

# ── KPI principali ──────────────────────────────────────────────────
k1, k2 = st.columns(2)
k1.metric("Speso",       f"€ {tot_spesa_eur:,.0f}", f"¥ {tot_spesa_jpy:,.0f}")
k2.metric("Prenotazioni", f"€ {tot_pren_eur:,.0f}")

k3, k4 = st.columns(2)
k3.metric("Budget totale", f"€ {budget_totale:,.0f}")
k4.metric(
    "💰 Residuo",
    f"€ {budget_residuo:,.0f}",
    delta="✅ Ok" if budget_residuo >= 0 else "⚠️ Sforato"
)

if budget_totale > 0:
    perc = min(max((tot_spesa_eur + tot_pren_eur) / budget_totale, 0.0), 1.0)
    st.caption(f"Utilizzo budget: {perc*100:.1f}%")
    st.progress(perc)

# ── QUANTO CI RIMANE OGGI? ─────────────────────────────────────────
st.write("")
if st.button("📅 Quanto posso spendere oggi?", use_container_width=True):
    oggi = date.today()
    if oggi < DATA_INIZIO_VIAGGIO:
        giorni_rimasti = (DATA_FINE_VIAGGIO - DATA_INIZIO_VIAGGIO).days
    elif oggi > DATA_FINE_VIAGGIO:
        giorni_rimasti = 1
    else:
        giorni_rimasti = (DATA_FINE_VIAGGIO - oggi).days + 1

    if giorni_rimasti > 0 and budget_residuo > 0:
        budget_giornaliero = budget_residuo / giorni_rimasti
        st.success(
            f"Hai **€ {budget_residuo:,.0f}** residui "
            f"su **{giorni_rimasti} giorni** rimasti → "
            f"**€ {budget_giornaliero:,.0f}/giorno** "
            f"(≈ ¥ {budget_giornaliero * tasso_cambio:,.0f})"
        )
    elif budget_residuo <= 0:
        st.error("⚠️ Budget esaurito o sforato!")
    else:
        st.info("Viaggio concluso.")

st.divider()

# ── REVOLUT ────────────────────────────────────────────────────────
st.subheader("🏧 Revolut (¥)")

ricariche_rev = df[df["Categoria"] == "Ricarica Revolut"]["Importo JPY"].sum()
spese_rev     = df[df["Sorgente"]  == "Carta Credito JPY"]["Importo JPY"].sum()
saldo_revolut = ricariche_rev - spese_rev

# Avviso saldo basso
if saldo_revolut < SOGLIA_REVOLUT_LOW:
    st.warning(f"⚠️ Saldo Revolut basso: ¥ {saldo_revolut:,.0f} — ricarica presto!")
else:
    st.metric("Saldo Revolut", f"¥ {saldo_revolut:,.0f}")

col_r1, col_r2 = st.columns(2)

with col_r1:
    if st.button("💰 +¥10.000", use_container_width=True):
        try:
            with conn.session as session:
                session.execute(text("""
                    INSERT INTO spese (
                        _id, "Destinatario", "Data", "Data Pagamento", "Stato",
                        "Categoria", "Sorgente", "Valuta Originale", "Importo Originale",
                        "Importo EUR", "Importo JPY", "Note"
                    ) VALUES (
                        :id, 'Revolut', :data, :data, 'Spesa Effettiva',
                        'Ricarica Revolut', 'Carta Debito EUR', 'JPY', 10000.0,
                        :eur, 10000, 'Ricarica Rapida'
                    )
                """), {
                    "id": str(uuid.uuid4()),
                    "data": str(date.today()),
                    "eur": round(10000 / tasso_cambio, 4)
                })
                session.commit()
            st.success("¥ 10.000 aggiunti!")
            st.rerun()
        except Exception as e:
            st.error(f"Errore ricarica: {e}")

with col_r2:
    if st.button("💰 +¥20.000", use_container_width=True):
        try:
            with conn.session as session:
                session.execute(text("""
                    INSERT INTO spese (
                        _id, "Destinatario", "Data", "Data Pagamento", "Stato",
                        "Categoria", "Sorgente", "Valuta Originale", "Importo Originale",
                        "Importo EUR", "Importo JPY", "Note"
                    ) VALUES (
                        :id, 'Revolut', :data, :data, 'Spesa Effettiva',
                        'Ricarica Revolut', 'Carta Debito EUR', 'JPY', 20000.0,
                        :eur, 20000, 'Ricarica Rapida'
                    )
                """), {
                    "id": str(uuid.uuid4()),
                    "data": str(date.today()),
                    "eur": round(20000 / tasso_cambio, 4)
                })
                session.commit()
            st.success("¥ 20.000 aggiunti!")
            st.rerun()
        except Exception as e:
            st.error(f"Errore ricarica: {e}")

st.divider()

# ── PLAFOND CC EUR — solo giugno ───────────────────────────────────
st.subheader("💳 Plafond CC EUR — Giugno 2026")
df_giugno      = df[df["Data Pagamento"].str.startswith("2026-06")]
impegni_cc_eur = df_giugno[df_giugno["Sorgente"] == "Carta Credito EUR"]["Importo EUR"].sum()
residuo_cc     = plafond_cc - impegni_cc_eur

col_cc1, col_cc2 = st.columns(2)
col_cc1.metric("Utilizzato", f"€ {impegni_cc_eur:,.2f}")
col_cc2.metric(
    "Residuo plafond",
    f"€ {residuo_cc:,.2f}",
    delta="✅ Ok" if residuo_cc >= 0 else "⚠️ Sforato"
)
if plafond_cc > 0:
    perc_cc = min(max(impegni_cc_eur / plafond_cc, 0.0), 1.0)
    st.caption(f"Utilizzo plafond: {perc_cc*100:.1f}%")
    st.progress(perc_cc)

st.divider()

# ── SPESE PER PERSONA ──────────────────────────────────────────────
st.subheader("👨‍👩‍👧 Spese per persona")
rip_pers = (
    spese_reali
    .groupby("Destinatario")["Importo EUR"]
    .sum()
    .reset_index()
    .rename(columns={"Importo EUR": "€"})
    .sort_values("€", ascending=False)
)
st.dataframe(rip_pers, use_container_width=True, hide_index=True)

st.divider()

# ── REGISTRO SPESE — filtrabile per giorno ─────────────────────────
st.subheader("📜 Registro operazioni")

col_f1, col_f2 = st.columns([2, 1])
with col_f1:
    filtro_data = st.date_input(
        "Filtra per giorno",
        value=date.today(),
        key="filtro_data"
    )
with col_f2:
    mostra_tutti = st.checkbox("Tutti i giorni", value=False)

if mostra_tutti:
    df_view = df
else:
    df_view = df[df["Data"] == str(filtro_data)]

if df_view.empty:
    st.info("Nessuna operazione per questo giorno.")
else:
    # Colonne essenziali per mobile
    cols_mobile = ["Data", "Categoria", "Sorgente", "Importo JPY", "Importo EUR", "Note"]
    cols_show   = [c for c in cols_mobile if c in df_view.columns]
    st.dataframe(df_view[cols_show], use_container_width=True, hide_index=True)
