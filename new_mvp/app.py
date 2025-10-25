import streamlit as st
import pandas as pd
import numpy as np
import pdfplumber
from fpdf import FPDF
import io

st.set_page_config(page_title="DataHub ASP Siena", layout="wide")
st.title("🧠 Centralizzazione intelligente dei dati - ASP Siena")
st.write("Prototipo AI per armonizzare e sincronizzare dati eterogenei tra sistemi diversi (CSV, Excel, PDF).")

# -------------------------
# FUNZIONI UTILI
# -------------------------

def read_file(uploaded_file):
    """Carica e restituisce un DataFrame da CSV, Excel o PDF."""
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    elif uploaded_file.name.endswith((".xls", ".xlsx")):
        df = pd.read_excel(uploaded_file)
    elif uploaded_file.name.endswith(".pdf"):
        df = extract_table_from_pdf(uploaded_file)
    else:
        st.warning("Formato non supportato: " + uploaded_file.name)
        return None
    return df

def extract_table_from_pdf(uploaded_pdf):
    """Estrae tabelle o CSV testuale da PDF."""
    tables = []
    with pdfplumber.open(uploaded_pdf) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                df = pd.DataFrame(table[1:], columns=table[0])
                df = df.loc[:, ~df.columns.duplicated()]
                tables.append(df)
            else:
                # prova come testo CSV
                text = page.extract_text()
                if text:
                    rows = text.strip().split("\n")
                    header = rows[0].split(",")
                    data = [r.split(",") for r in rows[1:] if r.strip()]
                    df = pd.DataFrame(data, columns=header)
                    tables.append(df)
    if tables:
        # armonizza colonne
        all_columns = sorted(set(col for df in tables for col in df.columns))
        tables_fixed = []
        for df in tables:
            for col in all_columns:
                if col not in df.columns:
                    df[col] = pd.NA
            tables_fixed.append(df[all_columns])
        return pd.concat(tables_fixed, ignore_index=True)
    else:
        st.warning("Nessuna tabella rilevata nel PDF.")
        return pd.DataFrame()

def harmonize_data(dfs):
    """Armonizza i DataFrame normalizzando le colonne e unendo i dati."""
    normalized_dfs = []
    for df in dfs:
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        # uniforma CF
        if 'codicefiscale' in df.columns and 'cf' not in df.columns:
            df.rename(columns={'codicefiscale':'cf'}, inplace=True)
        normalized_dfs.append(df)

    common_cols = set.intersection(*(set(df.columns) for df in normalized_dfs))
    if not common_cols:
        st.warning("⚠️ Nessuna colonna comune trovata tra i file.")
        return pd.DataFrame()
    
    merged = pd.concat([df[list(common_cols)] for df in normalized_dfs], ignore_index=True)
    return merged

def generate_invoice_pdf(df_filtered, nome_cliente):
    """Genera PDF fattura fittizio per cliente selezionato"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"Fattura per {nome_cliente}", ln=True)
    pdf.set_font("Arial", size=12)
    total = 0
    if not df_filtered.empty:
        for _, row in df_filtered.iterrows():
            prodotto = row.get("prodotto", "")
            prezzo = float(row.get("prezzo", 0))
            quantita = int(row.get("quantità", 1))
            pdf.cell(0, 8, f"{prodotto} x{quantita} - €{prezzo*quantita:.2f}", ln=True)
            total += prezzo*quantita
    pdf.cell(0, 10, f"Totale: €{total:.2f}", ln=True)
    return pdf.output(dest='S').encode('latin1')

# -------------------------
# INTERFACCIA
# -------------------------

# Menu principale
area = st.radio("Seleziona area operativa:", ["Sanitario", "Finanziario", "Amministrativo"])

# Caricamento file
uploaded_files = st.file_uploader(
    "Carica file CSV, Excel o PDF", 
    type=["csv", "xls", "xlsx", "pdf"], 
    accept_multiple_files=True
)

dfs = []
merged_df = pd.DataFrame()
if uploaded_files:
    for file in uploaded_files:
        df = read_file(file)
        if df is not None and not df.empty:
            dfs.append(df)
    if dfs:
        merged_df = harmonize_data(dfs)

# -------------------------
# Azioni per area
# -------------------------
if area == "Sanitario":
    azione = st.selectbox("Seleziona attività:", [
        "Visualizza cartella clinica",
        "Collega a ordine farmacia",
        "Report spese paziente"
    ])
elif area == "Finanziario":
    azione = st.selectbox("Seleziona attività:", [
        "Richiedi pagamento",
        "Genera fattura PDF",
        "Prepara email"
    ])
elif area == "Amministrativo":
    azione = st.selectbox("Seleziona attività:", [
        "Visualizza riepilogo acquisti",
        "Analisi consumi mense",
        "Report personale"
    ])

# -------------------------
# Esecuzione attività
# -------------------------
if not merged_df.empty:
    if 'nome' in merged_df.columns:
        utenti = merged_df['nome'].unique()
        nome_selezionato = st.selectbox("Seleziona utente:", utenti)

        if 'data' in merged_df.columns:
            merged_df['data'] = pd.to_datetime(merged_df['data'], errors='coerce')
            mesi = merged_df['data'].dt.month.unique()
            mese_selezionato = st.selectbox("Seleziona mese:", mesi)
        else:
            mese_selezionato = None

        # Filtro dati
        filtered_df = merged_df
        if nome_selezionato:
            filtered_df = filtered_df[filtered_df['nome'] == nome_selezionato]
        if mese_selezionato is not None and 'data' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['data'].dt.month == mese_selezionato]

        st.subheader(f"Dati filtrati per {nome_selezionato}")
        st.dataframe(filtered_df)

        # Azioni specifiche
        if area == "Finanziario":
            if azione == "Genera fattura PDF":
                pdf_bytes = generate_invoice_pdf(filtered_df, nome_selezionato)
                st.download_button("💾 Scarica fattura PDF", data=pdf_bytes, file_name=f"fattura_{nome_selezionato}.pdf", mime="application/pdf")
            elif azione == "Prepara email":
                st.code(f"Ciao {nome_selezionato},\n\nDevi pagare entro il mese prossimo la fattura allegata.\nCordiali saluti,\nASP Siena")
            elif azione == "Richiedi pagamento":
                st.write(f"Simulazione richiesta pagamento per {nome_selezionato}")
        else:
            st.write(f"Esecuzione attività '{azione}' per {nome_selezionato}...")

else:
    st.info("Carica almeno un file per iniziare le operazioni.")
