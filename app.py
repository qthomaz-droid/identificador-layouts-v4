# Arquivo: app.py

import streamlit as st
import os
import subprocess
import time
import sys
from dotenv import load_dotenv

# --- LÓGICA DE CARREGAMENTO EXPLÍCITO DE SEGREDOS ---
# Garante que os segredos sejam carregados ANTES de importar o 'identificador'
caminho_secrets = os.path.join(".streamlit", "secrets.toml")
if os.path.exists(caminho_secrets):
    load_dotenv(dotenv_path=caminho_secrets)
    print("Arquivo de segredos do Streamlit carregado para o ambiente.")

from identificador import identificar_layout, recarregar_modelo

# --- Configurações Iniciais ---
TEMP_DIR = "temp_files"
TRAIN_DIR = "arquivos_de_treinamento"
MAP_FILE = "mapeamento_layouts.xlsx"
for folder in [TEMP_DIR, TRAIN_DIR]:
    if not os.path.exists(folder):
        os.makedirs(folder)
st.set_page_config(page_title="Identificador de Layouts", layout="wide")
st.title("🤖 Identificador Automático de Layouts")

# ... (O resto do seu arquivo app.py permanece o mesmo, pois a lógica de exibição já está correta) ...
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
if 'analise_feita' not in st.session_state: st.session_state.analise_feita = False
if 'resultados' not in st.session_state: st.session_state.resultados = None
if 'senha_necessaria' not in st.session_state: st.session_state.senha_necessaria = False
if 'senha_incorreta' not in st.session_state: st.session_state.senha_incorreta = False
if 'caminho_arquivo_temp' not in st.session_state: st.session_state.caminho_arquivo_temp = ""
st.sidebar.title("Painel de Administração")
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    username_input = st.sidebar.text_input("Usuário", key="username")
    password_input = st.sidebar.text_input("Senha", type="password", key="password")
    if st.sidebar.button("Login"):
        # A lógica de login agora usa os.getenv, que foi populado pelo dotenv
        if (os.getenv("username") and os.getenv("password") and
            username_input == os.getenv("username") and 
            password_input == os.getenv("password")):
            st.session_state.authenticated = True; st.rerun()
        else:
            st.sidebar.error("Usuário ou senha incorretos.")
if st.session_state.authenticated:
    st.sidebar.success(f"Bem-vindo, {os.getenv('username', 'Admin')}!")
    st.sidebar.header("Upload de Arquivos")
    uploaded_map_file = st.sidebar.file_uploader("1. Enviar mapeamento (.xlsx)", type=['xlsx'])
    if uploaded_map_file:
        try:
            with open(MAP_FILE, "wb") as f: f.write(uploaded_map_file.getbuffer())
            st.sidebar.success(f"'{MAP_FILE}' atualizado!")
        except Exception as e:
            st.sidebar.error(f"Erro ao salvar: {e}")
    uploaded_training_files = st.sidebar.file_uploader("2. Enviar arquivos de treinamento", accept_multiple_files=True)
    if uploaded_training_files:
        for file in uploaded_training_files:
            with open(os.path.join(TRAIN_DIR, file.name), "wb") as f: f.write(file.getbuffer())
        st.sidebar.success(f"{len(uploaded_training_files)} arquivo(s) salvos.")
    st.sidebar.header("Gerenciamento do Modelo")
    if st.sidebar.button("Iniciar Retreinamento do Modelo"):
        st.sidebar.info("O treinamento foi iniciado em segundo plano...")
        subprocess.Popen([sys.executable, 'treinador_em_massa.py'])
    if st.sidebar.button("Recarregar Modelo na Aplicação"):
        with st.spinner("Recarregando modelo..."):
            if recarregar_modelo():
                st.sidebar.success("Modelo recarregado!"); time.sleep(1); st.rerun()
            else:
                st.sidebar.error("Falha ao recarregar.")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False; st.rerun()
st.divider()
st.header("Identificar Layout")
sistema_input = st.text_input("Sistema (Opcional)", key="sistema_input")
uploaded_file = st.file_uploader("Selecione o arquivo para identificar", type=['pdf', 'xlsx', 'xls', 'txt', 'csv', 'xml'], key="file_uploader", on_change=processar_novo_arquivo)
if st.session_state.senha_necessaria:
    st.warning("🔒 O PDF está protegido por senha.")
    senha_manual = st.text_input("Digite a senha do PDF:", type="password", key="pwd_input")
    if st.button("Tentar novamente"):
        if senha_manual:
            with st.spinner('Analisando...'):
                analisar_arquivo(st.session_state.caminho_arquivo_temp, sistema=st.session_state.sistema_input, senha=senha_manual)
                st.rerun()
elif st.session_state.senha_incorreta:
    st.error("A senha manual está incorreta.")
elif st.session_state.analise_feita:
    resultados = st.session_state.resultados
    if resultados and isinstance(resultados, list) and len(resultados) > 0 and resultados[0]['pontuacao'] >= 85:
        st.subheader("🏆 Ranking de Layouts Compatíveis")
    else:
        st.subheader("Estes são os resultados que mais se aproximam")
    if isinstance(resultados, dict) and 'erro' in resultados:
        st.error(f"Ocorreu um erro: {resultados['erro']}")
    elif not resultados:
        st.warning("Nenhum layout compatível foi encontrado.")
    elif isinstance(resultados, list):
        for i, res in enumerate(resultados):
            rank = i + 1
            if res['pontuacao'] >= 85:
                emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"**{rank}º**"
            else:
                emoji = f"**{rank}º**"
            with st.container(border=True):
                col1, col2 = st.columns([1, 4])
                with col1:
                    if res.get("url_previa"):
                        st.image(res["url_previa"], caption=f"Exemplo {res['codigo_layout']}", width=150)
                with col2:
                    st.markdown(f"### {emoji} {res['banco']}")
                    st.markdown(f"- **Código:** `{res['codigo_layout']}`\n- **Confiança:** **{round(res['pontuacao'])}%**")