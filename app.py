import streamlit as st
import pandas as pd
import sqlite3
from PIL import Image
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO

# --- CONFIGURAZIONE OFFICINA (Basata sul tuo resoconto) ---
NOME_OFFICINA = "BIKE LAB"
SETTORI = [
    "COPERTONI", 
    "PASTIGLIE", 
    "ACCESSORI FRENI", 
    "TRASMISSIONE", 
    "CAMERE D'ARIA", 
    "ACCESSORI TELAIO",
    "ALTRO"
]

# --- FUNZIONI DATABASE ---
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

# --- FUNZIONE GENERAZIONE ETICHETTA ---
def genera_etichetta(barcode_val, nome_prod, prezzo):
    try:
        rv = BytesIO()
        Code128(str(barcode_val), writer=ImageWriter()).write(rv)
        return rv
    except Exception:
        return None

# --- SIDEBAR NAVIGAZIONE ---
st.sidebar.title(f"🚲 {NOME_OFFICINA}")
menu = st.sidebar.radio("Menu principale", ["🏠 Dashboard", "📥 Carico Fatture (Gmail/OCR)", "📦 Magazzino & Etichette", "📊 Contabilità"])

# --- SEZIONE 1: DASHBOARD ---
if menu == "🏠 Dashboard":
    st.header(f"Gestione Operativa {NOME_OFFICINA}")
    
    db_con = get_connection()
    df = pd.read_sql_query("SELECT * FROM prodotti", db_con)
    db_con.close()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Articoli Totali", len(df))
    with col2:
        sottoscorta = len(df[df['quantita'] < 3]) if not df.empty else 0
        st.metric("Allerta Sottoscorta", sottoscorta)
    with col3:
        val_acq = (df['quantita'] * df['prezzo_acquisto']).sum() if not df.empty else 0
        st.metric("Valore Attuale", f"€ {val_acq:,.2f}")

    st.divider()
    
    st.subheader("📲 Scarico Rapido Barcode")
    barcode_scan = st.text_input("Scansiona per scaricare (-1)", placeholder="Inquadra il codice...")
    if barcode_scan:
        db_con = get_connection()
        c = db_con.cursor()
        c.execute("SELECT componente, quantita FROM prodotti WHERE barcode=?", (barcode_scan,))
        res = c.fetchone()
        if res:
            st.info(f"Articolo: **{res[0]}** | Stock attuale: {res[1]}")
            if st.button("CONFERMA SCARICO", use_container_width=True):
                c.execute("UPDATE prodotti SET quantita = quantita - 1 WHERE barcode=?", (barcode_scan,))
                db_con.commit()
                st.success("Giacenza aggiornata!")
                st.rerun()
        else:
            st.error("Codice non trovato.")
        db_con.close()

# --- SEZIONE 2: CARICO FATTURE ---
elif menu == "📥 Carico Fatture (Gmail/OCR)":
    st.header("Automazione Carico")
    t1, t2 = st.tabs(["📧 Gmail", "📷 Foto Fattura"])
    with t1:
        st.write("Sincronizzazione fatture fornitori...")
        if st.button("Sincronizza ora"):
            st.info("Ricerca allegati PDF in corso...")
    with t2:
        up = st.file_uploader("Carica PDF o Immagine", type=['png', 'jpg', 'pdf'])
        if up:
            st.image(up, width=300)

# --- SEZIONE 3: MAGAZZINO E ETICHETTE ---
elif menu == "📦 Magazzino & Etichette":
    st.header("Giacenze e Stampa Etichette")
    
    with st.expander("📥 Importa Inventario da CSV (Fogli Google)"):
        uploaded_csv = st.file_uploader("Carica file .csv", type="csv")
        if uploaded_csv:
            df_import = pd.read_csv(uploaded_csv)
            st.write("Anteprima dati caricati:")
            st.dataframe(df_import.head())
            
            if st.button("ESEGUI IMPORTAZIONE"):
                db_con = get_connection()
                c = db_con.cursor()
                
                # Funzione per trovare le colonne anche se i nomi variano
                def find_col(possible_names, default_val):
                    for col in df_import.columns:
                        if any(name.lower() in col.lower() for name in possible_names):
                            return col
                    return None

                col_map = {
                    'barcode': find_col(['barcode', 'codice'], 'Barcode'),
                    'cat': find_col(['cat'], 'Categoria'),
                    'comp': find_col(['comp', 'nome', 'art'], 'Componente'),
                    'marca': find_col(['marca', 'brand'], 'Marca'),
                    'qty': find_col(['quant', 'qty', 'pezzi'], 'Quantita'),
                    'prezzo_a': find_col(['acq', 'costo'], 'Prezzo_Acquisto'),
                    'prezzo_v': find_col(['vend', 'listino'], 'Prezzo_Vendita')
                }

                for _, row in df_import.iterrows():
                    cat_raw = str(row.get(col_map['cat'], 'ALTRO')).upper()
                    clean_cat = cat_raw.replace("TOT.", "").strip()
                    if clean_cat not in SETTORI: clean_cat = "ALTRO"

                    c.execute('''INSERT OR REPLACE INTO prodotti VALUES (?,?,?,?,?,?,?)''', 
                              (str(row.get(col_map['barcode'], '')), 
                               clean_cat, 
                               str(row.get(col_map['comp'], 'Articolo')), 
                               str(row.get(col_map['marca'], '')), 
                               int(row.get(col_map['qty'], 0)), 
                               float(row.get(col_map['prezzo_a'], 0.0)), 
                               float(row.get(col_map['prezzo_v'], 0.0))))
                db_con.commit()
                db_con.close()
                st.success("Importazione completata con successo!")
                st.rerun()

    st.divider()
    sel_settore = st.selectbox("Seleziona Settore da visualizzare", SETTORI)
    db_con = get_connection()
    df_m = pd.read_sql_query("SELECT * FROM prodotti WHERE categoria=?", db_con, params=(sel_settore,))
    db_con.close()
    
    if not df_m.empty:
        for idx, row in df_m.iterrows():
            with st.expander(f"📦 {row['componente']} - Qty: {row['quantita']}"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.write(f"**Marca:** {row['marca']} | **Prezzo:** €{row['prezzo_vendita']:.2f}")
                with c2:
                    if st.button("🖨️ Etichetta", key=f"p_{row['barcode']}"):
                        lbl = genera_etichetta(row['barcode'], row['componente'], row['prezzo_vendita'])
                        if lbl:
                            st.image(lbl, caption=f"Prezzo: €{row['prezzo_vendita']}")
                            st.download_button("Salva", lbl, f"etichetta_{row['barcode']}.png")
    else:
        st.info(f"Nessun articolo nel settore {sel_settore}")

# --- SEZIONE 4: CONTABILITÀ ---
elif menu == "📊 Contabilità":
    st.header("Analisi Economica")
    db_con = get_connection()
    df_c = pd.read_sql_query("SELECT * FROM prodotti", db_con)
    db_con.close()
    if not df_c.empty:
        tot_acq = (df_c['quantita'] * df_c['prezzo_acquisto']).sum()
        st.metric("Valore Totale Inventario (Costo)", f"€ {tot_acq:,.2f}")
        st.subheader("Suddivisione per Categoria")
        st.bar_chart(df_c.groupby('categoria')['prezzo_acquisto'].sum())
