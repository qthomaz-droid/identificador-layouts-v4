# Arquivo: testa_api.py (versão com parse correto da resposta JSON)

import requests
import json
import os
from dotenv import load_dotenv

# Carrega o segredo do arquivo .env para manter o código limpo
load_dotenv()
API_SECRET = os.getenv('API_SECRET', '4722c7e4c11f186a30af5d4be091b236') # Usa o valor padrão se .env não for encontrado
API_BASE_URL = "https://manager.conciliadorcontabil.com.br/api/"

def inspecionar_api_layouts():
    """Conecta na API, busca os dados dos layouts e os imprime na tela."""
    print("--- Iniciando teste de conexão com a API ---")
    
    try:
        # 1. Obter o token de acesso
        print("1/3 - Solicitando token de acesso via POST...")
        token_url = f"{API_BASE_URL}get-token"
        response_token = requests.post(token_url, data={'secret': API_SECRET})
        response_token.raise_for_status()
        
        token_data = response_token.json().get("data", {})
        access_token = token_data.get("access_token")
        
        if not access_token:
            print("ERRO: 'access_token' não encontrado na resposta. Resposta recebida:")
            print(response_token.json())
            return

        print("Token obtido com sucesso!")

        # 2. Buscar a lista de layouts
        print("\n2/3 - Buscando a lista de layouts...")
        auth_headers = {'Authorization': f'Bearer {access_token}'}
        response_layouts = requests.get(f"{API_BASE_URL}layouts?orderby=id,asc", headers=auth_headers)
        response_layouts.raise_for_status()
        
        # --- CORREÇÃO PRINCIPAL AQUI ---
        # A resposta completa é um dicionário, nós queremos a lista de dentro da chave "data"
        resposta_completa = response_layouts.json()
        dados_layouts = resposta_completa.get("data", []) # Pega a lista de dentro de "data"
        # --- FIM DA CORREÇÃO ---

        print("Lista de layouts recebida!")
        print("\n--- AMOSTRA DA RESPOSTA DA API (PRIMEIRO LAYOUT DA LISTA) ---")
        
        # 3. Imprimir o primeiro resultado de forma legível
        if dados_layouts and isinstance(dados_layouts, list):
            primeiro_layout = dados_layouts[0]
            print(json.dumps(primeiro_layout, indent=4, ensure_ascii=False))
        else:
            print("A chave 'data' na resposta da API não continha uma lista de layouts ou a lista estava vazia.")
        
        print("\n--- FIM DO TESTE ---")

    except requests.exceptions.RequestException as e:
        print(f"\nERRO DE CONEXÃO: {e}")
    except json.JSONDecodeError:
        print("\nERRO DE FORMATO: A resposta da API não é um JSON válido.")

if __name__ == "__main__":
    inspecionar_api_layouts()