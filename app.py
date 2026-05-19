import streamlit as st
import pandas as pd
from datetime import datetime, date
import requests
import uuid
import json
import os

# ── PERSISTENZA DATI ─────────────────────────────────────────────────────
DATA_DIR = "dati_spese"
DATA_FILE = os.path.join(DATA_DIR, "spese_tokyo.json")

# Crea la cartella se non esiste
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def load_data():
    """Carica i dati dal file JSON"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Errore nel caricamento dei dati: {e}")
            return []
    return []

def save_data(operazioni):
    """Salva i dati nel file JSON"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(operazioni, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Errore nel salvataggio dei dati: {e}")

# ── PAGE CONFIG ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Travel Budget Tracker",
    page_icon="🇯🇵",
    layout="wide"
)

# ── CSS PERSONALIZZATO PER MOBILE ────────────────────────────────────────
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
    
    /* Mobile: riduce padding su schermi piccoli */
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

# ══════════════════════════════════════════════════════════════════[...]
# SESSION STATE
# ══════════════════════════════════════════════════════════════════[...]
if "operazioni" not in st.session_state:
    st.session_state["operazioni"] = load_data()

if "tasso_cambio" not in st.session_state:
    st.session_state["tasso_cambio"] = 165.0

if "quick_presets" not in st.session_state:
    # Preset di default vuoti - l'utente li customize
    st.session_state["quick_presets"] = {}

if "quick_selected" not in st.session_state:
    st.session_state["quick_selected"] = None

# ══════════════════════════════════════════════════════════════════[...]
# AUTOMAZIONE PRENOTAZIONI → SPESE
# ══════════════════════════════════════════════════════════════════[...]
oggi_str = date.today().strftime("%Y-%m-%d")

for op in st.session_state["operazioni"]:

    if op.get("Stato") != "Prenotazione":
        continue

    if op.get("Data Pagamento"):

        if pd.to_datetime(op["Data Pagamento"]) <= pd.to_datetime(date.today()):
            op["Stato"] = "Spesa Effettiva"

# ══════════════════════════════════════════════════════════════════[...]
# COSTANTI
# ══════════════════════════════════════════════════════════════════[...]
CATEGORIE = [
    "Trasporti",
    "Alloggi",
    "Cibo",
    "Shopping",
    "Altro",
    "Prelievo ATM",
    "Ricarica Revolut"
]

SORGENTI = [
    "Carta Credito JPY",
    "Carta Credito EUR",
    "Carta Debito EUR",
    "Wallet Contanti"
]

DESTINATARI = [
    "Famiglia",
    "Francesco",
    "Guia",
    "Matilde"
]

# ══════════════════════════════════════════════════════════════════[...]
# FUNZIONI
# ══════════════════════════════════════════════════════════════════[...]
def get_live_rate() -> tuple[float, bool]:

    try:
        r = requests.get(
            "https://open.er-api.com/v6/latest/EUR",
            timeout=5
        )

        r.raise_for_status()

        return float(r.json()["rates"]["JPY"]), True

    except Exception:
        return st.session_state["tasso_cambio"], False


def converti(importo: float, valuta: str, tasso: float):

    if valuta == "EUR":
        return importo, importo * tasso

    return importo / tasso, importo


def elimina_per_id(ids):

    st.session_state["operazioni"] = [
        op for op in st.session_state["operazioni"]
        if op.get("_id") not in ids
    ]
    save_data(st.session_state["operazioni"])


def get_categorie_usate():
    """Ritorna le categorie effettivamente usate nelle operazioni"""
    if not st.session_state["operazioni"]:
        return CATEGORIE
    
    df_temp = pd.DataFrame(st.session_state["operazioni"])
    categorie_usate = df_temp["Categoria"].unique().tolist()
    
    # Aggiungi categorie non ancora usate
    for cat in CATEGORIE:
        if cat not in categorie_usate:
            categorie_usate.append(cat)
    
    return sorted(categorie_usate)


def get_sorgenti_usate():
    """Ritorna le sorgenti effettivamente usate nelle operazioni"""
    if not st.session_state["operazioni"]:
        return SORGENTI
    
    df_temp = pd.DataFrame(st.session_state["operazioni"])
    sorgenti_usate = df_temp["Sorgente"].unique().tolist()
    
    # Aggiungi sorgenti non ancora usate
    for sorg in SORGENTI:
        if sorg not in sorgenti_usate:
            sorgenti_usate.append(sorg)
    
    return sorted(sorgenti_usate)


def calcola_saldo_revolut():
    """Calcola il saldo attuale del conto Revolut"""
    if not st.session_state["operazioni"]:
        return 0
    
    df_temp = pd.DataFrame(st.session_state["operazioni"])
    
    # Somma ricariche (positive)
    ricariche = df_temp[
        df_temp["Categoria"] == "Ricarica Revolut"
    ]["Importo JPY"].sum()
    
    # Somma spese Revolut (negative)
    spese = df_temp[
        df_temp["Sorgente"] == "Carta Credito JPY"
    ]["Importo JPY"].sum()
    
    return ricariche - spese

# ══════════════════════════════════════════════════════════════════[...]
# SIDEBAR
# ══════════════════════════════════════════════════════════════════[...]
with st.sidebar:

    st.header("⚙️ Configurazione")

    # ── TASSO CAMBIO ────────────────────────────────────────────────────────
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

    # ── TAB CONFIGURAZIONE ───────────────────────────────────────────────────
    tab_date, tab_budget, tab_preset, tab_backup = st.tabs(
        ["📅 Date", "💰 Budget", "⚡ Preset", "📂 Backup"]
    )

    with tab_date:
        st.subheader("Date Viaggio")

        data_inizio = st.date_input(
            "Inizio",
            value=date(2026, 6, 13),
            key="d_inizio"
        )

        data_fine = st.date_input(
            "Fine",
            value=date(2026, 6, 26),
            key="d_fine"
        )

    with tab_budget:
        st.subheader("Budget e Limiti")

        budget_totale = st.number_input(
            "Budget massimo viaggio (€)",
            min_value=0.0,
            value=10000.0,
            step=100.0
        )

        st.write("---")
        st.write("💳 Gestione Conti e Carte")

        plafond_cc = st.number_input(
            "Plafond Mensile CC EUR (€)",
            min_value=0.0,
            value=3000.0,
            step=500.0
        )

    with tab_preset:
        st.subheader("Personalizza Preset Rapidi")
        
        st.write("Aggiungi i tuoi preset personalizzati")
        
        nome_preset = st.text_input(
            "Nome preset (es: Metro, Sushi, Caffè)",
            placeholder="Inserisci il nome...",
            key="preset_name_input"
        )
        
        if nome_preset:
            col_cat, col_sorg, col_val = st.columns(3)
            
            with col_cat:
                categoria_preset = st.selectbox(
                    "Categoria",
                    get_categorie_usate(),
                    key="preset_cat_select"
                )
            
            with col_sorg:
                sorgente_preset = st.selectbox(
                    "Sorgente",
                    get_sorgenti_usate(),
                    key="preset_sorg_select"
                )
            
            with col_val:
                valuta_preset = st.selectbox(
                    "Valuta",
                    ["JPY", "EUR"],
                    key="preset_val_select"
                )
            
            if st.button("➕ Salva Preset", use_container_width=True):
                st.session_state["quick_presets"][nome_preset] = {
                    "categoria": categoria_preset,
                    "sorgente": sorgente_preset,
                    "valuta": valuta_preset
                }
                st.success(f"✅ Preset '{nome_preset}' salvato!")
                st.rerun()
        
        st.write("---")
        
        if st.session_state["quick_presets"]:
            st.write("**I tuoi preset:**")
            
            for preset_name in st.session_state["quick_presets"].keys():
                col_name, col_del = st.columns([4, 1])
                
                with col_name:
                    preset_data = st.session_state["quick_presets"][preset_name]
                    st.caption(
                        f"🏷️ {preset_name} | "
                        f"{preset_data['categoria']} | "
                        f"{preset_data['sorgente']} | "
                        f"{preset_data['valuta']}"
                    )
                
                with col_del:
                    if st.button("🗑️", key=f"del_preset_{preset_name}"):
                        del st.session_state["quick_presets"][preset_name]
                        st.success("Eliminato!")
                        st.rerun()
        else:
            st.info("Nessun preset salvato. Creane uno sopra!")

    with tab_backup:
        st.subheader("Backup e Ripristino")

        file_up = st.file_uploader(
            "Ripristina da CSV",
            type="csv"
        )

        if file_up:

            try:
                df_imp = pd.read_csv(file_up)

                if "_id" not in df_imp.columns:
                    df_imp["_id"] = [
                        str(uuid.uuid4())
                        for _ in range(len(df_imp))
                    ]

                existing_ids = {
                    op["_id"]
                    for op in st.session_state["operazioni"]
                }

                nuovi = [
                    r for r in df_imp.to_dict("records")
                    if r["_id"] not in existing_ids
                ]

                st.session_state["operazioni"].extend(nuovi)
                save_data(st.session_state["operazioni"])

                st.success(
                    f"Importati {len(nuovi)} record "
                    f"({len(df_imp)-len(nuovi)} duplicati ignorati)"
                )

            except Exception as e:
                st.error(f"Errore: {e}")

        st.write("---")

        if st.session_state["operazioni"]:

            df_exp = pd.DataFrame(
                st.session_state["operazioni"]
            )

            csv_bytes = df_exp.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                "⬇️ CSV Backup",
                data=csv_bytes,
                file_name="spese_tokyo.csv",
                mime="text/csv",
                use_container_width=True
            )

# ══════════════════════════════════════════════════════════════════[...]
# NUOVA OPERAZIONE
# ══════════════════════════════════════════════════════════════════[...]
st.header("➕ Nuova Operazione")

# ── QUICK TAGS (Nascosti in expander) ───────────────────────────────────────
if st.session_state["quick_presets"]:
    with st.expander("⚡ Preset Rapidi", expanded=False):
        st.write("Scegli un preset per compilare velocemente i campi:")
        
        quick_cols = st.columns(2)
        for i, (label, vals) in enumerate(st.session_state["quick_presets"].items()):
            with quick_cols[i % 2]:
                if st.button(
                    label,
                    use_container_width=True,
                    key=f"qt_{i}"
                ):
                    st.session_state["quick_selected"] = vals
                    st.rerun()

q = st.session_state["quick_selected"]

# ── FORM ──────────────────────────────────────────────────────────────[...]
with st.form("form_ins", clear_on_submit=True):

    # ── DATI ────────────────────────────────────────────────────────────[...]
    data_op = st.date_input(
        "Data Inserimento",
        date.today()
    )

    stato = st.selectbox(
        "Stato",
        ["Spesa Effettiva", "Prenotazione"]
    )

    data_pag = st.date_input(
        "Data Addebito Automatico",
        date.today()
    )

    cat_idx = (
        get_categorie_usate().index(q["categoria"]) 
        if q and q.get("categoria") in get_categorie_usate() 
        else 0
    )

    categoria = st.selectbox(
        "Categoria",
        get_categorie_usate(),
        index=cat_idx
    )

    # ── FONTE E VALUTA ───────────────────────────────────────────────────
    sorg_idx = (
        get_sorgenti_usate().index(q["sorgente"]) 
        if q and q.get("sorgente") in get_sorgenti_usate() 
        else 0
    )

    sorgente = st.selectbox(
        "Sorgente",
        get_sorgenti_usate(),
        index=sorg_idx
    )

    val_idx = ["JPY", "EUR"].index(q["valuta"]) if q and q.get("valuta") else 0

    valuta = st.selectbox(
        "Valuta",
        ["JPY", "EUR"],
        index=val_idx
    )

    importo = st.number_input(
        "Importo",
        min_value=0.0,
        value=0.0,
        step=1.0,
        format="%.2f"
    )

    destinatario = st.selectbox(
        "Destinatario Spesa",
        DESTINATARI
    )

    # ── NOTE ────────────────────────────────────────────────────────────[...]
    note = st.text_area(
        "Note / Descrizione",
        placeholder="Es: Cena sushi a Shibuya…",
        height=100
    )

    submitted = st.form_submit_button(
        "🚀 Registra",
        use_container_width=True
    )

    # ── SALVATAGGIO ──────────────────────────────────────────────────────
    if submitted and importo > 0:

        imp_eur, imp_jpy = converti(
            importo,
            valuta,
            tasso_cambio
        )

        nota_fin = (
            f"[{destinatario}] "
            + (note if note else "-")
        )

        st.session_state["operazioni"].append({

            "_id": str(uuid.uuid4()),

            "Destinatario": destinatario,

            "Data": data_op.strftime("%Y-%m-%d"),

            "Data Pagamento": data_pag.strftime("%Y-%m-%d"),

            "Stato": stato,

            "Categoria": categoria,

            "Sorgente": sorgente,

            "Valuta Originale": valuta,

            "Importo Originale": round(importo, 2),

            "Importo EUR": round(imp_eur, 4),

            "Importo JPY": round(imp_jpy, 0),

            "Note": nota_fin,
        })

        save_data(st.session_state["operazioni"])

        st.session_state["quick_selected"] = None

        st.success(
            f"✅ Spesa registrata per: {destinatario}"
        )

        st.rerun()

# ── ANNULLA ULTIMA OPERAZIONE ────────────────────────────────────────────
if st.session_state["operazioni"]:

    if st.button("⏪ Annulla ultima operazione", use_container_width=True):

        st.session_state["operazioni"].pop()
        save_data(st.session_state["operazioni"])

        st.rerun()

# ══════════════════════════════════════════════════════���═══════════[...]
# RICARICA REVOLUT (Sezione dedicata)
# ══════════════════════════════════════════════════════════════════[...]
st.divider()

st.header("🏧 Gestione Conto Revolut (¥)")

saldo_revolut = calcola_saldo_revolut()

col_saldo, col_ricarica = st.columns([2, 1])

with col_saldo:
    st.metric(
        "Saldo Attuale",
        f"¥ {saldo_revolut:,.0f}"
    )

with col_ricarica:
    st.write("")  # Spacer
    st.write("")
    if st.button("💰 Ricarica", use_container_width=True):
        st.session_state["show_ricarica_form"] = True

if "show_ricarica_form" not in st.session_state:
    st.session_state["show_ricarica_form"] = False

if st.session_state["show_ricarica_form"]:
    
    with st.form("form_ricarica", clear_on_submit=True):
        
        st.subheader("💳 Aggiungi Fondi a Revolut")
        
        importo_ricarica = st.number_input(
            "Importo da aggiungere (¥)",
            min_value=0.0,
            value=0.0,
            step=1000.0,
            format="%.0f"
        )
        
        sorgente_ricarica = st.selectbox(
            "Sorgente Ricarica",
            ["Carta Credito EUR", "Carta Debito EUR", "Trasferimento Bancario"]
        )
        
        data_ricarica = st.date_input(
            "Data Ricarica",
            date.today()
        )
        
        note_ricarica = st.text_area(
            "Note (facoltativo)",
            placeholder="Es: Ricarica prima del viaggio...",
            height=80
        )
        
        col_submit, col_cancel = st.columns(2)
        
        with col_submit:
            submitted_ricarica = st.form_submit_button(
                "✅ Conferma Ricarica",
                use_container_width=True,
                type="primary"
            )
        
        with col_cancel:
            if st.form_submit_button(
                "❌ Annulla",
                use_container_width=True
            ):
                st.session_state["show_ricarica_form"] = False
                st.rerun()
        
        if submitted_ricarica and importo_ricarica > 0:
            
            # Converti importo EUR a JPY se sorgente è carta EUR
            if "EUR" in sorgente_ricarica:
                importo_eur = importo_ricarica / tasso_cambio
            else:
                importo_eur = 0
            
            nota_ricarica_fin = (
                f"Ricarica da {sorgente_ricarica} | "
                + (note_ricarica if note_ricarica else "-")
            )
            
            st.session_state["operazioni"].append({
                
                "_id": str(uuid.uuid4()),
                
                "Destinatario": "Revolut",
                
                "Data": data_ricarica.strftime("%Y-%m-%d"),
                
                "Data Pagamento": data_ricarica.strftime("%Y-%m-%d"),
                
                "Stato": "Spesa Effettiva",
                
                "Categoria": "Ricarica Revolut",
                
                "Sorgente": sorgente_ricarica,
                
                "Valuta Originale": "JPY",
                
                "Importo Originale": round(importo_ricarica, 0),
                
                "Importo EUR": round(importo_eur, 4),
                
                "Importo JPY": round(importo_ricarica, 0),
                
                "Note": nota_ricarica_fin,
            })
            
            save_data(st.session_state["operazioni"])
            
            st.session_state["show_ricarica_form"] = False
            
            st.success(f"✅ Ricarica di ¥ {importo_ricarica:,.0f} registrata!")
            st.rerun()

# ── STORICO RICARICHE ────────────────────────────────────────────────────
if st.session_state["operazioni"]:
    
    df_storico = pd.DataFrame(st.session_state["operazioni"])
    ricariche = df_storico[
        df_storico["Categoria"] == "Ricarica Revolut"
    ]
    
    if not ricariche.empty:
        
        with st.expander("📋 Storico Ricariche", expanded=False):
            
            ricariche_display = ricariche[[
                "Data",
                "Importo Originale",
                "Sorgente",
                "Note"
            ]].copy()
            
            ricariche_display.columns = ["Data", "Importo (¥)", "Sorgente", "Note"]
            ricariche_display["Importo (¥)"] = (
                ricariche_display["Importo (¥)"].astype(int).apply(lambda x: f"¥ {x:,}")
            )
            
            st.dataframe(
                ricariche_display.sort_values("Data", ascending=False),
                use_container_width=True,
                hide_index=True
            )
            
            tot_ricariche = ricariche["Importo JPY"].sum()
            st.caption(f"**Totale ricariche:** ¥ {tot_ricariche:,.0f}")

# ══════════════════════════════════════════════════════════════════[...]
# DASHBOARD
# ══════════════════════════════════════════════════════════════════[...]
st.divider()

st.header("📊 Cruscotto Finanziario")

if not st.session_state["operazioni"]:

    st.info(
        "Nessuna operazione ancora. "
        "Inserisci la prima spesa."
    )

    st.stop()

df = pd.DataFrame(
    st.session_state["operazioni"]
)

if "Data Pagamento" not in df.columns:
    df["Data Pagamento"] = df["Data"]

if "Destinatario" not in df.columns:
    df["Destinatario"] = "Famiglia"

df["Data"] = pd.to_datetime(df["Data"])
df["Data Pagamento"] = pd.to_datetime(df["Data Pagamento"])

# ── DATAFRAME PRINCIPALI ─────────────────────────────────────────────────
spese = df[
    df["Stato"] == "Spesa Effettiva"
]

prenotazioni = df[
    df["Stato"] == "Prenotazione"
]

spese_reali = spese[
    (spese["Categoria"] != "Prelievo ATM") &
    (spese["Categoria"] != "Ricarica Revolut")
]

# ── TOTALI ─────────────────────────────────────────────────────────────[...]
tot_spesa_eur = spese_reali["Importo EUR"].sum()

tot_spesa_jpy = spese_reali["Importo JPY"].sum()

tot_pren_eur = prenotazioni["Importo EUR"].sum()

prelievi_jpy = spese[
    spese["Categoria"] == "Prelievo ATM"
]["Importo JPY"].sum()

contanti_uscite = spese[
    (spese["Sorgente"] == "Wallet Contanti")
    &
    (spese["Categoria"] != "Prelievo ATM")
    &
    (spese["Categoria"] != "Ricarica Revolut")
]["Importo JPY"].sum()

saldo_contanti = (
    prelievi_jpy - contanti_uscite
)

budget_residuo = (
    budget_totale
    - tot_spesa_eur
    - tot_pren_eur
)

# ── KPI (Responsive) ─────────────────────────────────────────────────────
k1, k2 = st.columns(2)

with k1:
    st.metric(
        "Budget Totale",
        f"€ {budget_totale:,.2f}"
    )

with k2:
    st.metric(
        "Speso",
        f"€ {tot_spesa_eur:,.2f}",
        f"¥ {tot_spesa_jpy:,.0f}"
    )

k3, k4 = st.columns(2)

with k3:
    st.metric(
        "Prenotazioni",
        f"€ {tot_pren_eur:,.2f}"
    )

with k4:
    st.metric(
        "💰 Residuo",
        f"€ {budget_residuo:,.2f}",
        delta="✅ Ok" if budget_residuo >= 0 else "⚠️ Sforato",
        delta_color="normal"
        if budget_residuo >= 0
        else "inverse"
    )

# ── BUDGET BAR ───────────────────────────────────────────────────────────
if budget_totale > 0:

    perc_glob = min(
        (tot_spesa_eur + tot_pren_eur)
        / budget_totale,
        1.0
    )

    st.write(
        f"Utilizzo budget globale: "
        f"{perc_glob*100:.1f}%"
    )

    st.progress(perc_glob)

# ── PROIEZIONE ───────────────────────────────────────────────────────────
durata = max(
    (data_fine - data_inizio).days + 1,
    1
)

trascorsi = max(
    min(
        (date.today() - data_inizio).days + 1,
        durata
    ),
    1
) if date.today() >= data_inizio else 1

rimanenti = max(durata - trascorsi, 0)

if tot_spesa_eur > 0:

    media_gg = tot_spesa_eur / trascorsi

    proiezione = media_gg * durata

    budget_gg = budget_residuo / max(rimanenti, 1)

    st.info(
        f"📈 Media giornaliera: "
        f"€ {media_gg:.2f}\n\n"
        f"Proiezione finale: "
        f"€ {proiezione:,.2f}\n\n"
        f"Budget disponibile al giorno: "
        f"€ {budget_gg:.2f}"
    )

st.divider()

# ════════════════════���═════════════════════════════════════════════[...]
# GRAFICI (Responsive)
# ══════════════════════════════════════════════════════════════════[...]
g1, g2 = st.columns(1)  # Stack verticalmente su mobile

with g1:

    st.subheader("🥧 Ripartizione per Categoria")

    if not spese_reali.empty:

        rip = (
            spese_reali
            .groupby("Categoria")["Importo EUR"]
            .sum()
            .reset_index()
        )

        rip = rip.sort_values(
            "Importo EUR",
            ascending=False
        )

        st.bar_chart(
            rip.set_index("Categoria")["Importo EUR"]
        )

with g2:

    st.subheader("📈 Andamento Giornaliero")

    if not spese_reali.empty:

        daily = (
            spese_reali
            .groupby("Data")["Importo EUR"]
            .sum()
            .reset_index()
            .sort_values("Data")
        )

        daily["Cumulato (€)"] = (
            daily["Importo EUR"].cumsum()
        )

        daily = daily.rename(columns={
            "Importo EUR":
            "Spesa del giorno (€)"
        })

        st.line_chart(
            daily.set_index("Data")[
                [
                    "Spesa del giorno (€)",
                    "Cumulato (€)"
                ]
            ]
        )

st.divider()

# ══════════════════════════════════════════════════════════════════[...]
# RIPARTIZIONE SPESE
# ══════════════════════════════════════════════════════════════════[...]
st.subheader("👨‍👩‍👧 Ripartizione Spese")

rip_persona = (
    spese_reali
    .groupby("Destinatario")["Importo EUR"]
    .sum()
    .reset_index()
    .sort_values("Importo EUR", ascending=False)
)

st.dataframe(
    rip_persona,
    use_container_width=True,
    hide_index=True
)

st.bar_chart(
    rip_persona.set_index("Destinatario")["Importo EUR"]
)

st.divider()

# ════════════════════���═════════════════════════════════════════════[...]
# GESTIONE CARTE
# ══════════════════════════════════════════════════════════════════[...]
st.subheader("💳 Gestione Carte e Conti")

cc_jpy_speso = spese[
    (spese["Sorgente"] == "Carta Credito JPY") &
    (spese["Categoria"] != "Ricarica Revolut")
]["Importo JPY"].sum()

cc_jpy_prenotato = prenotazioni[
    prenotazioni["Sorgente"] == "Carta Credito JPY"
]["Importo JPY"].sum()

cd_eur = spese[
    spese["Sorgente"] == "Carta Debito EUR"
]["Importo EUR"].sum()

c1, c2 = st.columns(2)

with c1:
    st.metric(
        "Conto Revolut",
        f"¥ {saldo_revolut:,.0f}",
        f"Speso: ¥ {cc_jpy_speso:,.0f}",
        delta_color="off"
    )

with c2:
    st.metric(
        "Wallet Contanti",
        f"¥ {saldo_contanti:,.0f}",
        f"Speso: ¥ {contanti_uscite:,.0f}",
        delta_color="off"
    )

st.metric(
    "Carta Debito EUR",
    f"€ {cd_eur:,.2f}",
    "Totale Addebitato",
    delta_color="off"
)

if cc_jpy_prenotato > 0:

    st.caption(
        f"📌 Prenotazioni Revolut pendenti: "
        f"¥ {cc_jpy_prenotato:,.0f}"
    )

st.write("---")

st.write(
    "📈 Controllo Plafond Carta Credito EUR"
)

impegni_cc_eur = df[
    df["Sorgente"] == "Carta Credito EUR"
].copy()

if not impegni_cc_eur.empty:

    impegni_cc_eur["Mese"] = (
        impegni_cc_eur["Data Pagamento"]
        .dt.strftime("%Y-%m")
    )

    plafond_mensile = (
        impegni_cc_eur
        .groupby("Mese")["Importo EUR"]
        .sum()
        .reset_index()
    )

    cols_plafond = st.columns(
        min(len(plafond_mensile), 2)  # Max 2 colonne
    )

    for idx, row in plafond_mensile.iterrows():

        mese = row["Mese"]

        impegno_mese = row["Importo EUR"]

        residuo_mese = (
            plafond_cc - impegno_mese
        )

        perc = min(
            impegno_mese / plafond_cc,
            1.0
        ) if plafond_cc > 0 else 1.0

        with cols_plafond[
            idx % len(cols_plafond)
        ]:

            st.write(f"**{mese}**")

            st.write(
                f"€ {impegno_mese:,.2f} "
                f"/ € {plafond_cc:,.0f}"
            )

            st.progress(perc)

            if residuo_mese >= 0:

                st.success(
                    f"Residuo: "
                    f"€ {residuo_mese:,.2f}"
                )

            else:

                st.error(
                    f"Sforato di "
                    f"€ {abs(residuo_mese):,.2f}"
                )

else:

    st.info(
        "Nessun addebito su Carta Credito EUR."
    )

st.divider()

# ══════════════════════════════════════════════════════════════════[...]
# REGISTRO OPERAZIONI (Mobile-optimized)
# ══════════════════════════════════════════════════════════════════[...]
st.subheader("📋 Registro Operazioni")

# ── FILTRI (Mobile-friendly: stack verticale) ────────────────────────────
with st.expander("🔍 Filtri", expanded=True):

    f_stato = st.multiselect(
        "Stato",
        df["Stato"].unique(),
        default=list(df["Stato"].unique())
    )

    f_cat = st.multiselect(
        "Categoria",
        df["Categoria"].unique(),
        default=list(df["Categoria"].unique())
    )

    f_sorg = st.multiselect(
        "Sorgente",
        df["Sorgente"].unique(),
        default=list(df["Sorgente"].unique())
    )

    f_dest = st.multiselect(
        "Destinatario",
        df["Destinatario"].unique(),
        default=list(df["Destinatario"].unique())
    )

# ── FILTRI DATAFRAME ─────────────────────────────────────────────────────
df_vis = df[
    df["Stato"].isin(f_stato)
    &
    df["Categoria"].isin(f_cat)
    &
    df["Sorgente"].isin(f_sorg)
    &
    df["Destinatario"].isin(f_dest)
].copy()

# ── FORMATTAZIONE ────────────────────────────────────────────────────────
df_vis["Data"] = df_vis["Data"].dt.strftime("%Y-%m-%d")

df_vis["Data Pagamento"] = (
    df_vis["Data Pagamento"]
    .dt.strftime("%Y-%m-%d")
)

# ── CHECKBOX ELIMINAZIONE ───────────────────────────────────────────────
df_vis.insert(0, "🗑️", False)

# ── COLONNE MOBILE-FRIENDLY ─────────────────────────────────────────────
colonne_display = [
    "🗑️",
    "_id",
    "Data",
    "Categoria",
    "Importo Originale",
    "Valuta Originale",
    "Importo EUR",
]

# ── DATA EDITOR ──────────────────────────────────────────────────────────
edited = st.data_editor(

    df_vis[colonne_display],

    use_container_width=True,

    hide_index=True,

    column_config={

        "🗑️": st.column_config.CheckboxColumn(
            "🗑️",
            width="small"
        ),

        "_id": st.column_config.TextColumn(
            "ID",
            disabled=True,
            width="small"
        ),

        "Importo Originale":
        st.column_config.NumberColumn(
            "Importo",
            format="%.2f"
        ),

        "Importo EUR":
        st.column_config.NumberColumn(
            "EUR",
            format="€ %.2f"
        ),

        "Data": st.column_config.TextColumn(
            "Data",
            disabled=True
        ),

        "Categoria": st.column_config.TextColumn(
            disabled=True
        ),

        "Valuta Originale":
        st.column_config.TextColumn(
            disabled=True
        ),
    },
)

# ── DETTAGLI NASCOSTI (Espandibile) ──────────────────────────────────────
with st.expander("📄 Dettagli Completi"):
    
    st.dataframe(
        df_vis[[
            "_id",
            "Destinatario",
            "Data",
            "Data Pagamento",
            "Stato",
            "Categoria",
            "Sorgente",
            "Importo Originale",
            "Valuta Originale",
            "Importo EUR",
            "Importo JPY",
            "Note"
        ]],
        use_container_width=True,
        hide_index=True
    )

# ── ELIMINAZIONE ─────────────────────────────────────────────────────────
da_eliminare = edited[
    edited["🗑️"] == True
]["_id"].tolist()

if da_eliminare:

    if st.button(
        f"🗑️ Elimina {len(da_eliminare)} operazione/i",
        type="primary",
        use_container_width=True
    ):

        elimina_per_id(da_eliminare)

        st.success(
            f"Eliminate {len(da_eliminare)} operazioni."
        )

        st.rerun()

else:

    st.caption(
        "☝️ Spunta la colonna 🗑️ per eliminare righe."
    )
