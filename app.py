import streamlit as st
import pandas as pd
import sqlite3
from PIL import Image
import pytesseract
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO

# --- CONFIGURAZIONE OFFICINA ---
NOME_OFFICINA = "BIKE LAB" # Personalizza il nome qui
SETTORI = ["⚙️ TRASMISSIONE", "🛑 FRENI", "🚲 RUOTE/COPERTONI", "🛠️ TELAIO", "🔋 E-BIKE", "🧴 CONSUMABILI"]

# --- FUNZIONE CONNESSIONE DATABASE ---
def get_connection():
    conn = sqlite3.connect('magazzino_v3.db', check_same_thread=False)
    return conn

# Inizializzazione Database
def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS prodotti
                 (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
                  marca TEXT, quantita INTEGER, prezzo_acquisto REAL, prezzo_vendita REAL)''')
    conn.commit()
    conn.close()

init_db()

st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

# --- FUNZIONE GENERAZIONE ETICHETTA ---
def genera_etichetta(barcode_val, nome_prod, prezzo):
    try:
        rv = BytesIO()
        Code128(str(barcode_val), writer=ImageWriter()).write(rv)
        return rv
    except Exception as e:
        st.error(f"Errore generazione barcode: {e}")
        return None

# --- SIDEBAR NAVIGAZIONE ---
st.sidebar.title(f"🚲 {NOME_OFFICINA}")
menu = st.sidebar.radio("Menu principale", ["🏠 Dashboard", "📥 Carico Fatture (Gmail/OCR)", "📦 Magazzino & Etichette", "📊 Contabilità"])

# --- SEZIONE 1: DASHBOARD ---
if menu == "🏠 Dashboard":
    st.header(f"Benvenuto in {NOME_OFFICINA}")
    
    db_con = get_connection()
    df = pd.read_sql_query("SELECT * FROM prodotti", db_con)
    db_con.close()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Articoli in Stock", len(df))
    with col2:
        sottoscorta = len(df[df['quantita'] < 3]) if not df.empty else 0
        st.metric("Allerta Sottoscorta", sottoscorta)
    with col3:
        valore = (df['quantita'] * df['prezzo_acquisto']).sum() if not df.empty else 0
        st.metric("Valore Magazzino", f"€ {valore:,.2f}")

    st.divider()
    
    st.subheader("📸 Scarico Rapido (Barcode)")
    barcode_scan = st.text_input("Scansiona pezzo per scaricarlo (-1)", key="main_scan")
    if barcode_scan:
        db_con = get_connection()
        c = db_con.cursor()
        c.execute("SELECT componente, quantita FROM prodotti WHERE barcode=?", (barcode_scan,))
        res = c.fetchone()
        if res:
            st.warning(f"Prodotto: {res[0]} | Disponibilità: {res[1]}")
            if st.button("Conferma SCARICO"):
                c.execute("UPDATE prodotti SET quantita = quantita - 1 WHERE barcode=?", (barcode_scan,))
                db_con.commit()
                st.success("Scarico effettuato!")
                st.rerun()
        else:
            st.error("Prodotto non trovato nel database!")
        db_con.close()

# --- SEZIONE 2: CARICO FATTURE ---
elif menu == "📥 Carico Fatture (Gmail/OCR)":
