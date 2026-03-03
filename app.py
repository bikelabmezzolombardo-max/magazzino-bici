import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
from datetime import datetime

# --- 1. CONFIGURAZIONE E DATABASE ---
NOME_OFFICINA = "BIKE LAB MEZZOLOMBARDO"
SETTORI = ["COPERTONI", "PASTIGLIE", "ACCESSORI FRENI", "TRASMISSIONE", "CAMERE D'ARIA", "ACCESSORI TELAIO", "ALTRO"]

def get_db():
    conn = sqlite3.connect('magazzino_v3.db', check_same_thread=False)
    # Tabella Prodotti
    conn.execute('''CREATE TABLE IF NOT EXISTS prodotti
                 (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
                  marca TEXT, quantita INTEGER, prezzo_acquisto REAL, 
                  prezzo_vendita REAL)''')
    # NUOVA Tabella Fatture
    conn.execute('''CREATE TABLE IF NOT EXISTS fatture
                 (id_fattura TEXT PRIMARY KEY, data_doc TEXT, fornitore TEXT, 
                  importo REAL, file_name TEXT, data_caricamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    return conn

# --- 2. LOGICA ESTRAZIONE AVANZATA (Testata + Prodotti) ---
def analizza_pdf_completo(file):
    dati_doc = {"numero": "N/D", "data": "N/D", "totale": 0.0, "fornitore": "RMS"}
    prodotti = []
    
    try:
        with pdfplumber.open(file) as pdf:
            testo_completo = ""
            for page in pdf.pages:
                testo = page.extract_text()
                if not testo: continue
                testo_completo += testo
                
                linee = testo.split('\n')
                for linea in linee:
                    # Estrazione Prodotti (Regex RMS)
                    match_p = re.search(r'(\d+)\s+(.+?)\s+(\d+)\s+(\d+,\d{2})', linea)
                    if match_p:
                        prodotti.append({
                            "cod": match_p.group(1),
                            "desc": match_p.group(2).strip(),
                            "qty": int(match_p.group(3)),
                            "prezzo": float(match_p.group(4).replace(',', '.'))
                        })
            
            # Estrazione Dati Testata (Numero e Data)
            num_match = re.search(r'N\.\s*DOCUMENTO\s*\n\s*(\d+)', testo_completo)
            if num_match: dati_doc["numero"] = num_match.group(1)
            
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', testo_completo)
            if date_match: dati_doc["data"] = date_match.group(1)
            
            tot_match = re.search(r'TOTALE DOCUMENTO\s*\n.*?\n\s*(\d+,\d{2})', testo_completo)
            if tot_match: dati_doc["totale"] = float(tot_match.group(1).replace(',', '.'))
            
    except Exception as e:
        st.error(f"Errore analisi: {e}")
        
    return dati_doc, prodotti

# --- 3. INIZIALIZZAZIONE ---
st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

if 'doc_corrente' not in st.session_state:
    st.session_state['doc_corrente'] = None
if 'prodotti_correnti' not in st.session_state:
    st.session_state['prodotti_correnti'] = []

menu = st.sidebar.radio("Navigazione", ["🏠 Dashboard / Carico", "📦 Inventario", "📑 Archivio Fatture"])

# --- 4. DASHBOARD / CARICO ---
if menu == "🏠 Dashboard / Carico":
    st.title(f"🚲 {NOME_OFFICINA}")
    st.subheader("📥 INGRESSO MERCE")
    
    uploaded_file = st.file_uploader("Carica fattura PDF", type=["pdf"])

    if uploaded_file:
        if st.session_state.get('nome_file_last') != uploaded_file.name:
            doc, prods = analizza_pdf_completo(uploaded_file)
            st.session_state['doc_corrente'] = doc
            st.session_state['prodotti_correnti'] = prods
            st.session_state['nome_file_last'] = uploaded_file.name

        doc = st.session_state['doc_corrente']
        prods = st.session_state['prodotti_correnti']

        # Riepilogo Fattura
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("N. Documento", doc["numero"])
        c2.metric("Data", doc["data"])
        c3.metric("Totale Lordo", f"€ {doc['totale']}")
        
        if c4.button("💾 REGISTRA FATTURA", use_container_width=True):
            conn = get_db()
            try:
                conn.execute("INSERT INTO fatture (id_fattura, data_doc, fornitore, importo, file_name) VALUES (?,?,?,?,?)",
                             (doc["numero"], doc["data"], doc["fornitore"], doc["totale"], uploaded_file.name))
                conn.commit()
                st.success("Fattura archiviata correttamente!")
            except sqlite3.IntegrityError:
                st.warning("Questa fattura è già presente nell'archivio.")

        st.divider()
        st.write("### Catalogazione Prodotti")
        for i, prod in enumerate(prods):
            with st.expander(f"📦 {prod['desc']} (Cod: {prod['cod']})"):
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                with col1: cat = st.selectbox("Categoria", SETTORI, key=f"cat_{i}")
                with col2: st.write(f"Acq: €{prod['prezzo']}")
                with col3: pv = st.number_input("Vendita €", value=float(prod['prezzo']*1.6), key=f"pv_{i}")
                with col4:
                    if st.button("CARICA", key=f"btn_{i}"):
                        conn = get_db()
                        cursor = conn.cursor()
                        cursor.execute("SELECT quantita FROM prodotti WHERE barcode=?", (prod['cod'],))
                        existing = cursor.fetchone()
                        nuova_qty = prod['qty'] + (existing[0] if existing else 0)
                        conn.execute("INSERT OR REPLACE INTO prodotti VALUES (?,?,?,?,?,?,?)", 
                                     (prod['cod'], cat, prod['desc'], "RMS", nuova_qty, prod['prezzo'], pv))
                        conn.commit()
                        st.toast(f"Caricato: {prod['cod']}")

# --- 5. INVENTARIO ---
elif menu == "📦 Inventario":
    st.title("📦 Inventario")
    conn = get_db()
    df_all = pd.read_sql_query("SELECT * FROM prodotti", conn)
    for cat in SETTORI:
        df_cat = df_all[df_all['categoria'] == cat]
        with st.expander(f"📂 {cat} ({len(df_cat)})"):
            if not df_cat.empty:
                st.dataframe(df_cat[['barcode', 'componente', 'quantita', 'prezzo_acquisto']], use_container_width=True, hide_index=True)
                for _, r in df_cat.iterrows():
                    c_d, c_q, c_b = st.columns([3, 1, 1])
                    c_d.write(f"**{r['componente']}**")
                    n_s = c_q.number_input("Qty", 1, int(r['quantita']) if r['quantita']>0 else 1, key=f"s_{r['barcode']}", label_visibility="collapsed")
                    if c_b.button("SCARICA", key=f"b_{r['barcode']}", use_container_width=True):
                        conn.execute("UPDATE prodotti SET quantita = quantita - ? WHERE barcode = ?", (n_s, r['barcode']))
                        conn.commit()
                        st.rerun()

# --- 6. ARCHIVIO FATTURE ---
elif menu == "📑 Archivio Fatture":
    st.title("📑 Registro Fatture Caricate")
    conn = get_db()
    df_fat = pd.read_sql_query("SELECT id_fattura, data_doc, fornitore, importo, file_name, data_caricamento FROM fatture ORDER BY data_caricamento DESC", conn)
