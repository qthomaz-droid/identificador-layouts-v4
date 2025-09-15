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

MODELO_SEMANTICO, LAYOUT_EMBEDDINGS, LAYOUT_LABELS, METADADOS_LAYOUTS = None, None, None, {}
MODELO_CARREGADO = False

def buscar_e_mesclar_imagens_api(metadados_locais):
    # (código existente)
    pass
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
    # (código existente)
    pass
def extrair_texto_do_cabecalho(caminho_arquivo, senha_manual=None):
    # (código existente)
    pass
def normalizar_extensao(ext):
    # (código existente)
    pass
def get_compatibilidade_label(pontuacao):
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