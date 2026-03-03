import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re

# --- CONFIGURAZIONE ---
NOME_OFFICINA = "BIKE LAB MEZZOLOMBARDO"
SETTORI = ["COPERTONI", "PASTIGLIE", "ACCESSORI FRENI", "TRASMISSIONE", "CAMERE D'ARIA", "ACCESSORI TELAIO", "ALTRO"]

# Connessione DB sicura
def get_db():
    conn = sqlite3.connect('magazzino_v3.db', check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS prodotti (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, marca TEXT, quantita INTEGER, prezzo_acquisto REAL, prezzo_vendita REAL)')
    conn.execute('CREATE TABLE IF NOT EXISTS fatture (id_fattura TEXT PRIMARY KEY, data_doc TEXT, fornitore TEXT, importo REAL, file_name TEXT)')
    return conn

# Funzione estrazione sicura
def analizza_pdf_rms(file):
    prodotti = []
    dati_doc = {"numero": "N/D", "data": "N/D", "totale": 0.0}
    try:
        with pdfplumber.open(file) as pdf:
            testo_completo = "".join([p.extract_text() or "" for p in pdf.pages])
            # Estrazione testata
            num = re.search(r'N\.\s*DOCUMENTO\s*\n\s*(\d+)', testo_completo)
            if num: dati_doc["numero"] = num.group(1)
            
            # Estrazione righe prodotti
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    for linea in t.split('\n'):
                        m = re.search(r'(\d+)\s+(.+?)\s+(\d+)\s+(\d+,\d{2})', linea)
                        if m:
                            prodotti.append({"cod": m.group(1), "desc": m.group(2).strip(), "qty": int(m.group(3)), "prezzo": float(m.group(4).replace(',', '.'))})
    except Exception as e:
        st.error(f"Errore PDF: {e}")
    return dati_doc, prodotti

# --- UI ---
st.set_page_config(page_title=NOME_OFFICINA, layout="wide")

# Inizializzazione Session State per evitare loop
if 'doc_caricato' not in st.session_state:
    st.session_state.doc_caricato = None

menu = st.sidebar.radio("Menu", ["🏠 Dashboard", "📦 Inventario", "📑 Archivio"])

# --- DASHBOARD / CARICO ---
if menu == "🏠 Dashboard":
    st.title("📥 Carico Merce")
    up = st.file_uploader("Trascina qui la fattura RMS", type="pdf")
    
    if up:
        # Analizza solo se il file è cambiato
        if st.session_state.doc_caricato != up.name:
            with st.spinner("Analisi in corso..."):
                doc, prods = analizza_pdf_rms(up)
                st.session_state.dati_f = doc
                st.session_state.prod_f = prods
                st.session_state.doc_caricato = up.name

        d, p = st.session_state.dati_f, st.session_state.prod_f
        st.success(f"Documento n. {d['numero']} del {d['data']}")
        
        if st.button("REGISTRA FATTURA"):
            db = get_db()
            try:
                db.execute("INSERT INTO fatture VALUES (?,?,?,?,?)", (d['numero'], d['data'], "RMS", d['totale'], up.name))
                db.commit()
                st.toast("Fattura registrata!")
            except: st.warning("Già registrata.")

        for i, item in enumerate(p):
            with st.expander(f"{item['desc']}"):
                c1, c2, c3 = st.columns(3)
                cat = c1.selectbox("Settore", SETTORI, key=f"s_{i}")
                pv = c2.number_input("Prezzo Vendita", float(item['prezzo']*1.6), key=f"v_{i}")
                if c3.button("CARICA", key=f"b_{i}"):
                    db = get_db()
                    cur = db.cursor()
                    cur.execute("SELECT quantita FROM prodotti WHERE barcode=?", (item['cod'],))
                    old = cur.fetchone()
                    new_q = item['qty'] + (old[0] if old else 0)
                    db.execute("INSERT OR REPLACE INTO prodotti VALUES (?,?,?,?,?,?,?)", (item['cod'], cat, item['desc'], "RMS", new_q, item['prezzo'], pv))
                    db.commit()
                    st.toast("Salvato!")

# --- INVENTARIO ---
elif menu == "📦 Inventario":
    st.title("📦 Magazzino")
    db = get_db()
    df = pd.read_sql("SELECT * FROM prodotti", db)
    
    for s in SETTORI:
        df_s = df[df['categoria'] == s]
        with st.expander(f"{s} ({len(df_s)})"):
            if not df_s.empty:
                st.dataframe(df_s[['barcode','componente','quantita','prezzo_acquisto']], use_container_width=True, hide_index=True)
                # Scarico rapido
                col1, col2 = st.columns([3,1])
                target = col1.selectbox("Quale scaricare?", df_s['componente'].tolist(), key=f"sel_{s}")
                qty_out = col2.number_input("Pezzi", 1, 100, key=f"q_{s}")
                if st.button(f"SCARICA {s}", key=f"btn_{s}"):
                    db.execute("UPDATE prodotti SET quantita = quantita - ? WHERE componente = ?", (qty_out, target))
                    db.commit()
                    st.rerun()

# --- ARCHIVIO ---
elif menu == "📑 Archivio":
    st.title("📑 Archivio Documenti")
    db = get_db()
    df_f = pd.read_sql("SELECT * FROM fatture", db)
    st.dataframe(df_f, use_container_width=True)
