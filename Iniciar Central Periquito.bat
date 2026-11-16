@echo off
title Periquito AI - Central de Comando
cls
echo ========================================================
echo        PARROT AI - CENTRAL DE COMANDO ^& MODO VOZ 3D
echo ========================================================
echo.
echo Iniciando servidor nativo do Periquito...
start /b python "%~dp0main.py" --cockpit
timeout /t 2 /nobreak >nul
echo Abrindo janela do Periquito...
start msedge.exe --app=http://localhost:7860 --window-size=1260,860 2>nul || start http://localhost:7860
exit
