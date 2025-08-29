# Arquivo: treinador_em_massa.py (VERSÃO COM INTEGRAÇÃO DE API PARA IMAGENS)

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
import requests # <-- Nova importação

from identificador import extrair_texto_do_arquivo, STOPWORDS

# --- CONFIGURAÇÕES ---
PASTA_PRINCIPAL_TREINAMENTO = 'arquivos_de_treinamento'
PASTA_CACHE = 'cache_de_texto'
NOME_ARQUIVO_MAPEAMENTO = 'mapeamento_layouts.xlsx'

ARQUIVO_VECTORIZER = 'vectorizer.joblib'
ARQUIVO_MATRIZ_TFIDF = 'tfidf_matrix.joblib'
ARQUIVO_LABELS = 'layout_labels.joblib'
ARQUIVO_METADADOS = 'layouts_meta.json'

API_BASE_URL = "https://manager.conciliadorcontabil.com.br/api/"
API_SECRET = os.getenv('API_SECRET') # Carrega o segredo do arquivo .env

if not os.path.exists(PASTA_CACHE):
    os.makedirs(PASTA_CACHE)

def buscar_links_de_imagens_da_api():
    """Conecta na API, busca os layouts e retorna um dicionário de {codigo: url_imagem}."""
    print("Conectando à API para buscar links de imagens...")
    if not API_SECRET:
        print("AVISO: Segredo da API não encontrado no arquivo .env. Não será possível buscar imagens.")
        return {}

    try:
        # 1. Obter o token
        response_token = requests.get(f"{API_BASE_URL}get-token?secret={API_SECRET}")
        response_token.raise_for_status() # Lança um erro se a requisição falhar (ex: erro 404, 500)
        access_token = response_token.json().get("access_token")
        
        if not access_token:
            print("ERRO: Não foi possível obter o access_token da API.")
            return {}

        # 2. Buscar os layouts
        headers = {'Authorization': f'Bearer {access_token}'}
        response_layouts = requests.get(f"{API_BASE_URL}layouts?orderby=id,asc", headers=headers)
        response_layouts.raise_for_status()
        layouts_da_api = response_layouts.json()

        # 3. Criar o dicionário de mapeamento
        mapa_imagens = {}
        # PONTO DE ATENÇÃO: Verifique os nomes exatos dos campos na resposta da sua API
        for layout in layouts_da_api:
            codigo = str(layout.get('id')) # ASSUMINDO que o código do layout está no campo 'id'
            url_imagem = layout.get('imagem_url') # ASSUMINDO que o link da imagem está no campo 'imagem_url'
            if codigo and url_imagem:
                mapa_imagens[codigo] = url_imagem
        
        print(f"Sucesso! {len(mapa_imagens)} links de imagem encontrados na API.")
        return mapa_imagens

    except requests.exceptions.RequestException as e:
        print(f"ERRO ao se comunicar com a API: {e}")
        return {}


def atualizar_metadados(mapa_imagens):
    """Lê o excel, mescla com os dados da API e salva os metadados."""
    # ... (lógica de leitura do excel e atualização do .json) ...
    print("--- Etapa de Metadados ---")
    # ... (lógica de leitura do layouts_meta.json antigo) ...
    metadados_antigos = {}
    if os.path.exists(ARQUIVO_METADADOS):
        try:
            with open(ARQUIVO_METADADOS, 'r', encoding='utf-8') as f:
                lista_antiga = json.load(f)
                metadados_antigos = {item['codigo_layout']: item for item in lista_antiga}
            print(f"Encontrados {len(metadados_antigos)} layouts existentes.")
        except json.JSONDecodeError: pass
    
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
    
    # --- NOVA LÓGICA: ENRIQUECER METADADOS COM LINKS DA API ---
    print("Enriquecendo metadados com links de imagem da API...")
    for codigo, info in metadados_antigos.items():
        if codigo in mapa_imagens:
            info['url_previa'] = mapa_imagens[codigo]

    with open(ARQUIVO_METADADOS, 'w', encoding='utf-8') as f:
        json.dump(list(metadados_antigos.values()), f, indent=4, ensure_ascii=False)
    
    print(f"'{ARQUIVO_METADADOS}' foi atualizado com sucesso com {len(metadados_antigos)} registros.")
    return metadados_antigos

# ... (a função treinar_modelo_ml e a lógica de argparse permanecem as mesmas)
def treinar_modelo_ml(mapa_layouts):
    # ... (código existente)
    pass
if __name__ == '__main__':
    # Primeiro, busca os links da API
    mapa_links_imagens = buscar_links_de_imagens_da_api()

    # O resto do script usa esses links para enriquecer os dados
    parser = argparse.ArgumentParser(description="Treinador para o identificador de layouts.")
    parser.add_argument('--apenas-meta', action='store_true', help="Executa apenas a atualização do arquivo de metadados.")
    parser.add_argument('--apenas-cache', action='store_true', help="Executa apenas a leitura e salvamento dos textos no cache.")
    args = parser.parse_args()

    if args.apenas_cache:
        # A função de gerar cache precisa ser definida aqui se for usada
        pass
    elif args.apenas_meta:
        atualizar_metadados(mapa_links_imagens)
    else:
        mapa_final = atualizar_metadados(mapa_links_imagens)
        if mapa_final:
            # A função treinar_modelo_ml precisa ser definida aqui se for usada
            pass
    print("\n--- Processo Concluído ---")