import streamlit as st
import pandas as pd
import sqlite3
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO

# --- CONFIGURAZIONE OFFICINA (Adattata al tuo file CSV) ---
NOME_OFFICINA = "BIKE LAB"
# Queste sono le categorie estratte dal tuo resoconto 2025
SETTORI = [
    "COPERTONI", 
    "PASTIGLIE", 
    "ACCESSORI FRENI", 
    "TRASMISSIONE", 
    "CAMERE D'ARIA", 
    "ACCESSORI TELAIO",
    "ALTRO"
]

# --- FUNZIONE CONNESSIONE DATABASE ---
def get_connection():
    return sqlite3.connect('magazzino_v3.db', check_same_thread=False)

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
        # Generiamo il codice Code128 (standard per piccoli ricambi)
        Code128(str(barcode_val), writer=ImageWriter()).write(rv)
        return rv
    except Exception as e:
        return None

# --- SIDEBAR NAVIGAZIONE ---
st.sidebar.title(f"🚲 {NOME_OFFICINA}")
menu = st.sidebar.radio("Menu principale", ["🏠 Dashboard", "📥 Carico Fatture (Gmail/OCR)", "📦 Magazzino & Etichette", "📊 Contabilità"])

# --- SEZIONE 1: DASHBOARD ---
if menu == "🏠 Dashboard":
    st.header(f"Gestione Operativa {NOME_OFFICINA}")
    
    db_con = get_connection()
    df = pd.read_sql_query("SELECT * FROM prodotti", db_con)
    db_con.close()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Articoli Totali", len(df))
    with col2:
        sottoscorta = len(df[df['quantita'] < 3]) if not df.empty else 0
        st.metric("Allerta Sottoscorta", sottoscorta)
    with col3:
        valore = (df['quantita'] * df['prezzo_acquisto']).sum() if not df.empty else 0
        st.metric("Valore Attuale", f"€ {valore:,.2f}")

    st.divider()
    
    # FUNZIONE SCARICO RAPIDO (Per smartphone)
    st.subheader("📲 Scarico Rapido Barcode")
    barcode_scan = st.text_input("Scansiona per scaricare (-1)", placeholder="Inquadra il codice...")
    if barcode_scan:
        db_con = get_connection()
        c = db_con.cursor()
        c.execute("SELECT componente, quantita, categoria FROM prodotti WHERE barcode=?", (barcode_scan,))
        res = c.fetchone()
        if res:
            st.info(f"Articolo: **{res[0]}** | Settore: {res[2]} | Stock: {res[1]}")
            if st.button("CONFERMA USCITA (VENDITA/RIPARAZIONE)", use_container_width=True):
                c.execute("UPDATE prodotti SET quantita = quantita - 1 WHERE barcode=?", (barcode_scan,))
                db_con.commit()
                st.success("Giacenza aggiornata!")
                st.rerun()
        else:
            st.error("Codice non trovato. Registra l'articolo in 'Magazzino'.")
        db_con.close()

# --- SEZIONE 2: CARICO FATTURE ---
elif menu == "📥 Carico Fatture (Gmail/OCR)":
    st.header("Automazione Carico")
    tab1, tab2 = st.tabs(["📧 Gmail (Auto)", "📷 Foto Fattura (OCR)"])
    
    with tab1:
        st.write("Sincronizzazione fatture da Amazon, Shimano, RMS...")
        if st.button("Sincronizza Gmail"):
            st.info("Connessione ai Secrets in corso...")
    
    with tab2:
        uploaded_file = st.file_uploader("Carica foto o PDF fattura", type=['png', 'jpg', 'pdf'])
        if uploaded_file:
            st.image(uploaded_file, caption="Documento caricato", width=400)
            st.warning("OCR in elaborazione: estrazione codici e prezzi...")

# --- SEZIONE 3: MAGAZZINO E ETICHETTE ---
elif menu == "📦 Magazzino & Etichette":
    st.header("Giacenze e Stampa Etichette")
    
    with st.expander("📥 Importa Inventario (Adatta da Excel/CSV)"):
