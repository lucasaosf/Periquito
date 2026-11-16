"""
Conector do Bot do Discord para o Periquito AI
Suporta mensagens de texto, comandos em canais e voz.
"""

import os
import discord
from discord.ext import commands
from typing import Optional

from core.brain import PeriquitoBrain

class DiscordBotClient:
    def __init__(self, brain: PeriquitoBrain, token: Optional[str] = None):
        self.brain = brain
        self.token = token or os.getenv("DISCORD_BOT_TOKEN")

        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.voice_states = True

        self.bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)
        self._setup_events()

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            print(f"==================================================")
            print(f"🦜 PERIQUITO DISCORD BOT ONLINE!")
            print(f"Conectado como: {self.bot.user.name} (ID: {self.bot.user.id})")
            print(f"Servidores conectados: {len(self.bot.guilds)}")
            print(f"==================================================")

        @self.bot.event
        async def on_message(message: discord.Message):
            # Ignora mensagens do próprio bot
            if message.author == self.bot.user:
                return

            # Responde se for mencionado, em mensagem direta (DM) ou se começar com 'periquito'
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = self.bot.user in message.mentions
            content_lower = message.content.strip().lower()
            is_call = content_lower.startswith("periquito") or content_lower.startswith("!p ")

            if is_dm or is_mentioned or is_call:
                # Limpa menções
                cleaned_text = message.content
                for mention in message.mentions:
                    cleaned_text = cleaned_text.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
                if cleaned_text.lower().startswith("periquito"):
                    cleaned_text = cleaned_text[9:].strip(" ,:")
                elif cleaned_text.lower().startswith("!p "):
                    cleaned_text = cleaned_text[3:].strip()

                if not cleaned_text:
                    cleaned_text = "oi"

                async with message.channel.typing():
                    # Processa pelo cérebro unificado
                    result = self.brain.process_message(
                        text=cleaned_text,
                        user_id=str(message.author.id),
                        username=message.author.name,
                        display_name=message.author.display_name,
                        channel="discord"
                    )

                    text_resp = result.get("text", "")
                    file_path = result.get("file")

                    if file_path and os.path.exists(file_path):
                        await message.reply(text_resp, file=discord.File(file_path))
                    else:
                        await message.reply(text_resp)

            await self.bot.process_commands(message)

    def run(self):
        """Inicia o bot do Discord."""
        if not self.token or self.token == "seu_token_do_discord_aqui":
            print("Aviso: Token do Discord não configurado no arquivo config/.env")
            return
        self.bot.run(self.token)
