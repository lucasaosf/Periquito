"""
Central de Comando Web & Servidor Cockpit do Periquito AI (Porta 7860)
Fornece interface interativa com visualizador 3D (Orb), monitoramento e chat com voz.
"""

import os
import sys
import psutil
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import config, BASE_DIR, WORKSPACE_DIR, OUTBOX_DIR
from core.brain_bridge import PeriquitoBrain
from core.voice import synthesize_speech
from core.security import resolve_and_check_path, SecurityError

logger = logging.getLogger("PeriquitoCockpit")

app = FastAPI(title="Periquito AI - Central de Comando", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_cockpit_brain: Optional[PeriquitoBrain] = None


def set_cockpit_brain(brain: PeriquitoBrain):
    global _cockpit_brain
    _cockpit_brain = brain


def clean_text_for_speech(text: str) -> str:
    """Remove caracteres especiais e markdown para leitura natural pelo TTS."""
    import re
    cleaned = re.sub(r"[*_`#~\[\]\(\)>]", " ", text)
    cleaned = re.sub(r"https?://\S+", "link da internet", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


@app.get("/api/status")
async def get_system_status():
    """Retorna status de hardware e motores de IA para o painel."""
    mem = psutil.virtual_memory()
    cpu_usage = psutil.cpu_percent(interval=None)
    
    disks = {}
    for d in ["C:", "D:"]:
        if os.path.exists(d):
            usage = psutil.disk_usage(d)
            disks[d] = {
                "livre_gb": round(usage.free / (1024**3), 1),
                "total_gb": round(usage.total / (1024**3), 1),
                "percent_livre": round((usage.free / usage.total) * 100, 1)
            }

    engines = {
        "groq": {
            "name": "Groq LPU (Nuvem)",
            "model": config.models.groq_model,
            "active": bool(config.models.groq_key),
            "speed": "~1.1s"
        },
        "gemini": {
            "name": "Google Gemini (Nuvem)",
            "model": config.models.gemini_model,
            "active": bool(config.models.gemini_key),
            "speed": "~2.4s"
        },
        "ollama": {
            "name": "Ollama Local (Offline)",
            "model": config.models.ollama_model,
            "active": True,
            "speed": "Local (Offline)"
        }
    }

    return {
        "hardware": {
            "cpu_percent": cpu_usage,
            "ram_total_gb": round(mem.total / (1024**3), 1),
            "ram_usada_gb": round(mem.used / (1024**3), 1),
            "ram_percent": mem.percent,
            "discos": disks,
            "gpu": "NVIDIA GeForce GTX 1070"
        },
        "engines": engines,
        "services": {
            "discord": {"running": bool(config.discord.bot_token), "connected": True},
            "telegram": {"running": bool(config.telegram.bot_token), "connected": True}
        }
    }


@app.post("/api/chat")
async def process_chat(request: Request):
    """Processa mensagem de texto/voz, consulta o cérebro unificado e sintetiza áudio."""
    body = await request.json()
    message_text = body.get("text", "").strip()
    voice_enabled = body.get("voice", True)

    if not message_text:
        return JSONResponse({"error": "Mensagem vazia."}, status_code=400)

    brain = _cockpit_brain or PeriquitoBrain()
    resp_text = await brain.ask(message_text, user_name="Lucas", channel="desktop_app")

    audio_url = None
    if voice_enabled and resp_text:
        try:
            clean_speech = clean_text_for_speech(resp_text)
            if len(clean_speech) > 2:
                OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
                audio_path = OUTBOX_DIR / f"cockpit_voice_{os.getpid()}_{int(asyncio.get_event_loop().time())}.mp3"
                await synthesize_speech(clean_speech[:400], output_path=audio_path)
                audio_url = f"/api/audio/{audio_path.name}"
        except Exception as e:
            logger.warning(f"Erro ao sintetizar voz no cockpit: {e}")

    return {
        "text": resp_text,
        "audio_url": audio_url,
        "file_url": None
    }


@app.get("/api/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve arquivos de áudio temporários com blindagem contra path traversal."""
    safe_name = os.path.basename(filename)
    audio_path = OUTBOX_DIR / safe_name
    if audio_path.exists() and audio_path.is_file():
        return FileResponse(str(audio_path), media_type="audio/mpeg")
    return JSONResponse({"error": "Arquivo não encontrado"}, status_code=404)


# Monta arquivos estáticos da interface web
UI_DIR = BASE_DIR / "ui"
if UI_DIR.exists():
    app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")


async def run_cockpit_server_async(port: int = 7860):
    """Executa o servidor do Cockpit no event loop assíncrono."""
    cfg = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning"
    )
    server = uvicorn.Server(cfg)
    logger.info(f"🎛️ [Central de Comando Web] Ativa em http://127.0.0.1:{port}")
    await server.serve()
