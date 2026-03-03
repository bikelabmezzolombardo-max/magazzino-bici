import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re

# --- CONFIGURAZIONE ---
NOME_OFFICINA = "BIKE LAB MEZZOLOMBARDO"
SETTORI = ["COPERTONI", "PASTIGLIE", "ACCESSORI FRENI", "TRASMISSIONE", "CAMERE D'ARIA", "ACCESSORI TELAIO", "ALTRO"]

# Inizializzazione DB con tabella Fatture
def get_db():
    conn = sqlite3.connect('magazzino_v3.db', check_same_thread=False)
    # Tabella Prodotti
    conn.execute('''CREATE TABLE IF NOT EXISTS prodotti 
                 (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
                  marca TEXT, quantita INTEGER, prezzo_acquisto REAL, prezzo_vendita REAL)''')
    # Tabella Fatture (Ripristinata)
    conn.execute('''CREATE TABLE IF NOT EXISTS fatture 
                 (id_fattura TEXT PRIMARY KEY, data_doc TEXT, fornitore TEXT, importo REAL, file_name TEXT)''')
    return conn

# --- FUNZIONI DI ANALISI ---
def analizza_file(file):
    prodotti = []
    dati_doc = {"numero": "N/D", "data": "N/D", "totale": 0.0}
    
    if file.name.endswith('.pdf'):
        try:
            with pdfplumber.open(file) as pdf:
                testo_completo = "".join([p.extract_text() or "" for p in pdf.pages])
                # Cerca numero documento (Logica RMS)
                num = re.search(r'N\.\s*DOCUMENTO\s*\n\s*(\d+)', testo_completo)
                if num: dati_doc["numero"] = num.group(1)
                
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        for linea in t.split('\n'):
                            m = re.search(r'(\d+)\s+(.+?)\s+(\d+)\s+(\d+,\d{2})', linea)
                            if m:
                                p_acquisto = float(m.group(4).replace(',', '.'))
                                qty = int(m.group(3))
                                prodotti.append({"cod": m.group(1), "desc": m.group(2).strip(), "qty": qty, "prezzo": p_acquisto})
                                dati_doc["totale"] += (p_acquisto * qty)
        except Exception as e: st.error(f"Errore PDF: {e}")
    else:
        try:
            df = pd.read_csv(file, sep=None, engine='python')
            dati_doc["numero"] = f"CSV_{file.name}"
            for _, row in df.iterrows():
                cod = str(row.get('codice', '0'))
                desc = str(row.get('descrizione', 'N/D'))
                qty = int(row.get('quantita', 1))
                prezzo = float(str(row.get('prezzo', 0)).replace(',', '.'))
                prodotti.append({"cod": cod, "desc": desc, "qty": qty, "prezzo": prezzo})
                dati_doc["totale"] += (prezzo * qty)
        except Exception as e: st.error(f"Errore CSV: {e}")
            
    return dati_doc, prodotti

# --- INTERFACCIA ---
st.set_page_config(page_title=NOME_OFFICINA, layout="wide")

if 'file_caricato' not in st.session_state:
    st.session_state.file_caricato = None

menu = st.sidebar.radio("Menu", ["🏠 Carico Merce", "📦 Inventario Magazzino", "📑 Archivio Fatture"])

# --- 1. CARICO MERCE ---
if menu == "🏠 Carico Merce":
    st.title("📥 Ingresso Nuova Merce")
    up = st.file_uploader("Trascina qui il file della bolla (PDF o CSV)", type=["pdf", "csv"])
    
    if up:
        if st.session_state.file_caricato != up.name:
            doc, prods = analizza_file(up)
            st.session_state.dati_f = doc
            st.session_state.prod_f = prods
            st.session_state.file_caricato = up.name

        d, p = st.session_state.dati_f, st.session_state.prod_f
        st.info(f"📄 Doc. N: {d['numero']} | Valore Merce: € {d['totale']:.2f}")
        
        # Tasto per archiviare la fattura
        if st.button("💾 REGISTRA FATTURA IN ARCHIVIO"):
            db = get_db()
            try:
                db.execute("INSERT INTO fatture VALUES (?,?,?,?,?)", (d['numero'], "Oggi", "RMS/Fornitore", d['totale'], up.name))
                db.commit()
                st.success("Fattura registrata correttamente!")
            except: st.warning("Documento già presente in archivio.")

        st.write("---")
        for i, item in enumerate(p):
            with st.expander(f"📦 {item['desc']} (Cod: {item['cod']})"):
                c1, c2, c3 = st.columns([2, 1, 1])
                cat = c1.selectbox("Settore", SETTORI, key=f"s_{i}")
                pv = c2.number_input("Prezzo Vendita €", float(item['prezzo']*1.6), key=f"v_{i}")
                if c3.button("AGGIUNGI A STOCK", key=f"b_{i}"):
                    db = get_db()
                    cur = db.cursor()
                    cur.execute("SELECT quantita FROM prodotti WHERE barcode=?", (item['cod'],))
                    old = cur.fetchone()
                    new_q = item['qty'] + (old[0] if old else 0)
                    db.execute("INSERT OR REPLACE INTO prodotti VALUES (?,?,?,?,?,?,?)", 
                                 (item['cod'], cat, item['desc'], "Fornitore", new_q, item['prezzo'], pv))
                    db.commit()
                    st.toast("Caricato!")

# --- 2. INVENTARIO ---
elif menu == "📦 Inventario Magazzino":
    st.title("📦 Situazione Magazzino")
    db = get_db()
    df = pd.read_sql("SELECT * FROM prodotti", db)
    for s in SETTORI:
        df_s = df[df['categoria'] == s]
        with st.expander(f"📂 {s} ({len(df_s)})"):
            if not df_s.empty:
                st.dataframe(df_s[['barcode','componente','quantita','prezzo_acquisto']], use_container_width=True, hide_index=True)

# --- 3. ARCHIVIO (FATTURE RIPRISTINATE) ---
elif menu == "📑 Archivio Fatture":
    st.title("📑 Registro Documenti Caricati")
    db = get_db()
    df_f = pd.read_sql("SELECT * FROM fatture", db)
    if not df_f.empty:
        st.dataframe(df_f, use_container_width=True, hide_index=True)
        st.metric("Totale Acqu
