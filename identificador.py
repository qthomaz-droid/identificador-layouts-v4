# Arquivo: identificador.py

import fitz
import pandas as pd
import json
import os
import re
from collections import Counter
import xml.etree.ElementTree as ET

SENHAS_COMUNS = ["", "123456", "0000"]

STOPWORDS = [
    'de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para', 'é', 'com', 'não', 'uma',
    'os', 'no', 'se', 'na', 'por', 'mais', 'as', 'dos', 'como', 'mas', 'foi', 'ao', 'ele',
    'das', 'tem', 'à', 'seu', 'sua', 'ou', 'ser', 'quando', 'muito', 'há', 'nos', 'já',
    'está', 'eu', 'também', 'só', 'pelo', 'pela', 'até', 'isso', 'ela', 'entre', 'era',
    'depois', 'sem', 'mesmo', 'aos', 'ter', 'seus', 'quem', 'nas', 'me', 'esse', 'eles',
    'estão', 'você', 'tinha', 'foram', 'essa', 'num', 'nem', 'suas', 'meu', 'às', 'minha',
    'numa', 'pelos', 'elas', 'havia', 'seja', 'qual', 'será', 'nós', 'tenho', 'lhe',
    'deles', 'essas', 'esses', 'pelas', 'este', 'fosse', 'dele', 'tu', 'te', 'vocês',
    'vos', 'lhes', 'meus', 'minhas', 'teu', 'tua', 'teus', 'tuas', 'nosso', 'nossa',
    'nossos', 'nossas', 'dela', 'delas', 'esta', 'estes', 'estas', 'aquele', 'aquela',
    'aqueles', 'aquelas', 'isto', 'aquilo', 'estou', 'está', 'estamos', 'estão', 'estive',
    'esteve', 'estivemos', 'estiveram', 'estava', 'estávamos', 'estavam', 'estivera',
    'estivéramos', 'esteja', 'estejamos', 'estejam', 'estivesse', 'estivéssemos',
    'estivessem', 'estiver', 'estivermos', 'estiverem', 'houve', 'houveram', 'houvera',
    'houvéramos', 'haja', 'hajamos', 'hajam', 'houvesse', 'houvéssemos', 'houvessem',
    'houver', 'houvermos', 'houverem', 'houverei', 'houverá', 'houveremos', 'houverão',
    'houveria', 'houveríamos', 'houveriam', 'r$', 'cpf', 'cnpj', 'cep', 'data', 'valor',
    'saldo', 'total', 'doc', 'ag', 'conta', 'corrente', 'extrato', 'historico'
]

def carregar_base_layouts(caminho_json='layouts.json'):
    if not os.path.exists(caminho_json): return []
    try:
        with open(caminho_json, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def extrair_texto_do_arquivo(caminho_arquivo, senha_manual=None):
    texto_completo = ""
    extensao = os.path.splitext(caminho_arquivo)[1].lower()
    
    try:
        if extensao == '.pdf':
            with fitz.open(caminho_arquivo) as doc:
                if not doc.is_encrypted:
                    for pagina in doc:
                        texto_completo += pagina.get_text()
                    return texto_completo.lower()

                if senha_manual is not None:
                    if doc.authenticate(senha_manual) > 0:
                        for pagina in doc:
                            texto_completo += pagina.get_text()
                        return texto_completo.lower()
                    else:
                        return "SENHA_INCORRETA"
                
                else:
                    desbloqueado = False
                    for senha in SENHAS_COMUNS:
                        if doc.authenticate(senha) > 0:
                            desbloqueado = True
                            break
                    
                    if desbloqueado:
                        for pagina in doc:
                            texto_completo += pagina.get_text()
                        return texto_completo.lower()
                    else:
                        return "SENHA_NECESSARIA"

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

def identificar_layout(caminho_arquivo_cliente, senha_manual=None):
    layouts = carregar_base_layouts()
    texto_arquivo = extrair_texto_do_arquivo(caminho_arquivo_cliente, senha_manual=senha_manual)
    if texto_arquivo in ["SENHA_NECESSARIA", "SENHA_INCORRETA"]: return texto_arquivo
    if not layouts: return {"erro": "A base de layouts `layouts.json` está vazia."}
    if not texto_arquivo: return {"erro": "Não foi possível ler o conteúdo do arquivo."}
    extensao_arquivo = os.path.splitext(caminho_arquivo_cliente)[1].lower().replace('.', '')
    resultados_encontrados = []
    for layout in layouts:
        tipo_layout = layout.get('tipo_arquivo', '').lower()
        compativel = False
        if tipo_layout == extensao_arquivo: compativel = True
        elif tipo_layout == 'excel' and extensao_arquivo in ['xls', 'xlsx']: compativel = True
        elif tipo_layout in ['txt', 'csv'] and extensao_arquivo in ['txt', 'csv']: compativel = True
        if not compativel: continue
        palavras_chave_lower = [str(p).lower() for p in layout.get('palavras_chave', [])]
        palavras_encontradas = sum(1 for p in palavras_chave_lower if p in texto_arquivo)
        total_palavras = len(palavras_chave_lower)
        pontuacao = (palavras_encontradas / total_palavras) * 100 if total_palavras > 0 else 0
        if pontuacao > 0:
            resultados_encontrados.append({
                "codigo_layout": layout['codigo_layout'],
                "banco": layout['banco'],
                "pontuacao": round(pontuacao, 2)})
    if not resultados_encontrados: return []
    resultados_ordenados = sorted(resultados_encontrados, key=lambda x: x['pontuacao'], reverse=True)
    return resultados_ordenados[:5]

def sugerir_palavras_chave(caminho_arquivo, n_sugestoes=30):
    texto = extrair_texto_do_arquivo(caminho_arquivo)
    if texto in ["SENHA_NECESSARIA", "SENHA_INCORRETA"]: return []
    if not texto: return []
    palavras = re.findall(r'\b[a-zçãõáéíóúâêôà-]{3,}\b', texto)
    palavras_filtradas = [p for p in palavras if p not in STOPWORDS]
    contagem = Counter(palavras_filtradas)
    return [palavra for palavra, freq in contagem.most_common(n_sugestoes)]

def atualizar_layout_no_json(codigo_layout, banco_descricao, palavras_selecionadas, tipo_arquivo, caminho_json='layouts.json'):
    layouts = carregar_base_layouts(caminho_json)
    layout_existente = next((l for l in layouts if l['codigo_layout'] == codigo_layout), None)
    if layout_existente:
        palavras_atuais = set(layout_existente.get('palavras_chave', []))
        palavras_novas = set(palavras_selecionadas)
        layout_existente['palavras_chave'] = sorted(list(palavras_atuais.union(palavras_novas)))
        layout_existente['banco'] = banco_descricao
        layout_existente['tipo_arquivo'] = tipo_arquivo
    else:
        novo_layout = {"codigo_layout": codigo_layout, "banco": banco_descricao, "tipo_arquivo": tipo_arquivo, "palavras_chave": sorted(palavras_selecionadas), "requer_todas_palavras": True}
        layouts.append(novo_layout)
    try:
        with open(caminho_json, 'w', encoding='utf-8') as f:
            json.dump(layouts, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Erro ao salvar o arquivo JSON: {e}")
        return False