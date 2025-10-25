import streamlit as st
import pandas as pd
import numpy as np
import pdfplumber
from fpdf import FPDF
import io
import re

st.set_page_config(page_title="DataHub ASP Siena", layout="wide")

# -------------------------
# Stato pagina e login
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "show_upload" not in st.session_state:
    st.session_state.show_upload = False
if "show_manage" not in st.session_state:
    st.session_state.show_manage = False
if "uploaded_files_store" not in st.session_state:
    st.session_state.uploaded_files_store = {}
if "internal_db" not in st.session_state:
    st.session_state.internal_db = {}

# -------------------------
# WELCOME + LOGIN
# -------------------------
st.markdown("<div style='text-align:center'>", unsafe_allow_html=True)
st.title("🧠 DataHub — Centralizzazione intelligente dei dati (MVP)")

# Logo (placeholder)
# st.image("logo_azienda.png", width=150)  # se file locale presente
st.markdown("**Prototipo AI per armonizzare e sincronizzare dati eterogenei**")
st.markdown("</div>", unsafe_allow_html=True)

# Login centrale
col1, col2, col3 = st.columns([1,2,1])
with col2:
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    token = st.text_input("Token WHR-TIME")
    if st.button("Accedi"):
        if token.strip().upper().startswith("WHR"):
            st.session_state.logged_in = True
            st.success("Login effettuato (simulazione MVP).")
        else:
            st.error("Token non valido (deve iniziare con WHR).")

# Pulsante torna indietro in basso a sinistra
st.markdown("<div style='position:fixed; bottom:10px; left:10px'>"
            "<small><a href='#'>← Torna indietro</a></small>"
            "</div>", unsafe_allow_html=True)

if not st.session_state.logged_in:
    st.stop()
st.write("---")
col1, col2, col3 = st.columns([2,2,1])
with col1:
    if st.button("📂 Carica dati"):
        st.session_state.show_upload = True
        st.session_state.show_manage = False
with col2:
    if st.button("🛠️ Gestione dati"):
        st.session_state.show_manage = True
        st.session_state.show_upload = False

# Logout piccolo in basso a sinistra
st.markdown("<div style='position:fixed; bottom:10px; left:10px'>"
            "<small><a href='#' onclick='window.location.reload();'>Logout</a></small>"
            "</div>", unsafe_allow_html=True)
# --- Upload files ---
if st.session_state.show_upload:
    st.header("Caricamento file")
    uploaded = st.file_uploader("Trascina file qui (accetta multipli).", type=["csv","xls","xlsx","pdf","txt"], accept_multiple_files=True)
    if uploaded:
        for f in uploaded:
            if f.name in st.session_state.uploaded_files_store:
                st.warning(f"{f.name} già caricato; salto.")
                continue
            df = read_file(f)
            if df is not None and not df.empty:
                st.session_state.uploaded_files_store[f.name] = df
                st.success(f"Caricato: {f.name} — righe: {len(df)}")
        st.info("File caricati. Vai in 'Gestione dati' per lavorarli.")

# --- Gestione dati ---
if st.session_state.show_manage:
    st.header("Gestione dei dati")
    area = st.selectbox("Seleziona area:", ["Sanitario", "Finanziario", "Amministrativo", "Combinata / Multi-area"])
    
    # Seleziona file da DB interno o Drag&Drop
    db_option = st.radio("Scegli sorgente:", ["DB interno (dati caricati)", "Drag & Drop (carica file)"])
    
    if db_option == "DB interno (dati caricati)":
        # mostra CF rilevati nei file
        cf_index = {}
        for fname, df in st.session_state.uploaded_files_store.items():
            col, cf_val = find_cf_candidates_in_df(df)
            cf_index.setdefault(cf_val, []).append((fname, col))
        cf_keys = [k for k in cf_index.keys() if k]
        if cf_keys:
            cf_choice = st.selectbox("Seleziona CF (dal DB interno):", cf_keys)
            st.write("File con CF rilevato:")
            for fname, col in cf_index[cf_choice]:
                st.write(f"- {fname} (colonna: {col})")
            # armonizzazione
            frames = []
            for fname, col in cf_index[cf_choice]:
                df = st.session_state.uploaded_files_store[fname]
                mask = df[col].astype(str).str.contains(cf_choice, case=False, na=False)
                frames.append(df[mask])
            harmonized = pd.concat(frames, ignore_index=True)
            st.dataframe(harmonized)
            
            # selezione attività
            if area == "Sanitario":
                activity = st.selectbox("Seleziona attività:", ["Visualizza cartella clinica", "Collega a ordine farmacia", "Report spese paziente"])
            elif area == "Finanziario":
                activity = st.selectbox("Seleziona attività:", ["Richiedi pagamento", "Genera fattura PDF", "Prepara email"])
            elif area == "Amministrativo":
                activity = st.selectbox("Seleziona attività:", ["Visualizza riepilogo acquisti", "Analisi consumi mense", "Report personale"])
            else:
                activity = st.selectbox("Funzioni multi-area:", ["Armonizza dati paziente", "Genera fattura completa", "Report multi-paziente", "Controllo qualità / discrepanze"])
            
            # genera Excel con feedback
            if st.button("💾 Genera report Excel"):
                harmonized.to_excel(f"report_{cf_choice}.xlsx", index=False)
                st.success("Salvamento effettuato")
