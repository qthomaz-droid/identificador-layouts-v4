# Arquivo: bot_discord.py

import discord
import os
from dotenv import load_dotenv
import shutil
import subprocess
import datetime
import asyncio

from identificador import identificar_layout, recarregar_modelo, extrair_texto_do_arquivo

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

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
    if msg_lower.startswith('treinar layout'):
        if treinamento_em_andamento:
            await message.channel.send("Já existe um treinamento em andamento. Por favor, aguarde.")
            return

        try:
            partes = message.content.split()
            if len(partes) < 3: raise ValueError("Formato inválido")
            codigo_correto = partes[2]
        except (ValueError, IndexError):
            await message.channel.send("Formato do comando incorreto. Use: `Treinar layout <código>`")
            return
            
        if message.channel.id not in arquivos_recentes:
            await message.channel.send("Não há nenhum arquivo recente neste canal para eu aprender. Envie um arquivo primeiro.")
            return

        info_arquivo = arquivos_recentes[message.channel.id]
        caminho_original, nome_original = info_arquivo['caminho'], info_arquivo['nome']
        
        texto_teste = extrair_texto_do_arquivo(caminho_original)
        
        if texto_teste == "SENHA_NECESSARIA":
            await message.channel.send(f"🔒 Para usar o arquivo `{nome_original}` no treinamento, preciso da senha. Por favor, **envie a senha em uma nova mensagem**.")
            def check(m):
                return m.author == message.author and m.channel == message.channel
            try:
                senha_msg = await client.wait_for('message', timeout=120.0, check=check)
                senha_manual = senha_msg.content
                texto_teste = extrair_texto_do_arquivo(caminho_original, senha_manual=senha_manual)
                if texto_teste == "SENHA_INCORRETA":
                    await message.channel.send("❌ Senha incorreta. Treinamento cancelado.")
                    return
            except asyncio.TimeoutError:
                await message.channel.send("Tempo esgotado. Treinamento cancelado.")
                return
        
        if not texto_teste:
            await message.channel.send(f"Não consegui ler o conteúdo do arquivo `{nome_original}`. Treinamento cancelado.")
            return

        treinamento_em_andamento = True
        try:
            await message.channel.send(f"✅ Arquivo `{nome_original}` legível! Vou usá-lo para aprimorar o layout `{codigo_correto}`.")
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            novo_nome = f"{codigo_correto}_{timestamp}_{nome_original}"
            caminho_destino = os.path.join("arquivos_de_treinamento", novo_nome)
            shutil.copy(caminho_original, caminho_destino)
            await message.channel.send(f"Arquivo salvo para treinamento como `{novo_nome}`.")
            await message.channel.send("⚙️ Iniciando o retreinamento do modelo... Eu avisarei quando terminar.")
            
            processo = await asyncio.create_subprocess_exec('python', 'treinador_em_massa.py', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = await processo.communicate()

            if processo.returncode == 0:
                recarregar_modelo()
                await message.channel.send("🎉 **Treinamento concluído!** Meu cérebro foi atualizado.")
            else:
                await message.channel.send(f"❌ Erro durante o retreinamento: ```{stderr.decode()}```")
        finally:
            treinamento_em_andamento = False
        return

    if message.attachments:
        for attachment in message.attachments:
            file_extension = os.path.splitext(attachment.filename)[1].lower()
            if file_extension in EXTENSOES_SUPORTADAS:
                
                sistema_alvo = message.content.strip()
                aviso_sistema = f" com preferência para o sistema **{sistema_alvo}**" if sistema_alvo else ""
                msg_processando = await message.channel.send(f"Olá, {message.author.mention}! Analisando `{attachment.filename}`{aviso_sistema}...")
                
                caminho_arquivo_temp = os.path.join("temp_files", attachment.filename)
                await attachment.save(caminho_arquivo_temp)
                
                arquivos_recentes[message.channel.id] = {'caminho': caminho_arquivo_temp, 'nome': attachment.filename}
                
                resultados = identificar_layout(caminho_arquivo_temp, sistema_alvo=sistema_alvo)
                
                if resultados == "SENHA_NECESSARIA":
                    await msg_processando.edit(content=f"🔒 {message.author.mention}, o arquivo `{attachment.filename}` está protegido. Envie a senha para continuar.")

                    def check(m):
                        return m.author == message.author and m.channel == message.channel

                    try:
                        senha_msg = await client.wait_for('message', timeout=120.0, check=check)
                        senha_manual = senha_msg.content
                        
                        await msg_processando.edit(content=f"Senha recebida. Processando `{attachment.filename}` novamente...")
                        resultados = identificar_layout(caminho_arquivo_temp, sistema_alvo=sistema_alvo, senha_manual=senha_manual)

                    except asyncio.TimeoutError:
                        await msg_processando.edit(content=f"Tempo esgotado. Tente novamente.")
                        return

                if not resultados or isinstance(resultados, dict):
                    erro = resultados.get('erro', '') if isinstance(resultados, dict) else ''
                    resposta = f"Não encontrei um layout compatível para `{attachment.filename}`. {erro}"
                elif resultados == "SENHA_INCORRETA":
                    resposta = f"❌ A senha fornecida para `{attachment.filename}` está incorreta."
                else:
                    resposta = f"**Análise de `{attachment.filename}` concluída!** Os layouts mais prováveis{aviso_sistema} são:\n\n"
                    for i, res in enumerate(resultados):
                        emoji = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}º**"
                        resposta += f"{emoji} **Código:** `{res['codigo_layout']}` | **Descrição:** {res['banco']} | **Confiança:** {res['pontuacao']}%\n"
                    resposta += "\nPara me ensinar o correto, use o comando: `Treinar layout <código>`"
                
                await message.channel.send(resposta)

client.run(TOKEN)