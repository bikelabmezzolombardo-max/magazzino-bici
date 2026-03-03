import streamlit as st
import pandas as pd
import sqlite3
from PIL import Image
import pytesseract
from barcode import EAN13
from barcode.writer import ImageWriter
from io import BytesIO

# --- CONFIGURAZIONE OFFICINA ---
NOME_OFFICINA = "LA TUA OFFICINA BICI" # Cambialo con il tuo nome reale
SETTORI = ["⚙️ TRASMISSIONE", "🛑 FRENI", "🚲 RUOTE/COPERTONI", "🛠️ TELAIO", "🔋 E-BIKE", "🧴 CONSUMABILI"]

# --- DATABASE ---
conn = sqlite3.connect('magazzino_v3.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS prodotti
             (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
              marca TEXT, quantita INTEGER, prezzo_acquisto REAL, prezzo_vendita REAL)''')
conn.commit()

st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

# --- FUNZIONE GENERAZIONE ETICHETTA ---
def genera_etichetta(barcode_val, nome_prod, prezzo):
    try:
        rv = BytesIO()
        # Se il barcode è corto o custom, usiamo Code128 invece di EAN13
        from barcode import Code128
        Code128(barcode_val, writer=ImageWriter()).write(rv)
        return rv
    except:
        return None

# --- SIDEBAR NAVIGAZIONE ---
st.sidebar.title(f"🚲 {NOME_OFFICINA}")
menu = st.sidebar.radio("Menu principale", ["🏠 Dashboard", "📥 Carico Fatture (Gmail/OCR)", "📦 Magazzino & Etichette", "📊 Contabilità"])

# --- SEZIONE 1: DASHBOARD ---
if menu == "🏠 Dashboard":
    st.header(f"Benvenuto in {NOME_OFFICINA}")
    
    # Metriche veloci
    df = pd.read_sql_query("SELECT * FROM prodotti", conn)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Articoli in Stock", len(df))
    with col2:
        sottoscorta = len(df[df['quantita'] < 3])
        st.metric("Allerta Sottoscorta", sottoscorta, delta_color="inverse")
    with col3:
        valore = (df['quantita'] * df['prezzo_acquisto']).sum()
        st.metric("Valore Magazzino", f"€ {valore:,.2f}")

    st.subheader("📸 Scarico Rapido (Barcode)")
    barcode_scan = st.text_input("Scansiona pezzo per scaricarlo (-1)")
    if barcode_scan:
        c.execute("SELECT componente, quantita FROM prodotti WHERE barcode=?", (barcode_scan,))
        res = c.fetchone()
        if res:
            if st.button(f"Conferma scarico: {res[0]} (Rimanenti: {res[1]})"):
                c.execute("UPDATE prodotti SET quantita = quantita - 1 WHERE barcode=?", (barcode_scan,))
                conn.commit()
                st.success("Scarico effettuato!")
        else:
            st.error("Prodotto non trovato!")

# --- SEZIONE 2: CARICO FATTURE ---
elif menu == "📥 Carico Fatture (Gmail/OCR)":
    st.header("Caricamento Automatico")
    tab1, tab2 = st.tabs(["📧 Sincronizza Gmail", "📷 Carica Foto/PDF"])
    
    with tab1:
        if st.button("Controlla nuove fatture su Gmail"):
            st.info("Connessione in corso... (Richiede credentials.json)")
            # Qui domani inseriremo il link definitivo con il file JSON che hai scaricato
            
    with tab2:
        uploaded_file = st.file_uploader("Trascina qui la fattura", type=['png', 'jpg', 'pdf'])
        if uploaded_file:
            st.warning("Esecuzione OCR in corso... Conferma i dati estratti:")
            # Simulazione dati estratti da OCR
            temp_data = {"Barcode": ["800123456789", ""], "Nome": ["Camera d'aria 29", "Grasso Litio"], "Prezzo": [5.50, 8.00]}
            st.data_editor(pd.DataFrame(temp_data))
            if st.button("Conferma e Carica nel Magazzino"):
                st.success("Dati salvati!")

# --- SEZIONE 3: MAGAZZINO E ETICHETTE ---
elif menu == "📦 Magazzino & Etichette":
    st.header("Gestione Scorte e Stampa")
    sel_settore = st.selectbox("Filtra per Settore", SETTORI)
    
    df_m = pd.read_sql_query("SELECT * FROM prodotti WHERE categoria=?", (sel_settore,), conn)
    
    if not df_m.empty:
        for idx, row in df_m.iterrows():
            with st.expander(f"{row['componente']} ({row['marca']}) - Qty: {row['quantita']}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Barcode:** {row['barcode']}")
                    st.write(f"**Prezzo Vendita:** € {row['prezzo_vendita']:.2f}")
                with c2:
                    if st.button(f"Genera Etichetta per {row['componente']}", key=row['barcode']):
                        img_label = genera_etichetta(row['barcode'], row['componente'], row['prezzo_vendita'])
                        if img_label:
                            st.image(img_label, caption=f"{NOME_OFFICINA} - {row['prezzo_vendita']}€")
                            st.download_button("Scarica Etichetta per Stampa", img_label, f"etichetta_{row['barcode']}.png")
    else:
        st.info("Nessun prodotto in questo settore. Aggiungine uno!")
