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

st.set_page_config(page_title=NOME_OFFICINA, layout="wide", page_icon="🚲")

# --- LOGICA DI ESTRAZIONE (Simulata per il tuo PDF RMS) ---
def estrai_dati_da_pdf(file):
    # In una fase successiva qui useremo PyPDF2 o simili. 
    # Ora lo impostiamo per leggere i dati che abbiamo visto nel tuo file 2611294.PDF
    dati = [
        {"cod": "9781", "desc": "CARTER CRUISER 46 TRI.ACC.NERO", "qty": 1, "prezzo": 9.48},
        {"cod": "0320", "desc": "CONF.10 FIL.CAMBIO 1,2X3500", "qty": 1, "prezzo": 4.06},
        {"cod": "524", "desc": "CATENA 10V X10 SILVER-BLACK", "qty": 4, "prezzo": 13.74},
        {"cod": "9386", "desc": "ANELLO CHIUS. BDU4XX/37YY/31YY", "qty": 2, "prezzo": 5.31}
    ]
    return dati

# --- INTERFACCIA ---
st.title(f"🚲 {NOME_OFFICINA} - Dashboard")

# Sezione Carico Merce
with st.container():
    st.subheader("📥 INGRESSO MERCE")
    uploaded_file = st.file_uploader("Carica Bolla/Fattura PDF", type=["pdf"])

    if uploaded_file:
        prodotti_rilevati = estrai_dati_da_pdf(uploaded_file)
        st.write(f"### 📋 Prodotti trovati nel documento: {uploaded_file.name}")
        st.info("Assegna una categoria e conferma l'inserimento per ogni riga.")

        # Tabella di catalogazione
        for i, prod in enumerate(prodotti_rilevati):
            with st.expander(f"📦 {prod['desc']} (Cod: {prod['cod']})", expanded=True):
                c1, c2, c3, c4, c5 = st.columns([1, 2, 2, 1, 1])
                
                with c1:
                    st.text_input("Codice", prod['cod'], key=f"cod_{i}", disabled=True)
                with c2:
                    st.text_input("Descrizione", prod['desc'], key=f"desc_{i}")
                with c3:
                    cat = st.selectbox("Categoria", SETTORI, key=f"cat_{i}")
                with c4:
                    prezzo_v = st.number_input("Prezzo Vendita €", value=float(prod['prezzo']*1.6), key=f"pv_{i}")
                with c5:
                    st.write(" ") # Spazio per allineare il tasto
                    if st.button("✅ CARICA", key=f"btn_{i}"):
                        conn = get_db()
                        conn.execute('''INSERT OR REPLACE INTO prodotti 
                                     (barcode, categoria, componente, marca, quantita, prezzo_acquisto, prezzo_vendita) 
                                     VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                                     (prod['cod'], cat, prod['desc'], "RMS", prod['qty'], prod['prezzo'], prezzo_v))
                        conn.commit()
                        st.success("Ok!")

st.divider()

# Visualizzazione Magazzino
st.subheader("📦 Giacenze attuali")
conn = get_db()
df_inv = pd.read_sql_query("SELECT * FROM prodotti", conn)
if not df_inv.empty:
    st.dataframe(df_inv, use_container_width=True, hide_index=True)
else:
    st.write("Il magazzino è vuoto. Carica una bolla per iniziare.")
