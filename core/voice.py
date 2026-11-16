"""
Módulo de Voz do Periquito AI
Gera fala ultranatural em Português Brasileiro usando Edge-TTS (sem custo e sem API externa).
"""

import os
import asyncio
import edge_tts
import datetime
from typing import Optional

DEFAULT_VOICE = "pt-BR-AntonioNeural" # Voz masculina brasileira natural e amigável

class VoiceEngine:
    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice
        self.temp_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "audio_temp"
        )
        os.makedirs(self.temp_dir, exist_ok=True)

    async def speak_to_file(self, text: str, output_file: Optional[str] = None) -> str:
        """Sintetiza texto em arquivo de áudio MP3."""
        if not output_file:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            output_file = os.path.join(self.temp_dir, f"periquito_fala_{timestamp}.mp3")

        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(output_file)
        return output_file

    def generate_audio_sync(self, text: str, output_file: Optional[str] = None) -> str:
        """Versão síncrona para chamadas diretas."""
        return asyncio.run(self.speak_to_file(text, output_file))

    def play_audio(self, audio_path: str) -> None:
        """Reproduz o áudio nos alto-falantes ou fone do computador sem travar."""
        if os.path.exists(audio_path):
            import subprocess
            subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", audio_path],
                shell=True
            )
