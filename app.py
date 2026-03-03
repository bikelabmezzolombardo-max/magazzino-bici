import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re

# --- 1. CONFIGURAZIONE E DATABASE ---
NOME_OFFICINA = "BIKE LAB MEZZOLOMBARDO"
SETTORI = ["COPERTONI", "PASTIGLIE", "ACCESSORI FRENI", "TRASMISSIONE", "CAMERE D'ARIA", "ACCESSORI TELAIO", "ALTRO"]

def get_db():
    conn = sqlite3.connect('magazzino_v3.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS prodotti
                 (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
                  marca TEXT, quantita INTEGER, prezzo_acquisto REAL, 
                  prezzo_vendita REAL)''')
    return conn

# --- 2. LOGICA ESTRAZIONE DATI (RMS) ---
def analizza_pdf_rms(file):
    prodotti = []
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                testo = page.extract_text()
                if not testo: continue
                linee = testo.split('\n')
                for linea in linee:
                    # Regex per catturare lo schema RMS: Codice | Descrizione | Quantità | Prezzo
                    match = re.search(r'(\d+)\s+(.+?)\s+(\d+)\s+(\d+,\d{2})', linea)
                    if match:
                        prodotti.append({
                            "cod": match.group(1),
                            "desc": match.group(2).strip(),
                            "qty": int(match.group(3)),
                            "prezzo": float(match.group(4).replace(',', '.'))
                        })
    except Exception as e:
        st.error(f"Errore lettura PDF: {e}")
    return prodotti

# --- 3. INIZIALIZZAZIONE INTERFACCIA ---
st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

if 'lista_temporanea' not in st.session_state:
    st.session_state['lista_temporanea'] = []
if 'nome_file' not in st.session_state:
    st.session_state['nome_file'] = ""

menu = st.sidebar.radio("Navigazione", ["🏠 Dashboard / Carico", "📦 Inventario per Categoria"])

# --- 4. DASHBOARD (INGRESSO MERCE) ---
if menu == "🏠 Dashboard / Carico":
    st.title(f"🚲 {NOME_OFFICINA}")
    st.subheader("📥 INGRESSO MERCE")
    
    uploaded_file = st.file_uploader("Carica la fattura/bolla in PDF", type=["pdf"])

    if uploaded_file and uploaded_file.name != st.session_state['nome_file']:
        st.session_state['lista_temporanea'] = analizza_pdf_rms(uploaded_file)
        st.session_state['nome_file'] = uploaded_file.name

    if st.session_state['lista_temporanea']:
        st.info(f"Prodotti trovati in: {st.session_state['nome_file']}")
        
        for i, prod in enumerate(st.session_state['lista_temporanea']):
            with st.expander(f"📦 {prod['desc']} (Cod: {prod['cod']})"):
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                with c1:
                    categoria = st.selectbox("Macro-categoria", SETTORI, key=f"cat_{i}")
                with c2:
                    st.write(f"Acquisto: €{prod['prezzo']}")
                with c3:
                    prezzo_v = st.number_input("Prezzo Vendita €", value=float(prod['prezzo']*1.6), key=f"pv_{i}")
                with c4:
                    st.write("")
                    if st.button("SALVA IN DB", key=f"btn_{i}", use_container_width=True):
                        conn = get_db()
                        # Qui aggiungiamo alla giacenza esistente se il prodotto c'è già
                        cursor = conn.cursor()
                        cursor.execute("SELECT quantita FROM prodotti WHERE barcode=?", (prod['cod'],))
                        existing = cursor.fetchone()
                        
                        nuova_qty = prod['qty'] + (existing[0] if existing else 0)
                        
                        conn.execute('''INSERT OR REPLACE INTO prodotti 
                                     (barcode, categoria, componente, marca, quantita, prezzo_acquisto, prezzo_vendita) 
                                     VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                                     (prod['cod'], categoria, prod['desc'], "RMS", nuova_qty, prod['prezzo'], prezzo_v))
                        conn.commit()
                        st.toast(f"✅ {prod['cod']} aggiunto!")

# --- 5. INVENTARIO ---
elif menu == "📦 Inventario per Categoria":
    st.title("📦 Inventario Suddiviso")
    conn = get_db()
    df_all = pd.read_sql_query("SELECT * FROM prodotti", conn)
    conn.close()

    if df_all.empty:
        st.warning("Nessun dato in magazzino.")
    else:
        for cat in SETTORI:
            df_cat = df_all[df_all['categoria'] == cat]
            with st.expander(f"📂 {cat} ({len(df_cat)} articoli)", expanded=True):
                if not df_cat.empty:
                    # Mostriamo le colonne richieste
                    df_view = df_cat[['barcode', 'componente', 'quantita', 'prezzo_acquisto']]
                    df_view.columns = ['Codice Articolo', 'Descrizione', 'Stock / Pezzi Acq.', 'Prezzo Acquisto (€)']
                    st.dataframe(df_view, use_container_width=True, hide_index=True)
                    
                    valore = (df_cat['quantita'] * df_cat['prezzo_acquisto']).sum()
                    st.write(f"**Valore Totale {cat}:** € {valore:,.2f}")
