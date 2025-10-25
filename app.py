import streamlit as st
import pandas as pd
import pdfplumber
import io

st.set_page_config(page_title="DataHub ASP Siena", layout="wide")

st.title("🧠 Centralizzazione intelligente dei dati - ASP Siena")
st.write("Prototipo AI per armonizzare e sincronizzare dati eterogenei tra sistemi diversi (CSV, Excel, PDF).")

# --- FUNZIONI ---
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
    """Estrae tabelle da PDF testuali e armonizza colonne."""
    tables = []
    with pdfplumber.open(uploaded_pdf) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                df = pd.DataFrame(table[1:], columns=table[0])
                # Rimuovo eventuali colonne duplicate
                df = df.loc[:, ~df.columns.duplicated()]
                tables.append(df)
    if tables:
        # Trovo tutte le colonne presenti in tutte le tabelle
        all_columns = sorted(set(col for df in tables for col in df.columns))
        # Riempi con NaN le colonne mancanti
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
    """Esempio di armonizzazione: uniforma nomi colonne e unisce i dataset."""
    normalized_dfs = []
    for df in dfs:
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        normalized_dfs.append(df)

    common_cols = set.intersection(*(set(df.columns) for df in normalized_dfs))
    if not common_cols:
        st.warning("⚠️ Nessuna colonna comune trovata tra i file.")
        return pd.DataFrame()
    
    merged = pd.concat([df[list(common_cols)] for df in normalized_dfs], ignore_index=True)
    return merged

# --- INTERFACCIA ---
st.header("📤 Carica i tuoi file")
uploaded_files = st.file_uploader(
    "Carica file CSV, Excel o PDF", 
    type=["csv", "xls", "xlsx", "pdf"], 
    accept_multiple_files=True
)

if uploaded_files:
    dfs = []
    for file in uploaded_files:
        df = read_file(file)
        if df is not None and not df.empty:
            st.subheader(f"📄 Anteprima di {file.name}")
            st.dataframe(df.head())
            dfs.append(df)

    if len(dfs) > 1:
        st.markdown("---")
        st.header("🔄 Armonizzazione e fusione dei dati")
        merged_df = harmonize_data(dfs)
        if not merged_df.empty:
            st.dataframe(merged_df.head())
            st.success("✅ Dati armonizzati con successo!")
            st.download_button(
                label="💾 Scarica dataset armonizzato (CSV)",
                data=merged_df.to_csv(index=False).encode('utf-8'),
                file_name="dati_armonizzati.csv",
                mime="text/csv"
            )
else:
    st.info("Carica almeno due file per iniziare la sincronizzazione dei dati.")

st.markdown("---")
st.header("📊 Analisi esplorativa (facoltativa)")
if uploaded_files:
    if 'merged_df' in locals() and not merged_df.empty:
        st.write("Numero record totali:", len(merged_df))
        st.write("Colonne comuni:", list(merged_df.columns))
        st.bar_chart(merged_df.select_dtypes(include='number').head(50))
