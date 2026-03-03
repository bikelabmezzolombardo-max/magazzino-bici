import streamlit as st
import pandas as pd
import sqlite3
import datetime
import os
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
    except Exception:
        return None

# --- LOGICA GMAIL ---
def get_gmail_service():
    if "google_credentials" not in st.secrets:
        st.error("Configura 'google_credentials' nei Secrets di Streamlit!")
        return None
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
        st.metric("Valore Magazzino",
