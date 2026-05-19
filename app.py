import streamlit as st
import pandas as pd

# --- IMPOSTAZIONI INIZIALI ---
st.set_page_config(page_title="Travel Budget Tracker", page_icon="🇯🇵")
st.title("Gestione Spese Tokyo 🇯🇵")

# SOGLIA DI BUDGET (Modifica questa cifra in base alle tue esigenze)
BUDGET_TOTALE_EUR = 1500.00 

# Tasso di cambio fisso
TASSO_CAMBIO = 165.00

# Inizializzazione del "Database" temporaneo
if 'operazioni' not in st.session_state:
    st.session_state['operazioni'] = []

# --- GESTIONE DATI: BACKUP E RIPRISTINO ---
with st.expander("💾 Salvataggio e Ripristino Dati (Backup)"):
    st.write("Fai un backup a fine giornata per non perdere i dati se chiudi il browser.")
    
    file_caricato = st.file_uploader("Ripristina da un backup precedente", type="csv")
    if file_caricato is not None:
        try:
            df_importato = pd.read_csv(file_caricato)
            st.session_state['operazioni'] = df_importato.to_dict('records')
            st.success("Dati caricati con successo!")
        except Exception:
            st.error("Errore nel caricamento del file.")

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
with st.form("form_inserimento"):
    col1, col2 = st.columns(2)
    
    with col1:
        stato = st.selectbox("Stato", ["Spesa Effettiva", "Prenotazione"])
        categoria = st.selectbox("Categoria", ["Trasporti", "Alloggi", "Cibo", "Shopping", "Altro", "Prelievo ATM"])
    
    with col2:
        sorgente = st.selectbox("Sorgente Fondo", ["Carta Credito JPY", "Carta Credito EUR", "Carta Debito EUR", "Wallet Contanti"])
        valuta = st.selectbox("Valuta Inserimento", ["JPY", "EUR"])
        
    importo = st.number_input("Importo", min_value=0.0, step=1.0, format="%.2f")
    
    submit = st.form_submit_button("Registra Operazione")

    if submit and importo > 0:
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
    
    tot_prenotazioni_eur = prenotazioni['Importo EUR'].sum()
    
    prelievi = spese[spese['Categoria'] == 'Prelievo ATM']['Importo JPY'].sum()
    spese_contanti = spese[(spese['Sorgente'] == 'Wallet Contanti') & (spese['Categoria'] != 'Prelievo ATM')]['Importo JPY'].sum()
    saldo_contanti_jpy = prelievi - spese_contanti
    
    spese_reali = spese[spese['Categoria'] != 'Prelievo ATM']
    tot_spesa_eur = spese_reali['Importo EUR'].sum()
    tot_spesa_jpy = spese_reali['Importo JPY'].sum()

    # --- INDICATORE VISIVO BUDGET ATTUALE VS TARGET ---
    # Unisce le spese reali e le prenotazioni per darti l'impegno finanziario totale impegnato
    totale_impegnato_eur = tot_spesa_eur + tot_prenotazioni_eur
    percentuale_budget = min(float(totale_impegnato_eur / BUDGET_TOTALE_EUR), 1.0)
    
    st.write(f"📊 **Monitoraggio Budget Globale:** {percentuale_budget*100:.1f}% utilizzato (€ {totale_impegnato_eur:,.2f} su € {BUDGET_TOTALE_EUR:,.2f})")
    st.progress(percentuale_budget)
    if totale_impegnato_eur > BUDGET_TOTALE_EUR:
        st.error(f"⚠️ Attenzione: Hai superato la soglia budget prefissata di € {BUDGET_TOTALE_EUR:,.2f}!")
    st.write("") # Spazio

    # TOTALI METRICI
    colA, colB, colC = st.columns(3)
    colA.metric("Spesa Effettiva", f"€ {tot_spesa_eur:,.2f}", f"¥ {tot_spesa_jpy:,.0f}")
    colB.metric("Prenotazioni", f"€ {tot_prenotazioni_eur:,.2f}")
    colC.metric("Saldo Contanti", f"¥ {saldo_contanti_jpy:,.0f}")
    
    st.subheader("Ripartizione per Categoria")
    if not spese_reali.empty:
        ripartizione = spese_reali.groupby('Categoria')['Importo EUR'].sum().reset_index()
        st.dataframe(ripartizione, use_container_width=True)
    
    st.subheader("Storico Operazioni")
    st.dataframe(df[['Stato', 'Categoria', 'Sorgente', 'Importo Originale', 'Valuta']], use_container_width=True)

else:
    st.info("Nessuna operazione. Inizia a inserire le tue spese!")
        st.dataframe(df[['Data', 'Stato', 'Categoria', 'Sorgente', 'Importo Originale', 'Valuta Originale', 'Note']], use_container_width=True)

else:
    st.info("Nessuna operazione registrata. Configura i tuoi parametri e inizia ad inserire i dati!")
