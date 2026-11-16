#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ponto de Entrada Principal do Periquito AI
Gerencia inicialização do cérebro, canais de mensageria e automações.
"""

import os
import sys
import argparse
import threading
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    # Tenta na raiz
    load_dotenv()

from core.brain import PeriquitoBrain
from channels.discord_bot import DiscordBotClient
from channels.telegram_bot import TelegramBotClient
from channels.console_cli import run_console

def main():
    parser = argparse.ArgumentParser(description="Periquito AI - Assistente Pessoal Nativo")
    parser.add_argument("--discord", action="store_true", help="Iniciar bot do Discord")
    parser.add_argument("--telegram", action="store_true", help="Iniciar bot do Telegram")
    parser.add_argument("--cli", action="store_true", help="Iniciar terminal interativo local")
    parser.add_argument("--all", action="store_true", help="Iniciar Discord e Telegram simultaneamente")

    args = parser.parse_args()
    brain = PeriquitoBrain()

    if args.discord:
        client = DiscordBotClient(brain)
        client.run()
    elif args.telegram:
        client = TelegramBotClient(brain)
        client.run()
    elif args.all:
        print("🦜 Iniciando todos os canais conectados do Periquito...")
        threads = []

        # Thread do Discord
        discord_client = DiscordBotClient(brain)
        t_disc = threading.Thread(target=discord_client.run, daemon=True)
        t_disc.start()
        threads.append(t_disc)

        # Thread do Telegram (roda na principal para polling do asyncio)
        telegram_client = TelegramBotClient(brain)
        telegram_client.run()
    else:
        # Padrão: Terminal local interativo
        run_console()

if __name__ == "__main__":
    main()
