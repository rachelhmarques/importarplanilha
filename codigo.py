import streamlit as st
import pandas as pd
from fuzzywuzzy import fuzz
from io import BytesIO
from datetime import datetime
import re
import openpyxl
from openpyxl.styles import numbers

# Set page config
st.set_page_config(page_title="Excel Processor", layout="wide")

# App title and description
st.title("📊 Excel Data Processor")
st.markdown("""
This tool processes Excel files to match descriptions and generate separate files for each 'Disponível'.
Upload the Excel file with 'Planilha1' and 'Página1' sheets to begin.
""")

# File upload section
uploaded_file = st.file_uploader(
    "Upload Excel File (Economatos - planilha_Modelo_para_Importacao_do_Plano_de_categorias.xlsx)",
    type=["xlsx"]
)

# Function to find the best match using fuzzy string matching
def find_best_match(description, pagina1_descriptions):
    if pd.isna(description):
        return None
    best_match = None
    highest_score = 0
    clean_description = description.strip()
    for pagina1_desc in pagina1_descriptions:
        if pd.isna(pagina1_desc):
            continue
        # Remove leading code for comparison, but preserve original for output
        clean_pagina1_desc = pagina1_desc.split(' - ', 1)[-1].strip() if ' - ' in pagina1_desc else pagina1_desc.strip()
        # Use token_sort_ratio for complex descriptions, partial_ratio for short ones
        score = fuzz.token_sort_ratio(clean_description, clean_pagina1_desc) if len(clean_description) > 20 or ',' in clean_description else fuzz.partial_ratio(clean_description, clean_pagina1_desc)
        # Adjust threshold: stricter for short descriptions, more lenient for complex ones
        threshold = 85 if len(clean_description) < 20 else 75
        if score > highest_score and score >= threshold:
            highest_score = score
            best_match = pagina1_desc  # Use original Página1 description
    return best_match

# Function to format dates to DD/MM/YYYY
def format_date(value):
    if pd.isna(value):
        return value
    try:
        # Convert to datetime, handling various formats
        date_val = pd.to_datetime(value, errors='coerce')
        if pd.isna(date_val):
            return value  # Return original if not a valid date
        return date_val.strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        return value  # Return original if conversion fails

# Process the file when uploaded
if uploaded_file is not None:
    try:
        with st.spinner('Processing file...'):
            # Read the uploaded Excel file
            excel_data = pd.ExcelFile(uploaded_file)

            # Load the sheets
            base_df = pd.read_excel(excel_data, sheet_name='Planilha1', skiprows=8)
            pagina1_df = pd.read_excel(excel_data, sheet_name='Página1', skiprows=4)

            # Show preview of the data
            st.subheader("Data Preview")
            tab1, tab2 = st.tabs(["Planilha1", "Página1"])
            
            with tab1:
                st.write("Planilha1 (first 10 rows):")
                st.dataframe(base_df.head(10))
                
            with tab2:
                st.write("Página1 (first 10 rows):")
                st.dataframe(pagina1_df.head(10))

            # Validate required columns
            if 'Detalhe' not in base_df.columns:
                st.error("Error: Column 'Detalhe' not found in Planilha1")
                st.stop()
                
            if len(pagina1_df.columns) < 2:
                st.error("Error: Column B not found in Página1")
                st.stop()

            # Get descriptions from Página1
            pagina1_descriptions = pagina1_df.iloc[:, 1]  # Column B

            # Filter out unwanted entries
            unwanted = ['Transferência entre Disponíveis - Saída', 'Transferência entre Disponíveis - Entrada', 'Saldo Inicial']
            base_df = base_df[~base_df['Detalhe'].isin(unwanted)]

            # Process the 'Detalhe' column
            updated_descriptions = base_df['Detalhe'].copy()
            for i in range(len(base_df)):
                desc = base_df['Detalhe'].iloc[i]
                best_match = find_best_match(desc, pagina1_descriptions)
                if best_match:
                    updated_descriptions.iloc[i] = best_match  # Use exact match from Página1

            # Update the 'Detalhe' column
            base_df['Detalhe'] = updated_descriptions

            # Get unique values in Column C (index 2, assumed to be Centro de Custo/Disponível)
            unique_disponiveis = base_df.iloc[:, 2].dropna().unique()

            # Create a download button for each file
            st.subheader("Processed Files")
            st.write(f"Found {len(unique_disponiveis)} unique 'Disponível' values to process")

            # Create a zip file with all outputs
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
                for disponivel in unique_disponiveis:
                    # Filter rows for the current Disponível
                    filtered_df = base_df[base_df.iloc[:, 2] == disponivel]

                    # Create new DataFrame for the "Dados" sheet
                    output_df = pd.DataFrame({
                        'Data de Competência': filtered_df.iloc[:, 1],  # Column B (dates)
                        'Data de Vencimento': filtered_df.iloc[:, 1],  # Column B (dates)
                        'Data de Pagamento': filtered_df.iloc[:, 1],  # Column B (dates)
                        'Valor': filtered_df.iloc[:, 9],  # Column J
                        'Categoria': filtered_df.iloc[:, 3],  # Column D
                        'Descrição': filtered_df.apply(lambda row: row.iloc[5] if not pd.isna(row.iloc[5]) else row['Detalhe'], axis=1),  # Column F, fallback to Column D
                        'Cliente/Fornecedor': None,  # Blank
                        'CNPJ/CPF Cliente/Fornecedor': None,  # Blank
                        'Centro de Custo': None,  # Blank
                        'Observações': None  # Blank
                    })

                    # Format dates in Columns A, B, C to DD/MM/YYYY
                    for col in ['Data de Competência', 'Data de Vencimento', 'Data de Pagamento']:
                        output_df[col] = output_df[col].apply(format_date)

                    # Sanitize the Disponível name for use as a filename
                    safe_disponivel = re.sub(r'[<>:"/\\|?*]', '_', str(disponivel))
                    output_file = f'{safe_disponivel}.xlsx'

                    # Save to Excel in memory
                    excel_buffer = BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        output_df.to_excel(writer, sheet_name='Dados', index=False)

                        # Access the openpyxl workbook and worksheet
                        workbook = writer.book
                        worksheet = writer.sheets['Dados']

                        # Apply DD/MM/YYYY format to Columns A, B, C (Excel columns 1, 2, 3)
                        for col in ['A', 'B', 'C']:
                            for row in range(2, len(output_df) + 2):  # Start from row 2 (Excel is 1-based, plus header)
                                cell = worksheet[f'{col}{row}']
                                if cell.value and isinstance(cell.value, str) and '/' in cell.value:
                                    cell.number_format = 'DD/MM/YYYY'
                                elif cell.value and isinstance(cell.value, (pd.Timestamp, datetime)):
                                    cell.value = cell.value.strftime('%d/%m/%Y')
                                    cell.number_format = 'DD/MM/YYYY'

                    # Add to zip file
                    zip_file.writestr(output_file, excel_buffer.getvalue())

            # Create download button for the zip file
            st.download_button(
                label="📥 Download All Files as ZIP",
                data=zip_buffer.getvalue(),
                file_name="processed_files.zip",
                mime="application/zip"
            )

            st.success("Processing complete! Click the button above to download all files.")

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.stop()
else:
    st.info("Please upload an Excel file to begin processing.")
