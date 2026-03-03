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
menu = st.sidebar.radio("Menu principale", ["🏠 Dashboard", "📥 Carico Fatture & DDT", "📦 Magazzino & Etichette", "📊 Contabilità"])

# --- 1. DASHBOARD ---
if menu == "🏠 Dashboard":
    st.header(f"Gestione Operativa {NOME_OFFICINA}")
    
    db_con = get_connection()
    df_all = pd.read_sql_query("SELECT * FROM prodotti", db_con)
    db_con.close()
    
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Articoli Totali", len(df_all))
    with col2: st.metric("Sottoscorta (<3)", len(df_all[df_all['quantita'] < 3]) if not df_all.empty else 0)
    with col3: 
        val_inv = (df_all['quantita'] * df_all['prezzo_acquisto']).sum() if not df_all.empty else 0
        st.metric("Valore Magazzino", f"€ {val_inv:,.2f}")

    st.divider()

    st.subheader("📁 Visualizzazione Rapida per Categoria")
    cols = st.columns(4)
    for i, settore in enumerate(SETTORI):
        if cols[i % 4].button(settore, use_container_width=True):
            st.session_state['cat_selezionata'] = settore

    if 'cat_selezionata' in st.session_state:
        sel = st.session_state['cat_selezionata']
        st.markdown(f"### 📦 Articoli in: **{sel}**")
        df_cat = df_all[df_all['categoria'] == sel]
        if not df_cat.empty:
            st.dataframe(df_cat[['componente', 'marca', 'quantita', 'prezzo_vendita']], use_container_width=True, hide_index=True)
        else:
            st.info(f"Nessun articolo trovato in {sel}.")

# --- 2. CARICO FATTURE, DDT E BOLLE ---
elif menu == "📥 Carico Fatture & DDT":
    st.header("Ricerca Documenti di Trasporto e Fatture")
    
    anno_attuale = datetime.datetime.now().year
    anno_sel = st.number_input("Seleziona anno di emissione", min_value=2020, max_value=2030, value=anno_attuale)
    
    st.info(f"L'app cercherà email contenenti 'Fattura', 'DDT', 'Bolla' o 'Documento di trasporto' emessi nel {anno_sel}")
    
    t1, t2 = st.tabs(["📧 Ricerca in Gmail", "📷 Caricamento Manuale"])
    
    with t1:
        st.write(f"Scansione Gmail per documenti {anno_sel}...")
        if st.button("Avvia ricerca automatica"):
            # Logica di ricerca: (DDT OR Bolla OR Fattura) after:YYYY-01-01
            st.warning(f"Ricerca in corso: 'DDT' o 'Bolla' dopo il 01/01/{anno_sel}...")
            # Qui si interfaccia con i Google Secrets per la ricerca effettiva
            
    with t2:
        up = st.file_uploader("Carica scansione DDT o Fattura", type=['pdf', 'jpg', 'png'])
        if up:
            st.success("Documento pronto per l'estrazione dati OCR.")

# --- 3. MAGAZZINO & IMPORTAZIONE ---
elif menu == "📦 Magazzino & Etichette":
    st.header("Gestione Giacenze")
    
    with st.expander("📥 Importa Inventario da CSV"):
        up_csv = st.file_uploader("Carica file .csv", type="csv")
        if up_csv:
            df_up = pd.read_csv(up_csv)
            if st.button("ESEGUI IMPORTAZIONE"):
                db_con = get_connection()
                def find(keys):
                    for k in keys:
                        for c in df_up.columns:
                            if k.lower() in c.lower(): return c
                    return None

                for _, row in df_up.iterrows():
                    raw_cat = str(row.get(find(['cat']), 'ALTRO')).upper().replace("TOT.", "").strip()
                    clean_cat = raw_cat if raw_cat in SETTORI else "ALTRO"
                    
                    db_con.execute('''INSERT OR REPLACE INTO prodotti VALUES (?,?,?,?,?,?,?,?)''',
                                  (str(row.get(find(['barcode', 'codice']), '')), clean_cat,
                                   str(row.get(find(['comp', 'art']), 'Articolo')),
                                   str(row.get(find(['marca', 'brand']), '')),
                                   int(row.get(find(['qty', 'quant']), 0)),
                                   float(row.get(find(['acq', 'costo']), 0.0)),
                                   float(row.get(find(['vend', 'listino']), 0.0)),
                                   anno_sel if 'anno_sel' in locals() else anno_attuale))
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
                if st.button(f"Stampa {r['barcode']}", key=f"btn_{r['barcode']}"):
                    img = genera_etichetta(r['barcode'])
                    if img:
                        st.image(img, caption=f"Prezzo: €{r['prezzo_vendita']:.2f}")

# --- 4. CONTABILITÀ ---
elif menu == "📊 Contabilità":
    st.header("Analisi Economica")
    db_con = get_connection()
    df_c = pd.read_sql_query("SELECT * FROM prodotti", db_con)
    db_con.close()
    if not df_c.empty:
        val_tot = (df_c['quantita'] * df_c['prezzo_acquisto']).sum()
        st.metric("Valore Totale Inventario (Costo)", f"€ {val_tot:,.2f}")
        st.bar_chart(df_c.groupby('categoria')['prezzo_acquisto'].sum())
