# Identificador de Layouts com Machine Learning

Este projeto é um sistema inteligente projetado para identificar layouts de arquivos contábeis (como extratos bancários e relatórios) em diversos formatos. Ele utiliza um modelo de Machine Learning (TF-IDF) para analisar o conteúdo textual dos arquivos e determinar o layout correspondente com um score de confiança.

A aplicação possui duas interfaces principais: uma aplicação web interativa e um bot para Discord, além de um painel de administração para gerenciamento do modelo.

## 🚀 Principais Funcionalidades

* **Identificação Inteligente:** Usa um modelo TF-IDF e similaridade de cossenos para encontrar os layouts mais prováveis.
* **Suporte a Múltiplos Formatos:** Lê arquivos `.pdf`, `.xlsx`, `.xls`, `.txt`, `.csv` e `.xml`.
* **OCR Integrado:** Capaz de extrair texto de imagens dentro de PDFs (como logos de bancos) usando Tesseract.
* **Interfaces Flexíveis:**
    * Uma **Aplicação Web** (`Streamlit`) com painel de administração protegido por senha.
    * Um **Bot para Discord** (`Discord.py`) para identificação e treinamento interativo via chat.
* **Treinamento Contínuo:** O modelo pode ser aprimorado continuamente através de um treinador em massa e de comandos de feedback no bot.
* **Integrações:** Conecta-se a APIs externas para enriquecer os dados (prévia de imagens) e automatizar fluxos de trabalho (criação de cards no Trello).
* **Tratamento de Arquivos Protegidos:** Solicita senhas de forma interativa para arquivos PDF protegidos.

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python 3.9+
* **Machine Learning:** Scikit-learn (`TfidfVectorizer`)
* **Interface Web:** Streamlit
* **Bot:** Discord.py
* **Leitura de Arquivos:** PyMuPDF (fitz), Pandas, openpyxl
* **OCR:** Tesseract
* **APIs:** Requests, Py-Trello

## ⚙️ Instalação e Configuração

Siga estes passos para configurar o ambiente de desenvolvimento em uma nova máquina.

### 1. Pré-requisitos

* **Python:** Garanta que você tenha o Python 3.9 ou superior instalado.
* **Git:** [Instale o Git](https://git-scm.com/downloads) para clonar o repositório.
* **Tesseract OCR:** É **obrigatório** instalar o Tesseract no sistema operacional.
    * Baixe o instalador para Windows [aqui](https://github.com/UB-Mannheim/tesseract/wiki).
    * Durante a instalação, certifique-se de adicionar o suporte ao idioma **Português** e marcar a opção para **adicionar o Tesseract ao PATH do sistema**.

### 2. Clonar o Repositório

```bash
git clone [https://github.com/qthomaz-droid/identificador-layouts.git](https://github.com/qthomaz-droid/identificador-layouts.git)
cd identificador-layouts
```

### 3. Configurar o Ambiente Virtual

É crucial usar um ambiente virtual para isolar as dependências do projeto.

```bash
# Criar o ambiente
python -m venv venv

# Ativar o ambiente (Windows)
.\venv\Scripts\activate
```

### 4. Instalar as Dependências Python

Com o ambiente ativado, instale todas as bibliotecas necessárias com um único comando:
```bash
pip install -r requirements.txt
```

### 5. Configurar os Arquivos de Segredos (MUITO IMPORTANTE)

As chaves de API e senhas não são armazenadas no GitHub. Você deve criá-las localmente.

**A. Para o Bot do Discord e o Treinador:**
Crie um arquivo chamado `.env` na raiz do projeto e adicione suas chaves:
```env
# Arquivo: .env
DISCORD_TOKEN="seu_token_do_bot_discord"
TRELLO_API_KEY="sua_chave_api_trello"
TRELLO_API_TOKEN="seu_token_trello"
TRELLO_BOARD_ID="id_do_seu_quadro_trello"
API_SECRET="segredo_da_sua_api_manager"
```

**B. Para a Aplicação Web (Streamlit):**
Crie uma pasta `.streamlit` na raiz do projeto e, dentro dela, um arquivo `secrets.toml`:
```toml
# Arquivo: .streamlit/secrets.toml
[admin_credentials]
username = "admin"
password = "sua_senha_para_o_painel_admin"

api_secret = "segredo_da_sua_api_manager"

[trello_credentials]
api_key = "sua_chave_api_trello"
token = "seu_token_trello"
board_id = "id_do_seu_quadro_trello"
```

### 6. Configurar os Dados de Treinamento

* **Arquivo de Mapeamento:** Crie ou adicione o arquivo `mapeamento_layouts.xlsx` na raiz do projeto. Ele deve conter as colunas: `codigo_layout`, `descricao`, `Formato`.
* **Arquivos de Exemplo:** Crie a pasta `arquivos_de_treinamento` e adicione seus arquivos de exemplo nela. O nome de cada arquivo deve conter o `codigo_layout` correspondente.

### 7. Treinar o Modelo de Machine Learning

Antes de usar as aplicações, você precisa treinar o modelo pela primeira vez.
```bash
# (Opcional) Gerar o cache de texto primeiro (processo longo)
python treinador_em_massa.py --apenas-cache

# Gerar os metadados e treinar o modelo de ML
python treinador_em_massa.py
```

## ▶️ Como Usar

Com o ambiente configurado e o modelo treinado, você pode iniciar as aplicações.

* **Para rodar a Aplicação Web:**
    ```bash
    streamlit run app.py
    ```

* **Para rodar o Bot do Discord:**
    ```bash
    python bot_discord.py
    ```