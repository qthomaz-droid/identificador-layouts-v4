# Arquivo: identificador.py (VERSÃO COM TIMEOUT GRANULAR NO OCR)

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
import re
from collections import defaultdict
from tqdm import tqdm

# --- CONFIGURAÇÕES ---
# Limite de tempo (em segundos) para o OCR de UMA ÚNICA imagem.
TIMEOUT_OCR_IMAGEM = 15
MAX_PAGINAS_PDF = 5

# ... (Configuração do Tesseract e STOPWORDS permanecem os mesmos) ...
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
    nome_arquivo = os.path.basename(caminho_arquivo)
    
    try:
        if extensao == '.pdf':
            with fitz.open(caminho_arquivo) as doc:
                if doc.is_encrypted:
                    # ... (lógica de senha não muda)
                    desbloqueado = False
                    if senha_manual is not None:
                        if doc.authenticate(senha_manual) > 0: desbloqueado = True
                        else: return "SENHA_INCORRETA"
                    else:
                        for senha in SENHAS_COMUNS:
                            if doc.authenticate(senha) > 0: desbloqueado = True; break
                    if not desbloqueado: return "SENHA_NECESSARIA"

                for i, pagina in enumerate(doc):
                    if i >= MAX_PAGINAS_PDF:
                        break
                    
                    texto_completo += pagina.get_text()
                    
                    for img_index, img_info in enumerate(pagina.get_images(full=True)):
                        try:
                            xref = img_info[0]
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            imagem = Image.open(io.BytesIO(image_bytes))
                            
                            # --- MUDANÇA PRINCIPAL: Timeout aplicado diretamente na chamada do OCR ---
                            texto_da_imagem = pytesseract.image_to_string(imagem, lang='por', timeout=TIMEOUT_OCR_IMAGEM)
                            
                            if texto_da_imagem:
                                texto_completo += " " + texto_da_imagem
                        except (RuntimeError, Exception) as ocr_error:
                            # Se o Tesseract exceder o tempo limite, ele gera um RuntimeError
                            print(f"\n    -> AVISO: OCR de uma imagem no arquivo '{nome_arquivo}' (pág {i+1}) excedeu o tempo limite de {TIMEOUT_OCR_IMAGEM}s. Continuando com o texto já extraído.")
                            continue # Pula para a próxima imagem

                return texto_completo.lower()

        # ... (código para outros formatos permanece o mesmo) ...
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
        if "partial block in aes filter" in str(e):
            print(f"    -> AVISO: O arquivo '{nome_arquivo}' parece estar corrompido (erro de filtro AES). Ele será ignorado.")
        else:
            print(f"    -> AVISO: Falha ao processar o arquivo '{nome_arquivo}'. Erro: {e}. Ele será ignorado.")
        return None
        
    return texto_completo.lower()


# ... (O resto do arquivo, com as funções identificar_layout, recarregar_modelo, etc., permanece o mesmo) ...
def normalizar_extensao(ext):
    if ext in ['xls', 'xlsx']: return 'excel'
    if ext in ['txt', 'csv']: return 'txt'
    return ext
def identificar_layout(caminho_arquivo_cliente, sistema_alvo=None, senha_manual=None):
    if not MODELO_CARREGADO: return {"erro": "Modelo de ML não foi treinado."}
    texto_arquivo = extrair_texto_do_arquivo(caminho_arquivo_cliente, senha_manual=senha_manual)
    if texto_arquivo in ["SENHA_NECESSARIA", "SENHA_INCORRETA"]: return texto_arquivo
    if not texto_arquivo: return {"erro": "Não foi possível ler o conteúdo."}
    extensao_arquivo = normalizar_extensao(os.path.splitext(caminho_arquivo_cliente)[1].lower().replace('.', ''))
    layouts_candidatos = []
    for codigo, meta in METADADOS_LAYOUTS.items():
        formato_layout = str(meta.get('formato', '')).lower()
        sistema_layout = str(meta.get('sistema', '')).lower()
        match_formato = (formato_layout == extensao_arquivo)
        match_sistema = True
        if sistema_alvo:
            match_sistema = (sistema_alvo.lower() == sistema_layout or sistema_alvo.lower() in str(meta.get('descricao', '')).lower())
        if match_formato and match_sistema:
            layouts_candidatos.append(codigo)
    if not layouts_candidatos: return []
    indices_candidatos = [LAYOUT_LABELS.index(cod) for cod in layouts_candidatos if cod in LAYOUT_LABELS]
    if not indices_candidatos: return []
    sub_matriz_tfidf = TFIDF_MATRIX[indices_candidatos, :]
    vetor_arquivo_novo = VECTORIZER.transform([texto_arquivo])
    similaridades = cosine_similarity(vetor_arquivo_novo, sub_matriz_tfidf)
    scores = similaridades[0]
    labels_candidatos = [LAYOUT_LABELS[i] for i in indices_candidatos]
    resultados_finais = sorted(zip(scores, labels_candidatos), key=lambda item: item[0], reverse=True)
    top_resultados = []
    for score, label in resultados_finais[:5]:
        if score > 0.01:
            meta = METADADOS_LAYOUTS.get(label)
            top_resultados.append({
                "codigo_layout": label,
                "banco": meta.get('descricao', f"Layout {label}"),
                "pontuacao": round(score * 100, 2)
            })
    return top_resultados
def recarregar_modelo():
    print("Recarregando modelo e metadados...")
    return carregar_modelo_e_meta()
def retreinar_modelo_completo():
    print("\n--- Iniciando Retreinamento Completo do Modelo de ML ---")
    if not os.path.exists(PASTA_CACHE):
        print("ERRO: Pasta de cache não encontrada. Não é possível retreinar.")
        return False
    textos_por_layout = defaultdict(str)
    print("Lendo textos do cache...")
    for nome_arquivo_cache in tqdm(os.listdir(PASTA_CACHE), desc="Lendo cache"):
        nome_original = os.path.splitext(nome_arquivo_cache)[0]
        match = re.search(r'\d+', nome_original)
        if match:
            codigo_layout = match.group(0)
            with open(os.path.join(PASTA_CACHE, nome_arquivo_cache), 'r', encoding='utf-8') as f:
                textos_por_layout[codigo_layout] += " " + f.read()
    if not textos_por_layout:
        print("Nenhum texto encontrado no cache para treinamento.")
        return False
    labels = list(textos_por_layout.keys())
    corpus = [textos_por_layout[label] for label in labels]
    print("\nTreinando o vetorizador TF-IDF...")
    vectorizer = TfidfVectorizer(stop_words=STOPWORDS, norm='l2', ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform(corpus)
    print("Salvando os novos arquivos do modelo de ML...")
    joblib.dump(vectorizer, ARQUIVO_VECTORIZER)
    joblib.dump(tfidf_matrix, ARQUIVO_MATRIZ_TFIDF)
    joblib.dump(labels, ARQUIVO_LABELS)
    print("Retreinamento concluído e novos modelos salvos.")
    return True