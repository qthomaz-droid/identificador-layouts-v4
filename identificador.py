# Arquivo: identificador.py

import os
import fitz
import pandas as pd
import joblib
import json
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import xml.etree.ElementTree as ET
import pytesseract
from PIL import Image
import io
import re
from collections import defaultdict
from tqdm import tqdm
import requests
import streamlit as st # Importado para usar o st.secrets

# --- CONFIGURAÇÕES ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
MAX_PAGINAS_PDF = 3
TIMEOUT_OCR_IMAGEM = 15
STOPWORDS = [
    'de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para', 'é', 'com', 'não', 'uma',
    'os', 'no', 'se', 'na', 'por', 'mais', 'as', 'dos', 'como', 'mas', 'foi', 'ao', 'ele',
    'das', 'tem', 'à', 'seu', 'sua', 'ou', 'ser', 'quando', 'muito', 'há', 'nos', 'já',
    'está', 'eu', 'também', 'só', 'pelo', 'pela', 'até', 'isso', 'ela', 'entre', 'era',
    'depois', 'sem', 'mesmo', 'aos', 'ter', 'seus', 'quem', 'nas', 'me', 'esse', 'eles',
    'estão', 'você', 'tinha', 'foram', 'essa', 'num', 'nem', 'suas', 'meu', 'às', 'minha',
    'r$', 'cpf', 'cnpj', 'cep', 'data', 'valor', 'saldo', 'total', 'doc', 'ag', 'conta',
    'corrente', 'extrato', 'historico', 'anterior', 'lançamentos', 'débito', 'credito',
    'agencia', 'documento', 'descrição', 'autenticação', 'resumo', 'periodo', 'aplic',
    'poupanca', 'investimento', 'iof', 'ir', 'imposto', 'renda', 'taxa', 'juros'
]
ARQUIVO_VECTORIZER = 'vectorizer.joblib'
ARQUIVO_MATRIZ_TFIDF = 'tfidf_matrix.joblib'
ARQUIVO_LABELS = 'layout_labels.joblib'
ARQUIVO_METADADOS = 'layouts_meta.json'
PASTA_CACHE = 'cache_de_texto'
API_BASE_URL = "https://manager.conciliadorcontabil.com.br/api/"

VECTORIZER, TFIDF_MATRIX, LAYOUT_LABELS, METADADOS_LAYOUTS = None, None, None, {}
MODELO_CARREGADO = False

def buscar_e_mesclar_imagens_api(metadados_locais):
    print("Buscando links de imagem na API do Manager...")
    api_secret = None
    
    # --- LÓGICA DE SEGREDOS ATUALIZADA ---
    # Tenta pegar o segredo do Streamlit primeiro (para o deploy na web)
    try:
        api_secret = st.secrets["api_secret"]
        print("Segredo da API carregado via st.secrets (ambiente Streamlit).")
    except (AttributeError, KeyError, FileNotFoundError):
        # Se falhar, tenta pegar do .env (para o bot e treinador local)
        print("AVISO: st.secrets não encontrado. Tentando carregar do .env via os.getenv().")
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

        mapa_imagens = {str(layout.get('codigo')): layout.get('imagem') for layout in layouts_da_api_lista if layout.get('codigo') and layout.get('imagem')}
        
        print(f"Sucesso! {len(mapa_imagens)} links de imagem encontrados. Mesclando com metadados...")
        for codigo, meta in metadados_locais.items():
            if codigo in mapa_imagens:
                meta['url_previa'] = mapa_imagens[codigo]
        
        return metadados_locais

    except Exception as e:
        print(f"ERRO CRÍTICO ao buscar imagens da API: {e}")
        return metadados_locais

def carregar_modelo_e_meta():
    global VECTORIZER, TFIDF_MATRIX, LAYOUT_LABELS, METADADOS_LAYOUTS, MODELO_CARREGADO
    try:
        VECTORIZER = joblib.load(ARQUIVO_VECTORIZER)
        TFIDF_MATRIX = joblib.load(ARQUIVO_MATRIZ_TFIDF)
        LAYOUT_LABELS = joblib.load(ARQUIVO_LABELS)
        
        with open(ARQUIVO_METADADOS, 'r', encoding='utf-8') as f:
            meta_list = json.load(f)
            metadados_locais = {str(item['codigo_layout']): item for item in meta_list}

        METADADOS_LAYOUTS = buscar_e_mesclar_imagens_api(metadados_locais)
        
        MODELO_CARREGADO = True
        print(f"Modelo de ML e {len(METADADOS_LAYOUTS)} metadados carregados.")
        return True
    except FileNotFoundError:
        MODELO_CARREGADO = False
        print("AVISO: Arquivos de modelo/metadados não encontrados.")
        return False
carregar_modelo_e_meta()
SENHAS_COMUNS = ["", "123456", "0000"]
def extrair_texto_do_arquivo(caminho_arquivo, senha_manual=None):
    # (Esta função permanece a mesma, completa e robusta)
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
def normalizar_extensao(ext):
    if ext in ['xls', 'xlsx']: return 'excel'
    if ext in ['txt', 'csv']: return 'txt'
    return ext
def identificar_layout(caminho_arquivo_cliente, sistema_alvo=None, senha_manual=None):
    if not MODELO_CARREGADO: return {"erro": "Modelo de ML não foi treinado."}
    texto_arquivo = extrair_texto_do_arquivo(caminho_arquivo_cliente, senha_manual=senha_manual)
    if texto_arquivo in ["SENHA_NECESSARIA", "SENHA_INCORRETA"]: return texto_arquivo
    if not texto_arquivo: return {"erro": "Não foi possível ler o conteúdo."}
    vetor_arquivo_novo = VECTORIZER.transform([texto_arquivo])
    similaridades = cosine_similarity(vetor_arquivo_novo, TFIDF_MATRIX)
    scores_brutos = similaridades[0]
    resultados_brutos = []
    for i, score in enumerate(scores_brutos):
        codigo_layout = LAYOUT_LABELS[i]
        resultados_brutos.append({"codigo_layout": codigo_layout, "pontuacao": score * 100})
    if sistema_alvo:
        for res in resultados_brutos:
            meta = METADADOS_LAYOUTS.get(res['codigo_layout'])
            if meta:
                termo_busca = sistema_alvo.lower()
                sistema_layout = str(meta.get('sistema', '')).lower()
                descricao_layout = str(meta.get('descricao', '')).lower()
                if termo_busca in sistema_layout or termo_busca in descricao_layout:
                    res['pontuacao'] += 25
    resultados_ordenados = sorted(resultados_brutos, key=lambda item: item['pontuacao'], reverse=True)
    extensao_arquivo = normalizar_extensao(os.path.splitext(caminho_arquivo_cliente)[1].lower().replace('.', ''))
    resultados_filtrados = []
    for resultado in resultados_ordenados:
        meta = METADADOS_LAYOUTS.get(resultado['codigo_layout'])
        if meta and str(meta.get('formato', '')).lower() == extensao_arquivo:
            resultado['banco'] = meta.get('descricao', f"Layout {resultado['codigo_layout']}")
            resultado['url_previa'] = meta.get('url_previa', None)
            resultados_filtrados.append(resultado)
    return resultados_filtrados[:5]
def recarregar_modelo():
    return carregar_modelo_e_meta()
def retreinar_modelo_completo():
    if not os.path.exists(PASTA_CACHE): return False
    textos_por_layout = defaultdict(str)
    for nome_arquivo_cache in tqdm(os.listdir(PASTA_CACHE), desc="Lendo cache"):
        nome_original = os.path.splitext(nome_arquivo_cache)[0]
        match = re.search(r'\d+', nome_original)
        if match:
            codigo_layout = match.group(0)
            with open(os.path.join(PASTA_CACHE, nome_arquivo_cache), 'r', encoding='utf-8') as f:
                textos_por_layout[codigo_layout] += " " + f.read()
    if not textos_por_layout: return False
    labels = list(textos_por_layout.keys())
    corpus = [textos_por_layout[label] for label in labels]
    vectorizer = TfidfVectorizer(stop_words=STOPWORDS, norm='l2', ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform(corpus)
    joblib.dump(vectorizer, ARQUIVO_VECTORIZER)
    joblib.dump(tfidf_matrix, ARQUIVO_MATRIZ_TFIDF)
    joblib.dump(labels, ARQUIVO_LABELS)
    return True