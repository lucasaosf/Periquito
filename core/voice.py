"""
Motor de Voz e Áudio do Periquito AI (100% Custo Zero)
- Transcrição Offline Lazy com Faster-Whisper
- Síntese de Fala Neural de Alta Qualidade com Edge-TTS (pt-BR)
- Execução não-bloqueante em threads separadas via asyncio.to_thread
"""

import os
import io
import asyncio
import logging
from pathlib import Path
from typing import Optional

from config import config, WORKSPACE_DIR

logger = logging.getLogger("VoiceEngine")

_whisper_instance = None


def _get_whisper_model():
    """Carrega o Faster-Whisper sob demanda (Lazy Loading) para poupar memória."""
    global _whisper_instance
    if _whisper_instance is None:
        try:
            from faster_whisper import WhisperModel
            model_size = config.local_mic.whisper_model
            logger.info(f"Carregando modelo Faster-Whisper ({model_size}) sob demanda...")
            _whisper_instance = WhisperModel(model_size, device="cpu", compute_type="int8")
        except Exception as e:
            logger.error(f"Não foi possível carregar faster-whisper: {e}")
            raise RuntimeError(f"Faster-whisper indisponível: {e}")
    return _whisper_instance


def transcribe_audio_file_sync(audio_path: str | Path, language: str = "pt") -> str:
    """Transcreve arquivo de áudio de forma síncrona (executado dentro de worker thread)."""
    model = _get_whisper_model()
    segments, info = model.transcribe(str(audio_path), language=language, beam_size=5)
    text = " ".join([seg.text.strip() for seg in segments]).strip()
    return text


async def transcribe_audio(audio_path: str | Path, language: str = "pt") -> str:
    """Wrapper assíncrono para transcrição não-bloqueante."""
    return await asyncio.to_thread(transcribe_audio_file_sync, audio_path, language)


async def synthesize_speech(text: str, output_path: Optional[str | Path] = None, voice: Optional[str] = None) -> Path:
    """
    Sintetiza áudio de fala neural realista em português usando Edge-TTS gratuito.
    """
    import edge_tts

    if not voice:
        voice = config.local_mic.voice_name

    if not output_path:
        out_dir = WORKSPACE_DIR / "outbox"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"resposta_voz_{os.getpid()}_{int(asyncio.get_event_loop().time())}.mp3"
    else:
        output_path = Path(output_path)

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))
    return output_path


def play_audio_file(audio_path: str | Path):
    """Reproduz áudio localmente no alto-falante do Windows."""
    try:
        import sounddevice as sd
        import soundfile as sf
        data, fs = sf.read(str(audio_path), dtype='float32')
        sd.play(data, fs)
        sd.wait()
    except Exception as e:
        logger.warning(f"Falha ao reproduzir áudio via sounddevice: {e}")
