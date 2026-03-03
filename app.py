import streamlit as st
import pandas as pd
import sqlite3

# --- CONFIGURAZIONE ---
NOME_OFFICINA = "BIKE LAB MEZZOLOMBARDO"
SETTORI = ["COPERTONI", "PASTIGLIE", "ACCESSORI FRENI", "TRASMISSIONE", "CAMERE D'ARIA", "ACCESSORI TELAIO", "ALTRO"]

def get_db():
    conn = sqlite3.connect('magazzino_v3.db', check_same_thread=False)
    # Aggiorno la tabella per includere i campi richiesti
    conn.execute('''CREATE TABLE IF NOT EXISTS prodotti
                 (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
                  marca TEXT, quantita INTEGER, prezzo_acquisto REAL, 
                  prezzo_vendita REAL)''')
    return conn

st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

# --- LOGICA DI ESTRAZIONE SIMULATA (RMS) ---
def estrai_dati_da_pdf(file):
    # Dati presi dalla tua bolla 2611294.PDF
    dati = [
        {"cod": "9781", "desc": "CARTER CRUISER 46 TRI.ACC.NERO", "qty": 1, "prezzo": 9.48},
        {"cod": "0320", "desc": "CONF.10 FIL.CAMBIO 1,2X3500", "qty": 1, "prezzo": 4.06},
        {"cod": "524", "desc": "CATENA 10V X10 SILVER-BLACK", "qty": 4, "prezzo": 13.74},
        {"cod": "4000", "desc": "Forcellino universale UDH", "qty": 2, "prezzo": 10.00},
        {"cod": "9386", "desc": "Anello chius. BDU4XX/37YY/31YY", "qty": 2, "prezzo": 5.31}
    ]
    return dati

# --- SIDEBAR ---
menu = st.sidebar.radio("Navigazione", ["🏠 Dashboard", "📦 Inventario per Categoria"])

# --- 1. DASHBOARD (CARICO MERCE) ---
if menu == "🏠 Dashboard":
    st.title(f"🚲 {NOME_OFFICINA}")
    
    with st.container():
        st.subheader("📥 INGRESSO MERCE")
        uploaded_file = st.file_uploader("Carica Bolla/Fattura PDF", type=["pdf"])

        if uploaded_file:
            prodotti_rilevati = estrai_dati_da_pdf(uploaded_file)
            st.write(f"### 📋 Documento: {uploaded_file.name}")
            
            for i, prod in enumerate(prodotti_rilevati):
                with st.expander(f"Articolo: {prod['desc']}", expanded=False):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    with c1:
                        cat = st.selectbox("Seleziona Macro-categoria", SETTORI, key=f"cat_{i}")
                    with c2:
                        prezzo_v = st.number_input("Prezzo Vendita Suggerito (€)", value=float(prod['prezzo']*1.6), key=f"pv_{i}")
                    with c3:
                        st.write(" ")
                        if st.button("CARICA", key=f"btn_{i}", use_container_width=True):
                            conn = get_db()
                            # Salviamo i dati nel DB
                            conn.execute('''INSERT OR REPLACE INTO prodotti 
                                         (barcode, categoria, componente, marca, quantita, prezzo_acquisto, prezzo_vendita) 
                                         VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                                         (prod['cod'], cat, prod['desc'], "RMS", prod['qty'], prod['prezzo'], prezzo_v))
                            conn.commit()
                            st.success("Fatto!")

# --- 2. INVENTARIO CON MACROCATEGORIE ---
elif menu == "📦 Inventario per Categoria":
    st.title("📦 Inventario Suddiviso")
    
    conn = get_db()
    # Carichiamo tutti i prodotti
    df_all = pd.read_sql_query("SELECT * FROM prodotti", conn)
    conn.close()
    
    if df_all.empty:
        st.warning("L'inventario è vuoto. Carica una bolla dalla Dashboard.")
    else:
        # Creiamo un expander per ogni Macro-categoria
        for cat in SETTORI:
            df_cat = df_all[df_all['categoria'] == cat]
            
            with st.expander(f"📂 {cat} ({len(df_cat)} articoli)", expanded=True):
                if not df_cat.empty:
                    # Rinominiamo le colonne per chiarezza come richiesto
                    df_view = df_cat[[
                        'barcode', 
                        'componente', 
                        'quantita', 
                        'prezzo_acquisto'
                    ]].copy()
                    
                    df_view.columns = ['Codice Articolo', 'Descrizione', 'Stock / Pezzi Acquistati', 'Prezzo Acquisto (€)']
                    
                    # Visualizzazione Tabella
                    st.dataframe(df_view, use_container_width=True, hide_index=True)
                    
                    # Calcolo Valore Categoria
                    valore_cat = (df_cat['quantita'] * df_cat['prezzo_acquisto']).sum()
                    st.write(f"**Valore totale stock {cat}:** € {valore_cat:,.2f}")
                else:
                    st.text("Nessun articolo presente in questa categoria.")
