@echo off
REM Define o título da janela do console para fácil identificação
title Bot Identificador de Layouts

REM Muda o diretório para a pasta raiz do seu projeto
REM O /d é importante para mudar de drive, se necessário (ex: do C: para o E:)
cd /d "E:\PROJETOS_DEV\identificador_semantico"

echo Ativando o ambiente virtual (venv)...
REM Ativa o ambiente virtual. O 'call' é crucial para que o script continue após a ativação.
call ".\venv\Scripts\activate.bat"

echo.
echo Iniciando o Bot do Discord...
echo Pressione Ctrl + C nesta janela para parar o bot.
echo.

REM Executa o script do bot usando o Python do ambiente ativado
python bot_discord.py

REM Pausa o script no final para que a janela não feche imediatamente se houver um erro
pause