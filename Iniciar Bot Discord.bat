@echo off
title Periquito AI - Bot do Discord
cls
echo ==================================================
echo    CONECTANDO PERIQUITO AO DISCORD...
echo ==================================================
echo.
python "%~dp0main.py" --discord
pause
