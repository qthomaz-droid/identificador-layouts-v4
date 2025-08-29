# Arquivo: bot_discord.py (VERSÃO COM LÓGICA DE MEDALHAS RESTAURADA)

import discord
import os
from dotenv import load_dotenv
import shutil
import subprocess
import datetime
import asyncio
import sys
from trello import TrelloClient

from identificador import identificar_layout, recarregar_modelo, extrair_texto_do_arquivo, retreinar_modelo_completo

# Carrega as variáveis de ambiente
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
TRELLO_API_KEY = os.getenv('TRELLO_API_KEY')
TRELLO_API_TOKEN = os.getenv('TRELLO_API_TOKEN')
TRELLO_BOARD_ID = os.getenv('TRELLO_BOARD_ID')

# ... (Configurações de pastas e intents do Discord não mudam) ...
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

    # ... (O código dos comandos !ajuda e trello-criar permanece o mesmo) ...
    if msg_lower == '!ajuda':
        embed = discord.Embed(
            title="🤖 Ajuda do Identificador de Layouts",
            description="Olá! Eu sou um bot treinado para identificar layouts de arquivos. Veja como me usar:",
            color=discord.Color.blue()
        )
        embed.add_field(name="📄 1. Para Identificar um Arquivo", value="Simplesmente **anexe um arquivo** (PDF, XLSX, TXT, etc.) a uma mensagem neste canal. Eu irei analisá-lo automaticamente.", inline=False)
        embed.add_field(name="🔍 Para Melhorar a Precisão (Opcional)", value="No campo de **comentário do anexo**, escreva o nome do **sistema** (ex: `Dominio`, `SCI`). Isso me ajuda a dar preferência aos layouts corretos.", inline=False)
        embed.add_field(name="🧠 2. Para me Ensinar o Layout Correto", value="Se eu errar a análise, você pode me treinar! Após eu dar uma resposta, basta enviar uma nova mensagem com o comando:\n`Treinar layout <código_correto>`\n*(Exemplo: `Treinar layout 123`)*", inline=False)
        embed.add_field(name="🔒 3. Arquivos com Senha", value="Se você enviar um arquivo PDF protegido, eu pedirei a senha no chat. Apenas responda com a senha e eu continuarei a análise.", inline=False)
        embed.add_field(name="✅ 4. Criar Tarefa no Trello", value="Para criar um card com o último arquivo enviado, use o comando:\n`trello-criar-sistema-relatorio-cliente-movimento-chamado-nomedalista`\n*(Dica: se o nome da lista tiver espaços, use `_`, ex: `Novos_Layouts`)*", inline=False)
        await message.channel.send(embed=embed)
        return
    if msg_lower.startswith('trello-criar'):
        await message.channel.send("Recebi o comando para criar um card no Trello. Processando...")
        try:
            partes = message.content.split('-')
            if len(partes) != 8:
                await message.channel.send("❌ Formato do comando incorreto. Use: `trello-criar-sistema-relatorio-cliente-movimento-chamado-nomedalista`")
                return
            _, _, nome_sistema, nome_relatorio, cliente, tipo_movimento, chamado, nome_lista = partes
            if message.channel.id not in arquivos_recentes:
                await message.channel.send("Não há nenhum arquivo recente para anexar. Envie o arquivo primeiro.")
                return
            trello = TrelloClient(api_key=TRELLO_API_KEY, token=TRELLO_API_TOKEN)
            board = trello.get_board(TRELLO_BOARD_ID)
            lista_destino_nome = nome_lista.replace('_', ' ')
            lista_trello = next((l for l in board.list_lists() if l.name.lower() == lista_destino_nome.lower()), None)
            if not lista_trello:
                await message.channel.send(f"❌ Não encontrei a lista '{lista_destino_nome}' no seu quadro do Trello.")
                return
            card_title = f"NOVO LAYOUT - {nome_sistema.upper()} - {nome_relatorio.upper()} - {cliente}"
            card_desc = (
                f"Tipo de movimento: {tipo_movimento.upper()}\n"
                f"Anexar arquivo - OK\n"
                f"Anexar mapeamento - OK\n"
                f"Nome do sistema: {nome_sistema.upper()}\n"
                f"Chamado: #{chamado}"
            )
            novo_card = lista_trello.add_card(name=card_title, desc=card_desc)
            info_arquivo = arquivos_recentes[message.channel.id]
            with open(info_arquivo['caminho'], 'rb') as f:
                novo_card.attach(name=info_arquivo['nome'], file=f)
            await message.channel.send(f"✅ **Card criado com sucesso na lista '{lista_trello.name}'!**\n{novo_card.url}")
        except Exception as e:
            await message.channel.send(f"❌ Ocorreu um erro ao criar o card no Trello. Detalhes: `{e}`")
        return
    if msg_lower.startswith('treinar layout'):
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
                sistema_alvo = message.content.strip()
                aviso_sistema = f" com preferência para **{sistema_alvo}**" if sistema_alvo else ""
                msg_processando = await message.channel.send(f"Analisando `{attachment.filename}`{aviso_sistema}...")
                
                caminho_arquivo_temp = os.path.join(PASTA_TEMP, attachment.filename)
                await attachment.save(caminho_arquivo_temp)
                
                arquivos_recentes[message.channel.id] = {'caminho': caminho_arquivo_temp, 'nome': attachment.filename}
                
                resultados = identificar_layout(caminho_arquivo_temp, sistema_alvo=sistema_alvo)
                
                if resultados == "SENHA_NECESSARIA":
                    # ... (lógica de senha para identificação)
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
                
                # --- LÓGICA DE FORMATAÇÃO DA RESPOSTA CORRIGIDA ---
                if not resultados or isinstance(resultados, dict):
                    erro = resultados.get('erro', '') if isinstance(resultados, dict) else ''
                    resposta = f"Não encontrei um layout compatível para `{attachment.filename}`. {erro}"
                elif resultados == "SENHA_INCORRETA":
                    resposta = f"❌ A senha fornecida para `{attachment.filename}` está incorreta."
                else:
                    # Título condicional restaurado
                    if resultados[0]['pontuacao'] >= 85:
                        resposta = f"**🏆 Análise de `{attachment.filename}` concluída!** Os layouts mais prováveis{aviso_sistema} são:\n\n"
                    else:
                        resposta = f"**🔎 Análise de `{attachment.filename}` concluída.** Estes são os resultados que mais se aproximam:\n\n"

                    # Ícones condicionais restaurados
                    for i, res in enumerate(resultados):
                        rank = i + 1
                        if res['pontuacao'] >= 85:
                            emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"**{rank}º**"
                        else:
                            emoji = f"**{rank}º**"
                        
                        resposta += f"{emoji} **Cód:** `{res['codigo_layout']}` | **Desc:** {res['banco']} | **Confiança:** {res['pontuacao']}%\n"
                    
                    resposta += "\nPara me ensinar o correto, use o comando: `Treinar layout <código>`"
                
                await message.channel.send(resposta)

client.run(DISCORD_TOKEN)