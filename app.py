import streamlit as st
import pandas as pd
import sqlite3

# --- CONFIGURAZIONE ---
NOME_OFFICINA = "BIKE LAB MEZZOLOMBARDO"
SETTORI = ["COPERTONI", "PASTIGLIE", "ACCESSORI FRENI", "TRASMISSIONE", "CAMERE D'ARIA", "ACCESSORI TELAIO", "ALTRO"]

def get_db():
    conn = sqlite3.connect('magazzino_v3.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS prodotti
                 (barcode TEXT PRIMARY KEY, categoria TEXT, componente TEXT, 
                  marca TEXT, quantita INTEGER, prezzo_acquisto REAL, 
                  prezzo_vendita REAL)''')
    return conn

st.set_page_config(page_title=NOME_OFFICINA, layout="wide")

# --- SIDEBAR ---
menu = st.sidebar.radio("Navigazione", ["🏠 Dashboard", "📦 Inventario Completo"])

# --- 1. DASHBOARD E INGRESSO MERCE ---
if menu == "🏠 Dashboard":
    st.title(f"🚲 {NOME_OFFICINA}")
    
    # Tasto Ingresso Merce
    with st.expander("📥 INGRESSO MERCE (Carica Fattura/Bolla)", expanded=True):
        uploaded_file = st.file_uploader("Trascina qui il file PDF di RMS o altri fornitori", type=["pdf"])
        
        if uploaded_file is not None:
            # Simulazione estrazione dati basata sul file 2611294.PDF (RMS)
            st.info(f"Documento {uploaded_file.name} caricato. Anteprima prodotti trovati:")
            
            # Dati estratti dall'esempio fornito 
            dati_anteprima = [
                {"codice": "9781", "descrizione": "CARTER CRUISER 46 TRI.ACC.NERO", "qty": 1, "prezzo": 9.48},
                {"codice": "0320", "descrizione": "CONF.10 FIL.CAMBIO 1,2X3500", "qty": 1, "prezzo": 4.06},
                {"codice": "524", "descrizione": "CATENA 10V X10 SILVER-BLACK", "qty": 4, "prezzo": 13.74},
                {"codice": "4000", "descrizione": "Forcellino universale UDH", "qty": 2, "prezzo": 10.00}
            ]
            
            df_temp = pd.DataFrame(dati_anteprima)
            
            # Tabella per catalogazione rapida
            for index, row in df_temp.iterrows():
                col1, col2, col3, col4 = st.columns([2, 3, 2, 2])
                with col1:
                    st.write(f"**Cod:** {row['codice']}")
                with col2:
                    st.write(f"{row['descrizione']}")
                with col3:
                    categoria = st.selectbox(f"Settore", SETTORI, key=f"cat_{index}")
                with col4:
                    if st.button(f"Carica {row['codice']}", key=f"save_{index}"):
                        conn = get_db()
                        conn.execute('''INSERT OR REPLACE INTO prodotti 
                                     (barcode, categoria, componente, marca, quantita, prezzo_acquisto, prezzo_vendita) 
                                     VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                                     (row['codice'], categoria, row['descrizione'], "RMS", row['qty'], row['prezzo'], row['prezzo']*1.5))
                        conn.commit()
                        st.success(f"Registrato!")

    st.divider()
    st.subheader("Stato Magazzino Rapido")
    # (Qui andranno le metriche totali come prima)

# --- 2. INVENTARIO ---
elif menu == "📦 Inventario Completo":
    st.header("Lista Prodotti a Sistema")
    conn = get_db()
    df_inv = pd.read_sql_query("SELECT * FROM prodotti", conn)
    st.dataframe(df_inv, use_container_width=True)
