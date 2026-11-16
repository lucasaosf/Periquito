"""
Conector do Bot do Telegram para o Periquito AI
Suporta mensagens de texto, áudios e imagens vindas do celular do Lucas.
"""

import os
import asyncio
from typing import Optional
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

from core.brain import PeriquitoBrain

class TelegramBotClient:
    def __init__(self, brain: PeriquitoBrain, token: Optional[str] = None):
        self.brain = brain
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        user = update.effective_user
        text = update.message.text

        # Processa a mensagem pelo cérebro unificado
        result = self.brain.process_message(
            text=text,
            user_id=str(user.id),
            username=user.username or "",
            display_name=user.full_name,
            channel="telegram"
        )

        resp_text = result.get("text", "")
        file_path = result.get("file")

        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                await update.message.reply_photo(photo=f, caption=resp_text)
        else:
            await update.message.reply_text(resp_text)

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        welcome = (
            f"🦜 Olá, {user.first_name}! Eu sou o **Periquito**, seu assistente de IA pessoal nativo.\n\n"
            f"Estou conectado ao seu computador e pronto para receber seus comandos de texto ou áudio!"
        )
        await update.message.reply_text(welcome)

    def run(self):
        """Inicia o bot do Telegram."""
        if not self.token or self.token == "seu_token_do_telegram_aqui":
            print("Aviso: Token do Telegram não configurado no arquivo config/.env")
            return

        print("==================================================")
        print("🦜 INICIANDO BOT DO TELEGRAM DO PERIQUITO...")
        print("==================================================")
        app = ApplicationBuilder().token(self.token).build()
        app.add_handler(CommandHandler("start", self._start_command))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_message))
        app.run_polling()
