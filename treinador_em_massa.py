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

# Importa as funções de extração do nosso cérebro
from identificador import extrair_texto_do_arquivo, extrair_texto_do_cabecalho

# --- CONFIGURAÇÕES ---
PASTA_PRINCIPAL_TREINAMENTO = 'arquivos_de_treinamento'
PASTA_CACHE = 'cache_de_texto'
NOME_ARQUIVO_MAPEAMENTO = 'mapeamento_layouts.xlsx'
NOME_MODELO_SEMANTICO = 'distiluse-base-multilingual-cased-v1'

ARQUIVO_EMBEDDINGS = 'layout_embeddings.joblib'
ARQUIVO_LABELS = 'layout_labels.joblib'
ARQUIVO_METADADOS = 'layouts_meta.json'

API_BASE_URL = "https://manager.conciliadorcontabil.com.br/api/"
load_dotenv() 
API_SECRET = os.getenv('API_SECRET')

if not os.path.exists(PASTA_CACHE):
    os.makedirs(PASTA_CACHE)

def sincronizar_mapeamento_com_api():
    """
    Busca todos os layouts da API, corrige os formatos 'EXCEL' para 'PDF' e
    cria/sobrescreve o arquivo mapeamento_layouts.xlsx.
    """
    print("--- Etapa de Sincronização com a API ---")
    if not API_SECRET:
        print("ERRO: Segredo da API não encontrado no arquivo .env. Não é possível sincronizar.")
        return False

    try:
        # 1. Obter token
        token_url = f"{API_BASE_URL}get-token"
        response_token = requests.post(token_url, data={'secret': API_SECRET})
        response_token.raise_for_status()
        access_token = response_token.json().get("data", {}).get("access_token")
        if not access_token:
            print("ERRO: Não foi possível obter o access_token da API.")
            return False

        # 2. Buscar layouts da API
        print("Buscando todos os layouts do Manager...")
        headers = {'Authorization': f'Bearer {access_token}'}
        response_layouts = requests.get(f"{API_BASE_URL}layouts?orderby=id,asc", headers=headers)
        response_layouts.raise_for_status()
        
        layouts_da_api_objeto = response_layouts.json()
        layouts_da_api_lista = layouts_da_api_objeto.get("data", [])

        if not isinstance(layouts_da_api_lista, list):
             print("ERRO: A API não retornou uma lista de layouts válida.")
             return False

        # 3. Preparar dados para o Excel, com a correção de formato
        dados_para_excel = []
        for layout in layouts_da_api_lista:
            formato_original = layout.get('formato')
            
            # --- LÓGICA DE CORREÇÃO AQUI ---
            # Se o formato for 'EXCEL' (ignorando maiúsculas/minúsculas), substitui por 'PDF'
            if formato_original and formato_original.upper() == 'EXCEL':
                formato_corrigido = 'PDF'
            else:
                formato_corrigido = formato_original

            dados_para_excel.append({
                'codigo_layout': layout.get('codigo'),
                'descricao': layout.get('nome'),
                'Formato': formato_corrigido
            })

        # 4. Criar o DataFrame e salvar no Excel
        df_final = pd.DataFrame(dados_para_excel)
        df_final.to_excel(NOME_ARQUIVO_MAPEAMENTO, index=False, engine='openpyxl')
        
        print(f"Sucesso! O arquivo '{NOME_ARQUIVO_MAPEAMENTO}' foi atualizado com {len(df_final)} layouts da API (formatos 'EXCEL' foram corrigidos para 'PDF').")
        return True

    except Exception as e:
        print(f"ERRO CRÍTICO durante a sincronização com a API: {e}")
        return False

def extrair_e_padronizar_sistema(descricao):
    """
    Função inteligente para extrair e padronizar o nome do sistema a partir da descrição.
    """
    descricao = str(descricao)
    sistema = ''
    if ' - ' in descricao:
        sistema = descricao.split(' - ')[0].strip()
    else:
        desc_sem_codigo = re.sub(r'^\d+\s*', '', descricao).strip()
        partes = desc_sem_codigo.split()
        if len(partes) > 0:
            sistema = partes[0].strip()
    
    if sistema.upper() == 'BB':
        return 'BB BANCO DO BRASIL'
    elif sistema.upper() == 'CEF':
        return 'CEF CAIXA ECONOMICA FEDERAL'
    else:
        return sistema

def atualizar_metadados():
    """
    Lê a planilha Excel, extrai cabeçalhos, classifica os relatórios
    e cria um layouts_meta.json completo.
    """
    print("\n--- Etapa de Metadados ---")
    
    print(f"Lendo o arquivo de mapeamento '{NOME_ARQUIVO_MAPEAMENTO}'...")
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
        
        print("Extraindo informações de cabeçalho dos arquivos de exemplo...")
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

        print("Classificando relatórios como 'Bancário' ou 'Financeiro'...")
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
        
        print(f"'{ARQUIVO_METADADOS}' foi atualizado com sucesso com {len(metadados_completos)} registros.")
        return mapa_layouts
        
    except Exception as e:
        print(f"ERRO ao ler o arquivo Excel: {e}.")
        return None

def treinar_modelo_ml(mapa_layouts):
    """
    Lê todos os arquivos de treinamento (usando cache) e treina o modelo de ML.
    """
    print("\n--- Etapa de Treinamento de Machine Learning (Usando Cache) ---")
    textos_por_layout = defaultdict(str)
    
    if not os.path.exists(PASTA_PRINCIPAL_TREINAMENTO):
        print("AVISO: Pasta de treinamento não encontrada. Pulando etapa de ML.")
        return

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
    if not textos_por_layout:
        print("AVISO: Nenhum arquivo encontrado para o treinamento de ML. Os arquivos de modelo não serão atualizados.")
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
    parser.add_argument(
        '--sincronizar-api',
        action='store_true',
        help="Executa apenas a sincronização da API para o arquivo Excel e atualiza os metadados."
    )
    parser.add_argument(
        '--apenas-meta',
        action='store_true',
        help="Executa apenas a atualização do arquivo de metadados a partir do Excel existente."
    )
    args = parser.parse_args()

    if args.sincronizar_api:
        if sincronizar_mapeamento_com_api():
            atualizar_metadados()
    elif args.apenas_meta:
        atualizar_metadados()
    else:
        sucesso_sinc = sincronizar_mapeamento_com_api()
        if sucesso_sinc:
            mapa_final = atualizar_metadados()
            if mapa_final:
                treinar_modelo_ml(mapa_final)
    
    print("\n--- Processo Concluído ---")