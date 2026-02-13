from github import Github
import os
import streamlit as st
from dotenv import load_dotenv

# Tenta carregar do .env local, mas prioriza st.secrets em produção
load_dotenv()

def get_config(key):
    # Tenta pegar dos secrets do Streamlit, senão pega do ambiente
    try:
        return st.secrets["general"][key]
    except:
        return os.getenv(key)

def upload_files_to_github(file_paths, commit_message="Atualização automática de modelo via Streamlit"):
    """
    Envia uma lista de arquivos locais para o GitHub, atualizando-os.
    """
    token = get_config("GITHUB_TOKEN")
    repo_name = get_config("REPO_NAME")
    branch = get_config("BRANCH_NAME")

    if not token or not repo_name:
        print("ERRO GITHUB: Token ou Nome do Repositório não configurados.")
        return False

    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        
        print(f"Conectado ao repositório: {repo_name}")

        for file_path in file_paths:
            # Caminho relativo dentro do repositório
            # Removemos o caminho absoluto para ficar apenas o nome do arquivo ou pasta relativa
            file_name = os.path.basename(file_path)
            
            # Lendo o conteúdo do arquivo local (binário para suportar xlsx, joblib, etc)
            with open(file_path, "rb") as f:
                content = f.read()

            try:
                # Tenta pegar o arquivo existente para atualizá-lo (precisa do sha)
                contents = repo.get_contents(file_name, ref=branch)
                repo.update_file(contents.path, commit_message, content, contents.sha, branch=branch)
                print(f"Arquivo ATUALIZADO no GitHub: {file_name}")
            except Exception:
                # Se não existe, cria um novo
                repo.create_file(file_name, commit_message, content, branch=branch)
                print(f"Arquivo CRIADO no GitHub: {file_name}")

        return True

    except Exception as e:
        print(f"ERRO ao enviar para o GitHub: {e}")
        return False