"""
Central de Comando Web & Servidor Cockpit do Periquito AI
Fornece API REST, controle dos bots do Discord e Telegram, monitoramento de hardware em tempo real e visualizador 3D.
"""

import os
import sys
import asyncio
import logging
import threading
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Adiciona raiz do projeto ao path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.brain import PeriquitoBrain
from core.voice import clean_text_for_speech
from channels.discord_bot import DiscordBotClient

logger = logging.getLogger("PeriquitoCockpit")

app = FastAPI(title="Periquito AI - Central de Comando", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instância única do Cérebro Unificado
brain = PeriquitoBrain()

# Gerenciador do Bot do Discord em background
class DiscordServiceManager:
    def __init__(self, brain_instance: PeriquitoBrain):
        self.brain = brain_instance
        self.client: Optional[DiscordBotClient] = None
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.is_running = False
        self.server_name = ""

    def start(self) -> Dict[str, Any]:
        if self.is_running:
            return {"status": "already_running", "message": "Bot do Discord já está ativo!"}
        
        token = os.getenv("DISCORD_BOT_TOKEN")
        if not token:
            return {"status": "error", "message": "Token do Discord não configurado no .env"}

        def _run():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.client = DiscordBotClient(brain=self.brain, token=token)
            self.is_running = True
            try:
                self.client.run()
            except Exception as e:
                logger.error(f"Erro no Discord Bot: {e}")
            finally:
                self.is_running = False

        self.thread = threading.Thread(target=_run, daemon=True)
        self.thread.start()
        return {"status": "started", "message": "Iniciando conexão com o Discord..."}

    def stop(self) -> Dict[str, Any]:
        if not self.is_running or not self.client:
            return {"status": "not_running", "message": "Bot do Discord não está ativo."}
        try:
            if self.loop and self.client.bot:
                asyncio.run_coroutine_threadsafe(self.client.bot.close(), self.loop)
            self.is_running = False
            return {"status": "stopped", "message": "Bot do Discord desconectado com sucesso."}
        except Exception as e:
            self.is_running = False
            return {"status": "error", "message": f"Erro ao parar bot: {e}"}

    def get_status(self) -> Dict[str, Any]:
        guilds = []
        if self.client and self.client.bot and self.client.bot.is_ready():
            guilds = [g.name for g in self.client.bot.guilds]
        return {
            "running": self.is_running,
            "connected": bool(self.client and self.client.bot and self.client.bot.is_ready()),
            "guilds": guilds,
            "bot_name": self.client.bot.user.name if (self.client and self.client.bot and self.client.bot.user) else "Periquito AI"
        }

discord_mgr = DiscordServiceManager(brain)


# ==============================================================================
# ENDPOINTS REST DA CENTRAL DE COMANDO
# ==============================================================================

@app.get("/api/status")
async def get_system_status():
    """Retorna o status completo do hardware, dos motores de IA e dos canais."""
    hw = brain.tools.get_system_status()
    discord_status = discord_mgr.get_status()

    # Checa motores de IA configurados
    engines = {
        "groq": {
            "name": "Groq LPU (Nuvem)",
            "model": brain.groq_model,
            "active": bool(brain.groq_key),
            "speed": "~1.1s"
        },
        "gemini": {
            "name": "Google Gemini (Nuvem)",
            "model": brain.gemini_model,
            "active": bool(brain.gemini_key),
            "speed": "~2.4s"
        },
        "ollama": {
            "name": "Ollama Local (Offline)",
            "model": brain.ollama_model,
            "active": True,
            "speed": "Local (GTX 1070)"
        }
    }

    return {
        "hardware": hw,
        "engines": engines,
        "services": {
            "discord": discord_status,
            "telegram": {"running": False, "connected": False}
        }
    }


@app.post("/api/chat")
async def process_chat(request: Request):
    """Processa mensagem de texto ou voz, gera resposta inteligente e sintetiza áudio."""
    body = await request.json()
    message_text = body.get("text", "").strip()
    voice_enabled = body.get("voice", True)

    if not message_text:
        return JSONResponse({"error": "Mensagem vazia."}, status_code=400)

    # Executa pelo cérebro nativo
    result = brain.process_message(
        text=message_text,
        user_id="cockpit_user",
        username="Lucas Aosf",
        display_name="Lucas Aosf",
        channel="cockpit"
    )

    resp_text = result.get("text", "")
    file_path = result.get("file")
    file_url = None
    if file_path and os.path.exists(file_path):
        file_url = f"/api/files/{os.path.basename(file_path)}"

    audio_url = None
    if voice_enabled and resp_text:
        try:
            # Limpa emojis e markdown para a síntese de voz fluida
            clean_speech = clean_text_for_speech(resp_text)
            if len(clean_speech) > 2:
                audio_file = await brain.voice.speak_to_file(clean_speech[:600])
                audio_url = f"/api/audio/{os.path.basename(audio_file)}"
        except Exception as e:
            logger.warning(f"Erro ao gerar áudio no cockpit: {e}")

    return {
        "text": resp_text,
        "audio_url": audio_url,
        "file_url": file_url
    }


@app.get("/api/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve os arquivos de voz MP3 gerados para o reprodutor e analisador 3D."""
    audio_path = os.path.join(brain.voice.temp_dir, filename)
    if os.path.exists(audio_path):
        return FileResponse(audio_path, media_type="audio/mpeg")
    return JSONResponse({"error": "Arquivo não encontrado"}, status_code=404)


@app.get("/api/files/{filename}")
async def get_generated_file(filename: str):
    """Serve arquivos e screenshots gerados pelo Periquito."""
    file_path = os.path.join(brain.voice.temp_dir, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return JSONResponse({"error": "Arquivo não encontrado"}, status_code=404)


@app.post("/api/services/discord/toggle")
async def toggle_discord():
    """Liga ou desliga o Bot do Discord com 1 clique."""
    if discord_mgr.is_running:
        res = discord_mgr.stop()
    else:
        res = discord_mgr.start()
    return res


@app.post("/api/tools/run")
async def run_tool(request: Request):
    """Executa ações rápidas no sistema operacional."""
    body = await request.json()
    action = body.get("action")

    if action == "qgis":
        msg = brain.tools.open_application("qgis")
        return {"message": msg}
    elif action == "rstudio":
        msg = brain.tools.open_application("rstudio")
        return {"message": msg}
    elif action == "screenshot":
        path = brain.tools.take_screenshot()
        if path:
            return {"message": "Captura de tela realizada!", "file_url": f"/api/files/{os.path.basename(path)}"}
        return {"message": "Falha ao tirar print."}
    elif action == "projects":
        msg = brain.tools.open_application("projetos")
        return {"message": msg}
    return {"message": "Ação desconhecida."}


# Monta arquivos estáticos da interface web
UI_DIR = os.path.join(BASE_DIR, "ui")
os.makedirs(UI_DIR, exist_ok=True)
app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")


def run_cockpit_server(port: int = 7860):
    """Inicia o servidor da Central de Comando."""
    print(f"==================================================")
    print(f"🦜 PERIQUITO AI - CENTRAL DE COMANDO INICIADA!")
    print(f"Acesse no navegador: http://localhost:{port}")
    print(f"==================================================")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    run_cockpit_server()
