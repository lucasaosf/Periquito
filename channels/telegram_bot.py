"""
Canal Oficial do Telegram do Periquito AI
- Canal de Comando Administrativo Pessoal (Apenas TELEGRAM_ADMIN_ID)
- Suporte a Texto, Áudio (Faster-Whisper) e Documentos (workspace/inbox/)
- Worker Assíncrono para Botões Interativos HITL e Envio de Arquivos PC -> Celular
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from config import config, INBOX_DIR
from core.brain_bridge import PeriquitoBrain
from core.ipc_store import (
    get_pending_hitl,
    resolve_hitl,
    get_pending_outbox_files,
    mark_outbox_file_sent,
    get_pending_notifications,
    mark_notification_delivered
)
from core.voice import transcribe_audio, synthesize_speech
from core.text_utils import slice_message

logger = logging.getLogger("TelegramChannel")


def _is_admin(user_id: int) -> bool:
    """Valida correspondência estrita com o ID numérico do administrador."""
    return config.telegram.admin_id != 0 and user_id == config.telegram.admin_id


class TelegramChannel:
    def __init__(self, brain: PeriquitoBrain):
        self.brain = brain
        self.app: Optional[Application] = None
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self):
        token = config.telegram.bot_token
        if not token or config.telegram.admin_id == 0:
            logger.warning("[Telegram] Token ou Admin ID não configurados no .env. Canal desativado.")
            return

        self.app = Application.builder().token(token).build()

        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
        self.app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self._handle_voice))
        self.app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, self._handle_file))

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        self._worker_task = asyncio.create_task(self._ipc_worker_loop())
        logger.info(f"🦜 [Telegram] Bot ativo no modo seguro (Admin ID: {config.telegram.admin_id})")

    async def stop(self):
        if self._worker_task:
            self._worker_task.cancel()
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user or not _is_admin(update.effective_user.id):
            return  # Ignora silenciosamente não-administradores
        await update.message.reply_text("🦜 Olá Lucas! O Periquito está pronto e conectado ao seu computador.")

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user or not _is_admin(update.effective_user.id):
            return

        user_text = update.message.text
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        response = await self.brain.ask(user_text, user_name="Lucas", channel="telegram")

        for chunk in slice_message(response, max_length=4000):
            await update.message.reply_text(chunk)

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user or not _is_admin(update.effective_user.id):
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")

        # Baixa arquivo de áudio no inbox
        voice_obj = update.message.voice or update.message.audio
        file = await context.bot.get_file(voice_obj.file_id)
        
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        local_audio_path = INBOX_DIR / f"voice_{update.message.message_id}.ogg"
        await file.download_to_drive(str(local_audio_path))

        # Transcrição via Faster-Whisper
        try:
            transcription = await transcribe_audio(local_audio_path)
        except Exception as e:
            transcription = ""
            logger.error(f"Erro na transcrição: {e}")

        if not transcription:
            await update.message.reply_text("⚠️ Não consegui compreender o áudio.")
            return

        await update.message.reply_text(f"🎤 *Você disse:* \"{transcription}\"", parse_mode="Markdown")

        response = await self.brain.ask(transcription, user_name="Lucas", channel="telegram")

        # Responde com texto e também sintetiza áudio de retorno
        for chunk in slice_message(response, max_length=4000):
            await update.message.reply_text(chunk)

        try:
            tts_path = await synthesize_speech(response[:400])
            if tts_path.exists():
                with open(tts_path, "rb") as f_voice:
                    await update.message.reply_voice(voice=f_voice)
        except Exception as e:
            logger.warning(f"Falha ao enviar resposta em voz: {e}")

    async def _handle_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user or not _is_admin(update.effective_user.id):
            return

        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        doc = update.message.document
        photo = update.message.photo

        if doc:
            f = await context.bot.get_file(doc.file_id)
            dest = INBOX_DIR / doc.file_name
            await f.download_to_drive(str(dest))
            caption = update.message.caption or f"Recebi o arquivo {doc.file_name}"
            prompt = f"{caption}. O arquivo foi salvo em: {dest}"
        elif photo:
            f = await context.bot.get_file(photo[-1].file_id)
            dest = INBOX_DIR / f"foto_{update.message.message_id}.jpg"
            await f.download_to_drive(str(dest))
            caption = update.message.caption or "Recebi esta foto"
            prompt = f"{caption}. A imagem foi salva em: {dest}"
        else:
            return

        await update.message.reply_text(f"📥 Arquivo salvo no inbox do PC: `{dest.name}`", parse_mode="Markdown")
        res = await self.brain.ask(prompt, user_name="Lucas", channel="telegram")
        for chunk in slice_message(res, max_length=4000):
            await update.message.reply_text(chunk)

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gerencia cliques nos botões de aprovação/recusa HITL."""
        query = update.callback_query
        if not query or not query.from_user or not _is_admin(query.from_user.id):
            await query.answer("Não autorizado.", show_alert=True)
            return

        data = query.data
        if data.startswith("approve_"):
            req_id = int(data.split("_")[1])
            resolve_hitl(req_id, approved=True)
            await query.answer("Ação APROVADA com sucesso!")
            await query.edit_message_text(f"{query.message.text}\n\n✅ **STATUS: APROVADO PELO LUCAS**", parse_mode="Markdown")
        elif data.startswith("reject_"):
            req_id = int(data.split("_")[1])
            resolve_hitl(req_id, approved=False)
            await query.answer("Ação RECUSADA.")
            await query.edit_message_text(f"{query.message.text}\n\n❌ **STATUS: RECUSADO PELO LUCAS**", parse_mode="Markdown")

    async def _ipc_worker_loop(self):
        """Worker contínuo vigiando SQLite WAL para HITL, Outbox e Notificações."""
        sent_hitl_ids = set()

        while True:
            try:
                # 1. Verifica solicitações de HITL
                pending_hitl = get_pending_hitl()
                for req in pending_hitl:
                    r_id = req["id"]
                    if r_id not in sent_hitl_ids:
                        sent_hitl_ids.add(r_id)
                        kb = [
                            [
                                InlineKeyboardButton("✅ Aprovar", callback_data=f"approve_{r_id}"),
                                InlineKeyboardButton("❌ Recusar", callback_data=f"reject_{r_id}")
                            ]
                        ]
                        text = (
                            f"⚠️ **[CONFIRMAÇÃO DE SEGURANÇA HITL]**\n\n"
                            f"**Ação:** `{req['action_type']}`\n"
                            f"**Detalhes:**\n{req['description']}\n\n"
                            f"⏳ _Aguardando sua decisão por até 60 segundos..._"
                        )
                        await self.app.bot.send_message(
                            chat_id=config.telegram.admin_id,
                            text=text,
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(kb)
                        )

                # 2. Verifica arquivos na fila de outbox (PC -> Celular)
                pending_files = get_pending_outbox_files()
                for pf in pending_files:
                    f_id = pf["id"]
                    f_path = Path(pf["file_path"])
                    if f_path.exists():
                        try:
                            with open(f_path, "rb") as send_doc:
                                await self.app.bot.send_document(
                                    chat_id=config.telegram.admin_id,
                                    document=send_doc,
                                    caption=pf.get("caption") or f"📄 {f_path.name}"
                                )
                            mark_outbox_file_sent(f_id, success=True)
                        except Exception as e:
                            logger.error(f"Erro ao entregar arquivo {f_path}: {e}")
                            mark_outbox_file_sent(f_id, success=False)
                    else:
                        mark_outbox_file_sent(f_id, success=False)

                # 3. Verifica notificações do sistema (ex: Alexa finalizada)
                pending_notifs = get_pending_notifications()
                for notif in pending_notifs:
                    n_id = notif["id"]
                    n_text = f"🔔 **{notif['title']}**\n{notif['message']}"
                    await self.app.bot.send_message(
                        chat_id=config.telegram.admin_id,
                        text=n_text,
                        parse_mode="Markdown"
                    )
                    mark_notification_delivered(n_id)

            except Exception as e:
                logger.error(f"Erro no IPC Worker Loop: {e}")

            await asyncio.sleep(1.0)
