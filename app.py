import streamlit as st
import pandas as pd
import sqlite3
import datetime
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO

# --- CONFIGURAZIONE ---
NOME_OFFICINA = "BIKE LAB"
SETTORI = ["COPERTONI", "PASTIGLIE", "ACCESSORI FRENI", "TRASMISSIONE", "CAMERE D'ARIA", "ACCESSORI TELAIO", "ALTRO"]

# --- FUNZIONI DATABASE ---
def get_connection():
    return sqlite3.connect('magazzino_v3.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    # Aggiunta colonna anno_emissione per tracciamento fatture
    conn.execute('''CREATE TABLE IF NOT EXISTS prodotti
                 (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
                  marca TEXT, quantita INTEGER, prezzo_acquisto REAL, 
                  prezzo_vendita REAL, anno_emissione INTEGER)''')
    conn.commit()
    conn.close()

init_db()
st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

# --- FUNZIONE GENERAZIONE ETICHETTA ---
def genera_etichetta(barcode_val, prezzo):
    try:
        rv = BytesIO()
        Code128(str(barcode_val), writer=ImageWriter()).write(rv)
        return rv
    except:
        return None

# --- SIDEBAR ---
st.sidebar.title(f"🚲 {NOME_OFFICINA}")
menu = st.sidebar.radio("Menu principale", ["🏠 Dashboard", "📥 Carico Fatture (Gmail/OCR)", "📦 Magazzino & Etichette", "📊 Contabilità"])

# --- 1. DASHBOARD ---
if menu == "🏠 Dashboard":
    st.header(f"Gestione Operativa {NOME_OFFICINA}")
    db_con = get_connection()
    df = pd.read_sql_query("SELECT * FROM prodotti", db_con)
    db_con.close()
    
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Articoli in Stock", len(df))
    with c2: st.metric("Sottoscorta (<3)", len(df[df['quantita'] < 3]) if not df.empty else 0)
    with c3: 
        valore = (df['quantita'] * df['prezzo_acquisto']).sum() if not df.empty else 0
        st.metric("Valore Magazzino", f"€ {valore:,.2f}")

# --- 2. CARICO FATTURE (CON FILTRO ANNO) ---
elif menu == "📥 Carico Fatture (Gmail/OCR)":
    st.header("Ricerca Fatture Fornitori")
    
    # Filtro anno richiesto
    anno_attuale = datetime.datetime.now().year
    anno_sel = st.number_input("Anno di emissione da filtrare", min_value=2020, max_value=2030, value=anno_attuale)
    
    t1, t2 = st.tabs(["📧 Sincronizzazione Gmail", "📷 Carica PDF/Foto"])
    with t1:
        st.write(f"Ricerca email con fatture emesse nel **{anno_sel}**")
        if st.button(f"Avvia scansione Gmail {anno_sel}"):
            st.info(f"Connessione ai server Google... Filtro impostato: dopo 01/01/{anno_sel}")
            # Qui si attiverà la logica Gmail con i Secrets
            
    with t2:
        up = st.file_uploader("Trascina qui la fattura", type=['pdf', 'jpg', 'png'])
        if up: st.success("File pronto per l'analisi OCR")

# --- 3. MAGAZZINO & IMPORTAZIONE ---
elif menu == "📦 Magazzino & Etichette":
    st.header("Gestione Giacenze")
    
    with st.expander("📥 Importa Inventario da CSV"):
        up_csv = st.file_uploader("Carica il file .csv", type="csv")
        if up_csv:
            df_up = pd.read_csv(up_csv)
            st.write("Colonne trovate:", list(df_up.columns))
            
            if st.button("ESEGUI IMPORTAZIONE"):
                db_con = get_connection()
                def find(keys):
                    for k in keys:
                        for c in df_up.columns:
                            if k.lower() in c.lower(): return c
                    return None

                for _, row in df_up.iterrows():
                    cat = str(row.get(find(['cat']), 'ALTRO')).upper().replace("TOT.", "").strip()
                    if cat not in SETTORI: cat = "ALTRO"
                    
                    db_con.execute('''INSERT OR REPLACE INTO prodotti VALUES (?,?,?,?,?,?,?,?)''',
                                  (str(row.get(find(['barcode', 'codice']), '')), cat,
                                   str(row.get(find(['comp', 'art']), 'Articolo')),
                                   str(row.get(find(['marca', 'brand']), '')),
                                   int(row.get(find(['qty', 'quant']), 0)),
                                   float(row.get(find(['acq', 'costo']), 0)),
                                   float(row.get(find(['vend', 'listino']), 0)),
                                   anno_sel))
                db_con.commit()
                db_con.close()
                st.success("Importazione completata!")

    st.divider()
    sel_set = st.selectbox("Seleziona Settore", SETTORI)
    db_con = get_connection()
    df_m = pd.read_sql_query("SELECT * FROM prodotti WHERE categoria=?", db_con, params=(sel_set,))
    db_con.close()
    
    if not df_m.empty:
        for _, r in df_m.iterrows():
            with st.expander(f"{r['componente']} - Qty: {r['quantita']}"):
                if st.button(f"Stampa {r['barcode']}", key=r['barcode']):
                    img = genera_etichetta(r['barcode'], r['prezzo_vendita'])
                    if img: st.image(img, caption=f"Prezzo: €{r
