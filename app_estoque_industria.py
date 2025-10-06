import streamlit as st
import pandas as pd
from gspread import service_account, service_account_from_dict

# --- Configurações Iniciais ---
PLANILHA_NOME = "Estoque_industria_Analitico"

# NOVAS COLUNAS QUE SERÃO EXIBIDAS NA TABELA FINAL (ORDEM DA SUA PLANILHA)
COLUNAS_EXIBICAO = [
    'TIPO',
    'RASTREIO',
    'NOTA FISCAL',
    'MATÉRIA-PRIMA',
    'PRODUTO',
    'KG',
    'CX'
]

# Colunas que precisam de limpeza e conversão numérica (KG e CX)
COLUNAS_NUMERICAS_LIMPEZA = ['KG', 'CX']

# --- Configurações de Página ---
st.set_page_config(
    page_title="Consulta Estoque Indústria",
    page_icon="🔎",
    layout="wide"
)

# --- Funções de Formatação (Padrão Brasileiro) ---

def formatar_br_numero_inteiro(x):
    """Formata número inteiro usando ponto como separador de milhar."""
    if pd.isna(x):
        return ''

    # Se não for inteiro, arredonda e converte para int
    val = int(round(x)) if pd.notna(x) else 0

    # Formata com separador de milhar (vírgula)
    s = f"{val:,}"

    # Inverte os separadores: vírgula milhar -> ponto (Padrão BR)
    return s.replace(',', '#TEMP#').replace('.', ',').replace('#TEMP#', '.').strip()


# --- Conexão e Carregamento de Dados ---
@st.cache_data(ttl=600)
def load_data():
    """Conecta e carrega os dados da planilha."""

    # --- AUTENTICAÇÃO UNIFICADA (NUVEM OU LOCAL) ---
    try:
        if "gcp_service_account" not in st.secrets:
             raise ValueError("Nenhuma seção [gcp_service_account] encontrada no st.secrets.")

        secrets_dict = dict(st.secrets["gcp_service_account"])
        private_key_corrompida = secrets_dict["private_key"]

        # Lógica de limpeza e padding da chave
        private_key_limpa = private_key_corrompida.replace('\n', '').replace(' ', '')
        private_key_limpa = private_key_limpa.replace('-----BEGINPRIVATEKEY-----', '').replace('-----ENDPRIVATEKEY-----', '')
        padding_necessario = len(private_key_limpa) % 4
        if padding_necessario != 0:
            private_key_limpa += '=' * (4 - padding_necessario)
        secrets_dict["private_key"] = f"-----BEGIN PRIVATE KEY-----\n{private_key_limpa}\n-----END PRIVATE KEY-----\n"

        gc = service_account_from_dict(secrets_dict)

    except Exception as e:
        st.error(f"Erro de autenticação/acesso: Verifique se a chave no secrets.toml (ou no Streamlit Cloud) está correta. Detalhe: {e}")
        return pd.DataFrame()

    # --- ACESSO À PLANILHA E LIMPEZA DE DADOS ---
    try:
        planilha = gc.open(PLANILHA_NOME)
        abanome = 'ESTOQUETotal'
        aba = planilha.workssheet(abanome)#sheet1

        data = aba.get_all_records()
        df = pd.DataFrame(data)

        # --- Limpeza de Tipos Numéricos (KG, CX) ---
        for col in COLUNAS_NUMERICAS_LIMPEZA:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                # 1. Remove separador de milhar (ponto)
                df[col] = df[col].str.replace('.', '', regex=False)
                # 2. Troca decimal (vírgula) por ponto
                df[col] = df[col].str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')

        df.dropna(how='all', inplace=True)

        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha: Verifique o nome da planilha ou permissões. Detalhe: {e}")
        return pd.DataFrame()

# --- Carregar e Exibir os Dados ---
df_estoque = load_data()

st.title("🔎 Consulta de Rastreio e Matéria-Prima")
st.markdown("---")

if not df_estoque.empty:

    # --- PREPARO DOS DADOS DE FILTRO ---
    for col_filtro in ['TIPO', 'PRODUTO', 'RASTREIO']:
        if col_filtro in df_estoque.columns:
            df_estoque[col_filtro] = df_estoque[col_filtro].astype(str).fillna('Não Informado')

    opcoes_tipo = ['Todos'] + sorted(df_estoque['TIPO'].unique().tolist())
    opcoes_produto = ['Todos'] + sorted(df_estoque['PRODUTO'].unique().tolist())

    # --- INTERFACE DE FILTRO ---
    st.subheader("Filtros de Consulta")

    col1, col2, col3 = st.columns(3)

    with col1:
        rastreio_input = st.text_input("🔍 Filtrar por Rastreio:", help="Filtro parcial (contém)")

    with col2:
        tipo_filtro = st.selectbox("📝 Filtrar por Tipo:", opcoes_tipo)

    with col3:
        produto_filtro = st.selectbox("🏭 Filtrar por Produto:", opcoes_produto)


    # --- LÓGICA DE FILTRAGEM ---
    df_filtrado = df_estoque.copy()

    # 1. Filtro por Rastreio (text input)
    rastreio_input = rastreio_input.lower().strip()
    if rastreio_input:
        df_filtrado = df_filtrado[
            df_filtrado['RASTREIO']
            .astype(str)
            .str.lower()
            .str.contains(rastreio_input, na=False)
        ]

    # 2. Filtro por Tipo (selectbox)
    if tipo_filtro != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['TIPO'] == tipo_filtro]

    # 3. Filtro por Produto (selectbox)
    if produto_filtro != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['PRODUTO'] == produto_filtro]


    # --- CÁLCULO E EXIBIÇÃO DOS TOTAIS (NOVA SEÇÃO) ---

    # 1. Calcula os totais (somente no DataFrame FILTRADO)
    total_kg = df_filtrado['KG'].sum()
    total_cx = df_filtrado['CX'].sum()

    # 2. Formata os totais para exibição
    total_kg_formatado = formatar_br_numero_inteiro(total_kg)
    total_cx_formatado = formatar_br_numero_inteiro(total_cx)

    st.markdown("---")
    st.subheader(f"Resultados Encontrados ({len(df_filtrado)} itens)")

    # Exibe os totais usando st.metric
    col_t1, col_t2, col_t3 = st.columns(3)

    with col_t1:
        st.metric(label="📦 Total de Caixas (CX)", value=total_cx_formatado)

    with col_t2:
        st.metric(label="⚖️ Total de Quilogramas (KG)", value=total_kg_formatado)

    with col_t3:
        # Espaço vazio ou métrica adicional se necessário
        st.write("")


    # --- APLICAÇÃO DA FORMATAÇÃO E SELEÇÃO DE COLUNAS ---

    # 1. Seleciona e copia APENAS as colunas desejadas
    try:
        df_display = df_filtrado[COLUNAS_EXIBICAO].copy()
    except KeyError as e:
        st.error(f"Erro: A coluna {e} não foi encontrada na sua planilha. Verifique se os nomes são exatos: {COLUNAS_EXIBICAO}")
        st.stop()

    # 2. Aplica a formatação de números inteiros nas colunas numéricas
    for col in COLUNAS_NUMERICAS_LIMPEZA:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(formatar_br_numero_inteiro)

    # --- EXIBIÇÃO ---
    if not df_filtrado.empty:
        st.dataframe(
            df_display,
            use_container_width=True
        )
    else:
        st.warning("Nenhum resultado encontrado para os filtros aplicados.")


