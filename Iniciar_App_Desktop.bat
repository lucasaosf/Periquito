@echo off
title Periquito AI - Central de Comando
cd /d "%~dp0"

:: Verifica se a porta 7860 ja esta ativa
netstat -ano | findstr :7860 >nul 2>&1
if %errorlevel% neq 0 (
    echo Iniciando o Periquito AI em segundo plano...
    start "Periquito Core" /min python main.py
    timeout /t 2 /nobreak >nul
)

:: Inicia a interface como Software Nativo (Modo App do Edge sem abas e sem barra de URL)
start msedge.exe --app="http://127.0.0.1:7860" --window-size=1260,840 --user-data-dir="%LOCALAPPDATA%\PeriquitoAI\Profile"
exit
