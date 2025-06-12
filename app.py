import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime
import pdfplumber # Você precisará instalar isso: pip install pdfplumber
from ofxtools.Writer import OfxWriter # Você precisará instalar isso: pip install ofxtools

# ... (imports existentes e verificações de fuzzywuzzy/openpyxl) ...

st.title("Ajuste de Planilhas e Extratos Bancários")
st.markdown("Faça o upload do arquivo (`Economatos - planilha_Modelo_para_Importacao_do_Plano_de_categorias.xlsx`) ou do extrato PDF do Banco do Brasil para gerar os arquivos separados ou OFX.")

# File uploader
uploaded_file = st.file_uploader("Selecione o arquivo (Excel ou PDF)", type=["xlsx", "pdf"])

if uploaded_file is not None:
    if uploaded_file.type == "application/pdf":
        try:
            with st.spinner("Processando extrato PDF..."):
                all_transactions = []
                with pdfplumber.open(uploaded_file) as pdf:
                    for page in pdf.pages:
                        # Extrair tabelas (assumindo que as transações estão em tabelas)
                        # Você pode precisar ajustar as configurações de extração de tabelas
                        tables = page.extract_tables()
                        for table in tables:
                            # Exemplo: Análise básica baseada no trecho do PDF
                            # Estrutura da linha: Dt. balancete, Dt. movimento, Ag. origem, Lote, Histórico, Valor R$, Documento, Saldo
                            for row in table:
                                if len(row) >= 7 and row[0] and row[5]: # Garantir que as colunas essenciais existam
                                    dt_movimento = row[1]
                                    historico = row[4]
                                    valor_rs = row[5] # Isso precisa de análise cuidadosa para C/D e valor

                                    # Limpeza básica da data (ex: "02/01/2025")
                                    try:
                                        transaction_date = datetime.strptime(dt_movimento.split(' ')[0], '%d/%m/%Y')
                                    except ValueError:
                                        continue # Pular se a data não puder ser analisada

                                    # Analisar valor e determinar o tipo de transação
                                    amount_str = valor_rs.replace('.', '').replace(',', '.')
                                    transaction_type = 'DEBIT'
                                    if 'C' in amount_str:
                                        transaction_type = 'CREDIT'
                                        amount_str = amount_str.replace(' C', '')
                                    elif 'D' in amount_str:
                                        transaction_type = 'DEBIT'
                                        amount_str = amount_str.replace(' D', '')

                                    try:
                                        amount = float(amount_str)
                                        if transaction_type == 'DEBIT':
                                            amount = -amount # Débitos são negativos em OFX
                                    except ValueError:
                                        continue # Pular se o valor não puder ser analisado

                                    all_transactions.append({
                                        'date': transaction_date,
                                        'type': transaction_type,
                                        'amount': amount,
                                        'memo': historico,
                                        'fitid': f"{transaction_date.strftime('%Y%m%d')}-{abs(hash(historico + str(amount)))}" # ID único simples
                                    })
                if not all_transactions:
                    st.warning("Nenhuma transação encontrada no PDF. Certifique-se de que o PDF contenha dados de tabela extraíveis.")
                    st.stop()

                # Gerar OFX
                writer = OfxWriter()
                # Configurar cabeçalho OFX e informações da conta (substitua pelos detalhes reais do banco)
                writer.new_profilemsg()
                writer.new_signonmsg(
                    fi_org='Banco do Brasil',
                    fi_fid='1000', # ID FI fictício, encontre o real se possível
                    gen_dt=datetime.now(),
                    user_id='SEU_ID_DE_USUARIO', # Substitua pelo ID de usuário real
                    user_key='SUA_CHAVE_DE_USUARIO' # Substitua pela chave de usuário real
                )
                writer.new_bankmsg()
                writer.new_stmttrnrs(
                    curdef='BRL',
                    bankid='001', # SWIFT/BIC do Banco do Brasil ou ID do banco
                    acctid='31779-9', # Número da conta do PDF
                    accttype='CHECKING', # Ou SAVINGS, etc.
                    dtstart=min(t['date'] for t in all_transactions),
                    dtend=max(t['date'] for t in all_transactions)
                )

                for t in all_transactions:
                    writer.stmttrn(
                        trntype=t['type'],
                        dtposted=t['date'],
                        trnamt=t['amount'],
                        fitid=t['fitid'],
                        memo=t['memo']
                    )

                ofx_data = writer.build()

                ofx_output_buffer = io.BytesIO()
                ofx_output_buffer.write(ofx_data)
                ofx_output_buffer.seek(0)

                st.download_button(
                    label="Download Extrato OFX (Money 2000)",
                    data=ofx_output_buffer,
                    file_name="extrato_bb_money2000.ofx",
                    mime="application/x-ofx" # Tipo MIME correto para OFX
                )
                st.success("Extrato OFX gerado com sucesso!")

        except Exception as e:
            st.error(f"Erro ao processar PDF: {str(e)}")

    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        # ... (lógica existente de processamento de Excel) ...
        if not openpyxl_available:
            st.error("Não é possível prosseguir sem 'openpyxl'. Por favor, instale-o e implante o aplicativo novamente.")
            st.stop()
        # ... (resto do seu código existente de processamento de Excel) ...

st.markdown("---")
st.markdown("Deus é bom o tempo todo. O tempo todo Deus é bom!")
