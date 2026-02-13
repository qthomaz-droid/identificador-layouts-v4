import os
import fitz
import pandas as pd
import joblib
import json
from sentence_transformers import SentenceTransformer, util
import xml.etree.ElementTree as ET
import pytesseract
from PIL import Image
import io
import re
from collections import defaultdict
import torch
import subprocess
import sys
import requests
import streamlit as st

# --- CONFIGURAÇÕES ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
MAX_PAGINAS_PDF = 3
TIMEOUT_OCR_IMAGEM = 15
AREA_CABECALHO_PERCENTUAL = 0.15 
STOPWORDS = []
NOME_MODELO_SEMANTICO = 'distiluse-base-multilingual-cased-v1'

# --- LÓGICA DE CAMINHOS ABSOLUTOS ---
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_EMBEDDINGS = os.path.join(DIRETORIO_ATUAL, 'layout_embeddings.joblib')
ARQUIVO_LABELS = os.path.join(DIRETORIO_ATUAL, 'layout_labels.joblib')
ARQUIVO_METADADOS = os.path.join(DIRETORIO_ATUAL, 'layouts_meta.json')
PASTA_CACHE = os.path.join(DIRETORIO_ATUAL, 'cache_de_texto')

API_BASE_URL = "https://manager.conciliadorcontabil.com.br/api/"

# --- FUNÇÃO DE CARREGAMENTO (COM CACHE) ---
@st.cache_resource
def carregar_recursos_modelo():
    """
    Função que carrega modelos e dados. O @st.cache_resource garante que,
    dentro do Streamlit, isso só rode uma vez por sessão.
    """
    print("Iniciando carregamento de recursos...")
    try:
        modelo_semantico = SentenceTransformer(NOME_MODELO_SEMANTICO)
        layout_embeddings = joblib.load(ARQUIVO_EMBEDDINGS)
        layout_labels = joblib.load(ARQUIVO_LABELS)
        
        with open(ARQUIVO_METADADOS, 'r', encoding='utf-8') as f:
            meta_list = json.load(f)
            metadados_locais = {str(item['codigo_layout']): item for item in meta_list}
        
        # Mescla com imagens da API
        metadados_finais = buscar_e_mesclar_imagens_api(metadados_locais)
        
        print("Recursos carregados com sucesso.")
        return True, modelo_semantico, layout_embeddings, layout_labels, metadados_finais

    except Exception as e:
        print(f"ERRO ao carregar recursos: {e}")
        return False, None, None, None, {}

def buscar_e_mesclar_imagens_api(metadados_locais):
    api_secret = None
    try:
        api_secret = st.secrets["api_secret"]
    except:
        api_secret = os.getenv('API_SECRET')

    if not api_secret:
        return metadados_locais
    
    try:
        token_url = f"{API_BASE_URL}get-token"
        response_token = requests.post(token_url, data={'secret': api_secret}, timeout=10)
        response_token.raise_for_status()
        access_token = response_token.json().get("data", {}).get("access_token")

        if access_token:
            headers = {'Authorization': f'Bearer {access_token}'}
            response_layouts = requests.get(f"{API_BASE_URL}layouts?orderby=id,asc", headers=headers, timeout=15)
            response_layouts.raise_for_status()
            
            layouts_api = response_layouts.json().get("data", [])
            mapa_imagens = {str(l.get('codigo')): l.get('imagem') for l in layouts_api if l.get('codigo') and l.get('imagem')}
            
            for codigo, meta in metadados_locais.items():
                if codigo in mapa_imagens:
                    meta['url_previa'] = mapa_imagens[codigo]
        
        return metadados_locais
    except Exception as e:
        print(f"AVISO API: Não foi possível buscar imagens: {e}")
        return metadados_locais

# --- FUNÇÕES DE APOIO ---

def recarregar_modelo():
    carregar_recursos_modelo.clear()
    sucesso, _, _, _, _ = carregar_recursos_modelo()
    return sucesso

def normalizar_extensao(ext):
    if ext in ['xls', 'xlsx']: return 'excel'
    if ext in ['txt', 'csv']: return 'txt'
    if ext in ['ofx']: return 'ofx'
    if ext in ['xml']: return 'xml'
    return ext

def get_compatibilidade_label(pontuacao):
    if pontuacao >= 85: return "Alta"
    elif pontuacao >= 60: return "Média"
    else: return "Baixa"

# --- EXTRAÇÃO DE TEXTO ---

def extrair_texto_do_arquivo(caminho_arquivo, senha_manual=None):
    texto_completo = ""
    extensao = os.path.splitext(caminho_arquivo)[1].lower()
    foi_ocr = False
    SENHAS_COMUNS = ["", "123456", "0000"]
    
    try:
        if extensao == '.pdf':
            with fitz.open(caminho_arquivo) as doc:
                if doc.is_encrypted:
                    desbloqueado = False
                    if senha_manual:
                        if doc.authenticate(senha_manual) > 0: desbloqueado = True
                        else: return "SENHA_INCORRETA", False
                    else:
                        for senha in SENHAS_COMUNS:
                            if doc.authenticate(senha) > 0: desbloqueado = True; break
                    if not desbloqueado: return "SENHA_NECESSARIA", False
                
                for i, pagina in enumerate(doc):
                    if i >= MAX_PAGINAS_PDF: break
                    texto_completo += pagina.get_text()
                    
                    for img_info in pagina.get_images(full=True):
                        try:
                            xref = img_info[0]
                            base_image = doc.extract_image(xref)
                            imagem = Image.open(io.BytesIO(base_image["image"]))
                            texto_img = pytesseract.image_to_string(imagem, lang='por', timeout=TIMEOUT_OCR_IMAGEM)
                            if texto_img: texto_completo += " " + texto_img
                        except: continue

                if len(texto_completo.strip()) < 50:
                    foi_ocr = True
                    texto_completo = "" 
                    for i, pagina in enumerate(doc):
                        if i >= MAX_PAGINAS_PDF: break
                        pix = pagina.get_pixmap(matrix=fitz.Matrix(2, 2))
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        texto_completo += pytesseract.image_to_string(img, lang='por')

        elif extensao in ['.xlsx', '.xls']:
            excel_file = pd.ExcelFile(caminho_arquivo)
            for sheet in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet, header=None)
                texto_completo += df.to_string(index=False) + "\n"

        elif extensao in ['.txt', '.csv', '.ofx']:
            with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
                texto_completo = f.read()

        elif extensao == '.xml':
            root = ET.parse(caminho_arquivo).getroot()
            for elem in root.iter():
                if elem.text: texto_completo += elem.text.strip() + ' '
                
    except Exception as e:
        print(f"Erro extração: {e}")
        return None, False
        
    return texto_completo.lower(), foi_ocr

# --- FUNÇÕES PRINCIPAIS (PROTEGIDAS CONTRA LOOP) ---

def identificar_layout(caminho_arquivo_cliente, sistema_alvo=None, descricao_adicional=None, tipo_relatorio_alvo=None, senha_manual=None):
    # Carrega recursos apenas quando a função é chamada
    sucesso, modelo, embeddings, labels, metadados = carregar_recursos_modelo()
    
    if not sucesso: 
        return [{"erro": "Não foi possível carregar os modelos de IA."}]
    
    texto_arquivo, foi_ocr = extrair_texto_do_arquivo(caminho_arquivo_cliente, senha_manual=senha_manual)
    
    if texto_arquivo in ["SENHA_NECESSARIA", "SENHA_INCORRETA"]: return texto_arquivo
    if not texto_arquivo: return [{"erro": "Arquivo vazio ou ilegível."}]
    
    texto_final = texto_arquivo + " " + (descricao_adicional or "")
    
    # Busca Semântica
    emb_query = modelo.encode(texto_final, convert_to_tensor=True)
    sims = util.pytorch_cos_sim(emb_query, embeddings)[0].cpu().tolist()

    resultados_brutos = []
    for i, score in enumerate(sims):
        resultados_brutos.append({"codigo_layout": labels[i], "pontuacao": score * 100})
    
    # Bônus por descrição e sistema
    if descricao_adicional or sistema_alvo:
        for res in resultados_brutos:
            meta = metadados.get(res['codigo_layout'])
            if meta:
                if descricao_adicional:
                    palavras_busca = set(re.findall(r'\b\w{3,}\b', descricao_adicional.lower()))
                    texto_meta = (meta.get('cabecalho','') + " " + meta.get('descricao','')).lower()
                    comuns = palavras_busca.intersection(set(re.findall(r'\b\w{3,}\b', texto_meta)))
                    if comuns: res['pontuacao'] += (len(comuns) / len(palavras_busca)) * 20
                
                if sistema_alvo:
                    if sistema_alvo.lower() in str(meta.get('sistema','')).lower(): res['pontuacao'] += 25
    
    # Filtro de Formato e Tipo
    ext_at = normalizar_extensao(os.path.splitext(caminho_arquivo_cliente)[1].lower().replace('.', ''))
    resultados_filtrados = []
    
    for res in sorted(resultados_brutos, key=lambda x: x['pontuacao'], reverse=True):
        meta = metadados.get(res['codigo_layout'])
        if meta and str(meta.get('formato', '')).lower() == ext_at:
            if not tipo_relatorio_alvo or tipo_relatorio_alvo.lower() == 'todos' or \
               str(meta.get('tipo_relatorio', '')).lower() == tipo_relatorio_alvo.lower():
                
                res['banco'] = meta.get('descricao', f"Layout {res['codigo_layout']}")
                res['url_previa'] = meta.get('url_previa')
                res['compatibilidade'] = get_compatibilidade_label(res['pontuacao'])
                res['foi_ocr'] = foi_ocr
                resultados_filtrados.append(res)
    
    return resultados_filtrados[:5]

def get_layouts_mapeados():
    #  Carrega recursos apenas se solicitado
    sucesso, _, _, _, metadados = carregar_recursos_modelo()
    return list(metadados.values()) if sucesso else []

def retreinar_modelo_completo():
    try:
        subprocess.run([sys.executable, 'treinador_em_massa.py'], check=True)
        return True
    except:
        return False