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
    # Tabella prodotti con colonna extra per tracciare l'ultima bolla
    conn.execute('''CREATE TABLE IF NOT EXISTS prodotti
                 (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
                  marca TEXT, quantita INTEGER, prezzo_acquisto REAL, 
                  prezzo_vendita REAL, ultima_bolla TEXT)''')
    conn.execute('CREATE TABLE IF NOT EXISTS fatture (id_fattura TEXT PRIMARY KEY, data_doc TEXT, fornitore TEXT, importo REAL, file_name TEXT)')
    return conn

# --- ANALISI PDF/CSV (Invariate) ---
def analizza_pdf_rms(file):
    prodotti = []
    dati_doc = {"numero": "N/D", "data": "N/D", "totale": 0.0}
    try:
        with pdfplumber.open(file) as pdf:
            testo_completo = "".join([p.extract_text() or "" for p in pdf.pages])
            num = re.search(r'N\.\s*DOCUMENTO\s*\n\s*(\d+)', testo_completo)
            if num: dati_doc["numero"] = num.group(1)
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    for linea in t.split('\n'):
                        m = re.search(r'(\d+)\s+(.+?)\s+(\d+)\s+(\d+,\d{2})', linea)
                        if m:
                            prodotti.append({"cod": m.group(1), "desc": m.group(2).strip(), "qty": int(m.group(3)), "prezzo": float(m.group(4).replace(',', '.'))})
    except Exception as e: st.error(f"Errore PDF: {e}")
    return dati_doc, prodotti

# --- INTERFACCIA ---
st.set_page_config(page_title=NOME_OFFICINA, layout="wide")

# Session State per gestire i duplicati nella sessione
if 'articoli_salvati' not in st.session_state:
    st.session_state.articoli_salvati = set()
if 'doc_caricato' not in st.session_state:
    st.session_state.doc_caricato = None

menu = st.sidebar.radio("Menu", ["🏠 Dashboard / Carico", "📦 Inventario", "📑 Archivio"])

if menu == "🏠 Dashboard / Carico":
    st.title("📥 Ingresso Merce")
    up = st.file_uploader("Carica Fattura PDF o CSV", type=["pdf", "csv"])
    
    if up:
        if st.session_state.doc_caricato != up.name:
            with st.spinner("Analisi..."):
                doc, prods = analizza_pdf_rms(up) if up.name.endswith('.pdf') else ({'numero': up.name, 'totale':0}, [])
                st.session_state.dati_f = doc
                st.session_state.prod_f = prods
                st.session_state.doc_caricato = up.name
                st.session_state.articoli_salvati = set() # Reset salvataggi per nuova bolla

        d = st.session_state.dati_f
        p = st.session_state.prod_f
        
        st.info(f"📄 Documento N: {d['numero']}")

        # Controllo se la bolla è già stata registrata nell'archivio fatture
        db = get_db()
        check_bolla = db.execute("SELECT id_fattura FROM fatture WHERE id_fattura=?", (d['numero'],)).fetchone()
        
        if check_bolla:
            st.warning("⚠️ Attenzione: Questa bolla risulta già caricata in Archivio!")

        st.subheader("Prodotti da catalogare")
        for i, item in enumerate(p):
            # CHIAVE UNICA: numero_bolla + codice_articolo
            chiave_item = f"{d['numero']}_{item['cod']}"
            
            # Verifichiamo se l'articolo è già stato cliccato in questa sessione
            gia_fatto = chiave_item in st.session_state.articoli_salvati
            
            with st.expander(f"{'✅' if gia_fatto else '📦'} {item['desc']} (Cod: {item['cod']})"):
                if gia_fatto:
                    st.success("Articolo già caricato a sistema per questa bolla.")
                else:
                    c1, c2, c3 = st.columns([2, 1, 1])
                    cat = c1.selectbox("Settore", SETTORI, key=f"s_{i}")
                    pv = c2.number_input("Prezzo Vendita €", float(item['prezzo']*1.6), key=f"v_{i}")
                    
                    if c3.button("CARICA", key=f"b_{i}", use_container_width=True):
                        db = get_db()
                        # 1. Recupera qty attuale
                        cur = db.cursor()
                        cur.execute("SELECT quantita FROM prodotti WHERE barcode=?", (item['cod'],))
                        old = cur.fetchone()
                        new_q = item['qty'] + (old[0] if old else 0)
                        
                        # 2. Inserisci e traccia la bolla
                        db.execute("INSERT OR REPLACE INTO prodotti VALUES (?,?,?,?,?,?,?,?)", 
                                     (item['cod'], cat, item['desc'], "RMS", new_q, item['prezzo'], pv, d['numero']))
                        db.commit()
                        
                        # 3. Segna come fatto nella sessione
                        st.session_state.articoli_salvati.add(chiave_item)
                        st.toast(f"Caricato: {item['cod']}")
                        st.rerun()

# --- (Resto del codice Inventario e Archivio rimane invariato) ---
