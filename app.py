import streamlit as st
import pandas as pd
from datetime import datetime

# --- IMPOSTAZIONI INIZIALI ---
st.set_page_config(page_title="Travel Budget Tracker", page_icon="🇯🇵", layout="wide")
st.title("Gestione Spese Tokyo 🇯🇵")

# Inizializzazione del "Database" temporaneo
if 'operazioni' not in st.session_state:
    st.session_state['operazioni'] = []

# --- CONFIGURAZIONI AVANZATE (Backup, Cambio e Budget) ---
with st.expander("⚙️ Configurazione, Budget e Backup"):
    col_conf1, col_conf2, col_conf3 = st.columns(3)
    
    with col_conf1:
        # Tasso di cambio modificabile dall'interfaccia
        tasso_cambio = st.number_input("Tasso di Cambio (1 EUR = X JPY)", min_value=1.0, value=165.0, step=0.5)
    
    with col_conf2:
        # Impostazione del Budget massimo per il viaggio
        budget_target_eur = st.number_input("Budget Massimo Viaggio (€)", min_value=0.0, value=1500.0, step=100.0)
        
    with col_conf3:
        st.write("---") # Spazio visivo
        
    st.divider()
    st.write("📂 **Ripristino e Salvataggio File**")
    # Caricamento backup
    file_caricato = st.file_uploader("Ripristina da un backup precedente", type="csv")
    if file_caricato is not None:
        try:
            df_importato = pd.read_csv(file_caricato)
            st.session_state['operazioni'] = df_importato.to_dict('records')
            st.success("Dati ripristinati correttamente!")
        except Exception as e:
            st.error("Errore nel caricamento del file.")

    # Scaricamento backup
    if st.session_state['operazioni']:
        df_export = pd.DataFrame(st.session_state['operazioni'])
        csv = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Scarica Backup Dati (CSV)",
            data=csv,
            file_name="spese_tokyo_backup.csv",
            mime="text/csv",
        )

# --- MASCHERA DI INSERIMENTO ---
st.header("Nuova Operazione")
with st.form("form_inserimento", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        data_op = st.date_input("Data Spesa", datetime.now())
        stato = st.selectbox("Stato", ["Spesa Effettiva", "Prenotazione"])
        categoria = st.selectbox("Categoria", ["Trasporti", "Alloggi", "Cibo", "Shopping", "Altro", "Prelievo ATM"])
    
    with col2:
        sorgente = st.selectbox("Sorgente Fondo", ["Carta Credito JPY", "Carta Credito EUR", "Carta Debito EUR", "Wallet Contanti"])
        valuta = st.selectbox("Valuta Inserimento", ["JPY", "EUR"])
        importo = st.number_input("Importo", min_value=0.0, step=1.0, format="%.2f")
        
    with col3:
        note = st.text_area("Note / Descrizione", placeholder="Es: Cena sushi a Shibuya, Souvenir, Biglietto metro...")
    
    submit = st.form_submit_button("🚀 Registra Operazione")

    if submit and importo > 0:
        importo_eur = importo if valuta == "EUR" else importo / tasso_cambio
        importo_jpy = importo if valuta == "JPY" else importo * tasso_cambio
        
        st.session_state['operazioni'].append({
            "Data": data_op.strftime("%Y-%m-%d"),
            "Stato": stato,
            "Categoria": categoria,
            "Sorgente": sorgente,
            "Valuta Originale": valuta,
            "Importo Originale": importo,
            "Importo EUR": importo_eur,
            "Importo JPY": importo_jpy,
            "Note": note if note else "-"
        })
        st.success("Operazione registrata!")

# --- STORNO ERRORI ---
if st.session_state['operazioni']:
    if st.button("⚠️ Annulla Ultima Operazione"):
        st.session_state['operazioni'].pop()
        st.success("Ultima operazione rimossa!")
        st.rerun()

# --- DASHBOARD E CALCOLI DI BILANCIO ---
st.divider()
st.header("Cruscotto Finanziario")

if st.session_state['operazioni']:
    df = pd.DataFrame(st.session_state['operazioni'])
    
    prenotazioni = df[df['Stato'] == 'Prenotazione']
    spese = df[df['Stato'] == 'Spesa Effettiva']
    
    # 1. Calcolo Totali Principali
    tot_prenotazioni_eur = prenotazioni['Importo EUR'].sum()
    
    prelievi_jpy = spese[spese['Categoria'] == 'Prelievo ATM']['Importo JPY'].sum()
    spese_contanti_jpy = spese[(spese['Sorgente'] == 'Wallet Contanti') & (spese['Categoria'] != 'Prelievo ATM')]['Importo JPY'].sum()
    saldo_contanti_jpy = prelievi_jpy - spese_contanti_jpy
    
    spese_reali = spese[spese['Categoria'] != 'Prelievo ATM']
    tot_spesa_eur = spese_reali['Importo EUR'].sum()
    tot_spesa_jpy = spese_reali['Importo JPY'].sum()

    # 2. Visualizzazione KPI Principali
    colA, colB, colC = st.columns(3)
    colA.metric("Spesa Effettiva Reale", f"€ {tot_spesa_eur:,.2f}", f"¥ {tot_spesa_jpy:,.0f}")
    colB.metric("Prenotazioni Attive", f"€ {tot_prenotazioni_eur:,.2f}")
    colC.metric("Saldo Contanti Disponibile", f"¥ {saldo_contanti_jpy:,.0f}")
    
    # 3. BARRA DI AVANZAMENTO BUDGET (Visuale)
    if budget_target_eur > 0:
        percentuale_budget = min(float(tot_spesa_eur / budget_target_eur), 1.0)
        st.write(f"📊 **Utilizzo del Budget Globale:** {percentuale_budget*100:.1f}% di € {budget_target_eur:,.2f}")
        st.progress(percentuale_budget)
        if tot_spesa_eur > budget_target_eur:
            st.warning("⚠️ Attenzione: Hai superato il budget massimo prefissato!")

    # 4. ESPOSIZIONE METODI DI PAGAMENTO (Stato Patrimoniale)
    st.subheader("💳 Esposizione Attuale per Carta (Solo spese effettive)")
    col_c1, col_c2, col_c3 = st.columns(3)
    
    cc_jpy = spese[spese['Sorgente'] == 'Carta Credito JPY']['Importo JPY'].sum()
    cc_eur = spese[spese['Sorgente'] == 'Carta Credito EUR']['Importo EUR'].sum()
    cd_eur = spese[spese['Sorgente'] == 'Carta Debito EUR']['Importo EUR'].sum()
    
    col_c1.metric("Carta Credito JPY", f"¥ {cc_jpy:,.0f}")
    col_c2.metric("Carta Credito EUR", f"€ {cc_eur:,.2f}")
    col_c3.metric("Carta Debito EUR", f"€ {cd_eur:,.2f}")

    # 5. RIPARTIZIONE CATEGORIE E TABELLA STORICO
    col_util1, col_util2 = st.columns([1, 2])
    
    with col_util1:
        st.subheader("Ripartizione Categorie")
        if not spese_reali.empty:
            ripartizione = spese_reali.groupby('Categoria')['Importo EUR'].sum().reset_index()
            st.dataframe(ripartizione, use_container_width=True)
            st.bar_chart(ripartizione.set_index('Categoria')['Importo EUR'])
            
    with col_util2:
        st.subheader("Storico Registro Operazioni")
        st.dataframe(df[['Data', 'Stato', 'Categoria', 'Sorgente', 'Importo Originale', 'Valuta Originale', 'Note']], use_container_width=True)

else:
    st.info("Nessuna operazione registrata. Configura i tuoi parametri e inizia ad inserire i dati!")
