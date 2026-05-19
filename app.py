import streamlit as st
import pandas as pd
from datetime import datetime, date
import requests
import io
import uuid
 
# ── PAGE CONFIG ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Travel Budget Tracker", page_icon="🇯🇵", layout="wide")
 
st.markdown("""
<style>
    div[data-testid="metric-container"] { background:#1e1e2e; border-radius:10px; padding:12px; }
    .stProgress > div > div { border-radius:10px; }
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)
 
st.title("🇯🇵 Gestione Spese Tokyo")
 
# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "operazioni" not in st.session_state:
    st.session_state["operazioni"] = []
if "tasso_cambio" not in st.session_state:
    st.session_state["tasso_cambio"] = 165.0
 
# ── AUTOMAZIONE CONVERSIONE PRENOTAZIONI ──────────────────────────────────────
oggi_str = date.today().strftime("%Y-%m-%d")
for op in st.session_state["operazioni"]:
    if op.get("Stato") == "Prenotazione" and op.get("Data Pagamento"):
        if op["Data Pagamento"] <= oggi_str:
            op["Stato"] = "Spesa Effettiva"
 
# ── FUNZIONI UTILITY ──────────────────────────────────────────────────────────
CATEGORIE = ["Trasporti", "Alloggi", "Cibo", "Shopping", "Altro", "Prelievo ATM"]
SORGENTI  = ["Carta Credito JPY", "Carta Credito EUR", "Carta Debito EUR", "Wallet Contanti"]
 
def get_live_rate() -> tuple[float, bool]:
    """Recupera il tasso EUR→JPY live da open.er-api.com."""
    try:
        r = requests.get("https://open.er-api.com/v6/latest/EUR", timeout=5)
        r.raise_for_status()
        return float(r.json()["rates"]["JPY"]), True
    except Exception:
        return st.session_state["tasso_cambio"], False
 
def converti(importo: float, valuta: str, tasso: float) -> tuple[float, float]:
    """Restituisce (importo_eur, importo_jpy)."""
    if valuta == "EUR":
        return importo, importo * tasso
    return importo / tasso, importo
 
def elimina_per_id(ids: list[str]):
    """Rimuove le operazioni con gli ID indicati."""
    st.session_state["operazioni"] = [
        op for op in st.session_state["operazioni"] if op.get("_id") not in ids
    ]
 
# ── SIDEBAR: CONFIGURAZIONE ───────────────────────────────────────────────────
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
        rate, ok = get_live_rate()
        if ok:
            st.session_state["tasso_cambio"] = rate
            st.success(f"Tasso aggiornato: ¥{rate:.2f}")
            st.rerun()
        else:
            st.error("Impossibile raggiungere l'API. Verifica la connessione.")
 
    st.divider()
 
    # Date viaggio predefinite
    st.subheader("📅 Date Viaggio")
    data_inizio = st.date_input("Inizio", value=date(2026, 6, 13), key="d_inizio")
    data_fine   = st.date_input("Fine",   value=date(2026, 6, 26), key="d_fine")
 
    st.divider()
 
    # Budget e Carte
    st.subheader("🎯 Budget e Limiti")
    budget_totale = st.number_input("Budget massimo viaggio (€)", min_value=0.0, value=10000.0, step=100.0)
    
    st.write("---")
    st.write("💳 **Gestione Conti e Carte**")
    fondo_revolut = st.number_input("Fondo Totale Ricaricato su Revolut (¥)", min_value=0.0, value=250000.0, step=10000.0)
    plafond_cc = st.number_input("Plafond Mensile CC EUR (€)", min_value=0.0, value=3000.0, step=500.0)
 
    st.divider()
 
    # Backup
    st.subheader("📂 Backup")
    file_up = st.file_uploader("Ripristina da CSV", type="csv")
    if file_up:
        try:
            df_imp = pd.read_csv(file_up)
            if "_id" not in df_imp.columns:
                df_imp["_id"] = [str(uuid.uuid4()) for _ in range(len(df_imp))]
            existing_ids = {op["_id"] for op in st.session_state["operazioni"]}
            nuovi = [r for r in df_imp.to_dict("records") if r["_id"] not in existing_ids]
            st.session_state["operazioni"].extend(nuovi)
            st.success(f"Importati {len(nuovi)} record ({len(df_imp)-len(nuovi)} duplicati ignorati)")
        except Exception as e:
            st.error(f"Errore: {e}")
 
    if st.session_state["operazioni"]:
        df_exp = pd.DataFrame(st.session_state["operazioni"])
 
        # CSV
        csv_bytes = df_exp.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ CSV Backup", data=csv_bytes, file_name="spese_tokyo.csv", mime="text/csv")
 
# ══════════════════════════════════════════════════════════════════════════════
# SEZIONE 1 — INSERIMENTO NUOVA OPERAZIONE
# ══════════════════════════════════════════════════════════════════════════════
st.header("➕ Nuova Operazione")
 
# Quick-tag buttons
QUICK_TAGS = {
    "🚇 Metro":    ("Trasporti",   "Wallet Contanti",    "JPY", 230),
    "🍜 Ramen":    ("Cibo",        "Wallet Contanti",    "JPY", 1200),
    "🏪 Konbini":  ("Cibo",        "Wallet Contanti",    "JPY", 500),
    "🍣 Sushi":    ("Cibo",        "Carta Credito JPY",  "JPY", 3500),
    "🛍️ Shopping": ("Shopping",    "Carta Credito JPY",  "JPY", 0),
    "💴 Prelievo": ("Prelievo ATM","Wallet Contanti",    "JPY", 0),
}
 
if "quick" not in st.session_state:
    st.session_state["quick"] = None
 
st.write("**⚡ Preset rapidi**")
cols_q = st.columns(len(QUICK_TAGS))
for i, (label, vals) in enumerate(QUICK_TAGS.items()):
    with cols_q[i]:
        if st.button(label, use_container_width=True, key=f"qt_{i}"):
            st.session_state["quick"] = vals
 
q = st.session_state["quick"]
 
with st.form("form_ins", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
 
    with c1:
        data_op   = st.date_input("Data Inserimento", date.today())
        stato     = st.selectbox("Stato", ["Spesa Effettiva", "Prenotazione"])
        data_pag  = st.date_input("Data Addebito Automatico", date.today())
        cat_idx   = CATEGORIE.index(q[0]) if q else 0
        categoria = st.selectbox("Categoria", CATEGORIE, index=cat_idx)
 
    with c2:
        sorg_idx  = SORGENTI.index(q[1]) if q else 0
        sorgente  = st.selectbox("Sorgente", SORGENTI, index=sorg_idx)
        val_idx   = ["JPY","EUR"].index(q[2]) if q else 0
        valuta    = st.selectbox("Valuta", ["JPY","EUR"], index=val_idx)
        importo   = st.number_input("Importo", min_value=0.0, value=float(q[3]) if q else 0.0, step=1.0, format="%.2f")
        n_persone = st.number_input("Dividi tra N persone", min_value=1, value=1, step=1)
 
    with c3:
        note = st.text_area("Note / Descrizione", placeholder="Es: Cena sushi a Shibuya…", height=210)
 
    submitted = st.form_submit_button("🚀 Registra", use_container_width=True)
    if submitted and importo > 0:
        imp_split = importo / n_persone
        imp_eur, imp_jpy = converti(imp_split, valuta, tasso_cambio)
        nota_fin = (f"[÷{n_persone}] " if n_persone > 1 else "") + (note if note else "-")
        
        st.session_state["operazioni"].append({
            "_id":              str(uuid.uuid4()),
            "Data":             data_op.strftime("%Y-%m-%d"),
            "Data Pagamento":   data_pag.strftime("%Y-%m-%d"),
            "Stato":            stato,
            "Categoria":        categoria,
            "Sorgente":         sorgente,
            "Valuta Originale": valuta,
            "Importo Originale": round(imp_split, 2),
            "Importo EUR":      round(imp_eur, 4),
            "Importo JPY":      round(imp_jpy, 0),
            "Note":             nota_fin,
        })
        st.session_state["quick"] = None
        st.success(f"✅ Registrato!{' (quota 1/' + str(n_persone) + ')' if n_persone > 1 else ''}")
        st.rerun()
 
if st.session_state["operazioni"]:
    if st.button("⏪ Annulla ultima operazione"):
        st.session_state["operazioni"].pop()
        st.rerun()
 
# ══════════════════════════════════════════════════════════════════════════════
# SEZIONE 2 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.header("📊 Cruscotto Finanziario")
 
if not st.session_state["operazioni"]:
    st.info("Nessuna operazione ancora. Inserisci la prima spesa per attivare il cruscotto.")
    st.stop()
 
df = pd.DataFrame(st.session_state["operazioni"])
if "Data Pagamento" not in df.columns:
    df["Data Pagamento"] = df["Data"]
 
df["Data"] = pd.to_datetime(df["Data"])
df["Data Pagamento"] = pd.to_datetime(df["Data Pagamento"])
 
spese        = df[df["Stato"] == "Spesa Effettiva"]
prenotazioni = df[df["Stato"] == "Prenotazione"]
spese_reali  = spese[spese["Categoria"] != "Prelievo ATM"]
 
tot_spesa_eur  = spese_reali["Importo EUR"].sum()
tot_spesa_jpy  = spese_reali["Importo JPY"].sum()
tot_pren_eur   = prenotazioni["Importo EUR"].sum()
 
prelievi_jpy    = spese[spese["Categoria"] == "Prelievo ATM"]["Importo JPY"].sum()
contanti_uscite = spese[(spese["Sorgente"] == "Wallet Contanti") & (spese["Categoria"] != "Prelievo ATM")]["Importo JPY"].sum()
saldo_contanti  = prelievi_jpy - contanti_uscite
 
budget_residuo  = budget_totale - tot_spesa_eur - tot_pren_eur
 
# ── KPI ROW ──────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
k1.metric("Budget Totale",     f"€ {budget_totale:,.2f}")
k2.metric("Speso",             f"€ {tot_spesa_eur:,.2f}", f"¥ {tot_spesa_jpy:,.0f}")
k3.metric("Prenotazioni",      f"€ {tot_pren_eur:,.2f}")
k4.metric(
    "💰 Residuo disponibile",
    f"€ {budget_residuo:,.2f}",
    delta="✅ Ok" if budget_residuo >= 0 else "⚠️ Sforato",
    delta_color="normal" if budget_residuo >= 0 else "inverse"
)
 
# Barra budget globale
if budget_totale > 0:
    perc_glob = min((tot_spesa_eur + tot_pren_eur) / budget_totale, 1.0)
    st.write(f"**Utilizzo budget globale (Speso + Prenotato):** {perc_glob*100:.1f}%")
    st.progress(perc_glob)
    if (tot_spesa_eur + tot_pren_eur) > budget_totale:
        st.error("❌ Budget globale superato!")
 
# ── PROIEZIONE ────────────────────────────────────────────────────────────────
durata   = max((data_fine - data_inizio).days + 1, 1)
trascorsi = max(min((date.today() - data_inizio).days + 1, durata), 1) if date.today() >= data_inizio else 1
rimanenti = max(durata - trascorsi, 0)
 
if tot_spesa_eur > 0:
    media_gg   = tot_spesa_eur / trascorsi
    proiezione = media_gg * durata
    budget_gg  = budget_residuo / max(rimanenti, 1)
    st.info(
        f"📈 **Proiezione viaggio:** al ritmo di **€ {media_gg:.2f}/giorno** raggiungerai circa "
        f"**€ {proiezione:,.2f}** a fine viaggio.  \n"
        f"Ti restano **{rimanenti} giorni** con un budget di **€ {budget_gg:.2f}/giorno** disponibile."
    )
 
st.divider()
 
# ── GRAFICI ───────────────────────────────────────────────────────────────────
g1, g2 = st.columns(2)
 
with g1:
    st.subheader("🥧 Ripartizione per Categoria")
    if not spese_reali.empty:
        rip = spese_reali.groupby("Categoria")["Importo EUR"].sum().reset_index()
        rip = rip.sort_values("Importo EUR", ascending=False)
        rip["%"] = (rip["Importo EUR"] / rip["Importo EUR"].sum() * 100).round(1)
        rip["Label"] = rip["Categoria"] + " (" + rip["%"].astype(str) + "%)"
 
        st.bar_chart(rip.set_index("Categoria")["Importo EUR"])
 
with g2:
    st.subheader("📈 Andamento Giornaliero Spese")
    if not spese_reali.empty:
        daily = (
            spese_reali
            .groupby("Data")["Importo EUR"]
            .sum()
            .reset_index()
            .sort_values("Data")
        )
        daily["Cumulato (€)"] = daily["Importo EUR"].cumsum()
        daily = daily.rename(columns={"Importo EUR": "Spesa del giorno (€)"})
        st.line_chart(daily.set_index("Data")[["Spesa del giorno (€)", "Cumulato (€)"]])
 
st.divider()
 
# ── GESTIONE CARTE E CONTI ────────────────────────────────────────────────────
st.subheader("💳 Gestione Carte e Conti")
 
# 1. Calcolo Revolut (Prepagata)
cc_jpy_speso = spese[spese["Sorgente"] == "Carta Credito JPY"]["Importo JPY"].sum()
cc_jpy_prenotato = prenotazioni[prenotazioni["Sorgente"] == "Carta Credito JPY"]["Importo JPY"].sum()
residuo_revolut = fondo_revolut - cc_jpy_speso
 
# 2. Calcolo CD
cd_eur = spese[spese["Sorgente"] == "Carta Debito EUR"]["Importo EUR"].sum()
 
# Metriche Superiori (Revolut, Contanti, Carta di Debito)
c1, c2, c3 = st.columns(3)
c1.metric("Conto Revolut (CC JPY)", f"¥ {residuo_revolut:,.0f}", f"Speso finora: ¥ {cc_jpy_speso:,.0f}", delta_color="off")
c2.metric("Wallet Contanti", f"¥ {saldo_contanti:,.0f}", f"Speso: ¥ {contanti_uscite:,.0f}", delta_color="off")
c3.metric("Carta Debito EUR", f"€ {cd_eur:,.2f}", "Totale Addebitato", delta_color="off")
 
if cc_jpy_prenotato > 0:
    st.caption(f"📌 *Nota: Hai ¥ {cc_jpy_prenotato:,.0f} di prenotazioni in sospeso su Revolut non ancora detratte dal saldo reale.*")
 
st.write("---")
st.write("📈 **Controllo Plafond Mensile: Carta Credito EUR**")
st.write("*(Il calcolo include spese effettive e prenotazioni raggruppate per mese di addebito)*")
 
# 3. Controllo Plafond Mensile CC EUR (Usiamo 'df' per includere anche le prenotazioni future)
impegni_cc_eur = df[df["Sorgente"] == "Carta Credito EUR"].copy()
 
if not impegni_cc_eur.empty:
    impegni_cc_eur["Mese"] = impegni_cc_eur["Data Pagamento"].dt.strftime("%Y-%m")
    plafond_mensile = impegni_cc_eur.groupby("Mese")["Importo EUR"].sum().reset_index()
    
    cols_plafond = st.columns(len(plafond_mensile))
    for idx, row in plafond_mensile.iterrows():
        mese = row["Mese"]
        impegno_mese = row["Importo EUR"]
        residuo_mese = plafond_cc - impegno_mese
        perc = min(impegno_mese / plafond_cc, 1.0) if plafond_cc > 0 else 1.0
        
        with cols_plafond[idx % len(cols_plafond)]:
            st.write(f"**Mese Addebito: {mese}**")
            st.write(f"Impegnato: € {impegno_mese:,.2f} / € {plafond_cc:,.0f}")
            st.progress(perc)
            if residuo_mese >= 0:
                st.success(f"Disponibilità residua: **€ {residuo_mese:,.2f}**")
            else:
                st.error(f"⚠️ Plafond superato di: **€ {abs(residuo_mese):,.2f}**")
else:
    st.info("Nessun addebito registrato su Carta Credito EUR.")
 
st.divider()
 
# ══════════════════════════════════════════════════════════════════════════════
# SEZIONE 3 — REGISTRO CON FILTRI E ELIMINAZIONE SELETTIVA
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("📋 Registro Operazioni")
 
# Filtri
f1, f2, f3 = st.columns(3)
with f1:
    f_stato = st.multiselect("Stato", df["Stato"].unique(), default=list(df["Stato"].unique()))
with f2:
    f_cat = st.multiselect("Categoria", df["Categoria"].unique(), default=list(df["Categoria"].unique()))
with f3:
    f_sorg = st.multiselect("Sorgente", df["Sorgente"].unique(), default=list(df["Sorgente"].unique()))
 
df_vis = df[
    df["Stato"].isin(f_stato) &
    df["Categoria"].isin(f_cat) &
    df["Sorgente"].isin(f_sorg)
].copy()
 
# Formattazione per la visualizzazione nella tabella
df_vis["Data"] = df_vis["Data"].dt.strftime("%Y-%m-%d")
df_vis["Data Pagamento"] = df_vis["Data Pagamento"].dt.strftime("%Y-%m-%d")
 
# Colonna Elimina (checkbox)
df_vis.insert(0, "🗑️", False)
 
edited = st.data_editor(
    df_vis[["🗑️","_id","Data","Data Pagamento","Stato","Categoria","Sorgente","Importo Originale","Valuta Originale","Importo EUR","Note"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "🗑️":   st.column_config.CheckboxColumn("🗑️", width="small"),
        "_id":  st.column_config.TextColumn("ID", disabled=True, width="small"),
        "Importo Originale": st.column_config.NumberColumn("Importo", format="%.2f"),
        "Importo EUR":       st.column_config.NumberColumn("EUR",    format="€ %.2f"),
        "Data":    st.column_config.TextColumn("Data Ins.", disabled=True),
        "Data Pagamento": st.column_config.TextColumn("Data Addebito", disabled=True),
        "Stato":   st.column_config.TextColumn(disabled=True),
        "Categoria": st.column_config.TextColumn(disabled=True),
        "Sorgente":  st.column_config.TextColumn(disabled=True),
        "Valuta Originale": st.column_config.TextColumn(disabled=True),
        "Note":    st.column_config.TextColumn(disabled=True),
    },
)
 
da_eliminare = edited[edited["🗑️"] == True]["_id"].tolist()
if da_eliminare:
    if st.button(f"🗑️ Elimina {len(da_eliminare)} operazione/i selezionate", type="primary"):
        elimina_per_id(da_eliminare)
        st.success(f"Eliminate {len(da_eliminare)} operazioni.")
        st.rerun()
else:
    st.caption("☝️ Spunta la colonna 🗑️ per eliminare righe specifiche.")
