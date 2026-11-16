"""
Conector do Bot do Discord para o Periquito AI
Suporta mensagens de texto, comandos em canais e voz no canal de áudio.
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
            print(f"Servidores conectados: {[g.name for g in self.bot.guilds]}")
            print(f"==================================================")

        @self.bot.event
        async def on_message(message: discord.Message):
            if message.author == self.bot.user:
                return

            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = self.bot.user in message.mentions
            content_lower = message.content.strip().lower()
            is_call = (
                content_lower.startswith("periquito") or
                content_lower.startswith("robson") or
                content_lower.startswith("!p ") or
                content_lower.startswith("!periquito")
            )

            if is_dm or is_mentioned or is_call:
                cleaned_text = message.content
                for mention in message.mentions:
                    cleaned_text = cleaned_text.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
                
                lower_clean = cleaned_text.lower()
                if lower_clean.startswith("periquito"):
                    cleaned_text = cleaned_text[9:].strip(" ,:")
                elif lower_clean.startswith("robson"):
                    cleaned_text = cleaned_text[6:].strip(" ,:")
                elif lower_clean.startswith("!p "):
                    cleaned_text = cleaned_text[3:].strip()
                elif lower_clean.startswith("!periquito"):
                    cleaned_text = cleaned_text[10:].strip()

                if not cleaned_text:
                    cleaned_text = "oi"

                # Comandos de voz na call
                if any(w in cleaned_text.lower() for w in ["entra na call", "entrar na call", "entra no canal de voz", "vem pra call"]):
                    if message.author.voice and message.author.voice.channel:
                        vc = message.author.voice.channel
                        if not message.guild.voice_client:
                            await vc.connect()
                            await message.reply(f"🦜 Entrei na sala de voz **{vc.name}**! Pode falar comigo.")
                        else:
                            await message.reply("🦜 Já estou conectado na sala de voz!")
                    else:
                        await message.reply("🦜 Você precisa estar em um canal de voz para eu entrar!")
                    return

                if any(w in cleaned_text.lower() for w in ["sai da call", "sair da call", "sai do canal de voz", "desconectar"]):
                    if message.guild.voice_client:
                        await message.guild.voice_client.disconnect()
                        await message.reply("🦜 Desconectei da sala de voz. Até logo!")
                    else:
                        await message.reply("🦜 Não estou conectado em nenhum canal de voz.")
                    return

                async with message.channel.typing():
                    result = self.brain.process_message(
                        text=cleaned_text,
                        user_id=str(message.author.id),
                        username=message.author.name,
                        display_name=message.author.display_name,
                        channel="discord"
                    )

                    text_resp = result.get("text", "")
                    file_path = result.get("file")

                    # Se estiver em canal de voz, fala a resposta em áudio também
                    if message.guild and message.guild.voice_client and message.guild.voice_client.is_connected():
                        try:
                            audio_file = await self.brain.voice.speak_to_file(text_resp[:300])
                            voice_client = message.guild.voice_client
                            if not voice_client.is_playing():
                                voice_client.play(discord.FFmpegPCMAudio(audio_file))
                        except Exception as e:
                            print(f"Erro ao reproduzir voz no Discord: {e}")

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
