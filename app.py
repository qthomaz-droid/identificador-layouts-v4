# Arquivo: app.py

import streamlit as st
import os
import subprocess
import time
import sys
import shutil
from datetime import datetime
from dotenv import load_dotenv
import requests
import zipfile
from io import BytesIO

# --- LÓGICA DE DOWNLOAD DOS MODELOS (RESOLVE O PROBLEMA DE DEPLOY) ---
@st.cache_resource
def setup_model_files():
    """
    Verifica se os arquivos do modelo existem. Se não, descarrega-os de um link de hospedagem.
    O decorador @st.cache_resource garante que isto só seja executado uma vez por sessão.
    """
    # Lista de arquivos essenciais que a aplicação precisa para funcionar
    arquivos_essenciais = [
        'layout_embeddings.joblib', 
        'layout_labels.joblib', 
        'layouts_meta.json'
    ]
    # O vectorizer é parte do modelo antigo, pode ser opcional dependendo da versão
    if os.path.exists('vectorizer.joblib'):
        arquivos_essenciais.append('vectorizer.joblib')

    # Verifica se algum dos arquivos essenciais está em falta
    precisa_descarregar = any(not os.path.exists(f) for f in arquivos_essenciais)

    if precisa_descarregar:
        with st.spinner("Configurando o ambiente pela primeira vez. A descarregar modelos de IA, por favor aguarde..."):
            
            # --- IMPORTANTE: SUBSTITUA PELA SUA URL DE DOWNLOAD DIRETO ---
            # 1. Compacte os seus ficheiros de modelo num único 'model_assets.zip'
            # 2. Faça o upload para um serviço como Google Drive, Dropbox ou Sync.com
            # 3. Gere um link de DOWNLOAD DIRETO e cole-o aqui.
            MODEL_URL = "drive.google.com/uc?export=download&id=1dEdw4WyVyNhLgqrwhrw2xgbLvPo4N9pv"
            
            try:
                # Descarrega o ficheiro zip para a memória
                response = requests.get(MODEL_URL)
                response.raise_for_status()
                
                # Extrai o zip para a pasta raiz do projeto
                with zipfile.ZipFile(BytesIO(response.content)) as z:
                    z.extractall(".")

                st.success("Ambiente configurado com sucesso! A aplicação será recarregada.")
                time.sleep(2)
                st.rerun()

            except Exception as e:
                st.error(f"Falha crítica ao descarregar ou extrair os modelos de IA: {e}")
                st.error("Verifique se a URL no app.py está correta e é um link de download direto.")
                st.stop() # Para a execução da aplicação se os modelos não puderem ser obtidos

# Executa a função de configuração no início de cada execução
setup_model_files()

# --- CARREGAMENTO DE SEGREDOS E O RESTO DA APLICAÇÃO ---
# Importa o cérebro DEPOIS de a configuração estar pronta
from identificador import identificar_layout, recarregar_modelo, extrair_texto_do_arquivo

caminho_secrets = os.path.join(".streamlit", "secrets.toml")
if os.path.exists(caminho_secrets):
    load_dotenv(dotenv_path=caminho_secrets)
    print("Arquivo de segredos do Streamlit carregado para o ambiente.")

# --- Configurações Iniciais ---
TEMP_DIR = "temp_files"
TRAIN_DIR = "arquivos_de_treinamento"
MAP_FILE = "mapeamento_layouts.xlsx"
CACHE_DIR = "cache_de_texto"
for folder in [TEMP_DIR, TRAIN_DIR, CACHE_DIR]:
    if not os.path.exists(folder):
        os.makedirs(folder)

st.set_page_config(page_title="Identificador Semântico", layout="wide")

col_logo1, col_logo2, col_logo3 = st.columns([1, 1, 1])
with col_logo2:
    if os.path.exists("CC_logo_horizontal_branco.png"):
        st.image("CC_logo_horizontal_branco.png")

st.title("IA identificadora de Layouts 🤖")

# --- Funções de Apoio ---
def analisar_arquivo(caminho_arquivo, sistema=None, descricao=None, tipo_relatorio=None, senha=None):
    st.session_state.resultados = identificar_layout(
        caminho_arquivo, 
        sistema_alvo=sistema, 
        descricao_adicional=descricao,
        tipo_relatorio_alvo=tipo_relatorio,
        senha_manual=senha
    )
    st.session_state.senha_incorreta = (st.session_state.resultados == "SENHA_INCORRETA")
    st.session_state.senha_necessaria = (st.session_state.resultados == "SENHA_NECESSARIA")
    st.session_state.analise_feita = True

def confirmar_e_retreinar(codigo_correto):
    if st.session_state.caminho_arquivo_temp and os.path.exists(st.session_state.caminho_arquivo_temp):
        nome_original = st.session_state.nome_arquivo_original
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        novo_nome_base = f"{codigo_correto}_confirmed_{timestamp}_{nome_original}"
        caminho_destino = os.path.join(TRAIN_DIR, novo_nome_base)
        shutil.copy(st.session_state.caminho_arquivo_temp, caminho_destino)
        texto_novo = extrair_texto_do_arquivo(caminho_destino)
        if texto_novo:
            caminho_cache = os.path.join(CACHE_DIR, novo_nome_base + '.txt')
            with open(caminho_cache, 'w', encoding='utf-8') as f:
                f.write(texto_novo)
        st.info(f"O layout '{codigo_correto}' foi reforçado. Iniciando retreinamento rápido...")
        subprocess.Popen([sys.executable, 'treinador_em_massa.py', '--retreinar-rapido'])
    else:
        st.error("Nenhum ficheiro válido para confirmar.")

# --- Gerenciamento de Estado ---
if 'analise_feita' not in st.session_state: st.session_state.analise_feita = False
if 'resultados' not in st.session_state: st.session_state.resultados = None
if 'senha_necessaria' not in st.session_state: st.session_state.senha_necessaria = False
if 'senha_incorreta' not in st.session_state: st.session_state.senha_incorreta = False
if 'caminho_arquivo_temp' not in st.session_state: st.session_state.caminho_arquivo_temp = ""
if 'nome_arquivo_original' not in st.session_state: st.session_state.nome_arquivo_original = ""
if 'authenticated' not in st.session_state: st.session_state.authenticated = False

# --- PAINEL DE ADMIN NA SIDEBAR ---
st.sidebar.title("Painel de Administração")
if not st.session_state.authenticated:
    username_input = st.sidebar.text_input("Utilizador", key="username")
    password_input = st.sidebar.text_input("Senha", type="password", key="password")
    if st.sidebar.button("Login"):
        if (os.getenv("username") and os.getenv("password") and
            username_input == os.getenv("username") and 
            password_input == os.getenv("password")):
            st.session_state.authenticated = True; st.rerun()
        else:
            st.sidebar.error("Utilizador ou senha incorretos.")
if st.session_state.authenticated:
    st.sidebar.success(f"Bem-vindo, {os.getenv('username', 'Admin')}!")
    st.sidebar.header("Upload de Ficheiros")
    uploaded_map_file = st.sidebar.file_uploader("1. Enviar mapeamento (.xlsx)", type=['xlsx'])
    if uploaded_map_file:
        try:
            with open(MAP_FILE, "wb") as f: f.write(uploaded_map_file.getbuffer())
            st.sidebar.success(f"'{MAP_FILE}' atualizado!")
        except Exception as e:
            st.sidebar.error(f"Erro ao salvar: {e}")
    uploaded_training_files = st.sidebar.file_uploader("2. Enviar ficheiros de treinamento", accept_multiple_files=True)
    if uploaded_training_files:
        for file in uploaded_training_files:
            with open(os.path.join(TRAIN_DIR, file.name), "wb") as f: f.write(file.getbuffer())
        st.sidebar.success(f"{len(uploaded_training_files)} ficheiro(s) salvos.")
    st.sidebar.header("Gerenciamento do Modelo")
    if st.sidebar.button("Iniciar Retreinamento do Modelo"):
        st.sidebar.info("O treinamento foi iniciado em segundo plano...")
        subprocess.Popen([sys.executable, 'treinador_em_massa.py'])
    if st.sidebar.button("Recarregar Modelo na Aplicação"):
        with st.spinner("A recarregar modelo..."):
            if recarregar_modelo():
                st.sidebar.success("Modelo recarregado!"); time.sleep(1); st.rerun()
            else:
                st.sidebar.error("Falha ao recarregar.")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False; st.rerun()

# --- INTERFACE PRINCIPAL DO IDENTIFICADOR ---
st.divider()
st.header("Identificar Layout")

with st.form(key="search_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        sistema_input = st.text_input("Sistema (Opcional)", placeholder="Ex: Dominio, SCI, Prosoft...")
    with col2:
        descricao_input = st.text_input("Descrição (Opcional)", placeholder="Ex: Extrato de conta, Relatório...")
    with col3:
        tipo_relatorio_input = st.selectbox("Tipo de Relatório", ("Todos", "Bancário", "Financeiro"))
    uploaded_file = st.file_uploader("Selecione ou arraste um ficheiro para analisar")
    submitted = st.form_submit_button("Analisar / Refazer Busca")

if submitted:
    if uploaded_file is not None:
        with st.spinner('A analisar novo ficheiro...'):
            caminho_arquivo = os.path.join(TEMP_DIR, uploaded_file.name)
            with open(caminho_arquivo, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.session_state.caminho_arquivo_temp = caminho_arquivo
            st.session_state.nome_arquivo_original = uploaded_file.name
            analisar_arquivo(caminho_arquivo, sistema=sistema_input, descricao=descricao_input, tipo_relatorio=tipo_relatorio_input)
    elif st.session_state.caminho_arquivo_temp:
        with st.spinner(f"A refazer busca para '{st.session_state.nome_arquivo_original}'..."):
            analisar_arquivo(st.session_state.caminho_arquivo_temp, sistema=sistema_input, descricao=descricao_input, tipo_relatorio=tipo_relatorio_input)
    else:
        st.warning("Por favor, selecione um ficheiro para analisar.")

# --- LÓGICA DE EXIBIÇÃO DE RESULTADOS ---
if st.session_state.senha_necessaria:
    st.warning("🔒 O PDF está protegido por senha.")
    senha_manual = st.text_input("Digite a senha do PDF:", type="password", key="pwd_input")
    if st.button("Tentar novamente"):
        if senha_manual:
            with st.spinner('A analisar...'):
                analisar_arquivo(st.session_state.caminho_arquivo_temp, sistema=sistema_input, descricao=descricao_input, tipo_relatorio=tipo_relatorio_input, senha=senha_manual)
                st.rerun()
elif st.session_state.senha_incorreta:
    st.error("A senha manual está incorreta.")
elif st.session_state.analise_feita:
    resultados = st.session_state.resultados
    if isinstance(resultados, list) and resultados:
        if resultados[0].get('compatibilidade') == 'Alta':
            st.subheader("🏆 Ranking de Layouts Compatíveis")
        else:
            st.subheader("Estes são os resultados que mais se aproximam")
        
        for res in resultados:
            with st.container(border=True):
                col_res_1, col_res_2, col_res_3 = st.columns([1, 3, 1])
                with col_res_1:
                    if res.get("url_previa"):
                        st.image(res["url_previa"], caption=f"Exemplo {res['codigo_layout']}", width=150)
                with col_res_2:
                    st.markdown(f"### {res['banco']}")
                    st.markdown(f"- **Código:** `{res['codigo_layout']}`\n- **Compatibilidade:** **{res['compatibilidade']}**")
                with col_res_3:
                    st.markdown('<div style="display: flex; align-items: center; justify-content: flex-end; height: 100%;">', unsafe_allow_html=True)
                    if st.button("Confirmar este layout", key=f"confirm_{res['codigo_layout']}"):
                        confirmar_e_retreinar(res['codigo_layout'])
                    st.markdown('</div>', unsafe_allow_html=True)
    elif isinstance(resultados, dict) and 'erro' in resultados:
        st.error(f"Ocorreu um erro: {resultados['erro']}")
    elif not resultados:
        st.warning("Nenhum layout compatível encontrado para os filtros selecionados.")