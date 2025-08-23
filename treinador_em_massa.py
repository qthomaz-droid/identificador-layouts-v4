# Arquivo: treinador_em_massa.py

import os
import json
from collections import Counter, defaultdict
import re
from identificador import extrair_texto_do_arquivo, carregar_base_layouts, STOPWORDS

PASTA_PRINCIPAL_TREINAMENTO = 'arquivos_de_treinamento'
ARQUIVO_JSON_LAYOUTS = 'layouts.json'
NUMERO_DE_PALAVRAS_CHAVE = 30
EXTENSOES_SUPORTADAS = ['.pdf', '.xlsx', '.xls', '.txt', '.csv', '.xml']

def extrair_senha_do_nome(nome_arquivo):
    match = re.search(r'senha[_\s-]*(\d+)', nome_arquivo, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def normalizar_extensao(ext):
    if ext in ['xls', 'xlsx']: return 'excel'
    if ext in ['txt', 'csv']: return 'txt'
    return ext

def treinar_em_massa_por_nome():
    print("--- Iniciando Treinamento por Nomes de Arquivo ---")
    if not os.path.exists(PASTA_PRINCIPAL_TREINAMENTO):
        print(f"ERRO: A pasta de treinamento '{PASTA_PRINCIPAL_TREINAMENTO}' não foi encontrada.")
        return

    arquivos_agrupados = defaultdict(list)
    print("1/3 - Mapeando e agrupando arquivos...")
    todos_os_arquivos = [f for f in os.listdir(PASTA_PRINCIPAL_TREINAMENTO) if os.path.splitext(f)[1].lower() in EXTENSOES_SUPORTADAS]

    for nome_arquivo in todos_os_arquivos:
        match = re.search(r'\d+', nome_arquivo)
        if match:
            codigo_layout = match.group(0)
            caminho_completo = os.path.join(PASTA_PRINCIPAL_TREINAMENTO, nome_arquivo)
            arquivos_agrupados[codigo_layout].append(caminho_completo)
    
    if not arquivos_agrupados:
        print("Nenhum arquivo com código numérico no nome foi encontrado para treinamento.")
        return
    
    print(f"Encontrados {len(arquivos_agrupados)} layouts únicos para treinar.")
    print("\n2/3 - Extraindo palavras-chave e validando tipos...")
    layouts_existentes = {layout['codigo_layout']: layout for layout in carregar_base_layouts(ARQUIVO_JSON_LAYOUTS)}

    for codigo_layout, lista_arquivos in arquivos_agrupados.items():
        tipos_de_arquivo_encontrados = set()
        for caminho_arquivo in lista_arquivos:
            ext = os.path.splitext(caminho_arquivo)[1].lower().replace('.', '')
            tipo_normalizado = normalizar_extensao(ext)
            tipos_de_arquivo_encontrados.add(tipo_normalizado)
        
        if len(tipos_de_arquivo_encontrados) > 1:
            print(f"  - ERRO: O layout '{codigo_layout}' contém múltiplos tipos de arquivo ({tipos_de_arquivo_encontrados}). Ignorando.")
            continue
        
        tipo_arquivo_final = list(tipos_de_arquivo_encontrados)[0]
        print(f"  - Processando layout '{codigo_layout}' (Tipo: {tipo_arquivo_final}, {len(lista_arquivos)} arquivos)...")
        
        texto_consolidado = ""
        for caminho_arquivo in lista_arquivos:
            nome_do_arquivo = os.path.basename(caminho_arquivo)
            senha_extraida = extrair_senha_do_nome(nome_do_arquivo)
            if senha_extraida:
                print(f"    -> Senha encontrada no nome do arquivo '{nome_do_arquivo}': '{senha_extraida}'.")
            
            texto_extraido = extrair_texto_do_arquivo(caminho_arquivo, senha_manual=senha_extraida)

            if texto_extraido and "SENHA_" not in texto_extraido:
                texto_consolidado += " " + texto_extraido
            else:
                print(f"    -> AVISO: Não foi possível ler o arquivo '{nome_do_arquivo}'.")

        if not texto_consolidado: continue
        palavras = re.findall(r'\b[a-zçãõáéíóúâêôà-]{4,}\b', texto_consolidado)
        palavras_filtradas = [p for p in palavras if p not in STOPWORDS]
        contagem = Counter(palavras_filtradas)
        novas_palavras_chave = [palavra for palavra, freq in contagem.most_common(NUMERO_DE_PALAVRAS_CHAVE)]

        if not novas_palavras_chave: continue
        
        layouts_existentes[codigo_layout] = {
            "codigo_layout": codigo_layout,
            "banco": f"Layout {codigo_layout} (treinado via massa)",
            "tipo_arquivo": tipo_arquivo_final,
            "palavras_chave": sorted(novas_palavras_chave),
            "requer_todas_palavras": False
        }

    print("\n3/3 - Salvando resultados no layouts.json...")
    try:
        lista_layouts_final = list(layouts_existentes.values())
        with open(ARQUIVO_JSON_LAYOUTS, 'w', encoding='utf-8') as f:
            json.dump(lista_layouts_final, f, indent=2, ensure_ascii=False)
        print(f"🎉 O arquivo '{ARQUIVO_JSON_LAYOUTS}' foi atualizado com sucesso!")
    except Exception as e:
        print(f"\nERRO FATAL: Não foi possível salvar o arquivo JSON. {e}")

if __name__ == '__main__':
    treinar_em_massa_por_nome()