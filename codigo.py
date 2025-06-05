
# Install required packages
!pip install fuzzywuzzy python-Levenshtein pandas openpyxl

import pandas as pd
from google.colab import files
from fuzzywuzzy import fuzz
import io
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import numbers
import re

# Prompt user to upload the Excel file
print("Please upload the Excel file (Economatos - planilha_Modelo_para_Importacao_do_Plano_de_categorias.xlsx):")
uploaded = files.upload()

try:
    # Read the uploaded Excel file
    file_name = list(uploaded.keys())[0]
    excel_data = pd.ExcelFile(io.BytesIO(uploaded[file_name]))

    # Load the sheets
    # Skip 8 rows to start from row 9 (0-based index) in Planilha1, as row 10 is the first data row
    base_df = pd.read_excel(excel_data, sheet_name='Planilha1', skiprows=8)
    # Skip 4 rows in Página1 to start from row 5
    pagina1_df = pd.read_excel(excel_data, sheet_name='Página1', skiprows=4)

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

    # Ensure 'Detalhe' column exists in Planilha1
    if 'Detalhe' not in base_df.columns:
        raise ValueError("Column 'Detalhe' not found in Planilha1")

    # Use Column B (index 1) in Página1 for descriptions
    if len(pagina1_df.columns) < 2:
        raise ValueError("Column B not found in Página1")
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

    # Get unique values in Column C (index 2, assumed to be Centro de Custo/Disponível)
    if len(base_df.columns) < 3:
        raise ValueError("Column C (Disponível) not found in Planilha1")
    unique_disponiveis = base_df.iloc[:, 2].dropna().unique()

    # Generate a separate file for each unique Disponível
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

        # Save the DataFrame to a new Excel file with only the "Dados" sheet
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
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

        # Download the file
        files.download(output_file)
        print(f"File saved and downloaded as {output_file}")

except Exception as e:
    print(f"An error occurred: {str(e)}")
