import streamlit as st
import pandas as pd

# --- IMPOSTAZIONI INIZIALI ---
st.set_page_config(page_title="Travel Budget Tracker", page_icon="🇯🇵")
st.title("Gestione Spese Tokyo 🇯🇵")

# Tasso di cambio fisso (media ultimi 3 mesi)
TASSO_CAMBIO = 165.00  # 1 EUR = 165 JPY (Puoi modificarlo qui)

# Inizializzazione del "Database" temporaneo in memoria
if 'operazioni' not in st.session_state:
    st.session_state['operazioni'] = []

# --- MASCHERA DI INSERIMENTO ---
st.header("Nuova Operazione")
with st.form("form_inserimento"):
    col1, col2 = st.columns(2)
    
    with col1:
        stato = st.selectbox("Stato", ["Spesa Effettiva", "Prenotazione"])
        categoria = st.selectbox("Categoria", ["Trasporti", "Alloggi", "Cibo", "Shopping", "Altro", "Souvenir", "Shinkansen", "Prelievo ATM"])
    
    with col2:
        sorgente = st.selectbox("Sorgente Fondo", ["Carta Credito JPY", "Carta Credito EUR", "Carta Debito EUR", "Wallet Contanti"])
        valuta = st.selectbox("Valuta Inserimento", ["JPY", "EUR"])
        
    importo = st.number_input("Importo", min_value=0.0, step=1.0, format="%.2f")
    
    submit = st.form_submit_button("Registra Operazione")

    if submit and importo > 0:
        # Calcolo conversioni per avere sempre la doppia valuta
        importo_eur = importo if valuta == "EUR" else importo / TASSO_CAMBIO
        importo_jpy = importo if valuta == "JPY" else importo * TASSO_CAMBIO
        
        st.session_state['operazioni'].append({
            "Stato": stato,
            "Categoria": categoria,
            "Sorgente": sorgente,
            "Valuta": valuta,
            "Importo Originale": importo,
            "Importo EUR": importo_eur,
            "Importo JPY": importo_jpy
        })
        st.success("Operazione registrata con successo!")

# --- DASHBOARD E CALCOLI DI BILANCIO ---
st.divider()
st.header("Cruscotto Finanziario")

if st.session_state['operazioni']:
    df = pd.DataFrame(st.session_state['operazioni'])
    
    # 1. Separazione Prenotazioni da Spese Effettive
    prenotazioni = df[df['Stato'] == 'Prenotazione']
    spese = df[df['Stato'] == 'Spesa Effettiva']
    
    tot_prenotazioni_eur = prenotazioni['Importo EUR'].sum()
    
    # 2. Logica Partita Doppia per i Contanti
    # I prelievi aumentano il Wallet Contanti. Le spese in contanti lo erodono.
    prelievi = spese[spese['Categoria'] == 'Prelievo ATM']['Importo JPY'].sum()
    spese_contanti = spese[(spese['Sorgente'] == 'Wallet Contanti') & (spese['Categoria'] != 'Prelievo ATM')]['Importo JPY'].sum()
    saldo_contanti_jpy = prelievi - spese_contanti
    
    # 3. Totale Spesa Effettiva Reale (Escludiamo i prelievi per non sdoppiare i costi)
    spese_reali = spese[spese['Categoria'] != 'Prelievo ATM']
    tot_spesa_eur = spese_reali['Importo EUR'].sum()
    tot_spesa_jpy = spese_reali['Importo JPY'].sum()

    # --- VISUALIZZAZIONE DATI ---
    colA, colB, colC = st.columns(3)
    colA.metric("Spesa Effettiva", f"€ {tot_spesa_eur:,.2f}", f"¥ {tot_spesa_jpy:,.0f}")
    colB.metric("Prenotazioni In Sospeso", f"€ {tot_prenotazioni_eur:,.2f}")
    colC.metric("Saldo Contanti (Wallet)", f"¥ {saldo_contanti_jpy:,.0f}")
    
    st.subheader("Ripartizione per Categoria (Spese Effettive)")
    if not spese_reali.empty:
        ripartizione = spese_reali.groupby('Categoria')['Importo EUR'].sum().reset_index()
        st.dataframe(ripartizione, use_container_width=True)
    
    st.subheader("Storico Operazioni")
    st.dataframe(df[['Stato', 'Categoria', 'Sorgente', 'Importo Originale', 'Valuta']], use_container_width=True)

else:
    st.info("Nessuna operazione registrata. Inizia ad inserire i dati!")
