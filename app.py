# Arquivo: app.py

import streamlit as st
from identificador import identificar_layout, recarregar_modelo, extrair_texto_do_arquivo, get_layouts_mapeados, log_search_action
import os
import subprocess
import time
import sys
import shutil
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
import csv
import zipfile
from io import BytesIO

# --- CARREGAMENTO EXPLÍCITO DE SEGREDOS ---
caminho_secrets = os.path.join(".streamlit", "secrets.toml")
if os.path.exists(caminho_secrets):
    load_dotenv(dotenv_path=caminho_secrets)

# --- Configurações Iniciais ---
TEMP_DIR = "temp_files"
TRAIN_DIR = "arquivos_de_treinamento"
MAP_FILE = "mapeamento_layouts.xlsx"
CACHE_DIR = "cache_de_texto"
LOG_FILE = "admin_log.csv"
SEARCH_LOG_FILE = "search_log.csv" # <-- Novo arquivo de log

for folder in [TEMP_DIR, TRAIN_DIR, CACHE_DIR]:
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

st.set_page_config(page_title="Identificador Semântico", layout="wide")

# --- Logo ---
col_logo1, col_logo2, col_logo3 = st.columns([1, 1, 1])
with col_logo2:
    if os.path.exists("CC_logo_horizontal_branco.png"):
        st.image("CC_logo_horizontal_branco.png")

st.title("Identificador de Layouts 🤖")

# --- SEÇÃO SUPERIOR: TUTORIAL E CONTADOR ---
layouts_mapeados = get_layouts_mapeados()
total_layouts = len(layouts_mapeados)

col_info, col_count = st.columns([3, 1])
with col_info:
    with st.expander("💡 Como obter os melhores resultados? Clique aqui para ver o guia rápido!"):
        st.markdown("""
        Para aumentar a precisão da IA, **preencha os campos opcionais**. Quanto mais contexto você fornecer, mais inteligente será a busca!
        - **Origem:** Informe o sistema ou banco de origem (Ex:Sicoob, Conta Azul).
        - **Descrição:** Adicione palavras-chave do relatório (Ex: `Extrato de conta`, `contas a pagar`).
        - **Tipo de Relatório:** Filtre entre **Bancário** (extratos) ou **Financeiro**.
        """)
with col_count:
    st.metric("Total de Layouts Mapeados", f"{total_layouts}")

# --- FUNÇÕES DE APOIO (DEFINIDAS NO TOPO) ---
def log_admin_action(username, action, details):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Admin", "Ação", "Detalhes"])
    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, username, action, details])

def analisar_arquivo(caminho_arquivo, sistema=None, descricao=None, tipo_relatorio=None, senha=None):
    st.session_state.resultados = identificar_layout(
        caminho_arquivo, sistema_alvo=sistema, descricao_adicional=descricao,
        tipo_relatorio_alvo=tipo_relatorio, senha_manual=senha
    )
    st.session_state.senha_incorreta = (st.session_state.resultados == "SENHA_INCORRETA")
    st.session_state.senha_necessaria = (st.session_state.resultados == "SENHA_NECESSARIA")
    st.session_state.analise_feita = True

    # --- LÓGICA DE LOG DE BUSCA ---
    if isinstance(st.session_state.resultados, list) and st.session_state.resultados:
        top_res = st.session_state.resultados[0]
        log_search_action(
            filename=st.session_state.nome_arquivo_original,
            user_origin=sistema,
            user_desc=descricao,
            user_type=tipo_relatorio,
            top_result_code=top_res.get('codigo_layout'),
            top_result_compat=top_res.get('compatibilidade')
        )

def confirmar_e_retreinar(codigo_correto):
    if st.session_state.caminho_arquivo_temp and os.path.exists(st.session_state.caminho_arquivo_temp):
        nome_original = st.session_state.nome_arquivo_original
        admin_user = os.getenv('username', 'N/A')
        detalhes_log = f"Arquivo '{nome_original}' confirmado para o layout '{codigo_correto}'."
        log_admin_action(admin_user, "Confirmação de Layout", detalhes_log)
        
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
        st.error("Nenhum arquivo válido para confirmar.")

# --- Gerenciamento de Estado ---
if 'analise_feita' not in st.session_state: st.session_state.analise_feita = False
if 'resultados' not in st.session_state: st.session_state.resultados = None
if 'senha_necessaria' not in st.session_state: st.session_state.senha_necessaria = False
if 'senha_incorreta' not in st.session_state: st.session_state.senha_incorreta = False
if 'caminho_arquivo_temp' not in st.session_state: st.session_state.caminho_arquivo_temp = ""
if 'nome_arquivo_original' not in st.session_state: st.session_state.nome_arquivo_original = ""
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'page_number' not in st.session_state: st.session_state.page_number = 0

# --- PAINEL DE ADMIN NA SIDEBAR (REFEITO) ---
st.sidebar.title("Painel de Administração")
if not st.session_state.authenticated:
    username_input = st.sidebar.text_input("Usuário", key="username")
    password_input = st.sidebar.text_input("Senha", type="password", key="password")
    if st.sidebar.button("Login"):
        if (os.getenv("username") and os.getenv("password") and
            username_input == os.getenv("username") and 
            password_input == os.getenv("password")):
            st.session_state.authenticated = True; st.rerun()
        else:
            st.sidebar.error("Usuário ou senha incorretos.")
if st.session_state.authenticated:
    st.sidebar.success(f"Bem-vindo, {os.getenv('username', 'Admin')}!")
    
    # --- 1. Upload de Treinamento em Lote ---
    st.sidebar.header("Treinamento em Lote (Upload)")
    with st.sidebar.expander("Adicionar Novos Layouts (via .zip)"):
        st.info("Envie um ou mais arquivos .zip (até 200MB cada) contendo os seus PDFs de exemplo. Os nomes dos arquivos devem seguir o padrão: `codigo_nomedolayout.pdf`.")
        
        uploaded_zip_files = st.file_uploader(
            "Selecione um ou mais arquivos .zip",
            type=['zip'],
            accept_multiple_files=True
        )
        
        if uploaded_zip_files:
            if st.button("Processar e Iniciar Treinamento"):
                total_files_extracted = 0
                with st.spinner("Extraindo arquivos..."):
                    for uploaded_file in uploaded_zip_files:
                        try:
                            with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                                zip_ref.extractall(TRAIN_DIR)
                                total_files_extracted += len(zip_ref.namelist())
                        except Exception as e:
                            st.error(f"Erro ao extrair '{uploaded_file.name}': {e}")
                
                st.success(f"{total_files_extracted} arquivos extraídos com sucesso!")
                st.info("O treinamento completo (sincronização da API + treinamento de ML) foi iniciado em segundo plano. Isto pode levar várias horas.")
                subprocess.Popen([sys.executable, 'treinador_em_massa.py'])

    # --- 2. Log de Requisições de Usuários ---
    st.sidebar.header("Log de Requisições de Usuários")
    with st.sidebar.expander("Ver Log de Buscas"):
        if os.path.exists(SEARCH_LOG_FILE):
            try:
                df_log = pd.read_csv(SEARCH_LOG_FILE)
                st.dataframe(df_log.tail(15))
                with open(SEARCH_LOG_FILE, "rb") as f:
                    st.download_button(
                        label="Baixar log completo (.csv)",
                        data=f,
                        file_name="search_log.csv",
                        mime="text/csv",
                    )
            except pd.errors.EmptyDataError:
                st.info("O log de buscas ainda está vazio.")
            except Exception as e:
                st.error(f"Erro ao ler o log: {e}")
        else:
            st.info("O log de buscas ainda está vazio.")
            
    # --- Botão de Logout ---
    st.sidebar.button("Logout")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False; st.rerun()

# --- INTERFACE PRINCIPAL: ABAS ---
tab1, tab2 = st.tabs(["🔍 Identificar Layout", "📂 Navegar por Todos os Layouts"])

with tab1:
    st.header("Analisar um Arquivo")
    with st.form(key="search_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            sistema_input = st.text_input("Origem (Opcional)", placeholder="Ex: Sicoob, Conta Azul...")
        with col2:
            descricao_input = st.text_input("Descrição (Opcional)", placeholder="Ex: Extrato de conta...")
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
            
    # Lógica de exibição de resultados da análise
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
            st.warning("Nenhum layout compatível encontrado para os filtros.")

with tab2:
    st.header("Navegar e Filtrar Todos os Layouts")
    
    col_nav1, col_nav2, col_nav3 = st.columns(3)
    with col_nav1:
        filtro_sistema = st.text_input("Filtrar por Origem", key="nav_sistema")
    with col_nav2:
        filtro_descricao = st.text_input("Filtrar por Descrição", key="nav_descricao")
    with col_nav3:
        filtro_tipo = st.selectbox("Filtrar por Tipo", ("Todos", "Bancário", "Financeiro"), key="nav_tipo")
    
    layouts_filtrados = get_layouts_mapeados()
    if filtro_sistema:
        layouts_filtrados = [l for l in layouts_filtrados if filtro_sistema.lower() in l.get('sistema', '').lower()]
    if filtro_descricao:
        layouts_filtrados = [l for l in layouts_filtrados if filtro_descricao.lower() in l.get('descricao', '').lower()]
    if filtro_tipo != "Todos":
        layouts_filtrados = [l for l in layouts_filtrados if l.get('tipo_relatorio') == filtro_tipo]
        
    st.write(f"**{len(layouts_filtrados)} layouts encontrados**")
    
    ITENS_POR_PAGINA = 10
    total_paginas = max(1, (len(layouts_filtrados) - 1) // ITENS_POR_PAGINA + 1)
    
    if st.session_state.page_number >= total_paginas:
        st.session_state.page_number = 0
        
    start_idx = st.session_state.page_number * ITENS_POR_PAGINA
    end_idx = start_idx + ITENS_POR_PAGINA
    
    for layout in layouts_filtrados[start_idx:end_idx]:
        with st.container(border=True):
            col_res_1, col_res_2 = st.columns([1, 4])
            with col_res_1:
                if layout.get("url_previa"):
                    st.image(layout["url_previa"], width=150)
            with col_res_2:
                st.markdown(f"##### {layout.get('descricao', 'N/A')}")
                st.markdown(f"**Código:** `{layout.get('codigo_layout', 'N/A')}` | **Origem:** `{layout.get('sistema', 'N/A')}` | **Tipo:** `{layout.get('tipo_relatorio', 'N/A')}`")

    st.divider()
    col_pag1, col_pag2, col_pag3 = st.columns([1, 2, 1])
    with col_pag1:
        if st.button("⬅️ Anterior"):
            if st.session_state.page_number > 0:
                st.session_state.page_number -= 1
                st.session_state.scroll_to_top = True
                st.rerun()
    with col_pag2:
        st.write(f"Página **{st.session_state.page_number + 1}** de **{total_paginas}**")
    with col_pag3:
        if st.button("Próxima ➡️"):
            if st.session_state.page_number < total_paginas - 1:
                st.session_state.page_number += 1
                st.session_state.scroll_to_top = True
                st.rerun()