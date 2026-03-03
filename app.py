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

# --- FUNZIONI DI ESTRAZIONE ---
def analizza_file(file):
    prodotti = []
    if file.name.endswith('.pdf'):
        try:
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    testo = page.extract_text()
                    if testo:
                        for linea in testo.split('\n'):
                            # Cerca il pattern tipico RMS: Codice, Descrizione, Quantità, Prezzo
                            m = re.search(r'(\d+)\s+(.+?)\s+(\d+)\s+(\d+,\d{2})', linea)
                            if m:
                                prodotti.append({
                                    "cod": m.group(1), 
                                    "desc": m.group(2).strip(), 
                                    "qty": int(m.group(3)), 
                                    "prezzo": float(m.group(4).replace(',', '.'))
                                })
        except Exception as e:
            st.error(f"Errore PDF: {e}")
    else: # Gestione CSV
        df = pd.read_csv(file)
        for _, row in df.iterrows():
            prodotti.append({
                "cod": str(row.get('codice', '0')), 
                "desc": str(row.get('descrizione', 'N/D')), 
                "qty": int(row.get('quantita', 1)), 
                "prezzo": float(str(row.get('prezzo', 0)).replace(',', '.'))
            })
    return prodotti

# --- INTERFACCIA ---
st.set_page_config(page_title=NOME_OFFICINA, layout="wide")

# Prevenzione loop ricaricamento
if 'file_in_memoria' not in st.session_state:
    st.session_state.file_in_memoria = None
    st.session_state.lista_prodotti = []

menu = st.sidebar.radio("Navigazione", ["🏠 Dashboard / Carico", "📦 Inventario"])

# --- DASHBOARD ---
if menu == "🏠 Dashboard / Carico":
    st.title(f"🚲 {NOME_OFFICINA}")
    up = st.file_uploader("Carica Bolla (PDF RMS o CSV)", type=["pdf", "csv"])

    if up:
        if st.session_state.file_in_memoria != up.name:
            st.session_state.lista_prodotti = analizza_file(up)
            st.session_state.file_in_memoria = up.name

        for i, prod in enumerate(st.session_state.lista_prodotti):
            with st.expander(f"📦 {prod['desc']} (Cod: {prod['cod']})"):
                c1, c2, c3 = st.columns([2, 1, 1])
                cat = c1.selectbox("Categoria", SETTORI, key=f"c_{i}")
                pv = c2.number_input("Prezzo Vendita €", value=float(prod['prezzo']*1.6), key=f"p_{i}")
                if c3.button("CARICA", key=f"b_{i}"):
                    conn = get_db()
                    cur = conn.cursor()
                    cur.execute("SELECT quantita FROM prodotti WHERE barcode=?", (prod['cod'],))
                    old = cur.fetchone()
                    new_q = prod['qty'] + (old[0] if old else 0)
                    conn.execute("INSERT OR REPLACE INTO prodotti VALUES (?,?,?,?,?,?,?)", 
                                 (prod['cod'], cat, prod['desc'], "RMS", new_q, prod['prezzo'], pv))
                    conn.commit()
                    st.toast(f"Caricato {prod['cod']}")

# --- INVENTARIO ---
elif menu == "📦 Inventario":
    st.title("📦 Inventario Magazzino")
    conn = get_db()
    df = pd.read_sql("SELECT * FROM prodotti", conn)
    
    for s in SETTORI:
        df_s = df[df['categoria'] == s]
        with st.expander(f"📂 {s} ({len(df_s)})"):
            if not df_s.empty:
                st.dataframe(df_s[['barcode', 'componente', 'quantita', 'prezzo_acquisto']], use_container_width=True, hide_index=True)
                # Funzione rapida di scarico
                st.write("---")
                col_sel, col_qty, col_btn = st.columns([3, 1, 1])
                scelta = col_sel.selectbox("Articolo da scaricare", df_s['componente'].tolist(), key=f"sel_{s}")
                q_via = col_qty.number_input("Pezzi", 1, 100, key=f"q_{s}")
                if col_btn.button("SCARICA", key=f"btn_{s}"):
                    conn.execute("UPDATE prodotti SET quantita = quantita - ? WHERE componente = ?", (q_via, scelta))
                    conn.commit()
                    st.rerun()
