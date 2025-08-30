# Arquivo: teste_bot.py

import discord
import os
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# A mesma lista de resultados FALSOS
resultados_falsos = [
    {
        "codigo_layout": "123",
        "banco": "Layout de Alta Confiança (Exemplo 1)",
        "pontuacao": 95.0,
        "url_previa": "https://manager.conciliadorcontabil.com.br/uploads/3/2023-04/3.jpg" # URL real da sua API
    },
    {
        "codigo_layout": "456",
        "banco": "Layout de Média Confiança (Exemplo 2)",
        "pontuacao": 75.0,
        "url_previa": "https://placehold.co/600x400/EEE/31343C/png?text=Exemplo2" # URL de placeholder
    },
    {
        "codigo_layout": "789",
        "banco": "Layout Sem Imagem (Exemplo 3)",
        "pontuacao": 90.0,
        "url_previa": None
    }
]

@client.event
async def on_ready():
    print(f'Bot de teste online como {client.user}')
    print("Digite '!teste' em qualquer canal para ver os resultados.")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.lower() == '!teste':
        await message.channel.send("**Executando teste de exibição de imagens...**")
        
        # Usamos exatamente a mesma lógica de exibição do seu bot_discord.py
        for i, res in enumerate(resultados_falsos):
            rank = i + 1
            if res['pontuacao'] >= 85:
                emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"**{rank}º**"
            else:
                emoji = f"**{rank}º**"
            
            embed = discord.Embed(
                title=f"{emoji} {res['banco']}",
                color=discord.Color.green() if res['pontuacao'] >= 85 else discord.Color.light_gray()
            )
            embed.add_field(name="Código", value=f"`{res['codigo_layout']}`", inline=True)
            embed.add_field(name="Confiança", value=f"**{round(res['pontuacao'])}%**", inline=True)
            
            if res.get("url_previa"):
                embed.set_thumbnail(url=res['url_previa'])
            
            await message.channel.send(embed=embed)
        
        await message.channel.send("--- Teste Concluído ---")

client.run(DISCORD_TOKEN)