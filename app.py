import streamlit as st
from identificador import (
    identificar_layout,
    recarregar_modelo,
    extrair_texto_do_arquivo,
    get_layouts_mapeados,
)
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
from streamlit.components.v1 import html

# --- CARREGAMENTO EXPLÍCITO DE SEGREDOS ---
caminho_secrets = os.path.join(".streamlit", "secrets.toml")
if os.path.exists(caminho_secrets):
    load_dotenv(dotenv_path=caminho_secrets)
    print("Arquivo de segredos do Streamlit carregado para o ambiente.")

# --- Configurações Iniciais ---
TEMP_DIR = "temp_files"
TRAIN_DIR = "arquivos_de_treinamento"
MAP_FILE = "mapeamento_layouts.xlsx"
CACHE_DIR = "cache_de_texto"
LOG_FILE = "admin_log.csv"
SEARCH_LOG_FILE = "search_log.csv"

# Suporte ao formato OFX e outros adicionado aqui
EXTENSOES_SUPORTADAS = ["pdf", "xlsx", "xls", "txt", "csv", "xml", "ofx"]

for folder in [TEMP_DIR, TRAIN_DIR, CACHE_DIR]:
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)

st.set_page_config(page_title="Identificador de Layouts", layout="wide", page_icon="🤖")

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
        st.markdown(f"""
        Para aumentar a precisão da IA, **preencha os campos opcionais**. Quanto mais contexto você fornecer, mais inteligente será a busca!
        - **Origem:** Informe o sistema ou banco de origem (Ex: Sicoob, SCI).
        - **Descrição:** Adicione palavras-chave do relatório (Ex: `Extrato de conta`).
        - **Tipo de Relatório:** Filtre entre **Bancário** (extratos) ou **Financeiro**.
        - **Formatos suportados:** {", ".join(EXTENSOES_SUPORTADAS).upper()}
        """)
with col_count:
    st.metric("Total de Layouts Mapeados", f"{total_layouts}")

# --- FUNÇÕES DE APOIO ---
def scroll_to_element(element_id):
    js = f"""
    <script>
        var element = document.getElementById('{element_id}');
        if (element) {{
            element.scrollIntoView({{ behavior: 'auto', block: 'start' }});
        }}
    </script>
    """
    html(js, height=0, width=0)

def log_admin_action(username, action, details):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "Admin", "Ação", "Detalhes"])
    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, username, action, details])

def log_search_action(filename, user_origin, user_desc, user_type, top_result_code, top_result_compat):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user = os.getenv('username', 'Utilizador Anónimo')
        if not os.path.exists(SEARCH_LOG_FILE):
            with open(SEARCH_LOG_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Utilizador", "Ficheiro", "Filtro Origem", "Filtro Descrição", "Filtro Tipo", "Resultado (Layout)", "Compatibilidade"])
        with open(SEARCH_LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, user, filename, user_origin, user_desc, user_type, top_result_code, top_result_compat])
    except Exception as e:
        print(f"ERRO ao escrever no log de busca: {e}")

def analisar_arquivo(caminho_arquivo, sistema=None, descricao=None, tipo_relatorio=None, senha=None):
    st.session_state.resultados = identificar_layout(
        caminho_arquivo, sistema_alvo=sistema, descricao_adicional=descricao,
        tipo_relatorio_alvo=tipo_relatorio, senha_manual=senha
    )
    st.session_state.senha_incorreta = (st.session_state.resultados == "SENHA_INCORRETA")
    st.session_state.senha_necessaria = (st.session_state.resultados == "SENHA_NECESSARIA")
    st.session_state.analise_feita = True

    if isinstance(st.session_state.resultados, list) and st.session_state.resultados:
        top_res = st.session_state.resultados[0]
        log_search_action(st.session_state.nome_arquivo_original, sistema, descricao, tipo_relatorio, top_res.get('codigo_layout'), top_res.get('compatibilidade'))

def confirmar_e_retreinar(codigo_correto):
    if st.session_state.caminho_arquivo_temp and os.path.exists(st.session_state.caminho_arquivo_temp):
        nome_original = st.session_state.nome_arquivo_original
        admin_user = os.getenv('username', 'N/A')
        log_admin_action(admin_user, "Confirmação de Layout", f"Arquivo '{nome_original}' -> Layout '{codigo_correto}'.")
        timestamp = datetime.now().strftime("%Y%m%d%H:%M:%S")
        novo_nome_base = f"{codigo_correto}_confirmed_{timestamp}_{nome_original}"
        caminho_destino = os.path.join(TRAIN_DIR, novo_nome_base)
        shutil.copy(st.session_state.caminho_arquivo_temp, caminho_destino)
        
        # Ajuste desempacotando o novo retorno (texto, foi_ocr)
        texto_novo, _ = extrair_texto_do_arquivo(caminho_destino)
        if texto_novo:
            with open(os.path.join(CACHE_DIR, novo_nome_base + '.txt'), 'w', encoding='utf-8') as f:
                f.write(texto_novo)
        st.info(f"O layout '{codigo_correto}' foi reforçado. Iniciando retreinamento...")
        subprocess.Popen([sys.executable, 'treinador_em_massa.py', '--retreinar-rapido'])
    else:
        st.error("Nenhum arquivo válido para confirmar.")

# --- Gerenciamento de Estado ---
keys_init = ['analise_feita', 'resultados', 'senha_necessaria', 'senha_incorreta', 'caminho_arquivo_temp', 'nome_arquivo_original', 'authenticated', 'page_number', 'scroll_to_top']
for key in keys_init:
    if key not in st.session_state:
        if key == 'page_number': st.session_state[key] = 0
        elif key in ['authenticated', 'analise_feita', 'senha_necessaria', 'senha_incorreta', 'scroll_to_top']: st.session_state[key] = False
        else: st.session_state[key] = None if key == 'resultados' else ""

# --- PAINEL DE ADMIN NA SIDEBAR ---
st.sidebar.title("Painel de Administração")
if not st.session_state.authenticated:
    username_input = st.sidebar.text_input("Usuário", key="username_login")
    password_input = st.sidebar.text_input("Senha", type="password", key="password_login")
    if st.sidebar.button("Login"):
        if (os.getenv("username") and os.getenv("password") and username_input == os.getenv("username") and password_input == os.getenv("password")):
            st.session_state.authenticated = True; st.rerun()
        else:
            st.sidebar.error("Usuário ou senha incorretos.")

if st.session_state.authenticated:
    st.sidebar.success(f"Bem-vindo, {os.getenv('username', 'Admin')}!")
    
    with st.sidebar.expander("Treinamento em Lote (.zip)"):
        uploaded_zip = st.file_uploader("Selecione arquivos .zip", type=["zip"], accept_multiple_files=True)
        if uploaded_zip and st.button("Processar ZIPs"):
            total = 0
            for up_zip in uploaded_zip:
                with zipfile.ZipFile(up_zip, "r") as z:
                    z.extractall(TRAIN_DIR)
                    total += len(z.namelist())
            st.sidebar.success(f"{total} arquivos extraídos!")
            subprocess.Popen([sys.executable, 'treinador_em_massa.py'])

    if st.sidebar.button("Sincronizar API e Recarregar"):
        st.sidebar.info("Sincronizando...")
        subprocess.Popen([sys.executable, 'treinador_em_massa.py', '--sincronizar-api'])
        time.sleep(5)
        if recarregar_modelo(): st.sidebar.success("Modelo atualizado!"); st.rerun()

    with st.sidebar.expander("Gerir Backups"):
        if st.button("Criar Backup"):
            assets = [MAP_FILE, 'layouts_meta.json', 'layout_embeddings.joblib', 'layout_labels.joblib', TRAIN_DIR, CACHE_DIR]
            buf = BytesIO()
            with zipfile.ZipFile(buf, "a", zipfile.ZIP_DEFLATED, False) as zf:
                for asset in assets:
                    if os.path.exists(asset):
                        if os.path.isfile(asset): zf.write(asset)
                        else:
                            for r, d, f in os.walk(asset):
                                for file in f: zf.write(os.path.join(r, file))
            buf.seek(0)
            st.download_button("Baixar Backup", data=buf, file_name="backup_layouts.zip")

    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False; st.rerun()

# --- INTERFACE PRINCIPAL: ABAS ---
tab1, tab2 = st.tabs(["🔍 Identificar Layout", "📂 Navegar por Todos os Layouts"])

with tab1:
    st.header("Analisar um Arquivo")
    with st.form(key="search_form"):
        col1, col2, col3 = st.columns(3)
        with col1: sistema_input = st.text_input("Origem (Opcional)", placeholder="Ex: Sicoob, SCI...")
        with col2: descricao_input = st.text_input("Descrição (Opcional)", placeholder="Ex: Extrato de conta...")
        with col3: tipo_relatorio_input = st.selectbox("Tipo de Relatório", ("Todos", "Bancário", "Financeiro"))
        uploaded_file = st.file_uploader("Selecione um ficheiro para analisar", type=EXTENSOES_SUPORTADAS)
        submitted = st.form_submit_button("Analisar / Refazer Busca")
    
    if submitted:
        if uploaded_file:
            caminho_arquivo = os.path.join(TEMP_DIR, uploaded_file.name)
            with open(caminho_arquivo, "wb") as f: f.write(uploaded_file.getbuffer())
            st.session_state.caminho_arquivo_temp, st.session_state.nome_arquivo_original = caminho_arquivo, uploaded_file.name
            analisar_arquivo(caminho_arquivo, sistema=sistema_input, descricao=descricao_input, tipo_relatorio=tipo_relatorio_input)
        elif st.session_state.caminho_arquivo_temp:
            analisar_arquivo(st.session_state.caminho_arquivo_temp, sistema=sistema_input, descricao=descricao_input, tipo_relatorio=tipo_relatorio_input)
        else: st.warning("Por favor, selecione um ficheiro.")

    if st.session_state.senha_necessaria:
        st.warning("🔒 O PDF está protegido por senha.")
        senha_manual = st.text_input("Digite a senha do PDF:", type="password", key="pwd_input")
        if st.button("Tentar novamente"):
            analisar_arquivo(st.session_state.caminho_arquivo_temp, sistema=sistema_input, descricao=descricao_input, tipo_relatorio=tipo_relatorio_input, senha=senha_manual); st.rerun()
    
    elif st.session_state.analise_feita:
        resultados = st.session_state.resultados
        if isinstance(resultados, list) and resultados:
            st.subheader("🏆 Ranking de Layouts Compatíveis")
            for res in resultados:
                with st.container(border=True):
                    col_res_1, col_res_2, col_res_3 = st.columns([1, 3, 1])
                    with col_res_1:
                        if res.get("url_previa"): st.image(res["url_previa"], width=150)
                    with col_res_2:
                        st.markdown(f"### {res['banco']}")
                        st.markdown(f"- **Código:** `{res['codigo_layout']}`\n- **Compatibilidade:** **{res['compatibilidade']}**")
                        # ALERTA OCR INTEGRADO
                        if res.get('foi_ocr'):
                            st.warning("⚠️ **Arquivo não editável:** Este PDF é uma imagem (escaneado ou salvo com Microsoft Print To PDF). O layout foi identificado via OCR, mas arquivos neste formato **não podem ser importados** no Conciliador. Solicite ao cliente o arquivo original e editável.")
                    with col_res_3:
                        if st.button("Confirmar este layout", key=f"confirm_{res['codigo_layout']}"): confirmar_e_retreinar(res['codigo_layout'])
        else: st.warning("Nenhum layout compatível encontrado.")

# --- ABA 2: NAVEGAÇÃO (ORIGINAL RESTAURADA) ---
with tab2:
    st.markdown("<div id='top-of-list'></div>", unsafe_allow_html=True)
    if st.session_state.scroll_to_top:
        scroll_to_element('top-of-list'); st.session_state.scroll_to_top = False

    st.header("Navegar e Filtrar Todos os Layouts")
    col_nav1, col_nav2, col_nav3 = st.columns(3)
    with col_nav1: filtro_sistema = st.text_input("Filtrar por Origem", key="nav_sistema")
    with col_nav2: filtro_descricao = st.text_input("Filtrar por Descrição", key="nav_descricao")
    with col_nav3: filtro_tipo = st.selectbox("Filtrar por Tipo", ("Todos", "Bancário", "Financeiro"), key="nav_tipo")
    
    layouts_filtrados = get_layouts_mapeados()
    if filtro_sistema: layouts_filtrados = [l for l in layouts_filtrados if filtro_sistema.lower() in l.get('sistema', '').lower()]
    if filtro_descricao: layouts_filtrados = [l for l in layouts_filtrados if filtro_descricao.lower() in l.get('descricao', '').lower()]
    if filtro_tipo != "Todos": layouts_filtrados = [l for l in layouts_filtrados if l.get('tipo_relatorio') == filtro_tipo]
        
    st.write(f"**{len(layouts_filtrados)} layouts encontrados**")
    
    ITENS_POR_PAGINA = 10
    total_paginas = max(1, (len(layouts_filtrados) - 1) // ITENS_POR_PAGINA + 1)
    if st.session_state.page_number >= total_paginas: st.session_state.page_number = 0
        
    start_idx = st.session_state.page_number * ITENS_POR_PAGINA
    end_idx = start_idx + ITENS_POR_PAGINA
    
    for layout in layouts_filtrados[start_idx:end_idx]:
        with st.container(border=True):
            col_res_1, col_res_2 = st.columns([1, 4])
            with col_res_1:
                if layout.get("url_previa"): st.image(layout["url_previa"], width=150)
            with col_res_2:
                st.markdown(f"##### {layout.get('descricao', 'N/A')}")
                st.markdown(f"**Código:** `{layout.get('codigo_layout', 'N/A')}` | **Origem:** `{layout.get('sistema', 'N/A')}` | **Tipo:** `{layout.get('tipo_relatorio', 'N/A')}`")

    st.divider()
    col_pag1, col_pag2, col_pag3 = st.columns([1, 2, 1])
    with col_pag1:
        if st.button("⬅️ Anterior"):
            if st.session_state.page_number > 0: st.session_state.page_number -= 1; st.session_state.scroll_to_top = True; st.rerun()
    with col_pag2: st.write(f"Página **{st.session_state.page_number + 1}** de **{total_paginas}**")
    with col_pag3:
        if st.button("Próxima ➡️"):
            if st.session_state.page_number < total_paginas - 1: st.session_state.page_number += 1; st.session_state.scroll_to_top = True; st.rerun()