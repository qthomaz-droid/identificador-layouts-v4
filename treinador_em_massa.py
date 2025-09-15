# Arquivo: treinador_em_massa.py

import os
import re
import json
from collections import defaultdict
import joblib
import pandas as pd
import argparse
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from datetime import datetime
import requests
from dotenv import load_dotenv

from identificador import extrair_texto_do_arquivo, extrair_texto_do_cabecalho, STOPWORDS

# --- CONFIGURAÇÕES ---
PASTA_PRINCIPAL_TREINAMENTO = 'arquivos_de_treinamento'
PASTA_CACHE = 'cache_de_texto'
NOME_ARQUIVO_MAPEAMENTO = 'mapeamento_layouts.xlsx'
NOME_MODELO_SEMANTICO = 'distiluse-base-multilingual-cased-v1'

ARQUIVO_EMBEDDINGS = 'layout_embeddings.joblib'
ARQUIVO_LABELS = 'layout_labels.joblib'
ARQUIVO_METADADOS = 'layouts_meta.json'
ARQUIVO_VECTORIZER = 'vectorizer.joblib' # Adicionado para consistência

API_BASE_URL = "https://manager.conciliadorcontabil.com.br/api/"
load_dotenv() 
API_SECRET = os.getenv('API_SECRET')

if not os.path.exists(PASTA_CACHE):
    os.makedirs(PASTA_CACHE)

def sincronizar_mapeamento_com_api():
    print("--- Etapa de Sincronização com a API ---")
    if not API_SECRET:
        print("ERRO: Segredo da API não encontrado no .env.")
        return False
    try:
        token_url = f"{API_BASE_URL}get-token"
        response_token = requests.post(token_url, data={'secret': API_SECRET})
        response_token.raise_for_status()
        access_token = response_token.json().get("data", {}).get("access_token")
        if not access_token:
            print("ERRO: Não foi possível obter o access_token da API.")
            return False
        print("Buscando todos os layouts do Manager...")
        headers = {'Authorization': f'Bearer {access_token}'}
        response_layouts = requests.get(f"{API_BASE_URL}layouts?orderby=id,asc", headers=headers)
        response_layouts.raise_for_status()
        layouts_da_api_objeto = response_layouts.json()
        layouts_da_api_lista = layouts_da_api_objeto.get("data", [])
        if not isinstance(layouts_da_api_lista, list):
             print("ERRO: A API não retornou uma lista de layouts válida.")
             return False
        dados_para_excel = []
        for layout in layouts_da_api_lista:
            formato_original = layout.get('formato')
            if formato_original and formato_original.upper() == 'EXCEL':
                formato_corrigido = 'PDF'
            else:
                formato_corrigido = formato_original
            dados_para_excel.append({'codigo_layout': layout.get('codigo'), 'descricao': layout.get('nome'), 'Formato': formato_corrigido})
        df_final = pd.DataFrame(dados_para_excel)
        df_final.to_excel(NOME_ARQUIVO_MAPEAMENTO, index=False, engine='openpyxl')
        print(f"Sucesso! '{NOME_ARQUIVO_MAPEAMENTO}' foi atualizado com {len(df_final)} layouts.")
        return True
    except Exception as e:
        print(f"ERRO CRÍTICO durante a sincronização com a API: {e}")
        return False

def extrair_e_padronizar_sistema(descricao):
    descricao = str(descricao)
    sistema = ''
    if ' - ' in descricao:
        sistema = descricao.split(' - ')[0].strip()
    else:
        desc_sem_codigo = re.sub(r'^\d+\s*', '', descricao).strip()
        partes = desc_sem_codigo.split()
        if len(partes) > 0:
            sistema = partes[0].strip()
    if sistema.upper() == 'BB': return 'BB BANCO DO BRASIL'
    elif sistema.upper() == 'CEF': return 'CEF CAIXA ECONOMICA FEDERAL'
    else: return sistema

def atualizar_metadados():
    print("\n--- Etapa de Metadados ---")
    if not os.path.exists(NOME_ARQUIVO_MAPEAMENTO):
        print(f"ERRO: Arquivo de mapeamento '{NOME_ARQUIVO_MAPEAMENTO}' não encontrado.")
        return None
    try:
        df_mapa = pd.read_excel(NOME_ARQUIVO_MAPEAMENTO, dtype=str, engine='openpyxl')
        df_mapa.fillna('', inplace=True)
        df_mapa.rename(columns={'Formato': 'formato'}, inplace=True)
        df_mapa['sistema'] = df_mapa['descricao'].apply(extrair_e_padronizar_sistema)
        metadados_completos = df_mapa.to_dict('records')
        mapa_layouts = {str(item['codigo_layout']): item for item in metadados_completos}
        print("Extraindo informações de cabeçalho...")
        cabecalhos_por_layout = defaultdict(str)
        if os.path.exists(PASTA_PRINCIPAL_TREINAMENTO):
            for nome_arquivo in os.listdir(PASTA_PRINCIPAL_TREINAMENTO):
                match = re.search(r'\d+', nome_arquivo)
                if match:
                    codigo_layout = match.group(0)
                    if codigo_layout in mapa_layouts:
                        caminho_completo = os.path.join(PASTA_PRINCIPAL_TREINAMENTO, nome_arquivo)
                        texto_cabecalho = extrair_texto_do_cabecalho(caminho_completo)
                        if texto_cabecalho:
                            cabecalhos_por_layout[codigo_layout] += " " + texto_cabecalho
        print("Classificando relatórios...")
        for meta_item in metadados_completos:
            codigo = str(meta_item.get('codigo_layout', ''))
            descricao = meta_item.get('descricao', '').lower()
            if 'extrato' in descricao:
                meta_item['tipo_relatorio'] = 'Bancário'
            else:
                meta_item['tipo_relatorio'] = 'Financeiro'
            if codigo in cabecalhos_por_layout:
                meta_item['cabecalho'] = " ".join(cabecalhos_por_layout[codigo].split())
        with open(ARQUIVO_METADADOS, 'w', encoding='utf-8') as f:
            json.dump(metadados_completos, f, indent=4, ensure_ascii=False)
        print(f"'{ARQUIVO_METADADOS}' foi atualizado com {len(metadados_completos)} registros.")
        return mapa_layouts
    except Exception as e:
        print(f"ERRO ao ler o arquivo Excel: {e}.")
        return None

def treinar_modelo_ml():
    print("\n--- Etapa de Treinamento de Machine Learning (Usando Cache) ---")
    textos_por_layout = defaultdict(str)
    if not os.path.exists(PASTA_CACHE):
        print("AVISO: Pasta de cache não encontrada. Pulando etapa de ML.")
        return
    print("Lendo textos do cache para o treinamento...")
    for nome_arquivo_cache in tqdm(os.listdir(PASTA_CACHE), desc="Lendo cache"):
        nome_original = os.path.splitext(nome_arquivo_cache)[0]
        match = re.search(r'\d+', nome_original)
        if match:
            codigo_layout = match.group(0)
            with open(os.path.join(PASTA_CACHE, nome_arquivo_cache), 'r', encoding='utf-8') as f:
                textos_por_layout[codigo_layout] += " " + f.read()
    if not textos_por_layout:
        print("AVISO: Nenhum texto encontrado no cache para treinar. Modelos não serão atualizados.")
        return
    labels = list(textos_por_layout.keys())
    corpus = [textos_por_layout[label] for label in labels]
    print("\nGerando embeddings semânticos...")
    model = SentenceTransformer(NOME_MODELO_SEMANTICO)
    embeddings = model.encode(corpus, show_progress_bar=True)
    print("Salvando os arquivos do modelo de ML...")
    joblib.dump(embeddings, ARQUIVO_EMBEDDINGS)
    joblib.dump(labels, ARQUIVO_LABELS)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("model_version.txt", "w") as f:
        f.write(timestamp)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Treinador para o identificador de layouts.")
    parser.add_argument('--sincronizar-api', action='store_true', help="Apenas sincroniza a API para o arquivo Excel e atualiza os metadados.")
    parser.add_argument('--apenas-meta', action='store_true', help="Apenas atualiza os metadados a partir do Excel existente.")
    parser.add_argument('--retreinar-rapido', action='store_true', help="Apenas retreina o modelo de ML a partir do cache de texto existente.")
    args = parser.parse_args()

    if args.sincronizar_api:
        if sincronizar_mapeamento_com_api():
            atualizar_metadados()
    elif args.apenas_meta:
        atualizar_metadados()
    elif args.retreinar_rapido:
        treinar_modelo_ml()
    else:
        sucesso_sinc = sincronizar_mapeamento_com_api()
        if sucesso_sinc:
            mapa_final = atualizar_metadados()
            if mapa_final:
                # A função treinar_modelo_ml agora é chamada sem argumentos
                treinar_modelo_ml()
    print("\n--- Processo Concluído ---")