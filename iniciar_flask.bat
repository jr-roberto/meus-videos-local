@echo off
:: Navega até a pasta do seu projeto Flask
cd /d "C:/Users/rober/projetos/meus-videos-local"

:: Ativa o ambiente virtual (se você usar um)
call .venv/Scripts/activate

:: Executa o aplicativo Flask (substitua 'app.py' pelo nome do seu arquivo principal)
python wsgi.py