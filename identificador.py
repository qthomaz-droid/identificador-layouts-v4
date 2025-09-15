# Arquivo: identificador.py

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

ARQUIVO_EMBEDDINGS = 'layout_embeddings.joblib'
ARQUIVO_LABELS = 'layout_labels.joblib'
ARQUIVO_METADADOS = 'layouts_meta.json'
PASTA_CACHE = 'cache_de_texto'
API_BASE_URL = "https://manager.conciliadorcontabil.com.br/api/"

MODELO_SEMANTICO, LAYOUT_EMBEDDINGS, LAYOUT_LABELS, METADADOS_LAYOUTS = None, None, None, {}
MODELO_CARREGADO = False

def buscar_e_mesclar_imagens_api(metadados_locais):
    print("Buscando links de imagem na API do Manager...")
    api_secret = None
    try:
        api_secret = st.secrets["api_secret"]
    except (AttributeError, KeyError, FileNotFoundError):
        api_secret = os.getenv('API_SECRET')

    if not api_secret:
        print("AVISO: Segredo da API não configurado. Imagens não serão carregadas.")
        return metadados_locais
    
    try:
        token_url = f"{API_BASE_URL}get-token"
        response_token = requests.post(token_url, data={'secret': api_secret})
        response_token.raise_for_status()
        access_token = response_token.json().get("data", {}).get("access_token")

        if not access_token:
            print("ERRO: 'access_token' não encontrado na resposta da API.")
            return metadados_locais

        headers = {'Authorization': f'Bearer {access_token}'}
        response_layouts = requests.get(f"{API_BASE_URL}layouts?orderby=id,asc", headers=headers)
        response_layouts.raise_for_status()
        
        layouts_da_api_objeto = response_layouts.json()
        layouts_da_api_lista = layouts_da_api_objeto.get("data", [])

        if not isinstance(layouts_da_api_lista, list):
             print(f"ERRO: A chave 'data' na resposta da API não contém uma lista.")
             return metadados_locais

        mapa_imagens = {str(layout.get('codigo')): layout.get('imagem') for layout in layouts_da_api_lista if layout.get('codigo') is not None and layout.get('imagem')}
        
        print(f"Sucesso! {len(mapa_imagens)} links de imagem encontrados. Mesclando com metadados...")
        for codigo, meta in metadados_locais.items():
            if codigo in mapa_imagens:
                meta['url_previa'] = mapa_imagens[codigo]
        
        return metadados_locais

    except Exception as e:
        print(f"ERRO CRÍTICO ao buscar imagens da API: {e}")
        return metadados_locais

def carregar_modelo_semantico():
    global MODELO_SEMANTICO, LAYOUT_EMBEDDINGS, LAYOUT_LABELS, METADADOS_LAYOUTS, MODELO_CARREGADO
    try:
        print("Carregando modelo semântico na memória...")
        MODELO_SEMANTICO = SentenceTransformer(NOME_MODELO_SEMANTICO)
        LAYOUT_EMBEDDINGS = joblib.load(ARQUIVO_EMBEDDINGS)
        LAYOUT_LABELS = joblib.load(ARQUIVO_LABELS)
        with open(ARQUIVO_METADADOS, 'r', encoding='utf-8') as f:
            meta_list = json.load(f)
            metadados_locais = {str(item['codigo_layout']): item for item in meta_list}
        
        METADADOS_LAYOUTS = buscar_e_mesclar_imagens_api(metadados_locais)

        MODELO_CARREGADO = True
        print(f"Modelo Semântico e {len(METADADOS_LAYOUTS)} metadados carregados com sucesso.")
        return True
    except Exception as e:
        MODELO_CARREGADO = False
        print(f"AVISO: Arquivos de modelo não encontrados ou erro ao carregar: {e}.")
        return False
carregar_modelo_semantico()
SENHAS_COMUNS = ["", "123456", "0000"]
def extrair_texto_do_arquivo(caminho_arquivo, senha_manual=None):
    texto_completo = ""
    extensao = os.path.splitext(caminho_arquivo)[1].lower()
    nome_arquivo = os.path.basename(caminho_arquivo)
    try:
        if extensao == '.pdf':
            with fitz.open(caminho_arquivo) as doc:
                if doc.is_encrypted:
                    desbloqueado = False
                    if senha_manual is not None:
                        if doc.authenticate(senha_manual) > 0: desbloqueado = True
                        else: return "SENHA_INCORRETA"
                    else:
                        for senha in SENHAS_COMUNS:
                            if doc.authenticate(senha) > 0: desbloqueado = True; break
                    if not desbloqueado: return "SENHA_NECESSARIA"
                for i, pagina in enumerate(doc):
                    if i >= MAX_PAGINAS_PDF: break
                    texto_completo += pagina.get_text()
                    for img_info in pagina.get_images(full=True):
                        try:
                            xref = img_info[0]
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            imagem = Image.open(io.BytesIO(image_bytes))
                            texto_da_imagem = pytesseract.image_to_string(imagem, lang='por', timeout=TIMEOUT_OCR_IMAGEM)
                            if texto_da_imagem: texto_completo += " " + texto_da_imagem
                        except (RuntimeError, Exception): continue
                return texto_completo.lower()
        elif extensao in ['.xlsx', '.xls']:
            excel_file = pd.ExcelFile(caminho_arquivo)
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
                texto_completo += df.to_string(index=False) + "\n"
        elif extensao in ['.txt', '.csv']:
            with open(caminho_arquivo, 'r', encoding='utf-8', errors='ignore') as f:
                texto_completo = f.read()
        elif extensao == '.xml':
            tree = ET.parse(caminho_arquivo)
            root = tree.getroot()
            for elem in root.iter():
                if elem.text: texto_completo += elem.text.strip() + ' '
    except Exception as e:
        print(f"AVISO: Falha ao processar '{nome_arquivo}'. Erro: {e}.")
        return None
    return texto_completo.lower()
def extrair_texto_do_cabecalho(caminho_arquivo, senha_manual=None):
    texto_cabecalho_bruto = ""
    extensao = os.path.splitext(caminho_arquivo)[1].lower()
    if extensao != '.pdf': return ""
    try:
        with fitz.open(caminho_arquivo) as doc:
            if doc.is_encrypted:
                if not (doc.authenticate(senha_manual or "") > 0): return ""
            for i, pagina in enumerate(doc):
                if i >= MAX_PAGINAS_PDF: break
                altura_pagina = pagina.rect.height
                area_cabecalho = fitz.Rect(0, 0, pagina.rect.width, altura_pagina * AREA_CABECALHO_PERCENTUAL)
                texto_cabecalho_bruto += pagina.get_text(clip=area_cabecalho)
    except Exception: return ""
    texto_limpo = texto_cabecalho_bruto.lower()
    texto_limpo = re.sub(r'[^a-zA-Z\s]', '', texto_limpo)
    texto_limpo = re.sub(r'\b[a-zA-Z]\b', '', texto_limpo)
    texto_limpo = " ".join(texto_limpo.split())
    return texto_limpo
def normalizar_extensao(ext):
    if ext in ['xls', 'xlsx']: return 'excel'
    if ext in ['txt', 'csv']: return 'txt'
    return ext
def get_compatibilidade_label(pontuacao):
    """Converte a pontuação numérica em um termo de compatibilidade."""
    if pontuacao >= 85:
        return "Alta"
    elif pontuacao >= 60:
        return "Média"
    else:
        return "Baixa"
def identificar_layout(caminho_arquivo_cliente, sistema_alvo=None, descricao_adicional=None, tipo_relatorio_alvo=None, senha_manual=None):
    if not MODELO_CARREGADO: return {"erro": "Modelo Semântico não foi treinado."}
    texto_arquivo = extrair_texto_do_arquivo(caminho_arquivo_cliente, senha_manual=senha_manual)
    if texto_arquivo in ["SENHA_NECESSARIA", "SENHA_INCORRETA"]: return texto_arquivo
    if not texto_arquivo: return {"erro": "Não foi possível ler o conteúdo."}
    
    texto_final_para_busca = texto_arquivo + " " + (descricao_adicional or "")
    
    embedding_arquivo_novo = MODELO_SEMANTICO.encode(texto_final_para_busca, convert_to_tensor=True)
    similaridades = util.pytorch_cos_sim(embedding_arquivo_novo, LAYOUT_EMBEDDINGS)
    scores_brutos = similaridades[0].cpu().tolist()

    resultados_brutos = []
    for i, score in enumerate(scores_brutos):
        codigo_layout = LAYOUT_LABELS[i]
        resultados_brutos.append({"codigo_layout": codigo_layout, "pontuacao": score * 100})
    
    if descricao_adicional:
        palavras_busca = set(re.findall(r'\b\w{3,}\b', descricao_adicional.lower()))
        if palavras_busca:
            for res in resultados_brutos:
                meta = METADADOS_LAYOUTS.get(res['codigo_layout'])
                if meta:
                    texto_cabecalho = meta.get('cabecalho', '')
                    texto_descricao = meta.get('descricao', '')
                    texto_combinado = texto_cabecalho + " " + texto_descricao
                    palavras_layout = set(re.findall(r'\b\w{3,}\b', texto_combinado.lower()))
                    palavras_em_comum = palavras_busca.intersection(palavras_layout)
                    if palavras_em_comum:
                        bonus = (len(palavras_em_comum) / len(palavras_busca)) * 20
                        res['pontuacao'] += bonus
    if sistema_alvo:
        for res in resultados_brutos:
            meta = METADADOS_LAYOUTS.get(res['codigo_layout'])
            if meta:
                termo_busca = sistema_alvo.lower()
                if termo_busca in str(meta.get('sistema', '')).lower() or termo_busca in str(meta.get('descricao', '')).lower():
                    res['pontuacao'] += 25
    
    resultados_ordenados = sorted(resultados_brutos, key=lambda item: item['pontuacao'], reverse=True)
    
    extensao_arquivo = normalizar_extensao(os.path.splitext(caminho_arquivo_cliente)[1].lower().replace('.', ''))
    resultados_filtrados = []
    for resultado in resultados_ordenados:
        meta = METADADOS_LAYOUTS.get(resultado['codigo_layout'])
        if meta:
            match_formato = (str(meta.get('formato', '')).lower() == extensao_arquivo)
            match_tipo_relatorio = True
            if tipo_relatorio_alvo and tipo_relatorio_alvo.lower() != 'todos':
                match_tipo_relatorio = (str(meta.get('tipo_relatorio', '')).lower() == tipo_relatorio_alvo.lower())
            if match_formato and match_tipo_relatorio:
                resultado['banco'] = meta.get('descricao', f"Layout {resultado['codigo_layout']}")
                resultado['url_previa'] = meta.get('url_previa', None)
                resultado['compatibilidade'] = get_compatibilidade_label(resultado['pontuacao'])
                resultados_filtrados.append(resultado)
    
    return resultados_filtrados[:5]
def recarregar_modelo():
    return carregar_modelo_semantico()
def retreinar_modelo_completo():
    try:
        subprocess.run([sys.executable, 'treinador_em_massa.py'], check=True)
        return True
    except Exception as e:
        print(f"Erro ao executar o script de retreinamento: {e}")
        return False