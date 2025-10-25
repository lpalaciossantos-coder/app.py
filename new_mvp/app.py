# app.py
import streamlit as st
import pandas as pd
import numpy as np
import pdfplumber
from fpdf import FPDF
import io
import re
from difflib import get_close_matches

# inizializzazione dello stato della pagina
if "page" not in st.session_state:
    st.session_state.page = "welcome"

def go_to(page_name: str):
    """Cambia pagina e ricarica l'app"""
    st.session_state.page = page_name
    st.rerun()

# -------------------------
# WELCOME PAGE
# -------------------------
if st.session_state.page == "welcome":
    st.title("🧠 Centralizzazione intelligente dei dati - ASP Siena")
    st.write("Prototipo AI per armonizzare e sincronizzare dati eterogenei tra sistemi diversi.")
    if st.button("Accedi al portale"):
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
            go_to("main_menu")
        else:
            st.error("Token non valido")
    if st.button("← Torna indietro"):
        go_to("welcome")

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
        go_to("welcome")

# -------------------------
# UPLOAD PAGE
# -------------------------
elif st.session_state.page == "upload":
    st.header("Caricamento file")
    uploaded_files = st.file_uploader("Carica CSV, Excel o PDF", type=["csv", "xls",]()

                                      
# -------------------------
# Helper / Config
# -------------------------
CF_VARIANTS = ["cf", "codice_fiscale", "codicefiscale", "codice fiscale", "codicef"]
CF_REGEX = re.compile(r'\b[A-Z0-9]{16}\b', flags=re.IGNORECASE)  # semplice pattern per CF italiano

def extract_table_from_pdf(uploaded_pdf):
    """Estrai tabelle con pdfplumber; se non ci sono tabelle, prova a estrarre testo e cercare righe CSV-like."""
    tables = []
    try:
        with pdfplumber.open(uploaded_pdf) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    df = df.loc[:, ~df.columns.duplicated()]
                    tables.append(df)
                else:
                    text = page.extract_text()
                    if text:
                        # prova a vedere se contiene linee con virgole
                        rows = [r for r in text.splitlines() if r.strip()]
                        if len(rows) >= 2 and ("," in rows[0] or ";" in rows[0]):
                            sep = "," if "," in rows[0] else ";"
                            header = [h.strip() for h in re.split(sep, rows[0])]
                            data = []
                            for r in rows[1:]:
                                parts = [p.strip() for p in re.split(sep, r)]
                                if len(parts) == len(header):
                                    data.append(parts)
                            if data:
                                df = pd.DataFrame(data, columns=header)
                                tables.append(df)
    except Exception as e:
        st.error(f"Errore lettura PDF: {e}")
    if tables:
        # armonizza colonne union
        all_columns = sorted(set(col for df in tables for col in df.columns))
        tables_fixed = []
        for df in tables:
            for col in all_columns:
                if col not in df.columns:
                    df[col] = pd.NA
            tables_fixed.append(df[all_columns])
        return pd.concat(tables_fixed, ignore_index=True)
    return pd.DataFrame()

def read_file(uploaded_file):
    """Carica CSV/Excel/PDF in DataFrame. Ritorna df o None."""
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
    except Exception as e:
        st.error(f"Errore caricamento file {uploaded_file.name}: {e}")
        return None

def find_cf_candidates_in_df(df):
    """Prova a individuare una colonna CF o estrarre CF dalle celle testuali."""
    cols = [c for c in df.columns]
    # normalize column names
    lowcols = {c: c.strip().lower().replace(" ", "_") for c in cols}
    # cerca colonne che sembrano CF
    for orig, low in lowcols.items():
        if any(v in low for v in ["codicefiscale", "codice_fiscale", "cf", "codicef"]):
            vals = df[orig].dropna().astype(str).str.upper().str.strip()
            # prendi il primo valore sembrante CF
            for v in vals:
                if CF_REGEX.match(v):
                    return orig, vals.iloc[0]
            # fallback: return col with many unique values
            return orig, vals.iloc[0] if not vals.empty else None
    # se non ci sono colonne CF, prova a cercare pattern nel testo di tutte celle
    text_cols = df.astype(str).apply(lambda col: col.str.cat(sep=" "), axis=0)
    for c, text in text_cols.items():
        m = CF_REGEX.search(text)
        if m:
            return c, m.group(0)
    return None, None

def normalize_columns(df):
    """Semplifica nomi colonne per armonizzazione."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def generate_report_pdf(harmonized_df, cf, month=None):
    """Genera un PDF minimale con le informazioni armonizzate per il CF e mese (se fornito)."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Report mensile per CF: {cf}", ln=True)
    if month:
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 8, f"Mese selezionato: {month}", ln=True)
    pdf.ln(4)
    pdf.set_font("Arial", size=11)
    if harmonized_df.empty:
        pdf.cell(0, 8, "Nessun dato disponibile.", ln=True)
    else:
        # limitiamo le righe per il PDF (per MVP)
        for _, row in harmonized_df.head(50).iterrows():
            line = " | ".join(f"{k}: {str(v)[:30]}" for k,v in row.items() if pd.notna(v))
            pdf.multi_cell(0, 6, line)
            pdf.ln(1)
    return pdf.output(dest="S").encode("latin1")

def make_email_template(problem_description, cf, file_names):
    """Crea un semplice template e-mail da copiare/incollare."""
    subject = f"[ACTION REQUIRED] Problema dati CF {cf}"
    body = (
        f"Ciao,\n\n"
        f"ho riscontrato un problema nei documenti caricati per il CF {cf}.\n"
        f"Dettagli: {problem_description}\n"
        f"File coinvolti: {', '.join(file_names)}\n\n"
        f"Puoi verificare e correggere? Grazie.\n\n"
        f"Saluti,\nTeam DataHub"
    )
    return subject, body

# -------------------------
# Session state: "DB" interno
# -------------------------
if "internal_db" not in st.session_state:
    # struttura: { cf_value: { 'sanitario': [dfs], 'finanziario': [dfs], 'amministrativo': [dfs] } }
    st.session_state.internal_db = {}
if "uploaded_files_store" not in st.session_state:
    st.session_state.uploaded_files_store = {}  # filename -> df

# -------------------------
# WELCOME & LOGIN
# -------------------------
st.title("🧠 DataHub — Centralizzazione intelligente dei dati (MVP)")
st.markdown("Benvenuto in **DataHub**: prototipo per armonizzare e sincronizzare dati eterogenei per ASP Siena.")

with st.expander("Login (area riservata)"):
    col1, col2 = st.columns([2,1])
    with col1:
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
    with col2:
        token = st.text_input("Token WHR-TIME")
        if st.button("Login (simulato)"):
            # login fittizio per l'MVP
            if token and token.strip().upper().startswith("WHR"):
                st.success("Login effettuato (simulazione). Puoi procedere.")
                st.session_state["logged_in"] = True
            else:
                st.error("Token non valido. Deve iniziare con 'WHR' (simulazione).")

if not st.session_state.get("logged_in", False):
    st.info("Effettua il login con token WHR-TIME per proseguire (simulazione MVP).")
    st.stop()

# -------------------------
# Schermata principale: due pulsanti
# -------------------------
st.write("---")
col1, col2, col3 = st.columns([2,2,1])
with col1:
    if st.button("📂 Carica dati (csv, txt, excel, pdf)"):
        st.session_state.show_upload = True
        st.session_state.show_manage = False
with col2:
    if st.button("🛠️ Gestione dei dati"):
        st.session_state.show_manage = True
        st.session_state.show_upload = False

# -------------------------
# Upload area (semplice)
# -------------------------
if st.session_state.get("show_upload"):
    st.header("Caricamento file (MVP)")
    uploaded = st.file_uploader("Trascina file qui (accetta multipli). Upload salva nel DB interno per demo.", 
                                type=["csv","txt","xls","xlsx","pdf"], accept_multiple_files=True)
    if uploaded:
        for f in uploaded:
            if f.name in st.session_state.uploaded_files_store:
                st.warning(f"{f.name} già caricato; salto.")
                continue
            df = read_file(f)
            if df is None or df.empty:
                st.warning(f"File {f.name} non contiene dati tabulari leggibili.")
                continue
            df = normalize_columns(df)
            st.session_state.uploaded_files_store[f.name] = df
            st.success(f"Caricato: {f.name} — righe: {len(df)}")
        st.write("File caricati nella sessione. Ora puoi andare in 'Gestione dei dati' per lavorarli.")

# -------------------------
# Gestione dei dati: menu e opzioni
# -------------------------
if st.session_state.get("show_manage"):
    st.header("Gestione dei dati")
    # Layout menu sulla sinistra
    menu_col, content_col = st.columns([1,3])
    with menu_col:
        st.subheader("Menu principale")
        area = st.radio("Seleziona area:", ["Sanitario", "Finanziario", "Amministrativo", "Combinata / Multi-area"])
        st.markdown("**Funzioni multi-area**")
        multi_ops = st.selectbox("Seleziona funzione combinata:", [
            "Armonizza dati paziente",
            "Genera fattura completa",
            "Report multi-paziente",
            "Controllo qualità / discrepanze"
        ])
        st.markdown("---")
        st.write("Sorgente dati:")
        db_option = st.radio("Scegli sorgente:", ["DB interno (dati caricati)", "Drag & Drop (carica file da analizzare)"])
    with content_col:
        st.subheader(f"Area: {area} — Modalità: {db_option}")
        # Modalità 1: DB interno
        if db_option == "DB interno (dati caricati)":
            if not st.session_state.uploaded_files_store:
                st.info("DB interno vuoto: carica prima i file nella sezione 'Carica dati'.")
            else:
                # Costruiamo una lista CF disponibili cercando CF in tutti file
                cf_index = {}
                for fname, df in st.session_state.uploaded_files_store.items():
                    col, cf_val = find_cf_candidates_in_df(df)
                    cf_index.setdefault(cf_val, []).append((fname, col))
                # pulizia di chiavi None
                cf_keys = [k for k in cf_index.keys() if k]
                if not cf_keys:
                    st.info("Nessun CF rilevato automaticamente nei file caricati.")
                else:
                    cf_choice = st.selectbox("Seleziona CF (dal DB interno):", cf_keys)
                    # Mostra file correlati
                    st.write("File con CF rilevato:")
                    for fname, col in cf_index[cf_choice]:
                        st.write(f"- {fname} (colonna: {col})")
                    # filtra per mese e mostra armonizzazione rapida
                    month_choice = st.selectbox("Seleziona mese (opzionale)", ["Tutti"] + [str(i) for i in range(1,13)])
                    # Costruiamo harmonized df per quel CF
                    frames = []
                    for fname, col in cf_index[cf_choice]:
                        df = st.session_state.uploaded_files_store[fname]
                        if col:
                            mask = df[col].astype(str).str.contains(cf_choice, case=False, na=False)
                            frames.append(df[mask])
                    if frames:
                        harmonized = pd.concat(frames, ignore_index=True)
                        # prova a convertire date se esiste colonna 'data'
                        if 'data' in harmonized.columns:
                            harmonized['data'] = pd.to_datetime(harmonized['data'], errors='coerce')
                            if month_choice != "Tutti":
                                harmonized = harmonized[harmonized['data'].dt.month == int(month_choice)]
                        st.write("Dati armonizzati (anteprima):")
                        st.dataframe(harmonized)
                        if st.button("Genera report PDF (DB interno)"):
                            pdf_bytes = generate_report_pdf(harmonized, cf_choice, month_choice if month_choice!="Tutti" else None)
                            st.download_button("💾 Scarica report PDF", data=pdf_bytes, file_name=f"report_{cf_choice}.pdf", mime="application/pdf")
                    else:
                        st.warning("Non sono riuscito a ricavare record per questo CF nei file caricati.")
        # Modalità 2: Drag & Drop per analizzare file al volo
        else:
            st.info("Drag & Drop: carica i file su cui vuoi lavorare (es. 2 file: CSV + PDF contenenti CF dello stesso paziente).")
            drag_files = st.file_uploader("Trascina qui 2 file (accetta csv, xlsx, pdf)", type=["csv","xls","xlsx","pdf","txt"], accept_multiple_files=True)
            if drag_files:
                if len(drag_files) > 5:
                    st.warning("Per l'MVP tieni massimo 2-3 file per test; qui useremo i primi 2.")
                # leggiamo i primi 2 file per la challenge
                files_to_use = drag_files[:2]
                temp_frames = {}
                cf_values = {}
                for f in files_to_use:
                    df = read_file(f)
                    if df is None or df.empty:
                        st.warning(f"Attenzione: il file {f.name} non sembra contenere tabelle leggibili.")
                        continue
                    df = normalize_columns(df)
                    temp_frames[f.name] = df
                    col, cf_val = find_cf_candidates_in_df(df)
                    cf_values[f.name] = {"col": col, "cf": cf_val}
                st.write("Riepilogo file caricati:")
                for fname, info in cf_values.items():
                    st.write(f"- {fname} → CF rilevato: {info['cf']} (col: {info['col']})")
                # Se nessun CF trovato, prova a chiedere all'utente
                detected_cfs = [v['cf'] for v in cf_values.values() if v['cf']]
                unique_cfs = list(set(detected_cfs))
                if not detected_cfs:
                    st.error("Nessun CF individuato automaticamente. Inseriscilo manualmente per procedere.")
                    manual_cf = st.text_input("Inserisci CF del paziente (16 caratteri):").strip().upper()
                else:
                    manual_cf = None
                # selezione attività specifica sotto area
                activity = None
                if area != "Combinata / Multi-area":
                    activity = st.selectbox("Seleziona attività specifica", [
                        "Visualizza cartella clinica",
                        "Collega a ordine farmacia",
                        "Report spese paziente"
                    ] if area == "Sanitario" else (
                        ["Genera fattura", "Prepara email", "Richiedi pagamento"] if area == "Finanziario" else
                        ["Riepilogo acquisti", "Analisi consumi mense", "Report personale"]
                    ))
                else:
                    activity = st.selectbox("Seleziona funzione combinata", multi_ops)
                # Azione principale: genera report mensile per CF
                if st.button("Genera report mensile (drag & drop)"):
                    # decidiamo quale CF usare per il report
                    cf_for_report = manual_cf if manual_cf else (unique_cfs[0] if len(unique_cfs)==1 else None)
                    if cf_for_report is None:
                        st.error("CF non determinato univocamente. Seleziona o inserisci manualmente il CF da analizzare.")
                    else:
                        # verifichiamo se tutti i file contengono lo stesso CF (se rilevato)
                        mismatch = False
                        mismatched_files = []
                        for fname, info in cf_values.items():
                            if info['cf'] and info['cf'].upper() != cf_for_report.upper():
                                mismatch = True
                                mismatched_files.append(fname)
                        if mismatch:
                            st.error("Errore: nei documenti caricati il CF non coincide.")
                            st.write("File con CF diverso:", mismatched_files)
                            # offriamo template mail
                            if st.button("Genera template email al tecnico / analista"):
                                subject, body = make_email_template(
                                    problem_description="CF non coincidenti nei documenti caricati.",
                                    cf=cf_for_report,
                                    file_names=list(temp_frames.keys())
                                )
                                st.subheader("Template email (copia/incolla)")
                                st.write("Oggetto:")
                                st.code(subject)
                                st.write("Corpo:")
                                st.code(body)
                        else:
                            # procediamo a armonizzare: prendiamo tutte le righe con quel CF
                            all_frames = []
                            for fname, df in temp_frames.items():
                                col = cf_values[fname]['col']
                                if col:
                                    mask = df[col].astype(str).str.contains(cf_for_report, case=False, na=False)
                                    all_frames.append(df[mask])
                                else:
                                    # fallback: cerca CF nel testo di tutte celle
                                    df_masked = df[df.astype(str).apply(lambda row: row.str.contains(cf_for_report, case=False, na=False).any(), axis=1)]
                                    all_frames.append(df_masked)
                            if all_frames:
                                harmonized = pd.concat(all_frames, ignore_index=True)
                                # chiedi mese opzionale
                                if 'data' in harmonized.columns:
                                    harmonized['data'] = pd.to_datetime(harmonized['data'], errors='coerce')
                                    month_opt = st.selectbox("Seleziona mese (opzionale)", ["Tutti"] + [str(i) for i in range(1,13)])
                                    if month_opt != "Tutti":
                                        harmonized = harmonized[harmonized['data'].dt.month == int(month_opt)]
                                else:
                                    month_opt = None
                                st.write("Anteprima dati armonizzati:")
                                st.dataframe(harmonized)
                                if st.button("Scarica report PDF (drag & drop)"):
                                    pdf_bytes = generate_report_pdf(harmonized, cf_for_report, month_opt if month_opt!="Tutti" else None)
                                    st.download_button("💾 Scarica report PDF", data=pdf_bytes, file_name=f"report_{cf_for_report}.pdf", mime="application/pdf")
                            else:
                                st.warning("Nessun record trovato per il CF selezionato nei file caricati.")
