"""
Conector do Bot do Discord para o Periquito AI (Voice-to-Voice em Tempo Real)
Capaz de ouvir a voz dos participantes pelo microfone na call, transcrever em ~0.3s via Groq Whisper,
gerar raciocínio inteligente e responder falando com áudio fluído na chamada!
"""

import os
import io
import re
import time
import wave
import shutil
import asyncio
import logging
import requests
import discord
from discord.ext import commands, voice_recv
from typing import Optional, Dict

from core.brain import PeriquitoBrain
from core.voice import clean_text_for_speech

logger = logging.getLogger("DiscordBot")

FFMPEG_PATH = shutil.which("ffmpeg") or r"C:\Users\Lucas Aosf\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"


class PeriquitoVoiceSink(voice_recv.AudioSink):
    """
    Captura o áudio dos microfones dos usuários na chamada do Discord,
    detecta pausas na fala, transcreve com Whisper e aciona a resposta por voz da IA.
    """
    def __init__(self, bot: commands.Bot, brain: PeriquitoBrain, voice_channel):
        super().__init__()
        self.bot = bot
        self.brain = brain
        self.voice_channel = voice_channel
        self.buffers: Dict[int, bytearray] = {}
        self.users: Dict[int, Any] = {}
        self.last_seen: Dict[int, float] = {}
        self.is_processing = False
        self.running = True
        
        # Inicia loop de detecção de silêncio e fala
        asyncio.create_task(self._silence_detector_loop())

    def wants_opus(self) -> bool:
        return False

    def cleanup(self):
        self.running = False
        self.buffers.clear()
        self.users.clear()

    def write(self, user, data):
        # Ignora bots e áudio vazio
        if not user or not data.pcm or getattr(user, 'bot', False):
            return

        # Se o Periquito estiver falando na call agora, ignora para evitar eco/interrupção
        if self.voice_client and self.voice_client.is_playing():
            return

        now = time.time()
        uid = user.id

        if uid not in self.buffers:
            self.buffers[uid] = bytearray()
            self.users[uid] = user

        self.buffers[uid].extend(data.pcm)
        self.last_seen[uid] = now

    async def _silence_detector_loop(self):
        """Monitora se algum usuário terminou de falar (pausa > 0.8s) para processar."""
        while self.running:
            await asyncio.sleep(0.2)
            if not self.voice_client or not self.voice_client.is_connected():
                continue

            # Se já estiver falando ou processando, aguarda
            if self.is_processing or (self.voice_client and self.voice_client.is_playing()):
                continue

            now = time.time()
            for uid, last_time in list(self.last_seen.items()):
                # Detectou fim da fala (silêncio de 0.8s)
                if now - last_time > 0.8:
                    pcm_bytes = bytes(self.buffers.get(uid, b""))
                    user = self.users.get(uid)

                    # Limpa buffers desse usuário
                    self.buffers.pop(uid, None)
                    self.last_seen.pop(uid, None)

                    # Só processa se tiver pelo menos ~0.5s de áudio (48000 * 2ch * 2bytes * 0.5s = 96000 bytes)
                    if len(pcm_bytes) > 76800 and user:
                        self.is_processing = True
                        asyncio.create_task(self._process_user_speech(user, pcm_bytes))
                        break

    async def _process_user_speech(self, user, pcm_data: bytes):
        try:
            # 1. Converte PCM bruto para WAV em memória
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(48000)
                wf.writeframes(pcm_data)
            wav_bytes = wav_io.getvalue()

            # 2. Transcrição Ultra-Rápida com Groq Whisper Large V3 Turbo (~300ms)
            groq_key = os.getenv("GROQ_API_KEY", "").strip()
            transcript = ""

            if groq_key:
                try:
                    res = requests.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {groq_key}"},
                        files={"file": ("speech.wav", wav_bytes, "audio/wav")},
                        data={"model": "whisper-large-v3-turbo", "language": "pt"},
                        timeout=8
                    )
                    if res.status_code == 200:
                        transcript = res.json().get("text", "").strip()
                except Exception as e:
                    print(f"Groq Whisper timeout/erro: {e}")

            if not transcript or len(transcript) < 2:
                self.is_processing = False
                return

            # Ignora alucinações comuns de silêncio
            if transcript.lower() in ["obrigado", "tchau", "legendas pela comunidade amara.org", "valeu", "subtitles by"]:
                self.is_processing = False
                return

            print(f"[VOZ OUVIDA NA CALL] {user.display_name} ({user.name}): {transcript}")

            # 3. Processamento no Cérebro do Periquito
            result = self.brain.process_message(
                text=transcript,
                user_id=str(user.id),
                username=user.name,
                display_name=user.display_name,
                channel="discord_voice"
            )

            text_resp = result.get("text", "")
            if not text_resp:
                self.is_processing = False
                return

            # Higieniza formatação e símbolos para fala natural
            clean_speech = clean_text_for_speech(text_resp)

            # 4. Síntese de Voz e Transmissão Direta na Call
            if len(clean_speech) > 2 and self.voice_client and self.voice_client.is_connected():
                audio_file = await self.brain.voice.speak_to_file(clean_speech[:350])
                if os.path.exists(audio_file):
                    if self.voice_client.is_playing():
                        self.voice_client.stop()
                    
                    source = discord.FFmpegPCMAudio(
                        audio_file,
                        executable=FFMPEG_PATH,
                        options="-vn -loglevel quiet"
                    )
                    self.voice_client.play(source)
                    print(f"[RESPOSTA FALADA NA CALL] Periquito -> {user.display_name}: {clean_speech}")

        except Exception as e:
            print(f"Erro no pipeline de voz: {e}")
        finally:
            # Aguarda um momento após falar para evitar auto-escuta
            await asyncio.sleep(0.5)
            self.is_processing = False


class DiscordBotClient:
    def __init__(self, brain: PeriquitoBrain, token: Optional[str] = None):
        self.brain = brain
        self.token = token or os.getenv("DISCORD_BOT_TOKEN")

        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.voice_states = True

        self.bot = commands.Bot(command_prefix=["!", "/"], intents=intents, help_command=None)
        self.active_sink: Optional[PeriquitoVoiceSink] = None
        self._setup_events()

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            print("==================================================")
            print(f"🦜 PERIQUITO DISCORD BOT ONLINE (VOICE-TO-VOICE ATIVO)!")
            print(f"Conectado como: {self.bot.user.name} (ID: {self.bot.user.id})")
            print(f"Servidores conectados: {[g.name for g in self.bot.guilds]}")
            print(f"Motor STT: Groq Whisper Large V3 Turbo")
            print(f"FFmpeg path: {FFMPEG_PATH}")
            print("==================================================")

        @self.bot.event
        async def on_message(message: discord.Message):
            if message.author == self.bot.user:
                return

            print(f"[DISCORD TEXTO] De {message.author.name} ({message.author.display_name}) em #{message.channel}: {message.content}")

            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = self.bot.user in message.mentions
            content_lower = message.content.strip().lower()

            is_in_voice = bool(message.guild and message.guild.voice_client and message.guild.voice_client.is_connected())
            author_in_voice = bool(message.author.voice and message.author.voice.channel)

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

            # Comandos de Call
            if any(w in lower_cmd for w in ["sai da call", "sair da call", "sai do canal de voz", "desconectar", "vaza da call", "sai daí"]):
                if message.guild and message.guild.voice_client:
                    try:
                        if self.active_sink:
                            self.active_sink.cleanup()
                            self.active_sink = None
                        await message.guild.voice_client.disconnect()
                        await message.reply("🦜 Desconectei da sala de voz. Até logo, galera!")
                    except Exception as e:
                        await message.reply(f"🦜 Erro ao sair da call: {e}")
                else:
                    await message.reply("🦜 Eu não estou em nenhum canal de voz agora.")
                return

            # Conexão com VoiceRecvClient
            if any(w in lower_cmd for w in ["entra na call", "entrar na call", "entra no canal de voz", "vem pra call", "conecta na call", "entra aqui"]) or (author_in_voice and not is_in_voice):
                if author_in_voice:
                    vc = message.author.voice.channel
                    try:
                        # Se houver um client desconectado ou com erro, limpa antes
                        if message.guild.voice_client and not message.guild.voice_client.is_connected():
                            try:
                                if self.active_sink:
                                    self.active_sink.cleanup()
                                    self.active_sink = None
                                await message.guild.voice_client.disconnect(force=True)
                            except Exception:
                                pass

                        if not message.guild.voice_client or not message.guild.voice_client.is_connected():
                            voice_client = await vc.connect(cls=voice_recv.VoiceRecvClient, timeout=20.0, reconnect=True)
                            self.active_sink = PeriquitoVoiceSink(self.bot, self.brain, vc)
                            voice_client.listen(self.active_sink)
                            await message.reply(f"🦜 Entrei na sala de voz **{vc.name}** com **escuta ativa**! Pode falar normalmente pelo microfone que eu te respondo por voz!")
                        else:
                            if message.guild.voice_client.channel != vc:
                                await message.guild.voice_client.move_to(vc)
                                await message.reply(f"🦜 Mudei para a sala de voz **{vc.name}**!")
                            elif hasattr(message.guild.voice_client, 'is_listening') and not message.guild.voice_client.is_listening():
                                if not self.active_sink:
                                    self.active_sink = PeriquitoVoiceSink(self.bot, self.brain, vc)
                                message.guild.voice_client.listen(self.active_sink)
                                await message.reply(f"🦜 Escuta ativa reativada na sala **{vc.name}**!")
                    except Exception as e:
                        print(f"Erro ao conectar na voz: {e}")
                else:
                    await message.reply("🦜 Você precisa estar em um canal de voz para eu entrar!")
                return

            # Resposta de Texto
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

                # Se estiver na voz, fala a resposta em áudio também
                voice_client = message.guild.voice_client if message.guild else None
                if voice_client and voice_client.is_connected():
                    try:
                        clean_speech = clean_text_for_speech(text_resp)
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
                    except Exception as e:
                        print(f"Erro ao reproduzir voz: {e}")

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
