import streamlit as st
import pdfplumber
import re
import csv
import io

st.title("Extrator de Transações do Extrato Banco do Brasil")

uploaded_file = st.file_uploader("Faça o upload do arquivo PDF do extrato", type=["pdf"])

if uploaded_file:
# Função para processar o texto extraído
def processar_texto(texto):
transacoes_local = []
linhas = texto.split('\n')
for linha in linhas:
# Aqui, você pode ajustar o padrão de extração conforme o layout do seu extrato
padrao = re.compile(r'(\d{2}/\d{2}/\d{4})\s+([\d\-,]+)\s+C|D')
match = padrao.search(linha)
if match:
data_str = match.group(1)
valor_str = match.group(2)
# Converter data
dia, mes, ano = data_str.split('/')
data = f"{ano}{mes}{dia}"
# Converter valor
valor = float(valor_str.replace(',', '').replace('-', ''))
if '-' in valor_str:
valor = -valor
# Armazenar transação
transacoes_local.append({
"tipo": "PIX ou TRANSFER",  # pode ajustar
"data": data,
"valor": valor,
"id": "",
"nome": "",
"memo": ""
})

return transacoes_local

# Leitura do PDF
with pdfplumber.open(uploaded_file) as pdf:
primeira_pagina = pdf.pages[0]
texto = primeira_pagina.extract_text()
transacoes = processar_texto(texto)

# Mostrar transações na tabela
if transacoes:
st.subheader("Transações Detectadas")
st.dataframe(transacoes)

# Criar CSV em memória
output = io.StringIO()
writer = csv.DictWriter(output, fieldnames=["tipo", "data", "valor", "id", "nome", "memo"])
writer.writeheader()
writer.writerows(transacoes)
csv_data = output.getvalue()

# Link para download
st.download_button(
label="Download do CSV",
data=csv_data,
file_name="extrato_extraido.csv",
mime="text/csv"
)
else:
st.info("Nenhuma transação detectada no PDF carregado.")
