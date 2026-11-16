"""
Conector do Bot do Discord para o Periquito AI
Suporta mensagens de texto, comandos em canais e transmissão de voz de alta fidelidade na call.
"""

import os
import re
import asyncio
import logging
import discord
from discord.ext import commands
from typing import Optional

from core.brain import PeriquitoBrain

logger = logging.getLogger("DiscordBot")


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
            print("==================================================")
            print(f"🦜 PERIQUITO DISCORD BOT ONLINE!")
            print(f"Conectado como: {self.bot.user.name} (ID: {self.bot.user.id})")
            print(f"Servidores conectados: {[g.name for g in self.bot.guilds]}")
            print("==================================================")

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

            # Também responde se estiver em canal de voz e qualquer um mandar mensagem no chat do canal
            is_in_voice = message.guild and message.guild.voice_client and message.guild.voice_client.is_connected()
            is_voice_text_chat = False
            if is_in_voice and hasattr(message.channel, "type"):
                if str(message.channel.type) == "voice":
                    is_voice_text_chat = True

            if is_dm or is_mentioned or is_call or is_voice_text_chat:
                cleaned_text = message.content
                for mention in message.mentions:
                    cleaned_text = cleaned_text.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
                
                lower_clean = cleaned_text.lower().strip()
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

                lower_cmd = cleaned_text.lower()

                # -------------------------------------------------------------
                # Comandos de Voz: Qualquer usuário pode chamar ou dispensar da call
                # -------------------------------------------------------------
                if any(w in lower_cmd for w in ["entra na call", "entrar na call", "entra no canal de voz", "vem pra call", "entra no voice"]):
                    if message.author.voice and message.author.voice.channel:
                        vc = message.author.voice.channel
                        try:
                            if not message.guild.voice_client:
                                await vc.connect(timeout=20.0, reconnect=True, self_deaf=True)
                                await message.reply(f"🦜 Entrei na sala de voz **{vc.name}**! Pode falar comigo no chat ou me mandar perguntas que eu falo aqui na call.")
                            else:
                                if message.guild.voice_client.channel != vc:
                                    await message.guild.voice_client.move_to(vc)
                                    await message.reply(f"🦜 Mudei para a sala de voz **{vc.name}**!")
                                else:
                                    await message.reply("🦜 Já estou conectado aqui com vocês na sala de voz!")
                        except Exception as e:
                            print(f"Erro ao conectar na voz: {e}")
                            await message.reply(f"🦜 Tive uma instabilidade ao entrar na call: {e}")
                    else:
                        await message.reply("🦜 Você precisa estar em um canal de voz para eu entrar!")
                    return

                if any(w in lower_cmd for w in ["sai da call", "sair da call", "sai do canal de voz", "desconectar", "vaza da call"]):
                    if message.guild.voice_client:
                        try:
                            await message.guild.voice_client.disconnect()
                            await message.reply("🦜 Desconectei da sala de voz. Até logo, galera!")
                        except Exception as e:
                            await message.reply(f"🦜 Erro ao sair da call: {e}")
                    else:
                        await message.reply("🦜 Eu não estou em nenhum canal de voz agora.")
                    return

                # -------------------------------------------------------------
                # Processamento da Mensagem no Cérebro do Periquito
                # -------------------------------------------------------------
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

                    # Se estiver em canal de voz, fala a resposta em áudio na call
                    if message.guild and message.guild.voice_client and message.guild.voice_client.is_connected():
                        try:
                            voice_client = message.guild.voice_client
                            clean_speech = re.sub(r"[*#_`~•🦜]", "", text_resp).strip()
                            if len(clean_speech) > 2:
                                audio_file = await self.brain.voice.speak_to_file(clean_speech[:400])
                                if os.path.exists(audio_file):
                                    if voice_client.is_playing():
                                        voice_client.stop()
                                    source = discord.FFmpegPCMAudio(
                                        audio_file,
                                        executable="ffmpeg",
                                        options="-vn -loglevel quiet"
                                    )
                                    voice_client.play(source)
                        except Exception as e:
                            print(f"Erro ao reproduzir voz no Discord: {e}")

                    # Envio no chat de texto (protegido contra limite de 2000 chars do Discord)
                    if file_path and os.path.exists(file_path):
                        await message.reply(text_resp[:1950], file=discord.File(file_path))
                    else:
                        if len(text_resp) > 1950:
                            for i in range(0, len(text_resp), 1950):
                                await message.reply(text_resp[i:i + 1950])
                        else:
                            await message.reply(text_resp)

            await self.bot.process_commands(message)

    def run(self):
        """Inicia o bot do Discord."""
        if not self.token:
            print("Aviso: Token do Discord não configurado no arquivo config/.env")
            return
        self.bot.run(self.token)
