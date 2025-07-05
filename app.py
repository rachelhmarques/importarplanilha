import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime
from functools import lru_cache
import numpy as np

# Module availability check with caching
@st.cache_data
def check_module_availability():
    """Check and cache module availability to avoid repeated imports"""
    modules = {'fuzzy': False, 'openpyxl': False}
    
    try:
        from fuzzywuzzy import fuzz
        modules['fuzzy'] = True
        st.info("Fuzzywuzzy module loaded successfully.")
    except ModuleNotFoundError:
        st.warning("The 'fuzzywuzzy' module is not installed. Falling back to exact string matching for 'Detalhe' column.")
    
    try:
        from openpyxl import Workbook
        from openpyxl.styles import numbers
        modules['openpyxl'] = True
        st.info("Openpyxl module loaded successfully.")
    except ModuleNotFoundError:
        st.error("The 'openpyxl' module is not installed. Excel file generation will fail.")
    
    return modules

# Cache expensive operations
@st.cache_data
def load_excel_data(file_contents):
    """Load Excel data with caching to avoid repeated file reads"""
    file_buffer = io.BytesIO(file_contents)
    excel_data = pd.ExcelFile(file_buffer)
    
    # Load sheets efficiently
    base_df = pd.read_excel(excel_data, sheet_name='Planilha1', skiprows=8)
    pagina1_df = pd.read_excel(excel_data, sheet_name='Página1', skiprows=4)
    
    return base_df, pagina1_df

@lru_cache(maxsize=1000)
def clean_string(text):
    """Cache string cleaning operations"""
    if pd.isna(text):
        return ""
    return str(text).strip().lower()

@st.cache_data
def preprocess_descriptions(pagina1_descriptions):
    """Preprocess descriptions for faster matching"""
    processed = []
    for desc in pagina1_descriptions:
        if pd.isna(desc):
            processed.append(None)
        else:
            clean_desc = desc.split(' - ', 1)[-1].strip() if ' - ' in desc else desc.strip()
            processed.append((desc, clean_desc.lower()))
    return processed

def vectorized_fuzzy_match(descriptions, pagina1_processed, fuzzy_available=False):
    """Optimized fuzzy matching using vectorized operations where possible"""
    if not fuzzy_available:
        # Optimized exact matching
        result = []
        desc_lower = [clean_string(desc) for desc in descriptions]
        
        for i, desc in enumerate(desc_lower):
            if not desc:
                result.append(None)
                continue
            
            match = None
            for original, clean in pagina1_processed:
                if original is not None and desc == clean:
                    match = original
                    break
            result.append(match)
        
        return result
    
    # Optimized fuzzy matching
    from fuzzywuzzy import fuzz
    result = []
    
    for desc in descriptions:
        if pd.isna(desc):
            result.append(None)
            continue
        
        clean_desc = clean_string(desc)
        if not clean_desc:
            result.append(None)
            continue
        
        best_match = None
        highest_score = 0
        
        # Pre-filter based on length for better performance
        threshold = 85 if len(clean_desc) < 20 else 75
        
        for original, clean_pagina1 in pagina1_processed:
            if original is None:
                continue
            
            # Use appropriate fuzzy matching algorithm
            if len(clean_desc) > 20 or ',' in clean_desc:
                score = fuzz.token_sort_ratio(clean_desc, clean_pagina1)
            else:
                score = fuzz.partial_ratio(clean_desc, clean_pagina1)
            
            if score > highest_score and score >= threshold:
                highest_score = score
                best_match = original
        
        result.append(best_match)
    
    return result

@st.cache_data
def format_dates_vectorized(date_series):
    """Vectorized date formatting for better performance"""
    def format_single_date(value):
        if pd.isna(value):
            return value
        try:
            date_val = pd.to_datetime(value, errors='coerce')
            if pd.isna(date_val):
                return value
            return date_val.strftime('%d/%m/%Y')
        except (ValueError, TypeError):
            return value
    
    return date_series.apply(format_single_date)

def process_excel_data(base_df, pagina1_df, fuzzy_available=False):
    """Optimized data processing with vectorized operations"""
    # Validate columns
    if 'Detalhe' not in base_df.columns:
        raise ValueError("Column 'Detalhe' not found in Planilha1")
    
    if len(pagina1_df.columns) < 2:
        raise ValueError("Column B not found in Página1")
    
    # Filter unwanted entries efficiently
    unwanted = ['Transferência entre Disponíveis - Saída', 
                'Transferência entre Disponíveis - Entrada', 
                'Saldo Inicial']
    base_df = base_df[~base_df['Detalhe'].isin(unwanted)].copy()
    
    # Preprocess descriptions once
    pagina1_descriptions = pagina1_df.iloc[:, 1]
    processed_descriptions = preprocess_descriptions(pagina1_descriptions)
    
    # Vectorized fuzzy matching
    matched_descriptions = vectorized_fuzzy_match(
        base_df['Detalhe'].values, 
        processed_descriptions, 
        fuzzy_available
    )
    
    # Update descriptions efficiently
    base_df['Detalhe'] = matched_descriptions
    
    return base_df

def create_output_files(base_df):
    """Optimized file generation with efficient DataFrame operations"""
    # Validate required columns
    if len(base_df.columns) < 10:
        raise ValueError("Insufficient columns in the data")
    
    # Get unique Disponíveis efficiently
    disponivel_column = base_df.iloc[:, 2].fillna('')
    unique_disponiveis = disponivel_column[disponivel_column.str.strip() != ''].unique()
    
    if len(unique_disponiveis) == 0:
        raise ValueError("No valid Disponível values found")
    
    files_data = []
    
    for disponivel in sorted(unique_disponiveis):
        # Efficient filtering
        mask = base_df.iloc[:, 2].fillna('') == disponivel
        filtered_df = base_df[mask]
        
        if filtered_df.empty:
            st.warning(f"No data found for Disponível: {disponivel}")
            continue
        
        # Create output DataFrame efficiently
        output_df = pd.DataFrame({
            'Data de Competência': filtered_df.iloc[:, 1],
            'Data de Vencimento': filtered_df.iloc[:, 1],
            'Data de Pagamento': filtered_df.iloc[:, 1],
            'Valor': filtered_df.iloc[:, 9],
            'Categoria': filtered_df.iloc[:, 3],
            'Descrição': filtered_df.apply(
                lambda row: row.iloc[5] if not pd.isna(row.iloc[5]) else row['Detalhe'], 
                axis=1
            ),
            'Cliente/Fornecedor': None,
            'CNPJ/CPF Cliente/Fornecedor': None,
            'Centro de Custo': None,
            'Observações': None
        })
        
        # Vectorized date formatting
        for col in ['Data de Competência', 'Data de Vencimento', 'Data de Pagamento']:
            output_df[col] = format_dates_vectorized(output_df[col])
        
        # Generate safe filename
        safe_disponivel = re.sub(r'[<>:"/\\|?*]', '_', str(disponivel))
        filename = f'{safe_disponivel}.xlsx'
        
        files_data.append((output_df, filename, disponivel))
    
    return files_data

def create_excel_buffer(output_df):
    """Optimized Excel file creation"""
    output_buffer = io.BytesIO()
    
    try:
        with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
            output_df.to_excel(writer, sheet_name='Dados', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Dados']
            
            # Efficient date formatting
            for col in ['A', 'B', 'C']:
                for row in range(2, len(output_df) + 2):
                    cell = worksheet[f'{col}{row}']
                    if cell.value and isinstance(cell.value, str) and '/' in cell.value:
                        cell.number_format = 'DD/MM/YYYY'
                    elif cell.value and isinstance(cell.value, (pd.Timestamp, datetime)):
                        cell.value = cell.value.strftime('%d/%m/%Y')
                        cell.number_format = 'DD/MM/YYYY'
    
    except Exception as e:
        raise RuntimeError(f"Excel generation failed: {str(e)}")
    
    output_buffer.seek(0)
    return output_buffer

# Main application
def main():
    st.set_page_config(
        page_title="Ajuste de Planilhas Conta Azul",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    st.title("📊 Ajuste de Planilhas Conta Azul")
    st.markdown("Faça o upload do arquivo (`Economatos - planilha_Modelo_para_Importacao_do_Plano_de_categorias.xlsx`) para gerar os arquivos separados.")
    
    # Check module availability
    modules = check_module_availability()
    
    # File uploader
    uploaded_file = st.file_uploader("Selecione o arquivo de Excel", type=["xlsx"])
    
    if uploaded_file is not None:
        if not modules['openpyxl']:
            st.error("Cannot proceed without 'openpyxl'. Please install it and redeploy the app.")
            st.stop()
        
        try:
            with st.spinner("🔄 Processando arquivo... Por favor, aguarde!"):
                # Load data with caching
                file_contents = uploaded_file.getvalue()
                base_df, pagina1_df = load_excel_data(file_contents)
                
                # Process data
                processed_df = process_excel_data(base_df, pagina1_df, modules['fuzzy'])
                
                # Create output files
                files_data = create_output_files(processed_df)
                
                st.success(f"✅ Processamento concluído! {len(files_data)} arquivo(s) gerado(s).")
                
                # Create download buttons
                col1, col2 = st.columns([1, 1])
                
                for i, (output_df, filename, disponivel) in enumerate(files_data):
                    with col1 if i % 2 == 0 else col2:
                        try:
                            excel_buffer = create_excel_buffer(output_df)
                            
                            st.download_button(
                                label=f"📥 Download {filename}",
                                data=excel_buffer,
                                file_name=filename,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"download_{i}"
                            )
                            st.success(f"Arquivo pronto: {disponivel}")
                        except Exception as e:
                            st.error(f"Erro ao gerar {filename}: {str(e)}")
        
        except Exception as e:
            st.error(f"❌ Erro durante o processamento: {str(e)}")
            st.info("Verifique se o arquivo está no formato correto e tente novamente.")

if __name__ == "__main__":
    main()

st.markdown("---")
st.markdown("🙏 Deus é bom o tempo todo. O tempo todo Deus é bom!")
