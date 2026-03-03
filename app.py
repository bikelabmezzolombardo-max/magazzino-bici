import streamlit as st
import pandas as pd
import sqlite3
import os
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
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

# --- AUTENTICAZIONE GMAIL ---
def get_gmail_service():
    creds = None
    # Il file token.json memorizza l'accesso dell'utente
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)

# --- AVVIO APP ---
init_db()
st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

# --- SIDEBAR ---
st.sidebar.title(f"🚲 {NOME_OFFICINA}")
menu = st.sidebar.radio("Menu", ["🏠 Dashboard", "📥 Carico Merci", "📦 Magazzino", "📊 Contabilità"])

# --- DASHBOARD ---
if menu == "🏠 Dashboard":
    st.header(f"Dashboard - {NOME_OFFICINA}")
    st.info("Benvenuto! Usa il menu a sinistra per gestire il magazzino.")

# --- CARICO MERCI (Integrazione Gmail) ---
elif menu == "📥 Carico Merci":
    st.header("Carico Merci da Gmail")
    
    anno_ricerca = st.selectbox("Seleziona Anno", [2024, 2025, 2026], index=1)
    
    if st.button("🔍 Cerca Fatture (inclusa RMS)"):
        try:
            service = get_gmail_service()
            # Query ottimizzata: cerca RMS o Fattura o Invoice con allegati
            query = f'after:{anno_ricerca}/01/01 "RMS" OR "Fattura" OR "Invoice" has:attachment'
            results = service.users().messages().list(userId='me', q=query).execute()
            messages = results.get('messages', [])

            if not messages:
                st.warning("Nessuna fattura trovata con i criteri inseriti.")
            else:
                st.success(f"Trovate {len(messages)} email potenziali.")
                for msg in messages:
                    m_data = service.users().messages().get(userId='me', id=msg['id']).execute()
                    subject = next(h['value'] for h in m_data['payload']['headers'] if h['name'] == 'Subject')
                    date = next(h['value'] for h in m_data['payload']['headers'] if h['name'] == 'Date')
                    st.write(f"**Soggetto:** {subject} | **Data:** {date}")
                    
                    # Bottone simulato per il "carico rapido"
                    if st.button(f"Carica dati da: {subject[:20]}...", key=msg['id']):
                        st.info("Funzione di estrazione dati automatica in fase di sviluppo.")

        except Exception as e:
            st.error(f"Errore di connessione: {e}")

    st.divider()
    st.subheader("Inserimento Manuale")
    with st.form("nuovo_prodotto"):
        c1, c2 = st.columns(2)
        with c1:
            bc = st.text_input("Barcode")
            cat = st.selectbox("Categoria", SETTORI)
            comp = st.text_input("Nome Componente")
        with c2:
            qta = st.number_input("Quantità", min_value=1)
            pr_v = st.number_input("Prezzo Vendita", min_value=0.0)
        
        if st.form_submit_button("Salva nel DB"):
            conn = get_connection()
            conn.execute("INSERT INTO prodotti (barcode, categoria, componente, quantita, prezzo_vendita) VALUES (?,?,?,?,?)",
                         (bc, cat, comp, qta, pr_v))
            conn.commit()
            conn.close()
            st.success("Prodotto salvato!")

# --- MAGAZZINO ---
elif menu == "📦 Magazzino":
    st.header("Inventario")
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM prodotti", conn)
    conn.close()
    st.dataframe(df, use_container_width=True)
