import streamlit as st
import pandas as pd
import sqlite3
import datetime
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO

# --- CONFIGURAZIONE OFFICINA ---
NOME_OFFICINA = "BIKE LAB"
SETTORI = ["COPERTONI", "PASTIGLIE", "ACCESSORI FRENI", "TRASMISSIONE", "CAMERE D'ARIA", "ACCESSORI TELAIO", "ALTRO"]

# --- FUNZIONI DATABASE ---
def get_connection():
    return sqlite3.connect('magazzino_v3.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS prodotti
                 (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
                  marca TEXT, quantita INTEGER, prezzo_acquisto REAL, prezzo_vendita REAL, anno_carico INTEGER)''')
    conn.commit()
    conn.close()

init_db()
st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

# --- NAVIGAZIONE ---
st.sidebar.title(f"🚲 {NOME_OFFICINA}")
menu = st.sidebar.radio("Menu", ["🏠 Dashboard", "📥 Carico Fatture (Gmail/OCR)", "📦 Magazzino & Etichette", "📊 Contabilità"])

# --- 1. DASHBOARD ---
if menu == "🏠 Dashboard":
    st.header(f"Gestione Operativa {NOME_OFFICINA}")
    db_con = get_connection()
    df = pd.read_sql_query("SELECT * FROM prodotti", db_con)
    db_con.close()
    
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Articoli in Stock", len(df))
    with c2: st.metric("Sottoscorta (<3)", len(df[df['quantita'] < 3]) if not df.empty else 0)
    with c3: 
        valore = (df['quantita'] * df['prezzo_acquisto']).sum() if not df.empty else 0
        st.metric("Valore Magazzino", f"€ {valore:,.2f}")

# --- 2. CARICO FATTURE (CON FILTRO ANNO) ---
elif menu == "📥 Car
