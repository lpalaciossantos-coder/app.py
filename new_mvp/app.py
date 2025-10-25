# app_mvp_v2.py
import streamlit as st
import pandas as pd
import pdfplumber
from fpdf import FPDF
import re
import io

# -------------------------
# PAGINA CORRENTE E NAVIGAZIONE
# -------------------------
if "page" not in st.session_state:
    st.session_state.page = "welcome"

def go_to(page_name: str):
    st.session_state.page = page_name
    st.rerun()

# -------------------------
# SESSION STATE
# -------------------------
if "uploaded_files_store" not in st.session_state:
    st.session_state.uploaded_files_store = {}
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "show_upload" not in st.session_state:
    st.session_state.show_upload = False
if "show_manage" not in st.session_state:
    st.session_state.show_manage = False

# -------------------------
# HELPERS
# -------------------------
CF_REGEX = re.compile(r'\b[A-Z0-9]{16}\b', flags=re.IGNORECASE)

def read_file(uploaded_file):
    try:
        name = uploaded_file.name.lower()
        if name.endswith(".csv") or name.endswith(".txt"):
            return pd.read_csv(uploaded_file)
        elif name.endswith((".xls", ".xlsx")):
            return pd.read_excel(uploaded_file)
        elif name.endswith(".pdf"):
            return extract_table_from_pdf(uploaded_file)
    except:
        return None

def extract_table_from_pdf(uploaded_pdf):
    tables = []
    try:
        with pdfplumber.open(uploaded_pdf) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    df = df.loc[:, ~df.columns.duplicated()]
                    tables.append(df)
    except:
        return pd.DataFrame()
    if tables:
        return pd.concat(tables, ignore_index=True)
    return pd.DataFrame()

def normalize_columns(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def find_cf_candidates_in_df(df):
    for col in df.columns:
        vals = df[col].dropna().astype(str).str.upper().str.strip()
        for v in vals:
            if CF_REGEX.match(v):
                return col, v
    return None, None

# -------------------------
# WELCOME PAGE
# -------------------------
if st.session_state.page == "welcome":
    st.image("logo_azienda.png", width=150)  # spazio per il logo
    st.title("🧠 DataHub MVP - ASP Siena")
    st.write("""
        Prototipo AI per armonizzare e sincronizzare dati eterogenei.
        \nCarica file, armonizza dati e genera report per pazienti.
    """)
    st.write("✨ Benvenuto! Inizia cliccando il pulsante per accedere.")
    if st.button("Accedi al portale"):
        go_to("login")

# -------------------------
# LOGIN PAGE
# -------------------------
elif st.session_state.page == "login":
    st.header("Login area riservata")
    col1, col2 = st.columns([2,1])
    with col1:
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        token = st.text_input("Token WHR-TIME")
        if st.button("Entra"):
            if token.strip().upper().startswith("WHR"):
                st.success("Login effettuato!")
                st.session_state.logged_in = True
                go_to("main_menu")
            else:
                st.error("Token non valido")
    with col2:
        if st.button("← Torna indietro"):
            go_to("welcome")

if not st.session_state.logged_in:
    st.stop()

# -------------------------
# MAIN MENU
# -------------------------
elif st.session_state.page == "main_menu":
    st.header("Menu principale")
    col1, col2 = st.columns([2,2])
    with col1:
        if st.button("📂 Carica dati"):
            go_to("upload")
    with col2:
        if st.button("🛠️ Gestione dati"):
            go_to("manage")
    st.button("🔒 Logout", key="logout_main", on_click=lambda: go_to("welcome"))

# -------------------------
# UPLOAD PAGE
# -------------------------
elif st.session_state.page == "upload":
    st.header("Caricamento file")
    uploaded = st.file_uploader("Trascina file qui", type=["csv","xls","xlsx","pdf","txt"], accept_multiple_files=True)
    if uploaded:
        for f in uploaded:
            if f.name in st.session_state.uploaded_files_store:
                st.warning(f"{f.name} già caricato")
                continue
            df = read_file(f)
            if df is not None and not df.empty:
                df = normalize_columns(df)
                st.session_state.uploaded_files_store[f.name] = df
                st.success(f"Caricato: {f.name} righe: {len(df)}")
            else:
                st.warning(f"File {f.name} non leggibile")
    if st.button("← Torna al menu"):
        go_to("main_menu")

# -------------------------
# GESTIONE DATI
# -------------------------
elif st.session_state.page == "manage":
    st.header("Gestione dati")
    area = st.radio("Seleziona area:", ["Sanitario","Finanziario","Amministrativo","Combinata / Multi-area"])
    db_option = st.radio("Sorgente dati:", ["DB interno","Drag & Drop"])
    
    if db_option=="Drag & Drop":
        files = st.file_uploader("Carica 2 file per CF del paziente", type=["csv","xls","xlsx","pdf","txt"], accept_multiple_files=True)
        if files:
            temp = {}
            cf_values = {}
            for f in files[:2]:
                df = read_file(f)
                if df is not None and not df.empty:
                    df = normalize_columns(df)
                    temp[f.name] = df
                    col, cf = find_cf_candidates_in_df(df)
                    cf_values[f.name] = {"col": col, "cf": cf}
            st.subheader("CF rilevati in ogni file")
            for fname, info in cf_values.items():
                st.write(f"- {fname}: CF={info['cf']} (colonna: {info['col']})")
            
            # selezione sotto-attività
            if area != "Combinata / Multi-area":
                activity = st.selectbox("Seleziona attività specifica", [
                    "Visualizza cartella clinica",
                    "Collega a ordine farmacia",
                    "Report spese paziente"
                ] if area=="Sanitario" else (
                    ["Genera fattura","Prepara email","Richiedi pagamento"] if area=="Finanziario" else
                    ["Riepilogo acquisti","Analisi consumi mense","Report personale"]
                ))
            else:
                activity = st.selectbox("Seleziona funzione combinata", [
                    "Armonizza dati paziente",
                    "Genera fattura completa",
                    "Report multi-paziente",
                    "Controllo qualità / discrepanze"
                ])
            
            # Pulsante finale con icona per scaricare Excel
            if st.button("💾 Genera report finale"):
                all_frames = []
                for fname, df in temp.items():
                    col = cf_values[fname]['col']
                    cf = cf_values[fname]['cf']
                    if col:
                        mask = df[col].astype(str).str.contains(cf, case=False, na=False)
                        all_frames.append(df[mask])
                if all_frames:
                    harmonized = pd.concat(all_frames, ignore_index=True)
                    # scarica Excel
                    output = io.BytesIO()
                    harmonized.to_excel(output, index=False)
                    st.download_button("📥 Scarica Excel", data=output.getvalue(), file_name="report.xlsx", mime="application/vnd.ms-excel")
                    st.success("✅ Salvamento effettuato!")
                else:
                    st.warning("Nessun dato trovato da armonizzare.")
    
    else:
        st.write("DB interno selezionato — funzione pronta per MVP")
    
    st.button("← Torna al menu", on_click=lambda: go_to("main_menu"))
