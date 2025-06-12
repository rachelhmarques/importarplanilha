import streamlit as st
import pdfplumber
import re
import csv
import io

st.title("Extrator de Transações do Extrato Banco do Brasil")

uploaded_file = st.file_uploader("Faça o upload do arquivo PDF do extrato", type=["pdf"])

def processar_texto(texto):
transacoes_local = []
linhas = texto.split('\n')
for linha in linhas:
# Aqui, você deve ajustar o padrão conforme o layout do seu extrato
# Exemplo de padrão para detectar datas e valores na linha
padrao = re.compile(r'(\d{2}/\d{2}/\d{4})\s+([\d\-,]+)\s*(C|D)?')
match = padrao.search(linha)
if match:
data_str = match.group(1)
valor_str = match.group(2)
# Converter data para AAAAMMDD
dia, mes, ano = data_str.split('/')
data = f"{ano}{mes}{dia}"

# Converter valor para float
valor = float(valor_str.replace('.', '').replace(',', '.'))
# Verifica se é débito ou crédito
tipo = match.group(3) if match.group(3) else ''

# Se for débito, valor negativo
if tipo == 'D':
valor = -valor

# Adiciona à lista de transações
transacoes_local.append({
"tipo": "PIX ou TRANSFER",  # Você pode ajustar este campo
"data": data,
"valor": valor,
"id": "",
"nome": "",
"memo": ""
})

return transacoes_local

if uploaded_file:
# Leitura do PDF
with pdfplumber.open(uploaded_file) as pdf:
primeira_pagina = pdf.pages[0]
texto = primeira_pagina.extract_text()

# Processa o texto extraído
transacoes = processar_texto(texto)

if transacoes:
st.subheader("Transações Detectadas")
st.dataframe(transacoes)

# Criar CSV em memória
output = io.StringIO()
writer = csv.DictWriter(output, fieldnames=["tipo", "data", "valor", "id", "nome", "memo"])
writer.writeheader()
writer.writerows(transacoes)
csv_data = output.getvalue()

# Botão para download
st.download_button(
label="Download do CSV",
data=csv_data,
file_name="extrato_extraido.csv",
mime="text/csv"
)
else:
st.info("Nenhuma transação detectada no PDF carregado.")
