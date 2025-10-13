import streamlit as st
import pandas as pd
from gspread import service_account, service_account_from_dict
from datetime import datetime
import json # Necessário para o tratamento robusto do st.secrets

# --- Configurações Iniciais ---
PLANILHA_NOME = "Estoque_industria_Analitico" # Verifique se este nome está EXATO
COLUNAS_NUMERICAS_LIMPEZA = ['KG', 'CX']
COLUNAS_DATA_FORMATACAO = ['FABRICACAO', 'VALIDADE']
ABA_NOME = "ESTOQUETotal"

# Colunas que serão exibidas na tabela final
COLUNAS_EXIBICAO = [
    'TIPO',
    'RASTREIO',
    'NOTA FISCAL',
    'MATÉRIA-PRIMA',
    'PRODUTO',
    'KG',
    'CX',
    'FABRICACAO',
    'VALIDADE',
    'STATUS VALIDADE'
]

# --- Configurações de Página ---
st.set_page_config(
    page_title="Consulta Estoque Indústria",
    page_icon="🔎",
    layout="wide"
)

# --- Formatar data (Padrão Brasileiro) ---

def formatar_br_data(d):
    """
    Formata um objeto datetime/Timestamp para o formato brasileiro dd/mm/aaaa.
    Lida com valores nulos (NaT) e vazios (pd.isna).
    """
    if pd.isna(d):
        return ''

    if pd.isnull(d):
        return ''

    try:
        # Usa strftime, o método padrão para formatar objetos datetime
        return d.strftime("%d/%m/%Y")
    except AttributeError:
        # Retorna o valor original (string, número) se a conversão falhou
        return str(d)

# --- Funções de Formatação (Padrão Brasileiro) ---

def formatar_br_numero_inteiro(x):
    """Formata número inteiro usando ponto como separador de milhar."""
    if pd.isna(x):
        return ''

    val = int(round(x)) if pd.notna(x) else 0
    s = f"{val:,}"

    return s.replace(',', '#TEMP#').replace('.', ',').replace('#TEMP#', '.').strip()


# --- Conexão e Carregamento de Dados ---
@st.cache_data(ttl=600)
def load_data():
    """Conecta e carrega os dados da planilha."""

    # --- AUTENTICAÇÃO ROBUSTA (st.secrets) ---
    try:
        if "gcp_service_account" not in st.secrets:
             raise ValueError("Nenhuma seção [gcp_service_account] encontrada no st.secrets.")

        secrets_dict = dict(st.secrets["gcp_service_account"])
        private_key_corrompida = secrets_dict["private_key"]

        private_key_limpa = private_key_corrompida.replace('\n', '').replace(' ', '')
        private_key_limpa = private_key_limpa.replace('-----BEGINPRIVATEKEY-----', '').replace('-----ENDPRIVATEKEY-----', '')
        padding_necessario = len(private_key_limpa) % 4
        if padding_necessario != 0:
            private_key_limpa += '=' * (4 - padding_necessario)
        secrets_dict["private_key"] = f"-----BEGIN PRIVATE KEY-----\n{private_key_limpa}\n-----END PRIVATE KEY-----\n"

        gc = service_account_from_dict(secrets_dict)
        
    except Exception as e:
        st.error(f"Erro de autenticação/acesso: Verifique se a chave no secrets.toml está correta. Detalhe: {e}")
        return pd.DataFrame(), None
        
    # --- ACESSO À PLANILHA E LEITURA ROBUSTA ---
    try:
        planilha = gc.open(PLANILHA_NOME)
        data_atualizacao_raw = planilha.get_lastUpdateTime() # nova função captura de data google drive
        aba = planilha.worksheet(ABA_NOME)

        # Leitura robusta usando get_all_values() com intervalo forçado
        # Seus dados vão até a coluna 'STATUS VALIDADE' (coluna J na planilha)
        RANGE_PLANILHA = "A1:K"
        all_data = aba.get_values(RANGE_PLANILHA)

        headers = all_data[0]
        data_rows = all_data[1:]

        df = pd.DataFrame(data_rows, columns=headers)

        # 1. LIMPEZA INICIAL DE COLUNAS/LINHAS VAZIAS
        df.columns = df.columns.str.strip()
        df.dropna(axis=1, how='all', inplace=True)
        df.dropna(how='all', inplace=True)

        # 2. CONVERSÃO DE TIPOS DE DADOS (CRUCIAL PARA A FORMATAÇÃO)

        # Converte Datas
        for col in COLUNAS_DATA_FORMATACAO:
            if col in df.columns:
                # dayfirst=True é essencial para garantir que 01/05/2025 seja lido como 1 de Maio
                df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)

        # Converte Números
        for col in COLUNAS_NUMERICAS_LIMPEZA:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].str.replace('.', '', regex=False)
                df[col] = df[col].str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Retorna o DataFrame limpo e convertido
        return df, data_atualizacao_raw

    except Exception as e:
        # Se o erro for aqui, ele pode ser um problema de nome de aba/permissão/estrutura
        st.error(f"Erro ao carregar dados da planilha: Verifique o nome da planilha ('{PLANILHA_NOME}'), a aba ('{ABA_NOME}') ou a estrutura de dados (células mescladas/vazias na linha 1). Detalhe: {e}")
        return pd.DataFrame(), None


# --- Carregar e Exibir os Dados ---
df_estoque, data_atualizacao_raw = load_data()

# --- FORMATAÇÃO E EXIBIÇÃO DA DATA DE ATUALIZAÇÃO ---
data_atualizacao_formatada = ""
if data_atualizacao_raw:
    try:
        # Converte a string ISO (gspread) para datetime
        data_dt = datetime.fromisoformat(data_atualizacao_raw.replace('Z', '+00:00'))
        data_atualizacao_formatada = formatar_br_data(data_dt)
    except Exception:
        data_atualizacao_formatada = "Erro ao formatar data"

st.title("🔎 Consulta Estoque Indústria")
if data_atualizacao_formatada:
    st.markdown(f"**Última Atualização:** {data_atualizacao_formatada}")
st.markdown("---")

if not df_estoque.empty:

    # --- PREPARO DOS DADOS DE FILTRO ---
    for col_filtro in ['TIPO', 'PRODUTO', 'RASTREIO', 'STATUS VALIDADE']:
        if col_filtro in df_estoque.columns:
            df_estoque[col_filtro] = df_estoque[col_filtro].astype(str).fillna('Não Informado')

    opcoes_tipo = ['Todos'] + sorted(df_estoque['TIPO'].unique().tolist())
    opcoes_produto = ['Todos'] + sorted(df_estoque['PRODUTO'].unique().tolist())
    opcoes_status = ['Todos'] + sorted(df_estoque['STATUS VALIDADE'].unique().tolist())

    # --- INTERFACE DE FILTRO ---
    st.subheader("Filtros de Consulta")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        rastreio_input = st.text_input("🔍 Filtrar por Rastreio:", help="Filtro parcial (contém)")

    with col2:
        tipo_filtro = st.selectbox("📝 Filtrar por Tipo:", opcoes_tipo)

    with col3:
        produto_filtro = st.selectbox("🏭 Filtrar por Produto:", opcoes_produto)

    with col4:
        status_filtro = st.selectbox("📅 Filtrar por Status:", opcoes_status)


    # --- LÓGICA DE FILTRAGEM ---
    df_filtrado = df_estoque.copy()

    rastreio_input = rastreio_input.lower().strip()
    if rastreio_input:
        df_filtrado = df_filtrado[
            df_filtrado['RASTREIO']
            .astype(str)
            .str.lower()
            .str.contains(rastreio_input, na=False)
        ]

    if tipo_filtro != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['TIPO'] == tipo_filtro]

    if produto_filtro != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['PRODUTO'] == produto_filtro]

    if status_filtro != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['STATUS VALIDADE'] == status_filtro]


    # --- CÁLCULO E EXIBIÇÃO DOS TOTAIS ---

    total_kg = df_filtrado['KG'].sum()
    total_cx = df_filtrado['CX'].sum()

    total_kg_formatado = formatar_br_numero_inteiro(total_kg)
    total_cx_formatado = formatar_br_numero_inteiro(total_cx)

    st.markdown("---")
    st.subheader(f"Resultados Encontrados ({len(df_filtrado)} itens)")

    col_t1, col_t2, col_t3 = st.columns(3)

    with col_t1:
        st.metric(label="📦 Total de Caixas (CX)", value=total_cx_formatado)

    with col_t2:
        st.metric(label="⚖️ Total de Quilogramas (KG)", value=total_kg_formatado)

    with col_t3:
        st.write("")


    # --- APLICAÇÃO DA FORMATAÇÃO E SELEÇÃO DE COLUNAS ---

    try:
        df_display = df_filtrado[COLUNAS_EXIBICAO].copy()
    except KeyError as e:
        st.error(f"Erro: A coluna {e} não foi encontrada. Verifique se os nomes são exatos: {COLUNAS_EXIBICAO}")
        st.stop()

    # Aplica a formatação de números inteiros
    for col in COLUNAS_NUMERICAS_LIMPEZA:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(formatar_br_numero_inteiro)

    # Aplicando a formatação nas datas
    for col in COLUNAS_DATA_FORMATACAO:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(formatar_br_data)

    # --- EXIBIÇÃO ---
    if not df_filtrado.empty:
        st.dataframe(
            df_display,
            use_container_width=True
        )
    else:
        st.warning("Nenhum resultado encontrado para os filtros aplicados.")

