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

# --- 3. INIZIALIZZAZIONE ---
st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

if 'lista_temporanea' not in st.session_state:
    st.session_state['lista_temporanea'] = []
if 'nome_file' not in st.session_state:
    st.session_state['nome_file'] = ""

# Cambio nome menu richiesto: "Inventario"
menu = st.sidebar.radio("Navigazione", ["🏠 Dashboard / Carico", "📦 Inventario"])

# --- 4. DASHBOARD (CARICO MERCE) ---
if menu == "🏠 Dashboard / Carico":
    st.title(f"🚲 {NOME_OFFICINA}")
    st.subheader("📥 INGRESSO MERCE (Carico)")
    
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
                    prezzo_v = st.number_input("Vendita €", value=float(prod['prezzo']*1.6), key=f"pv_{i}")
                with c4:
                    st.write("")
                    if st.button("CARICA", key=f"btn_{i}", use_container_width=True):
                        conn = get_db()
                        cursor = conn.cursor()
                        cursor.execute("SELECT quantita FROM prodotti WHERE barcode=?", (prod['cod'],))
                        existing = cursor.fetchone()
                        nuova_qty = prod['qty'] + (existing[0] if existing else 0)
                        
                        conn.execute('''INSERT OR REPLACE INTO prodotti 
                                     (barcode, categoria, componente, marca, quantita, prezzo_acquisto, prezzo_vendita) 
                                     VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                                     (prod['cod'], categoria, prod['desc'], "RMS", nuova_qty, prod['prezzo'], prezzo_v))
                        conn.commit()
                        st.toast(f"✅ {prod['cod']} caricato!")

# --- 5. INVENTARIO (CON FUNZIONE SCARICO) ---
elif menu == "📦 Inventario":
    st.title("📦 Inventario Magazzino")
    
    conn = get_db()
    df_all = pd.read_sql_query("SELECT * FROM prodotti", conn)
    
    if df_all.empty:
        st.warning("Il magazzino è vuoto.")
    else:
        for cat in SETTORI:
            df_cat = df_all[df_all['categoria'] == cat]
            with st.expander(f"📂 {cat} ({len(df_cat)} articoli)", expanded=True):
                if not df_cat.empty:
                    # Tabella riassuntiva
                    df_view = df_cat[['barcode', 'componente', 'quantita', 'prezzo_acquisto']]
                    df_view.columns = ['Codice', 'Descrizione', 'Stock attuale', 'Prezzo Acq.']
                    st.dataframe(df_view, use_container_width=True, hide_index=True)
                    
                    st.write("---")
                    st.write("🔧 **Gestione Scarico (Vendita/Utilizzo):**")
                    
                    # Sezione Scarico Merce
                    for _, r in df_cat.iterrows():
                        col_desc, col_qty, col_btn = st.columns([3, 1, 1])
                        with col_desc:
                            st.write(f"{r['componente']} (Disponibili: {r['quantita']})")
                        with col_qty:
                            n_scarico = st.number_input("Pezzi da togliere", min_value=1, max_value=int(r['quantita']) if r['quantita'] > 0 else 1, key=f"out_qty_{r['barcode']}", label_visibility="collapsed")
                        with col_btn:
                            if st.button("SCARICA", key=f"out_btn_{r['barcode']}", use_container_width=True):
                                if r['quantita'] >= n_scarico:
                                    nuova_qty = r['quantita'] - n_scarico
                                    conn.execute("UPDATE prodotti SET quantita = ? WHERE barcode = ?", (nuova_qty, r['barcode']))
                                    conn.commit()
                                    st.success(f"Scaricato! Nuovo stock: {nuova_qty}")
                                    st.rerun() # Ricarica per aggiornare i numeri
                                else:
                                    st.error("Quantità non sufficiente!")
                else:
                    st.write("Nessun articolo in questa categoria.")
    conn.close()
