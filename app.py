import streamlit as st
import pandas as pd
import sqlite3
import datetime
import os
from barcode import Code128
from barcode.writer import ImageWriter
from io import BytesIO
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# --- CONFIGURAZIONE ---
NOME_OFFICINA = "BIKE LAB MEZZOLOMBARDO"
SETTORI = ["COPERTONI", "PASTIGLIE", "ACCESSORI FRENI", "TRASMISSIONE", "CAMERE D'ARIA", "ACCESSORI TELAIO", "ALTRO"]
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

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

# --- FUNZIONE GENERAZIONE ETICHETTA ---
def genera_etichetta(barcode_val):
    try:
        rv = BytesIO()
        Code128(str(barcode_val), writer=ImageWriter()).write(rv)
        return rv
    except Exception:
        return None

# --- LOGICA GMAIL ---
def get_gmail_service():
    if "google_credentials" not in st.secrets:
        st.error("Configura 'google_credentials' nei Secrets di Streamlit!")
        return None
    creds_dict = dict(st.secrets["google_credentials"])
    creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
    return build('gmail', 'v1', credentials=creds)

# --- INIZIALIZZAZIONE ---
init_db()
st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

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
        if cols[i % 4].button(settore, key=f"btn_cat_{settore}", use_container_width=True):
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
    st.header("Ricerca Documenti da Gmail")
    anno_sel = st.number_input("Anno di riferimento", 2024, 2026, 2025)
    
    t1, t2 = st.tabs(["📧 Ricerca Automatica", "📷 Caricamento Manuale"])
    
    with t1:
        if st.button("Avvia Scansione Gmail (RMS, Fatture, DDT)"):
            service = get_gmail_service()
            if service:
                # Query ottimizzata per trovare la fattura RMS specifica
                query = f'after:{anno_sel}/01/01 "RMS" OR "Fattura" OR "DDT" OR "Invoice" has:attachment'
                results = service.users().messages().list(userId='me', q=query).execute()
                messages = results.get('messages', [])
                
                if not messages:
                    st.warning("Nessun documento trovato.")
                else:
                    for msg in messages:
                        m_data = service.users().messages().get(userId='me', id=msg['id']).execute()
                        subj = next(h['value'] for h in m_data['payload']['headers'] if h['name'] == 'Subject')
                        st.write(f"📄 **{subj}**")
                        if st.button("Analizza", key=msg['id']):
                            st.info("Estrazione dati in corso...")

    with t2:
        up = st.file_uploader("Carica PDF/Immagine manualmente", type=['pdf', 'jpg', 'png'])
        if up: st.success("Documento pronto per l'analisi.")

# --- 3. MAGAZZINO & ETICHETTE ---
elif menu == "📦 Magazzino & Etichette":
    st.header("Gestione Giacenze")
    
    with st.expander("📥 Importa Inventario da CSV"):
        up_csv = st.file_uploader("Carica file .csv", type="csv")
        if up_csv:
            df_up = pd.read_csv(up_csv)
            if st.button("ESEGUI IMPORTAZIONE"):
                db_con = get_connection()
                # Logica semplificata per inserimento
                for _, row in df_up.iterrows():
                    db_con.execute('''INSERT OR REPLACE INTO prodotti VALUES (?,?,?,?,?,?,?,?)''',
                                  (str(row.get('barcode', '')), str(row.get('categoria', 'ALTRO')),
                                   str(row.get('componente', 'Articolo')), str(row.get('marca', '')),
                                   int(row.get('quantita', 0)), float(row.get('acquisto', 0.0)),
                                   float(row.get('vendita', 0.0)), 2025))
                db_con.commit()
                db_con.close()
                st.success("Importazione completata!")

    st.divider()
    sel_set = st.selectbox("Seleziona Settore da visualizzare", SETTORI)
    db_con = get_connection()
    df_m = pd.read_sql_query("SELECT * FROM prodotti WHERE categoria=?", db_con, params=(sel_set,))
    db_con.close()
    
    if not df_m.empty:
        for _, r in df_m.iterrows():
            with st.expander(f"{r['componente']} - Qty: {r['quantita']}"):
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    st.write(f"**Barcode:** {r['barcode']} | **Prezzo:** €{r['prezzo_vendita']:.2f}")
                with col_b:
                    if st.button(f"Genera Barcode", key=f"bc_{r['barcode']}"):
                        img_io = genera_etichetta(r['barcode'])
                        if img_io: st.image(img_io)

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
