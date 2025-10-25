# app_mvp.py
import streamlit as st
import pandas as pd
import numpy as np
import pdfplumber
from fpdf import FPDF
import re

# -------------------------
# PAGINA CORRENTE E NAVIGAZIONE
# -------------------------
if "page" not in st.session_state:
    st.session_state.page = "welcome"

def go_to(page_name: str):
    st.session_state.page = page_name
    st.rerun()

# -------------------------
# SESSION STATE PER DATI
# -------------------------
if "uploaded_files_store" not in st.session_state:
    st.session_state.uploaded_files_store = {}
if "internal_db" not in st.session_state:
    st.session_state.internal_db = {}
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
        else:
            return None
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

def generate_report_pdf(df, cf, month=None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Report mensile per CF: {cf}", ln=True)
    pdf.set_font("Arial", size=12)
    if month:
        pdf.cell(0, 8, f"Mese: {month}", ln=True)
    pdf.ln(4)
    for _, row in df.head(50).iterrows():
        line = " | ".join(f"{k}:{v}" for k,v in row.items() if pd.notna(v))
        pdf.multi_cell(0, 6, line)
        pdf.ln(1)
    return pdf.output(dest="S").encode("latin1")

def make_email_template(problem_description, cf, file_names):
    subject = f"[ACTION REQUIRED] Problema dati CF {cf}"
    body = f"Ciao,\n\nProblema nei documenti CF {cf}: {problem_description}\nFile: {', '.join(file_names)}\n\nSaluti"
    return subject, body

# -------------------------
# WELCOME PAGE
# -------------------------
if st.session_state.page == "welcome":
    st.title("🧠 DataHub MVP - ASP Siena")
    st.write("Prototipo per armonizzare e sincronizzare dati eterogenei")
    if st.button("Accedi"):
        go_to("login")

# -------------------------
# LOGIN PAGE
# -------------------------
elif st.session_state.page == "login":
    st.header("Login area riservata")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    token = st.text_input("Token WHR-TIME")
    if st.button("Entra"):
        if token.strip().upper().startswith("WHR"):
            st.success("Login effettuato!")
            st.session_state.logged_in = True
            go_to("main_menu")
        else:
            st.error("Token non valido")
    if st.button("← Torna indietro"):
        go_to("welcome")

if not st.session_state.logged_in:
    st.stop()

# -------------------------
# MAIN MENU
# -------------------------
elif st.session_state.page == "main_menu":
    st.header("Menu principale")
    if st.button("📂 Carica dati"):
        go_to("upload")
    if st.button("🛠️ Gestione dati"):
        go_to("manage")
    if st.button("← Logout"):
        st.session_state.logged_in = False
        go_to("welcome")

# -------------------------
# UPLOAD PAGE
# -------------------------
elif st.session_state.page == "upload":
    st.header("Upload file (MVP)")
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
            st.write(cf_values)
            if st.button("Genera report mensile"):
                # logica CF mismatch / armonizzazione qui
                pass
    else:
        st.write("DB interno selezionato — funzione per MVP")

    if st.button("← Torna al menu"):
        go_to("main_menu")
