# Arquivo: identificador.py (VERSÃO COM BUSCA AMPLIADA POR SISTEMA)

import os
import fitz
import pandas as pd
import joblib
import json
from sklearn.metrics.pairwise import cosine_similarity
import xml.etree.ElementTree as ET
import pytesseract
from PIL import Image
import io

# ... (Todo o início do arquivo, incluindo STOPWORDS, carregamento do modelo e extrair_texto_do_arquivo, permanece o mesmo) ...
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
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
VECTORIZER, TFIDF_MATRIX, LAYOUT_LABELS, METADADOS_LAYOUTS = None, None, None, {}
MODELO_CARREGADO = False
def carregar_modelo_e_meta():
    global VECTORIZER, TFIDF_MATRIX, LAYOUT_LABELS, METADADOS_LAYOUTS, MODELO_CARREGADO
    try:
        VECTORIZER = joblib.load(ARQUIVO_VECTORIZER)
        TFIDF_MATRIX = joblib.load(ARQUIVO_MATRIZ_TFIDF)
        LAYOUT_LABELS = joblib.load(ARQUIVO_LABELS)
        with open(ARQUIVO_METADADOS, 'r', encoding='utf-8') as f:
            meta_list = json.load(f)
            METADADOS_LAYOUTS = {item['codigo_layout']: item for item in meta_list}
        MODELO_CARREGADO = True
        print("Modelo de ML e Metadados carregados com sucesso.")
        return True
    except FileNotFoundError:
        MODELO_CARREGADO = False
        print("AVISO: Arquivos de modelo/metadados não encontrados.")
        return False
carregar_modelo_e_meta()
SENHAS_COMUNS = ["", "123456", "0000"]
def extrair_texto_do_arquivo(caminho_arquivo, senha_manual=None):
    texto_completo = ""
    extensao = os.path.splitext(caminho_arquivo)[1].lower()
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
                for pagina in doc:
                    texto_completo += pagina.get_text()
                for i, pagina in enumerate(doc):
                    for img_info in pagina.get_images(full=True):
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        imagem = Image.open(io.BytesIO(image_bytes))
                        texto_da_imagem = pytesseract.image_to_string(imagem, lang='por')
                        if texto_da_imagem:
                            texto_completo += " " + texto_da_imagem
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
        print(f"Erro ao processar o arquivo {caminho_arquivo}: {e}")
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
    
    resultados_com_bonus = []
    BONUS_PONTUACAO = 25
    
    for i, score in enumerate(scores_brutos):
        codigo_layout = LAYOUT_LABELS[i]
        meta = METADADOS_LAYOUTS.get(codigo_layout)
        pontuacao = score * 100
        
        if meta and sistema_alvo:
            # --- LÓGICA DE BUSCA ATUALIZADA ---
            # Prepara os termos para a busca (em minúsculas)
            termo_busca = sistema_alvo.lower()
            sistema_layout = str(meta.get('sistema', '')).lower()
            descricao_layout = str(meta.get('descricao', '')).lower()
            
            # Aplica o bônus se o termo estiver NO SISTEMA OU NA DESCRIÇÃO
            if termo_busca in sistema_layout or termo_busca in descricao_layout:
                pontuacao += BONUS_PONTUACAO
        
        resultados_com_bonus.append({
            "codigo_layout": codigo_layout,
            "banco": meta.get('descricao', f"Layout {codigo_layout}") if meta else f"Layout {codigo_layout}",
            "pontuacao": round(pontuacao, 2)
        })

    resultados_finais = sorted(resultados_com_bonus, key=lambda item: item['pontuacao'], reverse=True)
    
    extensao_arquivo = normalizar_extensao(os.path.splitext(caminho_arquivo_cliente)[1].lower().replace('.', ''))
    top_resultados = []
    for resultado in resultados_finais:
        meta = METADADOS_LAYOUTS.get(resultado['codigo_layout'])
        if meta and str(meta.get('formato', '')).lower() == extensao_arquivo:
            top_resultados.append(resultado)
    
    return top_resultados[:5]

def recarregar_modelo():
    print("Recarregando modelo e metadados...")
    return carregar_modelo_e_meta()