# Arquivo: treinador_em_massa.py (VERSÃO COM BARRA DE PROGRESSO)

import os
import re
import json
from collections import defaultdict
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
import argparse
from tqdm import tqdm # <-- Importamos a nova biblioteca

from identificador import extrair_texto_do_arquivo, STOPWORDS

# --- CONFIGURAÇÕES ---
PASTA_PRINCIPAL_TREINAMENTO = 'arquivos_de_treinamento'
NOME_ARQUIVO_MAPEAMENTO = 'mapeamento_layouts.xlsx'

ARQUIVO_VECTORIZER = 'vectorizer.joblib'
ARQUIVO_MATRIZ_TFIDF = 'tfidf_matrix.joblib'
ARQUIVO_LABELS = 'layout_labels.joblib'
ARQUIVO_METADADOS = 'layouts_meta.json'

def atualizar_metadados():
    print("--- Etapa de Metadados ---")
    
    # ... (Esta função não muda) ...
    metadados_antigos = {}
    if os.path.exists(ARQUIVO_METADADOS):
        try:
            with open(ARQUIVO_METADADOS, 'r', encoding='utf-8') as f:
                lista_antiga = json.load(f)
                metadados_antigos = {item['codigo_layout']: item for item in lista_antiga}
            print(f"Encontrados {len(metadados_antigos)} layouts existentes em '{ARQUIVO_METADADOS}'.")
        except json.JSONDecodeError:
            print(f"AVISO: O arquivo '{ARQUIVO_METADADOS}' parece estar corrompido e será sobrescrito.")
    print(f"Lendo o arquivo de mapeamento '{NOME_ARQUIVO_MAPEAMENTO}'...")
    if not os.path.exists(NOME_ARQUIVO_MAPEAMENTO):
        print(f"AVISO: '{NOME_ARQUIVO_MAPEAMENTO}' não encontrado.")
        mapa_layouts_novos = {}
    else:
        try:
            df_mapa = pd.read_excel(
                NOME_ARQUIVO_MAPEAMENTO,
                dtype={'codigo_layout': str, 'descricao': str, 'Formato': str},
                engine='openpyxl'
            )
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
    print(f"Mapeamento do Excel carregado. Total de layouts conhecidos agora é {len(metadados_antigos)}.")
    with open(ARQUIVO_METADADOS, 'w', encoding='utf-8') as f:
        json.dump(list(metadados_antigos.values()), f, indent=4, ensure_ascii=False)
    print(f"'{ARQUIVO_METADADOS}' foi atualizado com sucesso.")
    return metadados_antigos


def treinar_modelo_ml(mapa_layouts):
    print("\n--- Etapa de Treinamento de Machine Learning ---")
    
    print("Lendo e processando arquivos de treinamento...")
    textos_por_layout = defaultdict(str)
    
    # Pega a lista de todos os arquivos para podermos usar na barra de progresso
    todos_os_arquivos = os.listdir(PASTA_PRINCIPAL_TREINAMENTO)

    # --- MUDANÇA PRINCIPAL AQUI ---
    # Envolvemos a lista de arquivos com a função tqdm() para criar a barra de progresso
    for nome_arquivo in tqdm(todos_os_arquivos, desc="Lendo arquivos de treinamento"):
        match = re.search(r'\d+', nome_arquivo)
        if match:
            codigo_layout = match.group(0)
            if codigo_layout in mapa_layouts:
                caminho_completo = os.path.join(PASTA_PRINCIPAL_TREINAMENTO, nome_arquivo)
                senha_extraida = re.search(r'senha[_\s-]*(\d+)', nome_arquivo, re.IGNORECASE)
                texto = extrair_texto_do_arquivo(caminho_completo, senha_manual=senha_extraida.group(1) if senha_extraida else None)
                if texto:
                    textos_por_layout[codigo_layout] += " " + texto

    if not textos_por_layout:
        print("AVISO: Nenhum arquivo encontrado para o treinamento de ML. Modelos não serão atualizados.")
        return

    labels = list(textos_por_layout.keys())
    corpus = [textos_por_layout[label] for label in labels]
    
    print("\nTreinando o vetorizador TF-IDF...")
    vectorizer = TfidfVectorizer(stop_words=STOPWORDS, norm='l2', ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform(corpus)

    print("Salvando os arquivos do modelo de ML...")
    joblib.dump(vectorizer, ARQUIVO_VECTORIZER)
    joblib.dump(tfidf_matrix, ARQUIVO_MATRIZ_TFIDF)
    joblib.dump(labels, ARQUIVO_LABELS)
    print("Arquivos de modelo de ML foram recriados com sucesso.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Treinador para o identificador de layouts.")
    parser.add_argument(
        '--apenas-meta',
        action='store_true',
        help="Executa apenas a atualização rápida do arquivo de metadados."
    )
    args = parser.parse_args()

    mapa_final = atualizar_metadados()

    if not args.apenas_meta:
        if mapa_final:
            treinar_modelo_ml(mapa_final)
        else:
            print("Treinamento de ML pulado devido a erro na leitura de metadados.")
    else:
        print("\nTreinamento de ML foi pulado conforme solicitado (--apenas-meta).")

    print("\n--- Processo Concluído ---")