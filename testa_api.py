# Arquivo: testa_api.py (versão com POST body e headers)

import requests
import json

# --- Configurações ---
API_BASE_URL = "https://manager.conciliadorcontabil.com.br/api/"
API_SECRET = "4722c7e4c11f186a30af5d4be091b236"

def inspecionar_api_layouts():
    """Conecta na API, busca os dados dos layouts e os imprime na tela."""
    print("--- Iniciando teste de conexão com a API ---")
    
    try:
        # 1. Obter o token de acesso usando POST com o 'secret' no corpo
        print("1/3 - Solicitando token de acesso via POST...")
        
        # --- MUDANÇAS AQUI ---
        # A URL agora está limpa, sem o parâmetro
        token_url = f"{API_BASE_URL}get-token"
        
        # Os dados a serem enviados no corpo da requisição
        post_data = {'secret': API_SECRET}
        
        # Headers para simular um cliente mais comum
        headers = {'User-Agent': 'Meu-App-Python/1.0'}
        
        # Faz a requisição POST, passando os dados no parâmetro 'data'
        response_token = requests.post(token_url, data=post_data, headers=headers)
        # --- FIM DAS MUDANÇAS ---

        response_token.raise_for_status()
        
        # Agora vamos procurar o token dentro da chave "data"
        token_data = response_token.json().get("data", {})
        access_token = token_data.get("access_token")
        
        if not access_token:
            print("ERRO: 'access_token' não encontrado na resposta da API. Resposta recebida:")
            print(response_token.json())
            return

        print("Token obtido com sucesso!")

        # 2. Buscar a lista de layouts (requer o token no header)
        print("\n2/3 - Buscando a lista de layouts...")
        auth_headers = {
            'Authorization': f'Bearer {access_token}',
            'User-Agent': 'Meu-App-Python/1.0'
            }
        response_layouts = requests.get(f"{API_BASE_URL}layouts?orderby=id,asc", headers=auth_headers)
        response_layouts.raise_for_status()
        dados_layouts = response_layouts.json()

        print("Lista de layouts recebida!")
        print("\n--- AMOSTRA DA RESPOSTA DA API (PRIMEIRO LAYOUT DA LISTA) ---")
        
        # 3. Imprimir o primeiro resultado de forma legível
        if dados_layouts and isinstance(dados_layouts, list):
            primeiro_layout = dados_layouts[0]
            print(json.dumps(primeiro_layout, indent=4, ensure_ascii=False))
        else:
            print("A API não retornou uma lista de layouts ou a lista está vazia.")
        
        print("\n--- FIM DO TESTE ---")

    except requests.exceptions.RequestException as e:
        print(f"\nERRO DE CONEXÃO: Falha ao se comunicar com a API. Detalhes: {e}")
    except json.JSONDecodeError:
        print("\nERRO DE FORMATO: A resposta da API não parece ser um JSON válido.")

if __name__ == "__main__":
    inspecionar_api_layouts()