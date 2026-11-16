"""
Módulo de Voz do Periquito AI
Gera fala ultranatural em Português Brasileiro usando Edge-TTS (sem custo e sem API externa).
Possui higienização avançada de texto para remover emojis, asteriscos, códigos e símbolos visuais,
falando com máxima fluidez e naturalidade sem soletrar pontuações ou emoticons.
"""

import os
import re
import asyncio
import unicodedata
import edge_tts
import datetime
from typing import Optional

DEFAULT_VOICE = "pt-BR-AntonioNeural" # Voz masculina brasileira natural e amigável


def clean_text_for_speech(text: str) -> str:
    """
    Higieniza o texto para síntese de voz (TTS).
    Remove emojis, símbolos, formatações markdown e caracteres visuais,
    preservando apenas a fala fluida, pausas e entonação natural.
    """
    if not text:
        return ""

    # 1. Remove blocos de código markdown (```...```) e código inline (`...`)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`+([^`]+)`+', r'\1', text)

    # 2. Converte links markdown [texto](url) para apenas 'texto' ANTES de remover URLs
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # 3. Remove URLs restantes (https://..., http://..., www....)
    text = re.sub(r'https?://\S+|www\.\S+', '', text)

    # 4. Remove menções do Discord (<@123>, <#123>, <:emoji:123>)
    text = re.sub(r'<@!?\d+>', '', text)
    text = re.sub(r'<#\d+>', '', text)
    text = re.sub(r'<:[a-zA-Z0-9_]+:\d+>', '', text)

    # 5. Remove cabeçalhos markdown (# Titulo) e citações (> citação) no início das linhas
    text = re.sub(r'^\s*#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)

    # 6. Converte marcadores de lista em início de linha para pausa suave
    text = re.sub(r'^\s*[-*+•▪●○]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n\s*[-*+•▪●○]\s+', ', ', text)

    # 7. Converte grandezas, moedas e símbolos para pronúncia falada fluida
    text = re.sub(r'R\$\s*(\d+(?:,\d{1,2})?)', r'\1 reais', text)
    text = re.sub(r'(?:\$|US\$)\s*(\d+(?:,\d{1,2})?)', r'\1 dólares', text)
    text = re.sub(r'(\d+)%', r'\1 por cento', text)
    text = re.sub(r'°C|ºC', ' graus célsius', text)
    text = re.sub(r'°|º', ' graus', text)
    text = re.sub(r'\bkm/h\b', 'quilômetros por hora', text, flags=re.IGNORECASE)

    # 8. Remove todos os Emojis e Símbolos pictográficos
    cleaned_chars = []
    for c in text:
        cat = unicodedata.category(c)
        code = ord(c)
        # Ignora categorias de símbolos visuais e emojis
        if cat in ('So', 'Sk', 'Cs'):
            continue
        if 0x1F000 <= code <= 0x1FFFF:  # Emojis, transportes, pictografias
            continue
        if 0x2600 <= code <= 0x27BF:    # Símbolos diversos, Dingbats
            continue
        if 0xFE00 <= code <= 0xFE0F:    # Variation selectors
            continue
        if code == 0x200D:              # Zero-width joiner
            continue
        cleaned_chars.append(c)
    text = ''.join(cleaned_chars)

    # 9. Remove marcadores de formatação de texto: negrito (** ou __), itálico (* ou _), riscado (~~)
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', text)
    text = re.sub(r'~{1,2}([^~]+)~{1,2}', r'\1', text)

    # 10. Substitui parênteses, colchetes e chaves por vírgula para manter pausa natural
    text = re.sub(r'[\(\[\{]', ', ', text)
    text = re.sub(r'[\)\]\}]', ', ', text)

    # 11. Remove símbolos técnicos e pontuações estranhas que o TTS tenta soletrar
    text = re.sub(r'[*#_~`|\\/^=+<>@•▪●○—–&"]', ' ', text)

    # 12. Normaliza pontuação e pausas
    text = re.sub(r'\?+', '?', text)
    text = re.sub(r'!+', '!', text)
    text = re.sub(r'\.{4,}', '...', text)

    # Remove vírgulas duplicadas ou vírgulas antes de pontuação final
    text = re.sub(r'\s*,\s*,+', ', ', text)
    text = re.sub(r',\s*([.!?])', r'\1', text)
    text = re.sub(r'(?<!\d)\s*,\s*|\s*,\s*(?!\d)', ', ', text)
    text = re.sub(r'\s*\.\s*(?!\.)', '. ', text)

    # 13. Remove espaços extras e quebras
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n+', ' ', text).strip()

    # Remove pontuação órfã no início ou fim
    text = re.sub(r'^[,\.\:\;\-\s]+', '', text)
    text = re.sub(r'[,\:\-\s]+$', '', text)

    return text


class VoiceEngine:
    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice
        self.temp_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "audio_temp"
        )
        os.makedirs(self.temp_dir, exist_ok=True)

    async def speak_to_file(self, text: str, output_file: Optional[str] = None) -> str:
        """Sintetiza texto em arquivo de áudio MP3 com fala natural sem emojis nem símbolos."""
        cleaned_text = clean_text_for_speech(text)
        if not cleaned_text:
            cleaned_text = "..."

        if not output_file:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            output_file = os.path.join(self.temp_dir, f"periquito_fala_{timestamp}.mp3")

        communicate = edge_tts.Communicate(cleaned_text, self.voice)
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
