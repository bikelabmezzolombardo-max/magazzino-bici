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
    # Tabella prodotti con colonna anno_emissione
    conn.execute('''CREATE TABLE IF NOT EXISTS prodotti
                 (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
                  marca TEXT, quantita INTEGER, prezzo_acquisto REAL, 
                  prezzo_vendita REAL, anno_emissione INTEGER)''')
    conn.commit()
    conn.close()

init_db()
st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

# --- FUNZIONE GENERAZIONE ETICHETTA ---
def genera_etichetta(barcode_val):
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
    
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Articoli in Stock", len(df))
    with col2: st.metric("Sottoscorta (<3)", len(df[df['quantita'] < 3]) if not df.empty else 0)
    with col3: 
        valore = (df['quantita'] * df['prezzo_acquisto']).sum() if not df.empty else 0
        st.metric("Valore Magazzino", f"€ {valore:,.2f}")

# --- 2. CARICO FATTURE (FILTRO ANNO) ---
elif menu == "📥 Carico Fatture (Gmail/OCR)":
    st.header("Ricerca Fatture Fornitori")
    anno_attuale = datetime.datetime.now().year
    anno_sel = st.number_input("Anno di emissione da cercare", min_value=2020, max_value=2030, value=anno_attuale)
    
    t1, t2 = st.tabs(["📧 Gmail Sync", "📷 Carica Documento"])
    with t1:
        st.write(f"Cerco fatture emesse nell'anno: **{anno_sel}**")
        if st.button(f"Scansiona Gmail {anno_sel}"):
            st.info(f"Ricerca email con filtri temporali per l'anno {anno_sel}...")
    with t2:
        up = st.file_uploader("Trascina file qui", type=['pdf', 'jpg', 'png'])

# --- 3. MAGAZZINO & IMPORTAZIONE ---
elif menu == "📦 Magazzino & Etichette":
    st.header("Gestione Giacenze")
    
    with st.expander("📥 Importa Inventario da CSV"):
        up_csv = st.file_uploader("Seleziona file .csv", type="csv")
        if up_csv:
            df_up = pd.read_csv(up_csv)
            if st.button("ESEGUI IMPORTAZIONE"):
                db_con = get_connection()
                # Funzione per trovare le colonne
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
                                   anno_sel if 'anno_sel' in locals() else anno_attuale))
                db_con.commit()
                db_con.close()
                st.success("Importazione completata!")

    st.divider()
    sel_set = st.selectbox("Filtra per Settore", SETTORI)
    db_con = get_connection()
    df_m = pd.read_sql_query("SELECT * FROM prodotti WHERE categoria=?", db_con, params=(sel_set,))
    db_con.close()
    
    if not df_m.empty:
        for _, r in df_m.iterrows():
            with st.expander(f"{r['componente']} - Qty: {r['quantita']}"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"Prezzo Vendita: €{r['prezzo_vendita']:.2f}")
                with col2:
                    if st.button(f"Etichetta {r['barcode']}", key=f"btn_{r['barcode']}"):
                        img = genera_etichetta(r['barcode'])
                        if img:
                            st.image(img, caption=f"Prezzo: €{r['prezzo_vendita']:.2f}")
    else:
        st.info("Nessun articolo trovato.")

# --- 4. CONTABILITÀ ---
elif menu == "📊 Contabilità":
    st.header("Analisi Economica")
    db_con = get_connection()
    df_c = pd.read_sql_query("SELECT * FROM prodotti", db_con)
    db_con.close()
    if not df_c.empty:
        valore_inv = (df_c['quantita'] * df_c['prezzo_acquisto']).sum()
        st.metric("Valore Totale Inventario (Costo)", f"€ {valore_inv:,.2f}")
        st.bar_chart(df_c.groupby('categoria')['prezzo_acquisto'].sum())
