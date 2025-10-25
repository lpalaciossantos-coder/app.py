# app.py
import streamlit as st
import pandas as pd
import numpy as np
import pdfplumber
from fpdf import FPDF
import io
import re

st.set_page_config(page_title="DataHub ASP Siena - MVP", layout="wide")

# -------------------------
# Helper / Config
# -------------------------
CF_REGEX = re.compile(r'\b[A-Z0-9]{16}\b', flags=re.IGNORECASE)

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
                else:
                    text = page.extract_text()
                    if text:
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
    cols = df.columns
    lowcols = {c: c.strip().lower().replace(" ", "_") for c in cols}
    for orig, low in lowcols.items():
        if any(v in low for v in ["codicefiscale","codice_fiscale","cf","codicef"]):
            vals = df[orig].dropna().astype(str).str.upper().str.strip()
            for v in vals:
                if CF_REGEX.match(v):
                    return orig, vals.iloc[0]
            return orig, vals.iloc[0] if not vals.empty else None
    # fallback: cerca pattern CF nel testo
    text_cols = df.astype(str).apply(lambda col: col.str.cat(sep=" "), axis=0)
    for c, text in text_cols.items():
        m = CF_REGEX.search(text)
        if m:
            return c, m.group(0)
    return None, None

def normalize_columns(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def generate_report_pdf(harmonized_df, cf, month=None):
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
        for _, row in harmonized_df.head(50).iterrows():
            line = " | ".join(f"{k}: {str(v)[:30]}" for k,v in row.items() if pd.notna(v))
            pdf.multi_cell(0, 6, line)
            pdf.ln(1)
    return pdf.output(dest="S").encode("latin1")

def make_email_template(problem_description, cf, file_names):
    subject = f"[ACTION REQUIRED] Problema dati CF {cf}"
    body = (
        f"Ciao,\n\n"
        f"ho riscontrato un problema nei documenti caricati per il CF {cf}.\n"
        f"Dettagli: {problem_description}\n"
        f"File coinvolti: {', '.join(file_names)}\n\n"
        f"Puoi verificare e correggere? Grazie.\n\n"
        f"Saluti,\nTeam DataHub"
    )
    # crea mailto link
    mailto_link = f"mailto:tecnico@azienda.it?subject={subject}&body={body}"
    return subject, body, mailto_link

# -------------------------
# Session state
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "uploaded_files_store" not in st.session_state:
    st.session_state.uploaded_files_store = {}
if "show_upload" not in st.session_state:
    st.session_state.show_upload = False
if "show_manage" not in st.session_state:
    st.session_state.show_manage = False

# -------------------------
# Welcome & Login
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
            if token and token.strip().upper().startswith("WHR"):
                st.success("Login effettuato (simulazione). Puoi procedere.")
                st.session_state.logged_in = True
            else:
                st.error("Token non valido. Deve iniziare con 'WHR' (simulazione).")

if not st.session_state.logged_in:
    st.info("Effettua il login con token WHR-TIME per proseguire (simulazione MVP).")
    st.stop()

# -------------------------
# Schermata principale
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
# Upload area
# -------------------------
if st.session_state.show_upload:
    st.header("Caricamento file (MVP)")
    uploaded = st.file_uploader("Trascina file qui (accetta multipli).", 
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
        st.info("File caricati nella sessione. Ora puoi andare in 'Gestione dei dati' per lavorarli.")

# -------------------------
# Gestione dati
# -------------------------
if st.session_state.show_manage:
    st.header("Gestione dei dati")
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
        if db_option == "DB interno (dati caricati)":
            st.info("Funzionalità DB interno non ancora completata per MVP.")
        else:
            st.info("Drag & Drop: carica i file su cui vuoi lavorare.")
            drag_files = st.file_uploader("Trascina qui file", type=["csv","xls","xlsx","pdf","txt"], accept_multiple_files=True)
            if drag_files:
                files_to_use = drag_files[:2]
                temp_frames = {}
                cf_values = {}
                for f in files_to_use:
                    df = read_file(f)
                    if df is None or df.empty:
                        st.warning(f"File {f.name} non contiene tabelle leggibili.")
                        continue
                    df = normalize_columns(df)
                    temp_frames[f.name] = df
                    col, cf_val = find_cf_candidates_in_df(df)
                    cf_values[f.name] = {"col": col, "cf": cf_val}

                st.write("Riepilogo CF rilevati:")
                for fname, info in cf_values.items():
                    st.write(f"- {fname} → CF rilevato: {info['cf']} (col: {info['col']})")

                # ---------------------
                # Sezione CF principale e gestione discrepanze
                # ---------------------
                detected_cfs = [v['cf'] for v in cf_values.values() if v['cf']]
                unique_cfs = list(set(detected_cfs))
                manual_cf = None
                if not detected_cfs:
                    manual_cf = st.text_input("Inserisci CF del paziente (16 caratteri):").strip().upper()

                cf_for_report = manual_cf if manual_cf else (unique_cfs[0] if len(unique_cfs)==1 else None)

                if cf_for_report is None:
                    st.error("CF non determinato univocamente. Inserisci manualmente il CF principale.")
                else:
                    # identifica mismatch: CF diverso o CF assente
                    mismatched_files = [fname for fname, info in cf_values.items() 
                                        if info['cf'] is None or info['cf'].upper() != cf_for_report.upper()]

                    if mismatched_files:
                        st.warning(f"⚠️ Nei documenti caricati il CF non coincide o manca: {mismatched_files}")
                        st.info(f"Verrà generato il report usando il CF: {cf_for_report} (manuale o primo CF valido trovato)")

                        subject, body, mailto = make_email_template(
                            problem_description="CF non coincidenti o assenti nei documenti caricati.",
                            cf=cf_for_report,
                            file_names=list(temp_frames.keys())
                        )
                        st.subheader("Template email")
                        st.write("Oggetto:")
                        st.code(subject)
                        st.write("Corpo:")
                        st.code(body)
                        st.markdown(f"[📧 Invia email](mailto:{mailto[7:]})")  # rimuove mailto: duplicato

                    # filtra dati per CF
                    all_frames = []
                    for fname, df in temp_frames.items():
                        col = cf_values[fname]['col']
                        if col:
                            mask = df[col].astype(str).str.contains(cf_for_report, case=False, na=False)
                            all_frames.append(df[mask])
                        else:
                            # cerca CF nel testo
                            df_masked = df[df.astype(str).apply(lambda row: row.str.contains(cf_for_report, case=False, na=False).any(), axis=1)]
                            all_frames.append(df_masked)
                    harmonized = pd.concat(all_frames, ignore_index=True)

                    if 'data' in harmonized.columns:
                        harmonized['data'] = pd.to_datetime(harmonized['data'], errors='coerce')
                        month_opt = st.selectbox("Seleziona mese (opzionale)", ["Tutti"] + [str(i) for i in range(1,13)])
                        if month_opt != "Tutti":
                            harmonized = harmonized[harmonized['data'].dt.month == int(month_opt)]
                    else:
                        month_opt = None

                    st.write("Anteprima dati armonizzati:")
                    st.dataframe(harmonized)

                    # download Excel
                    towrite = io.BytesIO()
                    harmonized.to_excel(towrite, index=False, engine='openpyxl')
                    towrite.seek(0)
                    st.download_button(
                        label="💾 Scarica report Excel",
                        data=towrite,
                        file_name=f"report_{cf_for_report}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    st.success("Salvamento effettuato ✅")
