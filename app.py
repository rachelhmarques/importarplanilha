import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import re
import zipfile
import subprocess
import sys
import openpyxl
from openpyxl.styles import numbers

# Função para instalar pacotes necessários
def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Verificar e instalar dependências
try:
    from thefuzz import fuzz  # Novo nome do fuzzywuzzy
except ImportError:
    try:
        from fuzzywuzzy import fuzz
    except ImportError:
        st.warning("Instalando pacotes necessários...")
        install('fuzzywuzzy')
        install('python-Levenshtein')
        from fuzzywuzzy import fuzz

# Configuração da página
st.set_page_config(page_title="📊 Processador de Planilhas", layout="wide", page_icon="📊")

# Título e descrição do aplicativo
st.title("📊 Processador de Planilhas para Economatos")
st.markdown("""
Este aplicativo processa arquivos Excel do modelo de importação do plano de categorias, realizando:
- Correspondência fuzzy de descrições
- Filtragem de entradas indesejadas
- Geração de arquivos separados por Centro de Custo/Disponível
- Formatação automática de datas
""")

# Função para encontrar a melhor correspondência
def find_best_match(description, pagina1_descriptions):
    if pd.isna(description):
        return None
    best_match = None
    highest_score = 0
    clean_description = str(description).strip()
    
    for pagina1_desc in pagina1_descriptions:
        if pd.isna(pagina1_desc):
            continue
            
        clean_pagina1_desc = str(pagina1_desc).split(' - ', 1)[-1].strip() if ' - ' in str(pagina1_desc) else str(pagina1_desc).strip()
        
        if len(clean_description) > 20 or ',' in clean_description:
            score = fuzz.token_sort_ratio(clean_description, clean_pagina1_desc)
        else:
            score = fuzz.partial_ratio(clean_description, clean_pagina1_desc)
        
        threshold = 85 if len(clean_description) < 20 else 75
        
        if score > highest_score and score >= threshold:
            highest_score = score
            best_match = pagina1_desc
            
    return best_match

# Função para formatar datas
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

# Upload do arquivo
uploaded_file = st.file_uploader(
    "Carregue o arquivo Excel (Modelo_para_Importacao_do_Plano_de_categorias.xlsx)",
    type=["xlsx"],
    help="O arquivo deve conter as planilhas 'Planilha1' e 'Página1'"
)

if uploaded_file is not None:
    try:
        with st.spinner('Processando arquivo...'):
            # Ler o arquivo Excel
            excel_data = pd.ExcelFile(uploaded_file)
            
            # Verificar se as planilhas necessárias existem
            required_sheets = ['Planilha1', 'Página1']
            if not all(sheet in excel_data.sheet_names for sheet in required_sheets):
                missing = [sheet for sheet in required_sheets if sheet not in excel_data.sheet_names]
                st.error(f"Planilhas obrigatórias não encontradas: {', '.join(missing)}")
                st.stop()
            
            # Carregar dados
            base_df = pd.read_excel(excel_data, sheet_name='Planilha1', skiprows=8)
            pagina1_df = pd.read_excel(excel_data, sheet_name='Página1', skiprows=4)
            
            # Mostrar visualização dos dados
            st.subheader("Visualização dos Dados")
            tab1, tab2 = st.tabs(["Planilha1", "Página1"])
            
            with tab1:
                st.write(f"Planilha1 (Total de linhas: {len(base_df)})")
                st.dataframe(base_df.head(10))
                
            with tab2:
                st.write(f"Página1 (Total de linhas: {len(pagina1_df)})")
                st.dataframe(pagina1_df.head(10))
            
            # Validar colunas necessárias
            if 'Detalhe' not in base_df.columns:
                st.error("Erro: Coluna 'Detalhe' não encontrada na Planilha1")
                st.stop()
                
            if len(pagina1_df.columns) < 2:
                st.error("Erro: Coluna B não encontrada na Página1")
                st.stop()
            
            # Processar correspondência de descrições
            st.subheader("Processando Correspondências")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            pagina1_descriptions = pagina1_df.iloc[:, 1]  # Coluna B
            unwanted = ['Transferência entre Disponíveis - Saída', 
                      'Transferência entre Disponíveis - Entrada', 
                      'Saldo Inicial']
            
            base_df = base_df[~base_df['Detalhe'].isin(unwanted)]
            updated_descriptions = base_df['Detalhe'].copy()
            
            total_rows = len(base_df)
            matches_found = 0
            
            for i in range(total_rows):
                desc = base_df['Detalhe'].iloc[i]
                best_match = find_best_match(desc, pagina1_descriptions)
                
                if best_match:
                    updated_descriptions.iloc[i] = best_match
                    matches_found += 1
                
                # Atualizar progresso
                if i % 10 == 0 or i == total_rows - 1:
                    progress_bar.progress((i + 1) / total_rows)
                    status_text.text(f"Processando... {i + 1}/{total_rows} linhas | {matches_found} correspondências encontradas")
            
            base_df['Detalhe'] = updated_descriptions
            
            # Gerar arquivos separados
            st.subheader("Gerando Arquivos")
            if len(base_df.columns) < 10:
                st.error("Erro: A Planilha1 não tem colunas suficientes")
                st.stop()
                
            unique_disponiveis = base_df.iloc[:, 2].dropna().unique()
            
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
                for idx, disponivel in enumerate(unique_disponiveis):
                    filtered_df = base_df[base_df.iloc[:, 2] == disponivel]
                    
                    output_df = pd.DataFrame({
                        'Data de Competência': filtered_df.iloc[:, 1],
                        'Data de Vencimento': filtered_df.iloc[:, 1],
                        'Data de Pagamento': filtered_df.iloc[:, 1],
                        'Valor': filtered_df.iloc[:, 9],
                        'Categoria': filtered_df.iloc[:, 3],
                        'Descrição': filtered_df.apply(
                            lambda row: row.iloc[5] if not pd.isna(row.iloc[5]) else row['Detalhe'], 
                            axis=1),
                        'Cliente/Fornecedor': None,
                        'CNPJ/CPF Cliente/Fornecedor': None,
                        'Centro de Custo': None,
                        'Observações': None
                    })
                    
                    # Formatar datas
                    for col in ['Data de Competência', 'Data de Vencimento', 'Data de Pagamento']:
                        output_df[col] = output_df[col].apply(format_date)
                    
                    # Nome do arquivo seguro
                    safe_disponivel = re.sub(r'[<>:"/\\|?*]', '_', str(disponivel))
                    output_file = f'{safe_disponivel}.xlsx'
                    
                    # Salvar em buffer
                    excel_buffer = BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
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
                    
                    # Adicionar ao ZIP
                    zip_file.writestr(output_file, excel_buffer.getvalue())
                    
                    # Atualizar progresso
                    progress_bar.progress((idx + 1) / len(unique_disponiveis))
                    status_text.text(f"Gerando arquivos... {idx + 1}/{len(unique_disponiveis)}")
            
            # Botão de download
            st.success("Processamento concluído com sucesso!")
            st.download_button(
                label="⬇️ Baixar Todos os Arquivos (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="arquivos_processados.zip",
                mime="application/zip",
                help="Clique para baixar um arquivo ZIP contendo todos os arquivos processados"
            )
            
            # Estatísticas
            st.markdown(f"""
            **Estatísticas do Processamento:**
            - Total de linhas processadas: {total_rows}
            - Correspondências encontradas: {matches_found} ({matches_found/total_rows:.1%})
            - Arquivos gerados: {len(unique_disponiveis)}
            """)
            
    except Exception as e:
        st.error(f"Ocorreu um erro durante o processamento: {str(e)}")
        st.stop()
else:
    st.info("Por favor, carregue um arquivo Excel para iniciar o processamento.")
