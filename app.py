import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re

# --- CONFIGURAZIONE ---
NOME_OFFICINA = "BIKE LAB MEZZOLOMBARDO"
SETTORI = ["COPERTONI", "PASTIGLIE", "ACCESSORI FRENI", "TRASMISSIONE", "CAMERE D'ARIA", "ACCESSORI TELAIO", "ALTRO"]

# Connessione DB
def get_db():
    conn = sqlite3.connect('magazzino_v3.db', check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS prodotti (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, marca TEXT, quantita INTEGER, prezzo_acquisto REAL, prezzo_vendita REAL)')
    conn.execute('CREATE TABLE IF NOT EXISTS fatture (id_fattura TEXT PRIMARY KEY, data_doc TEXT, fornitore TEXT, importo REAL, file_name TEXT)')
    return conn

# --- FUNZIONI DI ANALISI ---

def analizza_pdf_rms(file):
    prodotti = []
    dati_doc = {"numero": "N/D", "data": "N/D", "totale": 0.0}
    try:
        with pdfplumber.open(file) as pdf:
            testo_completo = "".join([p.extract_text() or "" for p in pdf.pages])
            # Numero documento RMS
            num = re.search(r'N\.\s*DOCUMENTO\s*\n\s*(\d+)', testo_completo)
            if num: dati_doc["numero"] = num.group(1)
            
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    for linea in t.split('\n'):
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
    return dati_doc, prodotti

def analizza_csv(file):
    prodotti = []
    dati_doc = {"numero": "CSV_" + file.name, "data": "Odierna", "totale": 0.0}
    try:
        df = pd.read_csv(file, sep=None, engine='python') # sep=None rileva automaticamente virgola o punto e virgola
        # Rinomina colonne per standardizzare (cerca nomi simili)
        mapping = {col: col.lower() for col in df.columns}
        df = df.rename(columns=mapping)
        
        for _, row in df.iterrows():
            # Cerchiamo di mappare le colonne comuni
            cod = str(row.get('codice', row.get('barcode', row.get('id', '0'))))
            desc = str(row.get('descrizione', row.get('nome', row.get('articolo', 'N/D'))))
            qty = int(row.get('quantita', row.get('qty', row.get('pezzi', 1))))
            prezzo = float(str(row.get('prezzo', row.get('acquisto', 0))).replace(',', '.'))
            
            prodotti.append({"cod": cod, "desc": desc, "qty": qty, "prezzo": prezzo})
            dati_doc["totale"] += (prezzo * qty)
    except Exception as e:
        st.error(f"Errore CSV: {e}. Assicurati che le colonne siano 'codice', 'descrizione', 'quantita', 'prezzo'.")
    return dati_doc, prodotti

# --- INTERFACCIA ---
st.set_page_config(page_title=NOME_OFFICINA, layout="wide")

if 'doc_caricato' not in st.session_state:
    st.session_state.doc_caricato = None

menu = st.sidebar.radio("Menu", ["🏠 Dashboard / Carico", "📦 Inventario", "📑 Archivio Fatture"])

# --- 1. DASHBOARD / CARICO ---
if menu == "🏠 Dashboard / Carico":
    st.title("📥 Ingresso Merce")
    up = st.file_uploader("Carica Fattura PDF (RMS) o file CSV", type=["pdf", "csv"])
    
    if up:
        if st.session_state.doc_caricato != up.name:
            with st.spinner("Elaborazione file..."):
                if up.name.endswith('.pdf'):
                    doc, prods = analizza_pdf_rms(up)
                else:
                    doc, prods = analizza_csv(up)
                
                st.session_state.dati_f = doc
                st.session_state.prod_f = prods
                st.session_state.doc_caricato = up.name

        d, p = st.session_state.dati_f, st.session_state.prod_f
        
        st.info(f"📄 Documento: {d['numero']} | Totale stimato: € {d['totale']:.2f}")
        
        if st.button("💾 REGISTRA DOCUMENTO IN ARCHIVIO"):
            db = get_db()
            try:
                db.execute("INSERT INTO fatture VALUES (?,?,?,?,?)", (d['numero'], d['data'], "Fornitore", d['totale'], up.name))
                db.commit()
                st.success("Documento salvato in archivio!")
            except: st.warning("Questo documento risulta già archiviato.")

        st.write("---")
        st.subheader("Catalogazione Prodotti rilevati")
        
        for i, item in enumerate(p):
            with st.expander(f"📦 {item['desc']} (Cod: {item['cod']})"):
                c1, c2, c3 = st.columns([2, 1, 1])
                cat = c1.selectbox("Settore", SETTORI, key=f"s_{i}")
                pv = c2.number_input("Prezzo Vendita €", float(item['prezzo']*1.6), key=f"v_{i}")
                if c3.button("CARICA IN MAGAZZINO", key=f"b_{i}"):
                    db = get_db()
                    cur = db.cursor()
                    cur.execute("SELECT quantita FROM prodotti WHERE barcode=?", (item['cod'],))
                    old = cur.fetchone()
                    new_q = item['qty'] + (old[0] if old else 0)
                    db.execute("INSERT OR REPLACE INTO prodotti VALUES (?,?,?,?,?,?,?)", (item['cod'], cat, item['desc'], "Dinamico", new_q, item['prezzo'], pv))
                    db.commit()
                    st.toast(f"Caricato {item['cod']}!")

# --- 2. INVENTARIO ---
elif menu == "📦 Inventario":
    st.title("📦 Inventario")
    db = get_db()
    df = pd.read_sql("SELECT * FROM prodotti", db)
    
    for s in SETTORI:
        df_s = df[df['categoria'] == s]
        with st.expander(f"📂 {s} ({len(df_s)} articoli)", expanded=False):
            if not df_s.empty:
                st.dataframe(df_s[['barcode','componente','quantita','prezzo_acquisto']], use_container_width=True, hide_index=True)
                
                st.write("**Scarico rapido:**")
                col1, col2, col3 = st.columns([3, 1, 1])
                target = col1.selectbox("Seleziona articolo", df_s['componente'].tolist(), key=f"sel_{s}")
                qty_out = col2.number_input("Pezzi da togliere", 1, 100, key=f"q_{s}")
                if col3.button("SCARICA", key=f"btn_{s}"):
                    db.execute("UPDATE prodotti SET quantita = quantita - ? WHERE componente = ?", (qty_out, target))
                    db.commit()
                    st.rerun()

# --- 3. ARCHIVIO ---
elif menu == "📑 Archivio Fatture":
    st.title("📑 Registro Documenti")
    db = get_db()
    df_f = pd.read_sql("SELECT * FROM fatture", db)
    if not df_f.empty:
        st.dataframe(df_f, use_container_width=True, hide_index=True)
    else:
        st.write("Nessuna fattura registrata.")
