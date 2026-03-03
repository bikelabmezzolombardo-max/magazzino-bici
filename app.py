import streamlit as st
import pandas as pd
import sqlite3
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO

# --- CONFIGURAZIONE OFFICINA ---
NOME_OFFICINA = "BIKE LAB"
SETTORI = ["⚙️ TRASMISSIONE", "🛑 FRENI", "🚲 RUOTE/COPERTONI", "🛠️ TELAIO", "🔋 E-BIKE", "🧴 CONSUMABILI"]

# --- FUNZIONE CONNESSIONE DATABASE ---
def get_connection():
    return sqlite3.connect('magazzino_v3.db', check_same_thread=False)

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
    st.header("Caricamento Automatico")
    st.info("Questa sezione permette di importare dati da Gmail o scansionare PDF.")
    
    tab1, tab2 = st.tabs(["📧 Gmail", "📷 OCR Foto"])
    with tab1:
        st.write("Sincronizzazione con la tua mail in corso...")
        if st.button("Avvia ricerca fatture"):
            st.warning("Configurazione Gmail Secrets richiesta per questa operazione.")
    with tab2:
        st.write("Carica una foto per estrarre i dati.")
        st.file_uploader("Scegli file", type=['png', 'jpg', 'pdf'])

# --- SEZIONE 3: MAGAZZINO E ETICHETTE ---
elif menu == "📦 Magazzino & Etichette":
    st.header("Gestione Scorte")
    
    with st.expander("📥 Importa Inventario 2025 (CSV)"):
        uploaded_csv = st.file_uploader("Carica file .csv", type="csv")
        if uploaded_csv:
            df_import = pd.read_csv(uploaded_csv)
            st.dataframe(df_import.head())
            if st.button("ESEGUI IMPORTAZIONE"):
                db_con = get_connection()
                c = db_con.cursor()
                for _, row in df_import.iterrows():
                    c.execute('''INSERT OR REPLACE INTO prodotti VALUES (?,?,?,?,?,?,?)''', 
                              (str(row.get('Barcode', '')), row.get('Categoria', 'Altro'), 
                               row.get('Componente', ''), row.get('Marca', ''), 
                               int(row.get('Quantita', 0)), float(row.get('Prezzo_Acquisto', 0.0)), 
                               float(row.get('Prezzo_Vendita', 0.0))))
                db_con.commit()
                db_con.close()
                st.success("Importazione completata!")

    sel_settore = st.selectbox("Seleziona Settore", SETTORI)
    db_con = get_connection()
    df_m = pd.read_sql_query("SELECT * FROM prodotti WHERE categoria=?", db_con, params=(sel_settore,))
    db_con.close()
    
    if not df_m.empty:
        for idx, row in df_m.iterrows():
            with st.expander(f"{row['componente']} - Qty: {row['quantita']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"Prezzo: €{row['prezzo_vendita']}")
                with col2:
                    if st.button("Etichetta", key=f"btn_{row['barcode']}"):
                        label = genera_etichetta(row['barcode'], row['componente'], row['prezzo_vendita'])
                        if label: st.image(label)

# --- SEZIONE 4: CONTABILITÀ ---
elif menu == "📊 Contabilità":
    st.header("Analisi Economica")
    st.write("Statistiche del magazzino in tempo reale.")
    db_con = get_connection()
    df_c = pd.read_sql_query("SELECT * FROM prodotti", db_con)
    db_con.close()
    if not df_c.empty:
        st.metric("Valore Totale", f"€ {(df_c['quantita'] * df_c['prezzo_acquisto']).sum():,.2f}")
