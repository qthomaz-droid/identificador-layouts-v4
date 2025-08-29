# Arquivo: app.py (VERSÃO COM INTERFACE APRIMORADA)

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

def processar_novo_arquivo():
    uploaded_file = st.session_state.get("file_uploader")
    if uploaded_file:
        caminho_arquivo = os.path.join(TEMP_DIR, uploaded_file.name)
        with open(caminho_arquivo, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.session_state.caminho_arquivo_temp = caminho_arquivo
        with st.spinner('Analisando arquivo...'):
            analisar_arquivo(caminho_arquivo, sistema=st.session_state.get("sistema_input"))

def analisar_arquivo(caminho_arquivo, sistema=None, senha=None):
    st.session_state.resultados = identificar_layout(caminho_arquivo, sistema_alvo=sistema, senha_manual=senha)
    st.session_state.senha_incorreta = (st.session_state.resultados == "SENHA_INCORRETA")
    st.session_state.senha_necessaria = (st.session_state.resultados == "SENHA_NECESSARIA")
    st.session_state.analise_feita = True

# --- Gerenciamento de Estado (Inicialização) ---
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

# --- PAINEL DE ADMIN NA SIDEBAR (sem alterações) ---
st.sidebar.title("Painel de Administração")
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
username_input = st.sidebar.text_input("Usuário", key="username")
password_input = st.sidebar.text_input("Senha", type="password", key="password")
if st.sidebar.button("Login"):
    if (st.secrets and "admin_credentials" in st.secrets and
        username_input == st.secrets["admin_credentials"]["username"] and 
        password_input == st.secrets["admin_credentials"]["password"]):
        st.session_state.authenticated = True; st.rerun()
    else:
        st.sidebar.error("Usuário ou senha incorretos.")
if st.session_state.authenticated:
    st.sidebar.success(f"Bem-vindo, {st.secrets['admin_credentials']['username']}!")
    st.sidebar.header("Upload de Arquivos")
    uploaded_map_file = st.sidebar.file_uploader("1. Enviar arquivo de mapeamento (.xlsx)", type=['xlsx'])
    if uploaded_map_file:
        try:
            with open(MAP_FILE, "wb") as f: f.write(uploaded_map_file.getbuffer())
            st.sidebar.success(f"Arquivo '{MAP_FILE}' atualizado!")
        except PermissionError:
            st.sidebar.error(f"Erro de Permissão! Verifique se o '{MAP_FILE}' não está aberto no Excel.")
        except Exception as e:
            st.sidebar.error(f"Ocorreu um erro ao salvar: {e}")
    uploaded_training_files = st.sidebar.file_uploader("2. Enviar arquivos de treinamento", accept_multiple_files=True)
    if uploaded_training_files:
        saved_count = 0
        for file in uploaded_training_files:
            with open(os.path.join(TRAIN_DIR, file.name), "wb") as f: f.write(file.getbuffer())
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
                st.sidebar.success("Modelo recarregado com sucesso!"); time.sleep(2); st.rerun()
            else:
                st.sidebar.error("Falha ao recarregar.")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False; st.rerun()

# --- INTERFACE PRINCIPAL DO IDENTIFICADOR ---
st.divider()
st.header("Identificar Layout")

sistema_input = st.text_input(
    "Sistema (Opcional)",
    help="Informe o nome do sistema para dar preferência a layouts desse sistema.",
    key="sistema_input"
)

uploaded_file = st.file_uploader(
    "Selecione o arquivo para identificar",
    type=['pdf', 'xlsx', 'xls', 'txt', 'csv', 'xml'],
    key="file_uploader",
    on_change=processar_novo_arquivo
)

# --- LÓGICA DE EXIBIÇÃO DE RESULTADOS (COM AS MELHORIAS) ---
if st.session_state.senha_necessaria:
    st.warning("🔒 O arquivo PDF está protegido por senha.")
    senha_manual = st.text_input("Por favor, digite a senha do PDF:", type="password", key="pwd_input")
    if st.button("Tentar novamente com a senha"):
        if senha_manual:
            with st.spinner('Analisando com a senha fornecida...'):
                analisar_arquivo(st.session_state.caminho_arquivo_temp, sistema=st.session_state.sistema_input, senha=senha_manual)
                st.rerun()
        else:
            st.error("Por favor, insira uma senha.")

elif st.session_state.senha_incorreta:
    st.error("A senha manual fornecida está incorreta.")

elif st.session_state.analise_feita:
    resultados = st.session_state.resultados
    
    # --- MUDANÇA 1: TÍTULO CONDICIONAL ---
    # Verifica se há resultados e se o primeiro tem confiança maior ou igual a 85%
    if resultados and isinstance(resultados, list) and resultados[0]['pontuacao'] >= 85:
        st.subheader("🏆 Ranking de Layouts Compatíveis")
    else:
        st.subheader("Estes são os 5 resultados que mais se aproximam do arquivo enviado.")
    
    if isinstance(resultados, str) and "SENHA" in resultados:
        pass
    elif isinstance(resultados, dict) and 'erro' in resultados:
        st.error(f"Ocorreu um erro: {resultados['erro']}")
    elif not resultados:
        st.warning("Nenhum layout compatível foi encontrado.")
    else:
        for i, res in enumerate(resultados):
            rank = i + 1
            
            # --- MUDANÇA 2: ÍCONES CONDICIONAIS ---
            # O emoji de medalha só é atribuído se a pontuação for >= 85
            if res['pontuacao'] >= 85:
                emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"**{rank}º**"
            else:
                emoji = f"**{rank}º**" # Sem medalha para scores baixos

            with st.container(border=True):
                st.markdown(f"### {emoji} {res['banco']}\n- **Código:** `{res['codigo_layout']}`\n- **Confiança:** **{res['pontuacao']}%**")