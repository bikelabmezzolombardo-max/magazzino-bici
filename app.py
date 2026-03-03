import streamlit as st
import pandas as pd
import sqlite3
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO

# --- CONFIGURAZIONE ---
NOME_OFFICINA = "BIKE LAB"
SETTORI = ["COPERTONI", "PASTIGLIE", "ACCESSORI FRENI", "TRASMISSIONE", "CAMERE D'ARIA", "ACCESSORI TELAIO", "ALTRO"]

def get_connection():
    return sqlite3.connect('magazzino_v3.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS prodotti
                 (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
                  marca TEXT, quantita INTEGER, prezzo_acquisto REAL, prezzo_vendita REAL)''')
    conn.commit()
    conn.close()

init_db()
st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

def genera_etichetta(barcode_val, nome_prod, prezzo):
    try:
        rv = BytesIO()
        Code128(str(barcode_val), writer=ImageWriter()).write(rv)
        return rv
    except: return None

# --- SIDEBAR ---
st.sidebar.title(f"🚲 {NOME_OFFICINA}")
menu = st.sidebar.radio("Menu", ["🏠 Dashboard", "📥 Carico Fatture", "📦 Magazzino & Etichette", "📊 Contabilità"])

# --- 1. DASHBOARD ---
if menu == "🏠 Dashboard":
    st.header(f"Officina {NOME_OFFICINA}")
    db_con = get_connection()
    df = pd.read_sql_query("SELECT * FROM prodotti", db_con)
    db_con.close()
    
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Articoli in DB", len(df))
    with c2: st.metric("Sottoscorta", len(df[df['quantita'] < 3]) if not df.empty else 0)
    with c3: st.metric("Valore Magazzino", f"€ {(df['quantita']*df['prezzo_acquisto']).sum():,.2f}" if not df.empty else "€ 0")

    st.subheader("📲 Scarico Rapido")
    scan = st.text_input("Scansiona Barcode per scaricare (-1)")
    if scan:
        db_con = get_connection()
        res = db_con.execute("SELECT componente, quantita FROM prodotti WHERE barcode=?", (scan,)).fetchone()
        if res:
            st.success(f"Trovato: {res[0]} (Disponibili: {res[1]})")
            if st.button("CONFERMA SCARICO VENDITA"):
                db_con.execute("UPDATE prodotti SET quantita = quantita - 1 WHERE barcode=?", (scan,))
                db_con.commit()
                st.rerun()
        else: st.error("Codice non trovato nel database!")
        db_con.close()

# --- 2. CARICO FATTURE ---
elif menu == "📥 Carico Fatture":
    st.header("Carico Merce")
    st.info("Sincronizzazione Gmail attiva con credenziali Secrets.")

# --- 3. MAGAZZINO (LOGICA DI IMPORTAZIONE MIGLIORATA) ---
elif menu == "📦 Magazzino & Etichette":
    st.header("Gestione Stock")
    
    with st.expander("📥 IMPORTA DA EXCEL/CSV (File Dettagliato)"):
        up = st.file_uploader("Carica il file con l'ELENCO PEZZI", type="csv")
        if up:
            df_up = pd.read_csv(up)
            st.write("Colonne trovate nel tuo file:", list(df_up.columns))
            
            if st.button("AVVIA IMPORTAZIONE"):
                db_con = get_connection()
                # Funzione per cercare le colonne in modo flessibile
                def find(names):
                    for n in names:
                        for col in df_up.columns:
                            if n.lower() in col.lower(): return col
                    return None

                col_map = {
                    'b': find(['barcode', 'codice', 'ean']),
                    'c': find(['cat']),
                    'n': find(['comp', 'nome', 'art']),
                    'm': find(['marca', 'brand']),
                    'q': find(['quant', 'qty', 'pezzi']),
                    'pa': find(['acq', 'costo']),
                    'pv': find(['vend', 'listino'])
                }

                count = 0
                for _, row in df_up.iterrows():
                    # Pulizia categoria
                    cat_val = str(row.get(col_map['c'], 'ALTRO')).upper().replace("TOT.", "").strip()
                    if cat_val not in SETTORI: cat_val = "ALTRO"
                    
                    db_con.execute("INSERT OR REPLACE INTO prodotti VALUES (?,?,?,?,?,?,?)",
                                  (str(row.get(col_map['b'], '')), cat_val, 
                                   str(row.get(col_map['n'], 'Articolo')), str(row.get(col_map['m'], '')),
                                   int(row.get(col_map['q'], 0)), float(row.get(col_map['pa'], 0)),
                                   float(row.get(col_map['pv'], 0))))
                    count += 1
                db_con.commit()
                db_con.close()
                st.success(f"Importati {count} articoli correttamente!")
                st.rerun()

    st.divider()
    set_sel = st.selectbox("Visualizza Settore", SETTORI)
    db_con = get_connection()
    df_m = pd.read_sql_query("SELECT * FROM prodotti WHERE categoria=?", db_con, params=(set_sel,))
    db_con.close()
    
    if not df_m.empty:
        for _, r in df_m.iterrows():
            with st.expander(f"{r['componente']} - Qty: {r['quantita']}"):
                if st.button(f"Genera Etichetta {r['barcode']}", key=r['barcode']):
                    lbl = genera_etichetta(r['barcode'], r['componente'], r['prezzo_vendita'])
                    if lbl: st.image(lbl)
    else: st.info("Nessun articolo trovato per questa categoria.")

# --- 4. CONTABILITÀ ---
elif menu == "📊 Contabilità":
    st.header("Analisi Economica")
    db_con = get_connection()
    df_c = pd.read_sql_query("SELECT * FROM prodotti", db_con)
    db_con.close()
    if not df_c.empty:
        st.metric("Valore Inventario Totale", f"€ {(df_c['quantita']*df_c['prezzo_acquisto']).sum():,.2f}")
        st.bar_chart(df_c.groupby('categoria')['prezzo_acquisto'].sum())
