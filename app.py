# Arquivo: app.py (VERSÃO COM FILTRO DE SISTEMA NA INTERFACE WEB)

import streamlit as st
from identificador import identificar_layout, recarregar_modelo
import os
import subprocess
import time

# --- Configurações Iniciais e Funções de Apoio ---
TEMP_DIR = "temp_files"
TRAIN_DIR = "arquivos_de_treinamento"
MAP_FILE = "mapeamento_layouts.xlsx"

for folder in [TEMP_DIR, TRAIN_DIR]:
    if not os.path.exists(folder):
        os.makedirs(folder)

st.set_page_config(page_title="Identificador de Layouts", layout="wide")
st.title("🤖 Identificador Automático de Layouts")

# --- LÓGICA DE LOGIN E PAINEL DE ADMIN NA SIDEBAR ---
# ... (O código do painel de administração na sidebar permanece o mesmo) ...
st.sidebar.title("Painel de Administração")
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
username_input = st.sidebar.text_input("Usuário", key="username")
password_input = st.sidebar.text_input("Senha", type="password", key="password")
if st.sidebar.button("Login"):
    if (username_input == st.secrets["admin_credentials"]["username"] and 
        password_input == st.secrets["admin_credentials"]["password"]):
        st.session_state.authenticated = True
        st.rerun()
    else:
        st.sidebar.error("Usuário ou senha incorretos.")
if st.session_state.authenticated:
    st.sidebar.success(f"Bem-vindo, {st.secrets['admin_credentials']['username']}!")
    st.sidebar.header("Upload de Arquivos")
    uploaded_map_file = st.sidebar.file_uploader("1. Enviar arquivo de mapeamento (.xlsx)", type=['xlsx'])
    if uploaded_map_file is not None:
        try:
            with open(MAP_FILE, "wb") as f:
                f.write(uploaded_map_file.getbuffer())
            st.sidebar.success(f"Arquivo '{MAP_FILE}' atualizado!")
        except PermissionError:
            st.sidebar.error(f"Erro de Permissão! Verifique se o arquivo '{MAP_FILE}' não está aberto no Excel.")
        except Exception as e:
            st.sidebar.error(f"Ocorreu um erro ao salvar: {e}")
    uploaded_training_files = st.sidebar.file_uploader("2. Enviar arquivos de treinamento", accept_multiple_files=True)
    if uploaded_training_files:
        saved_count = 0
        for file in uploaded_training_files:
            file_path = os.path.join(TRAIN_DIR, file.name)
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
            saved_count += 1
        st.sidebar.success(f"{saved_count} arquivo(s) salvos em '{TRAIN_DIR}'.")
    st.sidebar.header("Gerenciamento do Modelo")
    if st.sidebar.button("Iniciar Retreinamento do Modelo"):
        st.sidebar.info("O treinamento foi iniciado em segundo plano...")
        subprocess.Popen(['python', 'treinador_em_massa.py'])
        st.sidebar.warning("Aguarde a finalização antes de recarregar o modelo.")
    if st.sidebar.button("Recarregar Modelo na Aplicação"):
        with st.spinner("Recarregando modelo..."):
            if recarregar_modelo():
                st.sidebar.success("Modelo recarregado com sucesso!")
                time.sleep(2)
                st.rerun()
            else:
                st.sidebar.error("Falha ao recarregar.")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.rerun()

# --- INTERFACE PRINCIPAL DO IDENTIFICADOR (COM ALTERAÇÕES) ---
st.divider()
st.header("Identificar Layout")

# --- FUNÇÃO DE ANÁLISE ATUALIZADA ---
def analisar_arquivo(caminho_arquivo, sistema=None, senha=None):
    # Passa o parâmetro 'sistema' para a função de identificação
    st.session_state.resultados = identificar_layout(caminho_arquivo, sistema_alvo=sistema, senha_manual=senha)
    st.session_state.senha_incorreta = (st.session_state.resultados == "SENHA_INCORRETA")
    st.session_state.senha_necessaria = (st.session_state.resultados == "SENHA_NECESSARIA")
    st.session_state.analise_feita = True

# ... (Gerenciamento de Estado permanece o mesmo) ...
if 'analise_feita' not in st.session_state:
    st.session_state.analise_feita = False
if 'resultados' not in st.session_state:
    st.session_state.resultados = None
if 'senha_necessaria' not in st.session_state:
    st.session_state.senha_necessaria = False
if 'senha_incorreta' not in st.session_state:
    st.session_state.senha_incorreta = False
if 'caminho_arquivo_temp' not in st.session_state:
    st.session_state.caminho_arquivo_temp = ""

# --- NOVO CAMPO DE TEXTO PARA O SISTEMA ---
sistema_input = st.text_input(
    "Sistema que gerou o relatório (Opcional)",
    help="Informe o nome do sistema (ex: Dominio, SCI) para dar preferência a layouts desse sistema."
)

uploaded_file = st.file_uploader(
    "Selecione o arquivo para identificar",
    type=['pdf', 'xlsx', 'xls', 'txt', 'csv', 'xml'],
    key="identifier"
)

if uploaded_file is not None:
    caminho_atual = os.path.join(TEMP_DIR, uploaded_file.name)
    if st.session_state.caminho_arquivo_temp != caminho_atual:
        st.session_state.caminho_arquivo_temp = caminho_atual
        with open(caminho_atual, "wb") as f:
            f.write(uploaded_file.getbuffer())
        with st.spinner('Analisando arquivo...'):
            # Passa o valor do campo de sistema para a função de análise
            analisar_arquivo(caminho_atual, sistema=sistema_input)

# ... (O resto do código, de senha e exibição de resultados, permanece o mesmo) ...
if st.session_state.senha_necessaria:
    st.warning("🔒 O arquivo PDF está protegido por senha.")
    senha_manual = st.text_input("Por favor, digite a senha do PDF:", type="password", key="pwd_input")
    if st.button("Tentar novamente com a senha"):
        if senha_manual:
            with st.spinner('Analisando com a senha fornecida...'):
                analisar_arquivo(st.session_state.caminho_arquivo_temp, sistema=sistema_input, senha=senha_manual)
        else:
            st.error("Por favor, insira uma senha.")
if st.session_state.senha_incorreta:
    st.error("A senha manual fornecida está incorreta.")
if st.session_state.analise_feita and not st.session_state.senha_necessaria:
    st.subheader("🏆 Ranking de Layouts Compatíveis")
    resultados = st.session_state.resultados
    if isinstance(resultados, str) and "SENHA" in resultados:
        pass
    elif isinstance(resultados, dict) and 'erro' in resultados:
        st.error(f"Ocorreu um erro: {resultados['erro']}")
    elif not resultados:
        st.warning("Nenhum layout compatível foi encontrado.")
    else:
        for i, res in enumerate(resultados):
            rank, emoji = (i + 1, "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}º**")
            with st.container(border=True):
                st.markdown(f"### {emoji} {res['banco']}\n- **Código:** `{res['codigo_layout']}`\n- **Confiança:** **{res['pontuacao']}%**")