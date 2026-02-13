import discord
import os
from dotenv import load_dotenv
import shutil
import subprocess
import datetime
import asyncio
import sys
import multiprocessing  # <--- Necessário para o executável
from trello import TrelloClient

# --- LÓGICA DE CARREGAMENTO EXPLÍCITO DE SEGREDOS ---
caminho_script = os.path.dirname(os.path.abspath(__file__))
caminho_env = os.path.join(caminho_script, '.env')
load_dotenv(dotenv_path=caminho_env)

# Importa as funções corrigidas (Lazy Loading)
from identificador import identificar_layout, recarregar_modelo, extrair_texto_do_arquivo, retreinar_modelo_completo

# Carrega as variáveis de ambiente
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
TRELLO_API_KEY = os.getenv('TRELLO_API_KEY')
TRELLO_API_TOKEN = os.getenv('TRELLO_API_TOKEN')
TRELLO_BOARD_ID = os.getenv('TRELLO_BOARD_ID')

# --- Configurações e Criação de Pastas ---
PASTA_TEMP = 'temp_files'
PASTA_TREINAMENTO = 'arquivos_de_treinamento'
PASTA_CACHE = 'cache_de_texto'
for pasta in [PASTA_TEMP, PASTA_TREINAMENTO, PASTA_CACHE]:
    if not os.path.exists(pasta):
        os.makedirs(pasta)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

EXTENSOES_SUPORTADAS = ['.pdf', '.xlsx', '.xls', '.txt', '.csv', '.xml', '.ofx']
arquivos_recentes = {}
treinamento_em_andamento = False

@client.event
async def on_ready():
    print(f'Bot está online como {client.user}')

@client.event
async def on_message(message):
    global treinamento_em_andamento
    if message.author == client.user: return

    msg_lower = message.content.lower()
    
    # --- Comandos de Ajuda ---
    if msg_lower == 'ajuda':
        embed = discord.Embed(
            title="🤖 Ajuda do Identificador de Layouts",
            description="Veja como me usar:",
            color=discord.Color.blue()
        )
        embed.add_field(name="📄 1. Identificar Arquivo", value=f"Anexe ({', '.join(EXTENSOES_SUPORTADAS).upper()}).", inline=False)
        embed.add_field(name="🔍 Precisão", value="Escreva o **sistema** (ex: `Dominio`) no comentário do anexo.", inline=False)
        embed.add_field(name="⚠️ Alerta OCR", value="Eu aviso se o PDF for apenas imagem.", inline=False)
        await message.channel.send(embed=embed)
        return

    # --- Comando de Treinamento ---
    elif msg_lower.startswith('treinar layout'):
        if treinamento_em_andamento:
            await message.channel.send("Já existe um treinamento em andamento.")
            return
        try:
            codigo_correto = message.content.split()[2]
            if message.channel.id not in arquivos_recentes:
                await message.channel.send("❌ Nenhum arquivo recente para treinar.")
                return
            
            info = arquivos_recentes[message.channel.id]
            texto_teste, _ = extrair_texto_do_arquivo(info['caminho'], senha_manual=info.get('senha_fornecida'))
            
            if not texto_teste or texto_teste in ["SENHA_NECESSARIA", "SENHA_INCORRETA"]:
                await message.channel.send("❌ Conteúdo ilegível ou protegido.")
                return

            treinamento_em_andamento = True
            await message.channel.send(f"⚙️ Aprimorando layout `{codigo_correto}`...")
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            novo_nome = f"{codigo_correto}_confirmed_{timestamp}_{info['nome']}"
            shutil.copy(info['caminho'], os.path.join(PASTA_TREINAMENTO, novo_nome))
            
            with open(os.path.join(PASTA_CACHE, novo_nome + '.txt'), 'w', encoding='utf-8') as f:
                f.write(texto_teste)

            proc = await asyncio.create_subprocess_exec(sys.executable, 'treinador_em_massa.py', '--retreinar-rapido')
            await proc.communicate()
            recarregar_modelo()
            await message.channel.send("🎉 **Modelo atualizado!**")
        finally:
            treinamento_em_andamento = False
        return

    # --- LÓGICA DE ANÁLISE ---
    if message.attachments:
        for attachment in message.attachments:
            if os.path.splitext(attachment.filename)[1].lower() in EXTENSOES_SUPORTADAS:
                sistema_alvo = message.content.strip()
                msg_wait = await message.channel.send(f"⏳ Analisando `{attachment.filename}`...")
                
                caminho = os.path.join(PASTA_TEMP, attachment.filename)
                await attachment.save(caminho)
                arquivos_recentes[message.channel.id] = {'caminho': caminho, 'nome': attachment.filename}
                
                resultados = identificar_layout(caminho, sistema_alvo=sistema_alvo)
                
                if resultados == "SENHA_NECESSARIA":
                    await msg_wait.edit(content=f"🔒 `{attachment.filename}` tem senha. Responda aqui:")
                    try:
                        senha_msg = await client.wait_for('message', timeout=60.0, check=lambda m: m.author == message.author)
                        resultados = identificar_layout(caminho, sistema_alvo=sistema_alvo, senha_manual=senha_msg.content)
                        arquivos_recentes[message.channel.id]['senha_fornecida'] = senha_msg.content
                    except asyncio.TimeoutError:
                        await msg_wait.edit(content="❌ Timeout."); return
                
                await msg_wait.delete()

                if not resultados or isinstance(resultados, dict):
                    await message.channel.send("❌ Layout não identificado.")
                else:
                    for res in resultados:
                        cor = discord.Color.green() if res['compatibilidade'] == 'Alta' else discord.Color.orange()
                        embed = discord.Embed(title=f"{res['banco']}", color=cor)
                        embed.add_field(name="Código", value=f"`{res['codigo_layout']}`", inline=True)
                        embed.add_field(name="Confiança", value=f"**{res['compatibilidade']}**", inline=True)
                        
                        if res.get('foi_ocr'):
                            embed.description = "⚠️ **PDF IMAGEM:** Não pode ser importado diretamente. Peça o arquivo digital original."
                            embed.color = discord.Color.red()

                        if res.get("url_previa"): embed.set_thumbnail(url=res['url_previa'])
                        await message.channel.send(embed=embed)

# --- BLOCO DE PROTEÇÃO CONTRA LOOP (EXE) ---
if __name__ == '__main__':
    # Esta linha impede que o bot abra 1000 janelas ao iniciar como executável
    multiprocessing.freeze_support()
    
    if not DISCORD_TOKEN:
        print("ERRO: DISCORD_TOKEN não encontrado no arquivo .env")
        sys.exit(1)
        
    client.run(DISCORD_TOKEN)