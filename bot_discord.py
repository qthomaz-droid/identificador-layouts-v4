# Arquivo: bot_discord.py (VERSÃO COM COMANDO DE AJUDA)

import discord
import os
from dotenv import load_dotenv
import shutil
import subprocess
import datetime
import asyncio
import sys

from identificador import identificar_layout, recarregar_modelo, extrair_texto_do_arquivo, retreinar_modelo_completo

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

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
    
    # --- NOVA FUNCIONALIDADE: COMANDO DE AJUDA ---
    if msg_lower == '!ajuda':
        # Cria um "Embed", que é um bloco de mensagem formatado
        embed = discord.Embed(
            title="🤖 Ajuda do Identificador de Layouts",
            description="Olá! Eu sou um bot treinado para identificar layouts de arquivos. Veja como me usar:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📄 1. Para Identificar um Arquivo",
            value="Simplesmente **anexe um arquivo** (PDF, XLSX, TXT, etc.) a uma mensagem neste canal. Eu irei analisá-lo automaticamente.",
            inline=False
        )
        embed.add_field(
            name="🔍 Para Melhorar a Precisão (Opcional)",
            value="No campo de **comentário do anexo**, escreva o nome do **sistema** (ex: `Dominio`, `SCI`). Isso me ajuda a dar preferência aos layouts corretos.",
            inline=False
        )
        embed.add_field(
            name="🧠 2. Para me Ensinar o Layout Correto",
            value="Se eu errar a análise, você pode me treinar! Após eu dar uma resposta, basta enviar uma nova mensagem com o comando:\n`Treinar layout <código_correto>`\n*(Exemplo: `Treinar layout 123`)*",
            inline=False
        )
        embed.add_field(
            name="🔒 3. Arquivos com Senha",
            value="Se você enviar um arquivo PDF protegido, eu pedirei a senha no chat. Apenas responda com a senha e eu continuarei a análise.",
            inline=False
        )
        
        await message.channel.send(embed=embed)
        return # Para a execução aqui para não processar outros comandos
    
    # --- O resto do código permanece o mesmo ---
    if msg_lower.startswith('treinar layout'):
        # ... (código do comando de treinamento)
        if treinamento_em_andamento:
            await message.channel.send("Já existe um treinamento em andamento. Por favor, aguarde.")
            return
        try:
            codigo_correto = message.content.split()[2]
        except IndexError:
            await message.channel.send("Formato incorreto. Use: `Treinar layout <código>`")
            return
        if message.channel.id not in arquivos_recentes:
            await message.channel.send("Nenhum arquivo recente para treinar. Envie um arquivo primeiro.")
            return
        info_arquivo = arquivos_recentes[message.channel.id]
        caminho_original, nome_original = info_arquivo['caminho'], info_arquivo['nome']
        texto_teste = extrair_texto_do_arquivo(caminho_original)
        senha_manual_fornecida = None
        if texto_teste == "SENHA_NECESSARIA":
            await message.channel.send(f"🔒 Para usar `{nome_original}` no treinamento, preciso da senha. Envie a senha.")
            def check(m):
                return m.author == message.author and m.channel == message.channel
            try:
                senha_msg = await client.wait_for('message', timeout=120.0, check=check)
                senha_manual_fornecida = senha_msg.content
                texto_teste = extrair_texto_do_arquivo(caminho_original, senha_manual=senha_manual_fornecida)
                if texto_teste == "SENHA_INCORRETA":
                    await message.channel.send("❌ Senha incorreta. Treinamento cancelado.")
                    return
            except asyncio.TimeoutError:
                await message.channel.send("Tempo esgotado. Treinamento cancelado.")
                return
        if not texto_teste:
            await message.channel.send(f"Não consegui ler o conteúdo de `{nome_original}`. Treinamento cancelado.")
            return
        treinamento_em_andamento = True
        try:
            await message.channel.send(f"✅ Arquivo legível! Vou usá-lo para aprimorar o layout `{codigo_correto}`.")
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            novo_nome_base = f"{codigo_correto}_{timestamp}_{nome_original}"
            caminho_destino = os.path.join(PASTA_TREINAMENTO, novo_nome_base)
            shutil.copy(caminho_original, caminho_destino)
            caminho_cache = os.path.join(PASTA_CACHE, novo_nome_base + '.txt')
            with open(caminho_cache, 'w', encoding='utf-8') as f:
                f.write(texto_teste)
            await message.channel.send(f"Arquivo e texto salvos para o treinamento.")
            await message.channel.send("⚙️ Iniciando o retreinamento completo do modelo...")
            loop = asyncio.get_event_loop()
            sucesso = await loop.run_in_executor(None, retreinar_modelo_completo)
            if sucesso:
                recarregar_modelo()
                await message.channel.send("🎉 **Treinamento concluído!** Meu cérebro foi atualizado.")
            else:
                await message.channel.send("❌ Ocorreu um erro durante o retreinamento.")
        finally:
            treinamento_em_andamento = False
        return

    if message.attachments:
        for attachment in message.attachments:
            if os.path.splitext(attachment.filename)[1].lower() in EXTENSOES_SUPORTADAS:
                # ... (código de análise de arquivo)
                sistema_alvo = message.content.strip()
                aviso_sistema = f" com preferência para **{sistema_alvo}**" if sistema_alvo else ""
                msg_processando = await message.channel.send(f"Analisando `{attachment.filename}`{aviso_sistema}...")
                caminho_arquivo_temp = os.path.join(PASTA_TEMP, attachment.filename)
                await attachment.save(caminho_arquivo_temp)
                arquivos_recentes[message.channel.id] = {'caminho': caminho_arquivo_temp, 'nome': attachment.filename}
                resultados = identificar_layout(caminho_arquivo_temp, sistema_alvo=sistema_alvo)
                if resultados == "SENHA_NECESSARIA":
                    await msg_processando.edit(content=f"🔒 `{attachment.filename}` está protegido. Por favor, envie a senha.")
                    def check(m):
                        return m.author == message.author and m.channel == message.channel
                    try:
                        senha_msg = await client.wait_for('message', timeout=120.0, check=check)
                        senha_manual = senha_msg.content
                        arquivos_recentes[message.channel.id]['senha_fornecida'] = senha_manual
                        await msg_processando.edit(content=f"Senha recebida. Processando novamente...")
                        resultados = identificar_layout(caminho_arquivo_temp, sistema_alvo=sistema_alvo, senha_manual=senha_manual)
                    except asyncio.TimeoutError:
                        await msg_processando.edit(content="Tempo esgotado.")
                        return
                if not resultados or isinstance(resultados, dict):
                    resposta = f"Não encontrei um layout compatível para `{attachment.filename}`."
                elif resultados == "SENHA_INCORRETA":
                    resposta = f"❌ A senha fornecida está incorreta."
                else:
                    resposta = f"**Análise de `{attachment.filename}` concluída!**\n\n"
                    for i, res in enumerate(resultados):
                        emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}º**"
                        resposta += f"{emoji} **Cód:** `{res['codigo_layout']}` | **Desc:** {res['banco']} | **Confiança:** {res['pontuacao']}%\n"
                    resposta += "\nPara me ensinar, use: `Treinar layout <código>`"
                await message.channel.send(resposta)

client.run(TOKEN)