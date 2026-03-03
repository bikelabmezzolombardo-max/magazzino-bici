import streamlit as st
import pandas as pd
import sqlite3
import datetime
import os
import base64
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- CONFIGURAZIONE ---
NOME_OFFICINA = "BIKE LAB MEZZOLOMBARDO"
SETTORI = ["COPERTONI", "PASTIGLIE", "ACCESSORI FRENI", "TRASMISSIONE", "CAMERE D'ARIA", "ACCESSORI TELAIO", "ALTRO"]
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# --- FUNZIONI DATABASE ---
def get_connection():
    return sqlite3.connect('magazzino_v3.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS prodotti
                 (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
                  marca TEXT, quantita INTEGER, prezzo_acquisto REAL, 
                  prezzo_vendita REAL, anno_emissione INTEGER)''')
    conn.commit()
    conn.close()

# --- FUNZIONE GENERAZIONE ETICHETTA ---
def genera_etichetta(barcode_val):
    try:
        rv = BytesIO()
        Code128(str(barcode_val), writer=ImageWriter()).write(rv)
        return rv
    except:
        return None

# --- LOGICA GMAIL (Utilizza Secrets di Streamlit) ---
def get_gmail_service():
    if "google_credentials" not in st.secrets:
        st.error("Configura 'google_credentials' nei Secrets di Streamlit!")
        return None
    
    # Costruisci credenziali dai secrets (formato JSON/Dict)
    creds_dict = dict(st.secrets["google_credentials"])
    creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
    return build('gmail', 'v1', credentials=creds)

# --- INIZIALIZZAZIONE ---
init_db()
st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

# --- SIDEBAR ---
st.sidebar.title(f"🚲 {NOME_OFFICINA}")
menu = st.sidebar.radio("Menu principale", ["🏠 Dashboard", "📥 Carico Fatture & DDT", "📦 Magazzino & Etichette", "📊 Contabilità"])

# --- 1. DASHBOARD ---
if menu == "🏠 Dashboard":
    st.header(f"Gestione Operativa {NOME_OFFICINA}")
    db_con = get_connection()
    df_all = pd.read_sql_query("SELECT * FROM prodotti", db_con)
    db_con.close()
    
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Articoli Totali", len(df_all))
    with col2: st.metric("Sottoscorta (<3)", len(df_all[df_all['quantita'] < 3]) if not df_all.empty else 0)
    with col3: 
        val_inv = (df_all['quantita'] * df_all['prezzo_acquisto']).sum() if not df_all.empty else 0
        st.metric("Valore Magazzino", f"€ {val_inv:,.2f}")

    st.divider()
    st.subheader("📁 Visualizzazione Rapida per Categoria")
    cols = st.columns(4)
    for i, settore in enumerate(SETTORI):
        if cols[i % 4].button(settore, key=f"btn_cat_{settore}", use_container_width=True):
            st.session_state['cat_selezionata'] = settore

    if 'cat_selezionata' in st.session_state:
        sel = st.session_state['cat_selezionata']
        st.markdown(f"### 📦 Articoli in: **{sel}**")
        df_cat = df_all[df_all['categoria'] == sel]
        if not df_cat.empty:
            st.dataframe(df_cat[['componente', 'marca', 'quantita', 'prezzo_vendita']], use_container_width=True, hide_index=True)
        else:
            st.info(f"Nessun articolo trovato in {sel}.")

# --- 2. CARICO FATTURE, DDT E BOLLE ---
elif menu == "📥 Carico Fatture & DDT":
    st.header("Ricerca Documenti da Gmail")
    anno_sel = st.number_input("Anno", 2024, 2026, 2025)
    
    t1, t2 = st.tabs(["📧 Ricerca Automatica", "📷 Caricamento Manuale"])
    
    with t1:
        if st.button("Avvia Scansione (RMS, Fatture, DDT)"):
            service = get_gmail_service()
            if service:
                # Query potenziata per includere RMS e termini internazionali come Invoice
                query = f'after:{anno_sel}/01/01 "RMS" OR "Fattura" OR "DDT" OR "Invoice" OR "Bolla" has:attachment'
                results = service.users().messages().list(userId='me', q=query).execute()
                messages = results.get('messages', [])
                
                if not messages:
                    st.warning("Nessun documento trovato. Controlla i filtri.")
                else:
                    st.success(f"Trovate {len(messages)} email con possibili documenti.")
                    for msg in messages:
                        m_data = service.users().messages().get(userId='me', id=msg['id']).execute()
                        subj = next(h['value'] for h in m_data['payload']['headers'] if h['name'] == 'Subject')
                        st.write(f"📄 **{subj}**")
                        if st.button("Analizza Allegato", key=msg['id']):
                            st.info("Estrazione dati OCR in corso...")

    with t2:
        up = st.file_uploader("Carica PDF/Immagine", type=['pdf', 'jpg', 'png'])
        if up: st.success("Documento caricato correttamente.")

# --- 3. MAGAZZINO & ETICHETTE ---
elif menu == "📦 Magazzino & Etichette":
