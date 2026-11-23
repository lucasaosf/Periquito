"""
Canal Oficial do Discord do Periquito AI
- Isolamento total de usuários terceiros -> core/public_chat.py
- Comandos administrativos permitidos exclusivamente em DM ou canais privados autorizados
- Fatiamento automático em 1.900 caracteres
"""

import asyncio
import logging
from typing import Optional

import discord
from discord.ext import commands

from config import config
from core.brain_bridge import PeriquitoBrain
from core.public_chat import answer_public_message
from core.text_utils import slice_message

logger = logging.getLogger("DiscordChannel")


class DiscordChannel:
    def __init__(self, brain: PeriquitoBrain):
        self.brain = brain
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
        self._setup_events()

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            logger.info(f"🦜 [Discord] Conectado com sucesso como {self.bot.user} (ID: {self.bot.user.id})")

        @self.bot.event
        async def on_message(message: discord.Message):
            # Ignora as próprias mensagens
            if message.author.id == self.bot.user.id:
                return

            # Só processa se for mencionado ou se for mensagem direta (DM)
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = self.bot.user in message.mentions

            if not is_dm and not is_mentioned:
                return

            clean_text = message.clean_content.replace(f"@{self.bot.user.name}", "").strip()
            if not clean_text:
                return

            # 1. Usuário comum (não é administrador)
            if message.author.id != config.discord.admin_id:
                async with message.channel.typing():
                    social_reply = await asyncio.to_thread(answer_public_message, clean_text)
                    for chunk in slice_message(social_reply, max_length=1900):
                        await message.reply(chunk)
                return

            # 2. Administrador (Lucas)
            # Verifica se está em DM ou em canal privado explicitamente autorizado
            is_private_channel = is_dm or (message.channel.id in config.discord.private_channel_ids)

            if is_private_channel:
                async with message.channel.typing():
                    admin_reply = await self.brain.ask(clean_text, user_name="Lucas", channel="discord")
                    for chunk in slice_message(admin_reply, max_length=1900):
                        await message.reply(chunk)
            else:
                # Acionado em canal público do servidor: protege dados confidenciais
                async with message.channel.typing():
                    await message.reply("🔒 Comando pessoal recebido. Para sua segurança e privacidade, enviei a resposta completa na sua DM!")
                    admin_reply = await self.brain.ask(clean_text, user_name="Lucas", channel="discord")
                    try:
                        dm_channel = message.author.dm_channel or await message.author.create_dm()
                        for chunk in slice_message(admin_reply, max_length=1900):
                            await dm_channel.send(chunk)
                    except Exception as e:
                        logger.error(f"Erro ao enviar DM privada: {e}")

    async def start(self):
        token = config.discord.bot_token
        if not token or config.discord.admin_id == 0:
            logger.warning("[Discord] Token ou Admin ID não configurados no .env. Canal desativado.")
            return

        asyncio.create_task(self.bot.start(token))

    async def stop(self):
        if not self.bot.is_closed():
            await self.bot.close()
