
import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime

# Attempt to import required modules
fuzzy_available = False
try:
    from fuzzywuzzy import fuzz
    fuzzy_available = True
    st.info("Fuzzywuzzy module loaded successfully.")
except ModuleNotFoundError:
    st.warning("The 'fuzzywuzzy' module is not installed. Falling back to exact string matching for 'Detalhe' column. Ensure 'fuzzywuzzy' and 'python-Levenshtein' are in requirements.txt.")

openpyxl_available = False
try:
    from openpyxl import Workbook
    from openpyxl.styles import numbers
    openpyxl_available = True
    st.info("Openpyxl module loaded successfully.")
except ModuleNotFoundError:
    st.error("The 'openpyxl' module is not installed. Excel file generation will fail. Please ensure 'openpyxl' is included in your requirements.txt file.")

st.title("Economatos Excel Processor")
st.markdown("Upload the Excel file (`Economatos - planilha_Modelo_para_Importacao_do_Plano_de_categorias.xlsx`) to generate separate files for each Disponível.")

# File uploader
uploaded_file = st.file_uploader("Choose the Excel file", type=["xlsx"])

if uploaded_file is not None:
    if not openpyxl_available:
        st.error("Cannot proceed without 'openpyxl'. Please install it and redeploy the app.")
        st.stop()

    try:
        with st.spinner("Processing file..."):
            # Read the uploaded Excel file
            excel_data = pd.ExcelFile(uploaded_file)

            # Load the sheets
            base_df = pd.read_excel(excel_data, sheet_name='Planilha1', skiprows=8)
            pagina1_df = pd.read_excel(excel_data, sheet_name='Página1', skiprows=4)

            # Function to find the best match
            def find_best_match(description, pagina1_descriptions):
                if pd.isna(description):
                    return None
                if not fuzzy_available:
                    # Fallback to exact matching
                    clean_description = description.strip()
                    for pagina1_desc in pagina1_descriptions:
                        if pd.isna(pagina1_desc):
                            continue
                        clean_pagina1_desc = pagina1_desc.split(' - ', 1)[-1].strip() if ' - ' in pagina1_desc else pagina1_desc.strip()
                        if clean_description.lower() == clean_pagina1_desc.lower():
                            return pagina1_desc
                    return None
                # Fuzzy matching
                best_match = None
                highest_score = 0
                clean_description = description.strip()
                for pagina1_desc in pagina1_descriptions:
                    if pd.isna(pagina1_desc):
                        continue
                    clean_pagina1_desc = pagina1_desc.split(' - ', 1)[-1].strip() if ' - ' in pagina1_desc else pagina1_desc.strip()
                    score = fuzz.token_sort_ratio(clean_description, clean_pagina1_desc) if len(clean_description) > 20 or ',' in clean_description else fuzz.partial_ratio(clean_description, clean_pagina1_desc)
                    threshold = 85 if len(clean_description) < 20 else 75
                    if score > highest_score and score >= threshold:
                        highest_score = score
                        best_match = pagina1_desc
                return best_match

            # Ensure 'Detalhe' column exists
            if 'Detalhe' not in base_df.columns:
                st.error("Column 'Detalhe' not found in Planilha1")
                st.stop()

            # Use Column B (index 1) in Página1 for descriptions
            if len(pagina1_df.columns) < 2:
                st.error("Column B not found in Página1")
                st.stop()
            pagina1_descriptions = pagina1_df.iloc[:, 1]

            # Filter out unwanted entries
            unwanted = ['Transferência entre Disponíveis - Saída', 'Transferência entre Disponíveis - Entrada', 'Saldo Inicial']
            base_df = base_df[~base_df['Detalhe'].isin(unwanted)]

            # Process the 'Detalhe' column
            updated_descriptions = base_df['Detalhe'].copy()
            for i in range(len(base_df)):
                desc = base_df['Detalhe'].iloc[i]
                best_match = find_best_match(desc, pagina1_descriptions)
                if best_match:
                    updated_descriptions.iloc[i] = best_match

            # Update the 'Detalhe' column
            base_df['Detalhe'] = updated_descriptions

            # Function to format dates to DD/MM/YYYY
            def format_date(value):
                if pd.isna(value):
                    return value
                try:
                    date_val = pd.to_datetime(value, errors='coerce')
                    if pd.isna(date_val):
                        return value
                    return date_val.strftime('%d/%m/%Y')
                except (ValueError, TypeError):
                    return value

            # Get unique values in Column C (index 2, Disponível)
            if len(base_df.columns) < 3:
                st.error("Column C (Disponível) not found in Planilha1")
                st.stop()
            
            disponivel_column = base_df.iloc[:, 2].fillna('')
            unique_disponiveis = disponivel_column[disponivel_column.str.strip() != ''].unique()
            st.write("Detected unique Disponíveis:", list(unique_disponiveis))

            # Generate files for each unique Disponível
            if len(unique_disponiveis) == 0:
                st.warning("No valid Disponível values found in Column C.")
                st.stop()

            for disponivel in sorted(unique_disponiveis):
                filtered_df = base_df[base_df.iloc[:, 2].fillna('') == disponivel]
                
                if filtered_df.empty:
                    st.warning(f"No data found for Disponível: {disponivel}, skipping file generation")
                    continue

                # Create output DataFrame
                output_df = pd.DataFrame({
                    'Data de Competência': filtered_df.iloc[:, 1],
                    'Data de Vencimento': filtered_df.iloc[:, 1],
                    'Data de Pagamento': filtered_df.iloc[:, 1],
                    'Valor': filtered_df.iloc[:, 9],
                    'Categoria': filtered_df.iloc[:, 3],
                    'Descrição': filtered_df.apply(lambda row: row.iloc[5] if not pd.isna(row.iloc[5]) else row['Detalhe'], axis=1),
                    'Cliente/Fornecedor': None,
                    'CNPJ/CPF': None,
                    'Centro de Custo': None,
                    'Observações': None
                })

                # Format dates
                for col in ['Data de Competência', 'Data de Vencimento', 'Data de Pagamento']:
                    output_df[col] = output_df[col].apply(format_date)

                # Sanitize filename
                safe_disponivel = re.sub(r'[<>:"/\\|?*]', '_', str(disponivel))
                output_file_name = f'{safe_disponivel}.xlsx'

                # Save to BytesIO buffer
                output_buffer = io.BytesIO()
                with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                    output_df.to_excel(writer, sheet_name='Dados', index=False)
                    workbook = writer.book
                    worksheet = writer.sheets['Dados']
                    for col in ['A', 'B', 'C']:
                        for row in range(2, len(output_df) + 2):
                            cell = worksheet[f'{col}{row}']
                            if cell.value and isinstance(cell.value, str) and '/' in cell.value:
                                cell.number_format = 'DD/MM/YYYY'
                            elif cell.value and isinstance(cell.value, (pd.Timestamp, datetime)):
                                cell.value = cell.value.strftime('%d/%m/%Y')
                                cell.number_format = 'DD/MM/YYYY'

                output_buffer.seek(0)

                # Provide download button
                st.download_button(
                    label=f"Download {output_file_name}",
                    data=output_buffer,
                    file_name=output_file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.success(f"Generated file for Disponível: {disponivel}")

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")

st.markdown("---")
st.markdown("Built with Streamlit. Deployed via GitHub.")
