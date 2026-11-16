"""
Conector do Bot do Telegram para o Periquito AI
Suporta mensagens de texto, áudios/mensagens de voz com Groq Whisper,
fotos/screenshots e interação inteligente tanto em chats privados quanto em grupos.
"""

import os
import io
import re
import asyncio
import logging
import requests
from typing import Optional
from telegram import Update
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters
)

from core.brain import PeriquitoBrain
from core.voice import clean_text_for_speech

logger = logging.getLogger("TelegramBot")


class TelegramBotClient:
    def __init__(self, brain: PeriquitoBrain, token: Optional[str] = None):
        self.brain = brain
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        chat = update.effective_chat
        user = update.effective_user
        raw_text = update.message.text.strip()
        is_private = (chat.type == "private")

        bot_username = context.bot.username or "PeriquitoIAbot"

        # Em grupos, só responde se for chamado pelo nome ou marcado
        if not is_private:
            is_reply_to_bot = (
                update.message.reply_to_message and
                update.message.reply_to_message.from_user and
                update.message.reply_to_message.from_user.id == context.bot.id
            )
            is_mentioned = f"@{bot_username.lower()}" in raw_text.lower()
            starts_name = raw_text.lower().startswith(("periquito", "robson", "!p ", "!periquito"))

            if not (is_reply_to_bot or is_mentioned or starts_name):
                return

        # Limpa menção do texto
        cleaned_text = re.sub(rf"@{bot_username}\b", "", raw_text, flags=re.IGNORECASE).strip()
        if cleaned_text.lower().startswith("periquito"):
            cleaned_text = cleaned_text[9:].strip(" ,:")
        elif cleaned_text.lower().startswith("robson"):
            cleaned_text = cleaned_text[6:].strip(" ,:")
        elif cleaned_text.lower().startswith("!p "):
            cleaned_text = cleaned_text[3:].strip()

        if not cleaned_text:
            cleaned_text = "e aí, periquito!"

        # Envia indicador de digitação
        await context.bot.send_chat_action(chat_id=chat.id, action="typing")

        # Processa a mensagem pelo cérebro unificado
        result = self.brain.process_message(
            text=cleaned_text,
            user_id=str(user.id),
            username=user.username or "",
            display_name=user.full_name or user.first_name,
            channel="telegram"
        )

        resp_text = result.get("text", "")
        file_path = result.get("file")

        # Se houver imagem (print da tela, mapa, etc.)
        if file_path and os.path.exists(file_path):
            with open(file_path, "rb") as f:
                await update.message.reply_photo(photo=f, caption=resp_text[:1024])
        else:
            if len(resp_text) > 4000:
                for i in range(0, len(resp_text), 4000):
                    await update.message.reply_text(resp_text[i:i + 4000])
            else:
                await update.message.reply_text(resp_text)

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Processa mensagens de voz recebidas no Telegram com transcrição via Whisper."""
        if not update.message or not update.message.voice:
            return

        chat = update.effective_chat
        user = update.effective_user
        is_private = (chat.type == "private")

        # Em grupos, só responde a voz se for em resposta ao bot
        if not is_private:
            is_reply_to_bot = (
                update.message.reply_to_message and
                update.message.reply_to_message.from_user and
                update.message.reply_to_message.from_user.id == context.bot.id
            )
            if not is_reply_to_bot:
                return

        await context.bot.send_chat_action(chat_id=chat.id, action="record_voice")

        try:
            # 1. Baixa o áudio da mensagem de voz
            voice_file = await context.bot.get_file(update.message.voice.file_id)
            voice_bytes = await voice_file.download_as_bytearray()

            # 2. Transcrição Ultra-Rápida com Groq Whisper
            groq_key = os.getenv("GROQ_API_KEY", "").strip()
            transcript = ""
            if groq_key:
                try:
                    res = requests.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {groq_key}"},
                        files={"file": ("voice.ogg", bytes(voice_bytes), "audio/ogg")},
                        data={"model": "whisper-large-v3-turbo", "language": "pt"},
                        timeout=10
                    )
                    if res.status_code == 200:
                        transcript = res.json().get("text", "").strip()
                except Exception as e:
                    logger.warning(f"Erro Whisper Telegram: {e}")

            if not transcript:
                await update.message.reply_text("🦜 Não consegui entender o áudio com clareza. Pode repetir?")
                return

            # 3. Processamento no Cérebro do Periquito
            result = self.brain.process_message(
                text=transcript,
                user_id=str(user.id),
                username=user.username or "",
                display_name=user.full_name or user.first_name,
                channel="telegram_voice"
            )

            resp_text = result.get("text", "")
            file_path = result.get("file")

            # 4. Síntese de Resposta em Áudio
            clean_speech = clean_text_for_speech(resp_text)
            audio_path = None
            if len(clean_speech) > 2:
                audio_path = await self.brain.voice.speak_to_file(clean_speech[:600])

            if audio_path and os.path.exists(audio_path):
                with open(audio_path, "rb") as af:
                    await update.message.reply_voice(voice=af, caption=resp_text[:1024])
            else:
                await update.message.reply_text(resp_text)

            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    await update.message.reply_photo(photo=f)

        except Exception as e:
            logger.error(f"Erro ao processar voz no Telegram: {e}")
            await update.message.reply_text(f"🦜 Erro ao processar áudio: {e}")

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        welcome = (
            f"🦜 Olá, {user.first_name}! Eu sou o **Periquito**, seu assistente de IA pessoal nativo.\n\n"
            f"Estou conectado ao seu computador e pronto para receber seus comandos de texto ou mensagens de voz!\n\n"
            f"💡 **Dicas de uso:**\n"
            f"• Mande mensagens de texto ou **áudio de voz** pelo celular.\n"
            f"• Peça *'status do pc'*, *'tira um print da tela'*, ou tire qualquer dúvida.\n"
            f"• Só o Play tem permissão para comandar o computador diretamente!"
        )
        await update.message.reply_text(welcome)

    def run(self):
        """Inicia o bot do Telegram com requisições resilientes."""
        if not self.token or self.token == "seu_token_do_telegram_aqui":
            print("Aviso: Token do Telegram não configurado no arquivo config/.env")
            return

        print("==================================================")
        print("🦜 INICIANDO BOT DO TELEGRAM DO PERIQUITO...")
        print("==================================================")

        # Configura cliente HTTPX com timeouts adequados
        req = HTTPXRequest(
            connection_pool_size=8,
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=30.0
        )

        app = ApplicationBuilder().token(self.token).request(req).build()
        app.add_handler(CommandHandler("start", self._start_command))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_message))
        app.add_handler(MessageHandler(filters.VOICE, self._handle_voice))
        app.run_polling(drop_pending_updates=True, bootstrap_retries=5)
