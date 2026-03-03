import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re

# --- CONFIGURAZIONE ---
NOME_OFFICINA = "BIKE LAB MEZZOLOMBARDO"
SETTORI = ["COPERTONI", "PASTIGLIE", "ACCESSORI FRENI", "TRASMISSIONE", "CAMERE D'ARIA", "ACCESSORI TELAIO", "ALTRO"]

def get_db():
    conn = sqlite3.connect('magazzino_v3.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS prodotti
                 (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
                  marca TEXT, quantita INTEGER, prezzo_acquisto REAL, 
                  prezzo_vendita REAL)''')
    return conn

# --- ESTRAZIONE REALE DAL PDF ---
def analizza_pdf_rms(file):
    prodotti = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            testo = page.extract_text()
            if not testo:
                continue
            
            # Dividiamo il testo in righe
            linee = testo.split('\n')
            for linea in linee:
                # Cerchiamo righe che hanno un formato simile a quello RMS:
                # Esempio: "52 524 CATENA 10V X10 SILVER-BLACK 4 13,74 ..."
                # Usiamo una regex per catturare: Codice, Descrizione, Quantità, Prezzo
                match = re.search(r'(\d+)\s+(.+?)\s+(\d+)\s+(\d+,\d{2})', linea)
                
                if match:
                    codice = match.group(1)
                    descrizione = match.group(2)
                    quantita = int(match.group(3))
                    prezzo = float(match.group(4).replace(',', '.'))
                    
                    # Filtriamo righe che non sono prodotti (es. numeri di pagina o date)
                    if len(codice) >= 3 and len(descrizione) > 5:
                        prodotti.append({
                            "cod": codice,
                            "desc": descrizione,
                            "qty": quantita,
                            "prezzo": prezzo
                        })
    return prodotti

st.set_page_config(page_title=NOME_OFFICINA, layout="wide")

# --- RESET SESSIONE SE CAMBIA IL FILE ---
if 'ultimo_file' not in st.session_state:
    st.session_state['ultimo_file'] = None
    st.session_state['prodotti_caricati'] = []

# --- INTERFACCIA ---
st.title(f"🚲 {NOME_OFFICINA}")

menu = st.sidebar.radio("Navigazione", ["🏠 Dashboard / Carico", "📦 Inventario per Categoria"])

if menu == "🏠 Dashboard / Carico":
    st.subheader("📥 INGRESSO MERCE")
    
    uploaded_file = st.file_uploader("Carica una nuova fattura PDF", type=["pdf"])

    # Se il file è nuovo, analizzalo e salva in session_state
    if uploaded_file is not None and uploaded_file.name != st.session_state['ultimo_file']:
        with st.spinner('Analisi del nuovo documento in corso...'):
            st.session_state['prodotti_caricati'] = analizza_pdf_rms(uploaded_file)
            st.session_state['ultimo_file'] = uploaded_file.name
            st.success(f"Nuovo file caricato: {uploaded_file.name}")

    # Mostra i prodotti del file corrente
    if st.session_state['prodotti_caricati']:
        st.write(f"### Prodotti rilevati in: {st.session_state['ultimo_file']}")
        
        for i, prod in enumerate(st.session_state['prodotti_caricati']):
            with st.expander(f"📦 {prod['desc']} (Cod: {prod['cod']})"):
                c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                with c1:
                    categoria = st.selectbox("Categoria", SETTORI, key=f"cat_{i}")
                with c2:
                    st.write(f"Acquisto: €{prod['prezzo']}")
                with c3:
                    prezzo_v = st.number_input("Vendita €", value=float(prod['prezzo']*1.6), key=f"pv_{i}")
                with c4:
                    st.write("")
                    if st.button("SALVA", key=f"btn_{i}"):
                        conn = get_db()
                        conn.execute('''INSERT OR REPLACE INTO prodotti 
                                     (barcode, categoria, componente, marca, quantita, prezzo_acquisto, prezzo_vendita) 
                                     VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                                     (prod['cod'], categoria, prod['desc'], "RMS", prod['qty'], prod['prezzo'], prezzo_v))
                        conn.commit()
                        st.toast(f"Articolo {prod['cod']} salvato!")

elif menu == "📦 Inventario per Categoria":
    st.title("📦 Inventario Suddiviso")
    conn = get_db()
    df_all = pd.read_sql_query("SELECT * FROM prodotti", conn)
    
    for cat in SETTORI:
        df_cat = df_all[df_all['categoria'] == cat]
        with st.expander(f"📂 {cat} ({len(df_cat)} articoli)", expanded=True):
            if not df_cat.empty:
                df_show = df_cat[['barcode', 'componente', 'quantita', 'prezzo_acquisto']]
                df_show.columns = ['Codice', 'Descrizione', 'Stock', 'Prezzo Acq.']
                st.dataframe(df_show, use_container_width=True, hide_index=True)
            else:
                st.write("Categoria vuota.")
