"""
Canal de Microfone Local do Periquito AI
- Atalho Global no Windows com pynput (<ctrl>+<alt>+p)
- Gravação de Áudio via sounddevice
- Transcrição Rápida Offline (Faster-Whisper) e Resposta Falada (Edge-TTS)
"""

import os
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional

from config import config, INBOX_DIR
from core.brain_bridge import PeriquitoBrain
from core.voice import transcribe_audio, synthesize_speech, play_audio_file

logger = logging.getLogger("LocalMicChannel")


class LocalMicChannel:
    def __init__(self, brain: PeriquitoBrain):
        self.brain = brain
        self.is_recording = False
        self._listener = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        try:
            from pynput import keyboard
            hotkey_str = config.local_mic.hotkey

            # Mapeia combinação global
            self._listener = keyboard.GlobalHotKeys({
                hotkey_str: self._on_hotkey_triggered
            })
            self._listener.start()
            logger.info(f"🎤 [Microfone Local] Atalho global ativo: {hotkey_str}")
        except Exception as e:
            logger.warning(f"Não foi possível registrar atalho pynput para o microfone: {e}")

    def stop(self):
        if self._listener:
            self._listener.stop()

    def _on_hotkey_triggered(self):
        """Disparado quando a tecla de atalho é pressionada no Windows."""
        if self.is_recording:
            return
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._record_and_process(), self._loop)

    async def _record_and_process(self):
        self.is_recording = True
        logger.info("🎤 [Microfone] Gravando áudio (5 segundos)...")

        try:
            import sounddevice as sd
            import soundfile as sf
            import numpy as np

            sample_rate = 16000
            duration = 5.0  # 5 segundos de gravação

            # Grava áudio do microfone padrão
            recording = await asyncio.to_thread(
                sd.rec, int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="float32"
            )
            await asyncio.to_thread(sd.wait)

            INBOX_DIR.mkdir(parents=True, exist_ok=True)
            temp_wav = INBOX_DIR / f"mic_{int(time.time())}.wav"
            await asyncio.to_thread(sf.write, str(temp_wav), recording, sample_rate)

            # Transcreve áudio
            logger.info("🧠 [Microfone] Transcrevendo áudio...")
            text = await transcribe_audio(temp_wav)
            if not text:
                logger.info("Nenhuma fala detectada.")
                return

            logger.info(f"🎤 Você falou: '{text}'")

            # Processa no cérebro
            reply = await self.brain.ask(text, user_name="Lucas", channel="local_mic")
            logger.info(f"🦜 Resposta: {reply}")

            # Sintetiza voz e reproduz no alto-falante
            tts_path = await synthesize_speech(reply[:400])
            if tts_path.exists():
                await asyncio.to_thread(play_audio_file, tts_path)

        except Exception as e:
            logger.error(f"Erro no processamento do microfone local: {e}")
        finally:
            self.is_recording = False
