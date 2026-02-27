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
NOME_MODELO_SEMANTICO = 'distiluse-base-multilingual-cased-v1'

# --- LÓGICA DE CAMINHOS ABSOLUTOS ---
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_EMBEDDINGS = os.path.join(DIRETORIO_ATUAL, 'layout_embeddings.joblib')
ARQUIVO_LABELS = os.path.join(DIRETORIO_ATUAL, 'layout_labels.joblib')
ARQUIVO_METADADOS = os.path.join(DIRETORIO_ATUAL, 'layouts_meta.json')

API_BASE_URL = "https://manager.conciliadorcontabil.com.br/api/"

# --- FUNÇÃO DE CARREGAMENTO (LAZY LOADING PARA EVITAR LOOP) ---
@st.cache_resource
def carregar_recursos_modelo():
    """Carrega IA e metadados apenas quando solicitado, protegendo o servidor e o Windows."""
    print("Iniciando carregamento de recursos do modelo...")
    try:
        modelo_semantico = SentenceTransformer(NOME_MODELO_SEMANTICO)
        layout_embeddings = joblib.load(ARQUIVO_EMBEDDINGS)
        layout_labels = joblib.load(ARQUIVO_LABELS)
        
        with open(ARQUIVO_METADADOS, 'r', encoding='utf-8') as f:
            meta_list = json.load(f)
            metadados_locais = {str(item['codigo_layout']): item for item in meta_list}
        
        metadados_finais = buscar_e_mesclar_imagens_api(metadados_locais)
        return True, modelo_semantico, layout_embeddings, layout_labels, metadados_finais
    except Exception as e:
        print(f"Erro ao carregar recursos: {e}")
        return False, None, None, None, {}

def buscar_e_mesclar_imagens_api(metadados_locais):
    api_secret = None
    try:
        api_secret = st.secrets["api_secret"]
    except:
        api_secret = os.getenv('API_SECRET')

    if not api_secret: return metadados_locais
    
    try:
        token_url = f"{API_BASE_URL}get-token"
        res_token = requests.post(token_url, data={'secret': api_secret}, timeout=10)
        token = res_token.json().get("data", {}).get("access_token")

        if token:
            headers = {'Authorization': f'Bearer {token}'}
            res_layouts = requests.get(f"{API_BASE_URL}layouts?orderby=id,asc", headers=headers, timeout=15)
            layouts_api = res_layouts.json().get("data", [])
            mapa = {str(l.get('codigo')): l.get('imagem') for l in layouts_api if l.get('codigo') and l.get('imagem')}
            for cod, meta in metadados_locais.items():
                if cod in mapa: meta['url_previa'] = mapa[cod]
        return metadados_locais
    except Exception:
        return metadados_locais

# --- FUNÇÕES DE APOIO ---

def normalizar_extensao(ext):
    """Mapeia as extensões reais para as chaves de formato no banco de dados."""
    ext = ext.lower().replace('.', '')
    if ext in ['xls', 'xlsx']: return 'excel'
    if ext in ['txt', 'csv']: return 'txt'
    return ext # pdf, ofx, xml permanecem iguais

def get_compatibilidade_label(pontuacao):
    """Retorna o rótulo de confiança baseado na pontuação semântica."""
    if pontuacao >= 85: return "Alta"
    elif pontuacao >= 60: return "Média"
    else: return "Baixa"

# --- EXTRAÇÃO DE TEXTO ---

def extrair_texto_do_arquivo(caminho_arquivo, senha_manual=None):
    """Retorna (texto, foi_ocr). Suporta PDF, Excel, OFX, XML, CSV, TXT."""
    texto_completo = ""
    extensao = os.path.splitext(caminho_arquivo)[1].lower()
    foi_ocr = False
    
    try:
        if extensao == '.pdf':
            with fitz.open(caminho_arquivo) as doc:
                if doc.is_encrypted:
                    if senha_manual:
                        if not doc.authenticate(senha_manual) > 0: return "SENHA_INCORRETA", False
                    else:
                        desbloqueado = False
                        for s in ["", "123456", "0000"]:
                            if doc.authenticate(s) > 0: desbloqueado = True; break
                        if not desbloqueado: return "SENHA_NECESSARIA", False
                
                for i, pagina in enumerate(doc):
                    if i >= MAX_PAGINAS_PDF: break
                    texto_completo += pagina.get_text()
                    for img_info in pagina.get_images(full=True):
                        try:
                            xref = img_info[0]
                            base_image = doc.extract_image(xref)
                            texto_completo += " " + pytesseract.image_to_string(Image.open(io.BytesIO(base_image["image"])), lang='por')
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
            for sheet in pd.ExcelFile(caminho_arquivo).sheet_names:
                texto_completo += pd.read_excel(caminho_arquivo, sheet_name=sheet, header=None).to_string(index=False) + "\n"
        elif extensao in ['.txt', '.csv', '.ofx']:
            with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f: texto_completo = f.read()
        elif extensao == '.xml':
            for elem in ET.parse(caminho_arquivo).getroot().iter():
                if elem.text: texto_completo += elem.text.strip() + ' '
                
    except Exception as e:
        print(f"Erro na extração: {e}")
        return None, False
        
    return texto_completo.lower(), foi_ocr

def extrair_texto_do_cabecalho(caminho_arquivo, senha_manual=None):
    """Extrai apenas o topo das páginas para o treinador identificar bônus de sistema."""
    texto_cabecalho_bruto = ""
    extensao = os.path.splitext(caminho_arquivo)[1].lower()
    if extensao != '.pdf': return ""
    try:
        with fitz.open(caminho_arquivo) as doc:
            if doc.is_encrypted and not (doc.authenticate(senha_manual or "") > 0): return ""
            for i, pagina in enumerate(doc):
                if i >= MAX_PAGINAS_PDF: break
                area = fitz.Rect(0, 0, pagina.rect.width, pagina.rect.height * AREA_CABECALHO_PERCENTUAL)
                texto_cabecalho_bruto += pagina.get_text(clip=area)
    except Exception: return ""
    return " ".join(re.sub(r'[^a-zA-Z\s]', '', texto_cabecalho_bruto.lower()).split())

# --- FUNÇÕES PRINCIPAIS ---

def identificar_layout(caminho_arquivo_cliente, sistema_alvo=None, descricao_adicional=None, tipo_relatorio_alvo=None, senha_manual=None):
    # Carrega os recursos apenas quando necessário
    sucesso, modelo, embeddings, labels, metadados = carregar_recursos_modelo()
    if not sucesso: return [{"erro": "IA não carregada."}]
    
    texto, foi_ocr = extrair_texto_do_arquivo(caminho_arquivo_cliente, senha_manual=senha_manual)
    if texto in ["SENHA_NECESSARIA", "SENHA_INCORRETA"]: return texto
    if not texto: return [{"erro": "Arquivo ilegível."}]
    
    # Geração do Embedding da busca
    query_emb = modelo.encode(texto + " " + (descricao_adicional or ""), convert_to_tensor=True)
    sims = util.pytorch_cos_sim(query_emb, embeddings)[0].cpu().tolist()

    res_brutos = []
    for i, score in enumerate(sims):
        res_brutos.append({"codigo_layout": labels[i], "pontuacao": score * 100})
    
    # Aplicação de Bônus (Sistema Alvo e Descrição)
    for res in res_brutos:
        meta = metadados.get(res['codigo_layout'])
        if meta:
            if sistema_alvo and sistema_alvo.lower() in str(meta.get('sistema','')).lower(): 
                res['pontuacao'] += 25
            if descricao_adicional:
                palavras = set(re.findall(r'\b\w{3,}\b', descricao_adicional.lower()))
                texto_meta = (meta.get('cabecalho','') + " " + meta.get('descricao','')).lower()
                comuns = palavras.intersection(set(re.findall(r'\b\w{3,}\b', texto_meta)))
                if comuns: res['pontuacao'] += (len(comuns) / len(palavras)) * 20

    # Filtro por Formato e Tipo de Relatório
    ext_at = normalizar_extensao(os.path.splitext(caminho_arquivo_cliente)[1])
    filtrados = []
    
    for r in sorted(res_brutos, key=lambda x: x['pontuacao'], reverse=True):
        meta = metadados.get(r['codigo_layout'])
        # Valida se o formato do arquivo coincide com o layout
        if meta and str(meta.get('formato','')).lower() == ext_at:
            # Valida filtro Bancário/Financeiro
            if not tipo_relatorio_alvo or tipo_relatorio_alvo.lower() == 'todos' or \
               str(meta.get('tipo_relatorio', '')).lower() == tipo_relatorio_alvo.lower():
                
                # PREENCHIMENTO FINAL DOS DADOS (Onde estava o erro)
                r.update({
                    'banco': meta.get('descricao', f"Layout {r['codigo_layout']}"),
                    'url_previa': meta.get('url_previa'),
                    'foi_ocr': foi_ocr,
                    'compatibilidade': get_compatibilidade_label(r['pontuacao']) # CHAVE CORRIGIDA
                })
                filtrados.append(r)
                
    return filtrados[:5]

def get_layouts_mapeados():
    sucesso, _, _, _, metadados = carregar_recursos_modelo()
    return list(metadados.values()) if sucesso else []

def recarregar_modelo():
    carregar_recursos_modelo.clear()
    return carregar_recursos_modelo()[0]

def retreinar_modelo_completo():
    try:
        subprocess.run([sys.executable, 'treinador_em_massa.py'], check=True)
        return True
    except: return False