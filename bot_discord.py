# Arquivo: bot_discord.py

import os
import sys
from dotenv import load_dotenv

caminho_script = os.path.dirname(os.path.abspath(__file__))
caminho_env = os.path.join(caminho_script, '.env')
load_dotenv(dotenv_path=caminho_env)

from identificador import identificar_layout, recarregar_modelo, extrair_texto_do_arquivo, retreinar_modelo_completo
import discord
import shutil
import subprocess
import datetime
import asyncio
from trello import TrelloClient

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
TRELLO_API_KEY = os.getenv('TRELLO_API_KEY')
TRELLO_API_TOKEN = os.getenv('TRELLO_API_TOKEN')
TRELLO_BOARD_ID = os.getenv('TRELLO_BOARD_ID')

PASTA_TEMP = 'temp_files'
PASTA_TREINAMENTO = 'arquivos_de_treinamento'
PASTA_CACHE = 'cache_de_texto'
for pasta in [PASTA_TEMP, PASTA_TREINAMENTO, PASTA_CACHE]:
    if not os.path.exists(pasta):
        os.makedirs(pasta)
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
EXTENSOES_SUPORTADAS = ['.pdf', '.xlsx', '.xls', '.txt', '.csv', '.xml']
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
    
    # ... (os comandos de ajuda e trello não mudam)
    
    if message.attachments:
        for attachment in message.attachments:
            if os.path.splitext(attachment.filename)[1].lower() in EXTENSOES_SUPORTADAS:
                sistema_alvo = message.content.strip()
                aviso_sistema = f" com preferência para **{sistema_alvo}**" if sistema_alvo else ""
                msg_processando = await message.channel.send(f"Analisando `{attachment.filename}`{aviso_sistema}...")
                caminho_arquivo_temp = os.path.join(PASTA_TEMP, attachment.filename)
                await attachment.save(caminho_arquivo_temp)
                arquivos_recentes[message.channel.id] = {'caminho': caminho_arquivo_temp, 'nome': attachment.filename}
                resultados = identificar_layout(caminho_arquivo_temp, sistema_alvo=sistema_alvo)
                if resultados == "SENHA_NECESSARIA":
                    await msg_processando.edit(content=f"🔒 `{attachment.filename}` está protegido. Por favor, envie a senha.")
                    def check(m): return m.author == message.author and m.channel == message.channel
                    try:
                        senha_msg = await client.wait_for('message', timeout=120.0, check=check)
                        senha_manual = senha_msg.content
                        arquivos_recentes[message.channel.id]['senha_fornecida'] = senha_manual
                        await msg_processando.edit(content=f"Senha recebida. Processando novamente...")
                        resultados = identificar_layout(caminho_arquivo_temp, sistema_alvo=sistema_alvo, senha_manual=senha_manual)
                    except asyncio.TimeoutError:
                        await msg_processando.edit(content="Tempo esgotado."); return
                
                await msg_processando.delete()

                if not resultados or isinstance(resultados, dict):
                    await message.channel.send(f"Não encontrei um layout compatível para `{attachment.filename}`.")
                elif resultados == "SENHA_INCORRETA":
                    await message.channel.send(f"❌ A senha para `{attachment.filename}` está incorreta.")
                else:
                    confianca_primeiro = resultados[0]['confianca_label']
                    if resultados and isinstance(resultados, list) and len(resultados) > 0 and confianca_primeiro == 'Alta':
                        titulo_resposta = f"**🏆 Análise de `{attachment.filename}` concluída!**"
                    else:
                        titulo_resposta = f"**🔎 Análise de `{attachment.filename}` concluída.** Estes são os resultados:"
                    await message.channel.send(titulo_resposta)
                    for i, res in enumerate(resultados):
                        rank = i + 1
                        confianca = res['confianca_label']
                        if confianca == 'Alta':
                            emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"**{rank}º**"
                        else:
                            emoji = f"**{rank}º**"
                        embed = discord.Embed(title=f"{emoji} {res['banco']}", color=discord.Color.green() if confianca == 'Alta' else discord.Color.light_gray())
                        embed.add_field(name="Código", value=f"`{res['codigo_layout']}`", inline=True)
                        embed.add_field(name="Confiança", value=f"**{confianca}**", inline=True)
                        if res.get("url_previa"):
                            embed.set_thumbnail(url=res['url_previa'])
                        await message.channel.send(embed=embed)
                    await message.channel.send("\nPara me ensinar, use: `Treinar layout <código>`")
client.run(DISCORD_TOKEN)