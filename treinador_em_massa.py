# Arquivo: treinador_em_massa.py

import os
import re
import json
from collections import defaultdict
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
import argparse
from tqdm import tqdm
from datetime import datetime

from identificador import extrair_texto_do_arquivo, STOPWORDS

# --- CONFIGURAÇÕES ---
PASTA_PRINCIPAL_TREINAMENTO = 'arquivos_de_treinamento'
PASTA_CACHE = 'cache_de_texto'
NOME_ARQUIVO_MAPEAMENTO = 'mapeamento_layouts.xlsx'
ARQUIVO_VECTORIZER = 'vectorizer.joblib'
ARQUIVO_MATRIZ_TFIDF = 'tfidf_matrix.joblib'
ARQUIVO_LABELS = 'layout_labels.joblib'
ARQUIVO_METADADOS = 'layouts_meta.json'

if not os.path.exists(PASTA_CACHE):
    os.makedirs(PASTA_CACHE)

def atualizar_metadados():
    print("--- Etapa de Metadados ---")
    metadados_antigos = {}
    if os.path.exists(ARQUIVO_METADADOS):
        try:
            with open(ARQUIVO_METADADOS, 'r', encoding='utf-8') as f:
                lista_antiga = json.load(f)
                metadados_antigos = {item['codigo_layout']: item for item in lista_antiga}
        except json.JSONDecodeError:
            pass # Ignora arquivo corrompido
    
    print(f"Lendo o arquivo de mapeamento '{NOME_ARQUIVO_MAPEAMENTO}'...")
    if not os.path.exists(NOME_ARQUIVO_MAPEAMENTO):
        mapa_layouts_novos = {}
    else:
        try:
            df_mapa = pd.read_excel(NOME_ARQUIVO_MAPEAMENTO, dtype=str, engine='openpyxl')
            df_mapa.fillna('', inplace=True)
            df_mapa.rename(columns={'Formato': 'formato'}, inplace=True)
            df_mapa['sistema'] = df_mapa['descricao'].apply(lambda x: x.split(' - ')[0].strip() if ' - ' in x else '')
            mapa_layouts_novos = df_mapa.set_index('codigo_layout').to_dict('index')
            for codigo, info in mapa_layouts_novos.items():
                info['codigo_layout'] = codigo
        except Exception as e:
            print(f"ERRO ao ler o arquivo Excel: {e}.")
            return metadados_antigos
            
    metadados_antigos.update(mapa_layouts_novos)
    
    with open(ARQUIVO_METADADOS, 'w', encoding='utf-8') as f:
        json.dump(list(metadados_antigos.values()), f, indent=4, ensure_ascii=False)
    
    print(f"'{ARQUIVO_METADADOS}' foi atualizado com sucesso com {len(metadados_antigos)} registros.")
    return metadados_antigos

def gerar_cache_de_texto():
    print("\n--- Modo Apenas Cache: Lendo arquivos para gerar o cache de texto ---")
    for nome_arquivo in tqdm(os.listdir(PASTA_PRINCIPAL_TREINAMENTO), desc="Gerando cache"):
        caminho_cache = os.path.join(PASTA_CACHE, nome_arquivo + '.txt')
        if not os.path.exists(caminho_cache):
            caminho_completo = os.path.join(PASTA_PRINCIPAL_TREINAMENTO, nome_arquivo)
            senha_extraida = re.search(r'senha[_\s-]*(\d+)', nome_arquivo, re.IGNORECASE)
            texto_extraido = extrair_texto_do_arquivo(caminho_completo, senha_manual=senha_extraida.group(1) if senha_extraida else None)
            if texto_extraido:
                with open(caminho_cache, 'w', encoding='utf-8') as f:
                    f.write(texto_extraido)
    print("Geração de cache concluída.")

def treinar_modelo_ml(mapa_layouts):
    print("\n--- Etapa de Treinamento de Machine Learning (Usando Cache) ---")
    textos_por_layout = defaultdict(str)
    
    print("Verificando cache e lendo arquivos de treinamento...")
    for nome_arquivo in tqdm(os.listdir(PASTA_PRINCIPAL_TREINAMENTO), desc="Processando arquivos"):
        caminho_cache = os.path.join(PASTA_CACHE, nome_arquivo + '.txt')
        texto = ""
        if os.path.exists(caminho_cache):
            with open(caminho_cache, 'r', encoding='utf-8') as f:
                texto = f.read()
        else:
            caminho_completo = os.path.join(PASTA_PRINCIPAL_TREINAMENTO, nome_arquivo)
            senha_extraida = re.search(r'senha[_\s-]*(\d+)', nome_arquivo, re.IGNORECASE)
            texto_extraido = extrair_texto_do_arquivo(caminho_completo, senha_manual=senha_extraida.group(1) if senha_extraida else None)
            if texto_extraido:
                texto = texto_extraido
                with open(caminho_cache, 'w', encoding='utf-8') as f:
                    f.write(texto)
        if texto:
            match = re.search(r'\d+', nome_arquivo)
            if match:
                codigo_layout = match.group(0)
                if codigo_layout in mapa_layouts:
                    textos_por_layout[codigo_layout] += " " + texto

    if not textos_por_layout: return

    labels = list(textos_por_layout.keys())
    corpus = [textos_por_layout[label] for label in labels]
    
    print("\nTreinando o vetorizador TF-IDF...")
    vectorizer = TfidfVectorizer(stop_words=STOPWORDS, norm='l2', ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform(corpus)

    print("Salvando os arquivos do modelo de ML...")
    joblib.dump(vectorizer, ARQUIVO_VECTORIZER)
    joblib.dump(tfidf_matrix, ARQUIVO_MATRIZ_TFIDF)
    joblib.dump(labels, ARQUIVO_LABELS)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("model_version.txt", "w") as f:
        f.write(timestamp)
    print(f"Selo de versão do modelo criado: {timestamp}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Treinador para o identificador de layouts.")
    parser.add_argument('--apenas-meta', action='store_true', help="Executa apenas a atualização do arquivo de metadados.")
    parser.add_argument('--apenas-cache', action='store_true', help="Executa apenas a leitura e salvamento dos textos no cache.")
    args = parser.parse_args()
    if args.apenas_cache:
        gerar_cache_de_texto()
    elif args.apenas_meta:
        atualizar_metadados()
    else:
        mapa_final = atualizar_metadados()
        if mapa_final:
            treinar_modelo_ml(mapa_final)
    print("\n--- Processo Concluído ---")