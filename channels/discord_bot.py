"""
Conector do Bot do Discord para o Periquito AI
Suporta mensagens de texto, comandos em canais e transmissão de voz em alta definição na call.
Responde automaticamente sem precisar digitar o nome quando estiver na chamada ou canal de voz.
"""

import os
import re
import shutil
import asyncio
import logging
import discord
from discord.ext import commands
from typing import Optional

from core.brain import PeriquitoBrain

logger = logging.getLogger("DiscordBot")

FFMPEG_PATH = shutil.which("ffmpeg") or r"C:\Users\Lucas Aosf\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"


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
            print(f"FFmpeg path: {FFMPEG_PATH}")
            print("==================================================")

        @self.bot.event
        async def on_message(message: discord.Message):
            # Ignora as próprias mensagens do bot
            if message.author == self.bot.user:
                return

            print(f"[DISCORD MSG] De {message.author.name} ({message.author.display_name}) em #{message.channel}: {message.content}")

            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = self.bot.user in message.mentions
            content_lower = message.content.strip().lower()

            is_in_voice = bool(message.guild and message.guild.voice_client and message.guild.voice_client.is_connected())
            author_in_voice = bool(message.author.voice and message.author.voice.channel)

            # Detecta se é para responder:
            # 1. Se o bot estiver conectado na call de voz do servidor -> responde SEMPRE a tudo que mandarem!
            # 2. Se a mensagem for na DM
            # 3. Se o bot foi mencionado (@Periquito AI)
            # 4. Se a mensagem começar com periquito, robson, !p ou !periquito
            # 5. Se o autor estiver num canal de voz e mandar mensagem pedindo pra entrar
            should_respond = (
                is_in_voice or
                is_dm or
                is_mentioned or
                content_lower.startswith("periquito") or
                content_lower.startswith("robson") or
                content_lower.startswith("!p") or
                any(w in content_lower for w in ["entra na call", "vem pra call", "conecta na call", "sai da call"])
            )

            if not should_respond:
                return

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

            if not cleaned_text.strip():
                cleaned_text = "e aí, periquito!"

            lower_cmd = cleaned_text.lower()

            # -------------------------------------------------------------
            # 1. Comandos de Entrada e Saída da Chamada de Voz
            # -------------------------------------------------------------
            if any(w in lower_cmd for w in ["sai da call", "sair da call", "sai do canal de voz", "desconectar", "vaza da call", "sai daí"]):
                if message.guild and message.guild.voice_client:
                    try:
                        await message.guild.voice_client.disconnect()
                        await message.reply("🦜 Desconectei da sala de voz. Até logo, galera!")
                    except Exception as e:
                        await message.reply(f"🦜 Erro ao sair da call: {e}")
                else:
                    await message.reply("🦜 Eu não estou em nenhum canal de voz agora.")
                return

            if any(w in lower_cmd for w in ["entra na call", "entrar na call", "entra no canal de voz", "vem pra call", "conecta na call", "entra aqui"]):
                if author_in_voice:
                    vc = message.author.voice.channel
                    try:
                        if not message.guild.voice_client:
                            await vc.connect(timeout=20.0, reconnect=True, self_deaf=True)
                            await message.reply(f"🦜 Entrei na sala de voz **{vc.name}**! Pode falar comigo no chat que eu respondo por áudio aqui na chamada.")
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

            # Se o autor estiver num canal de voz e o bot ainda não estiver, entra automaticamente!
            if author_in_voice and message.guild:
                if not message.guild.voice_client or not message.guild.voice_client.is_connected():
                    try:
                        vc = message.author.voice.channel
                        await vc.connect(timeout=15.0, reconnect=True, self_deaf=True)
                    except Exception as e:
                        print(f"Tentativa de auto-connect na voz falhou: {e}")

            # -------------------------------------------------------------
            # 2. Processamento da Mensagem no Cérebro do Periquito
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

                # Se o bot estiver conectado em canal de voz, fala a resposta em áudio!
                voice_client = message.guild.voice_client if message.guild else None
                if voice_client and voice_client.is_connected():
                    try:
                        clean_speech = re.sub(r"[*#_`~•🦜]", "", text_resp).strip()
                        clean_speech = re.sub(r"https?://\S+", "", clean_speech).strip()
                        if len(clean_speech) > 2:
                            audio_file = await self.brain.voice.speak_to_file(clean_speech[:350])
                            if os.path.exists(audio_file):
                                if voice_client.is_playing():
                                    voice_client.stop()
                                source = discord.FFmpegPCMAudio(
                                    audio_file,
                                    executable=FFMPEG_PATH,
                                    options="-vn -loglevel quiet"
                                )
                                voice_client.play(source)
                                print(f"[VOZ DISCORD] Áudio reproduzido com sucesso na call: {audio_file}")
                    except Exception as e:
                        print(f"Erro ao reproduzir áudio no canal de voz: {e}")

                # Envio no chat de texto (protegido contra limite de 2000 chars)
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
