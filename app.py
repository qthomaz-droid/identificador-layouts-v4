# Arquivo: app.py (VERSÃO FINAL COM BOTÃO DE REFORÇO)

import streamlit as st
from identificador import identificar_layout, sugerir_palavras_chave, atualizar_layout_no_json
import os

# --- Configurações Iniciais ---
TEMP_DIR = "temp_files"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)
TIPOS_DE_ARQUIVO_ACEITOS = ['pdf', 'xlsx', 'xls', 'txt', 'csv', 'xml']
st.set_page_config(page_title="Identificador de Layouts", layout="wide")
st.title("🤖 Identificador Automático de Layouts")

# --- Funções de Apoio ---
def analisar_arquivo(caminho_arquivo, senha=None):
    """Função central que chama o identificador e armazena o resultado."""
    st.session_state.resultados = identificar_layout(caminho_arquivo, senha_manual=senha)
    st.session_state.senha_incorreta = (st.session_state.resultados == "SENHA_INCORRETA")
    st.session_state.senha_necessaria = (st.session_state.resultados == "SENHA_NECESSARIA")
    st.session_state.analise_feita = True

def reforcar_treinamento(codigo, descricao):
    """Função para reforçar um layout existente com as palavras do arquivo atual."""
    with st.spinner(f"Reforçando o layout '{codigo}'..."):
        novas_palavras_chave = sugerir_palavras_chave(st.session_state.caminho_arquivo_temp)
        if novas_palavras_chave:
            ext = os.path.splitext(st.session_state.caminho_arquivo_temp)[1].lower().replace('.', '')
            if ext in ['xls', 'xlsx']: ext = 'excel'
            elif ext in ['csv']: ext = 'txt'
            
            sucesso = atualizar_layout_no_json(codigo, descricao, novas_palavras_chave, ext)
            if sucesso:
                st.success(f"Obrigado! O layout '{codigo}' foi reforçado com as informações deste arquivo.")
                analisar_arquivo(st.session_state.caminho_arquivo_temp) # Re-analisa para mostrar o novo score
            else:
                st.error("Ocorreu um erro ao salvar a correção no layouts.json.")
        else:
            st.error("Não foi possível extrair novas palavras-chave deste arquivo para o treinamento.")
    st.rerun()


# --- Gerenciamento de Estado ---
if 'analise_feita' not in st.session_state:
    st.session_state.analise_feita = False
# ... (o resto do gerenciamento de estado permanece o mesmo) ...
if 'resultados' not in st.session_state:
    st.session_state.resultados = None
if 'senha_necessaria' not in st.session_state:
    st.session_state.senha_necessaria = False
if 'senha_incorreta' not in st.session_state:
    st.session_state.senha_incorreta = False
if 'caminho_arquivo_temp' not in st.session_state:
    st.session_state.caminho_arquivo_temp = ""


# --- Seção 1: IDENTIFICADOR ---
uploaded_file = st.file_uploader(
    "Selecione o arquivo para identificar",
    type=TIPOS_DE_ARQUIVO_ACEITOS,
    key="identifier"
)

if uploaded_file is not None:
    caminho_atual = os.path.join(TEMP_DIR, uploaded_file.name)
    # Verifica se é um arquivo novo para não reprocessar desnecessariamente
    if st.session_state.caminho_arquivo_temp != caminho_atual:
        st.session_state.caminho_arquivo_temp = caminho_atual
        with open(caminho_atual, "wb") as f:
            f.write(uploaded_file.getbuffer())
        with st.spinner('Analisando arquivo...'):
            analisar_arquivo(caminho_atual)

# ... (lógica de senha permanece a mesma) ...
if st.session_state.senha_necessaria:
    st.warning("🔒 O arquivo PDF está protegido por senha.")
    senha_manual = st.text_input("Por favor, digite a senha do PDF:", type="password", key="pwd_input")
    if st.button("Tentar novamente com a senha"):
        if senha_manual:
            with st.spinner('Analisando com a senha fornecida...'):
                analisar_arquivo(st.session_state.caminho_arquivo_temp, senha=senha_manual)
        else:
            st.error("Por favor, insira uma senha.")
if st.session_state.senha_incorreta:
    st.error("A senha manual fornecida está incorreta.")


# --- Exibição dos Resultados e NOVA SEÇÃO DE CORREÇÃO ---
if st.session_state.analise_feita and not st.session_state.senha_necessaria:
    st.subheader("🏆 Ranking de Layouts Compatíveis")
    resultados = st.session_state.resultados
    
    if isinstance(resultados, str) and "SENHA" in resultados:
        pass # Não exibe nada aqui, pois a mensagem de senha já foi mostrada
    elif isinstance(resultados, dict) and 'erro' in resultados:
        st.error(f"Ocorreu um erro: {resultados['erro']}")
    elif not resultados:
        st.warning("Nenhum layout compatível foi encontrado.")
    else:
        # --- MUDANÇA PRINCIPAL: Adicionando o botão em cada resultado ---
        for i, res in enumerate(resultados):
            rank, emoji = (i + 1, "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}º**")
            
            col1, col2 = st.columns([4, 1]) # Cria uma coluna para o texto e outra para o botão
            with col1:
                st.markdown(f"### {emoji} Layout {res['codigo_layout']}")
                st.markdown(f"- **Código:** `{res['codigo_layout']}`\n- **Confiança:** **{res['pontuacao']}%**")
            
            with col2:
                # O 'key' é essencial para que cada botão seja único
                if st.button("Este é o correto ✅", key=f"confirm_{res['codigo_layout']}"):
                    reforcar_treinamento(res['codigo_layout'], res['codigo_layout'])
            
            st.divider() # Adiciona uma linha divisória

    # --- Seção de correção manual (ainda útil se o layout não estiver na lista) ---
    with st.expander("❓ Nenhuma das opções está correta? Informe o layout aqui!"):
        # (O código desta seção permanece o mesmo da versão anterior)
        st.info("Informe o código do layout que deveria ter sido encontrado. O sistema irá aprender com este arquivo para melhorar futuras identificações.")
        col1, col2 = st.columns(2)
        with col1:
            codigo_correto = st.text_input("Código do Layout Correto", key="codigo_correto")
        with col2:
            descricao_correta = st.text_input("Descrição do Layout (opcional se já existir)", key="descricao_correta")
        if st.button("Corrigir e Treinar com este Arquivo", key="btn_corrigir"):
            if not codigo_correto:
                st.error("O código do layout é obrigatório.")
            else:
                reforcar_treinamento(codigo_correto.strip(), descricao_correta.strip() if descricao_correta else f"Layout {codigo_correto}")

# --- Seção de Treinamento Manual (para criar layouts do zero) ---
st.markdown("---")
with st.expander("🧠 Treinar um layout com seleção manual de palavras"):
    # (O código desta seção permanece o mesmo da versão anterior)
    trainer_file = st.file_uploader("Selecione o arquivo para treinar", type=TIPOS_DE_ARQUIVO_ACEITOS, key="trainer")
    # ... (resto do código do treinador manual) ...
    if trainer_file is not None:
        caminho_treino_temp = os.path.join(TEMP_DIR, trainer_file.name)
        with open(caminho_treino_temp, "wb") as f: f.write(trainer_file.getbuffer())
        with st.spinner("Extraindo sugestões..."): sugestoes = sugerir_palavras_chave(caminho_treino_temp)
        if sugestoes:
            st.write("**Sugestões de Palavras-Chave:**")
            codigo_layout_input = st.text_input("1. Código do Layout", key="train_codigo")
            banco_descricao_input = st.text_input("2. Descrição", key="train_desc")
            palavras_selecionadas = st.multiselect("3. Selecione as palavras-chave:", options=sugestoes, key="train_palavras")
            if st.button("Salvar/Atualizar Layout", key="train_salvar"):
                if not all([codigo_layout_input, banco_descricao_input, palavras_selecionadas]):
                    st.warning("Preencha todos os campos.")
                else:
                    ext = os.path.splitext(trainer_file.name)[1].lower().replace('.', '')
                    if atualizar_layout_no_json(codigo_layout_input.strip(), banco_descricao_input.strip(), palavras_selecionadas, ext):
                        st.success("Layout salvo/atualizado!")
                    else:
                        st.error("Erro ao salvar.")
        else:
            st.error("Não foi possível extrair palavras-chave. Verifique se o arquivo está protegido por senha.")
        os.remove(caminho_treino_temp)