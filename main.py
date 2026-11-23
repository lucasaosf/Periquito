"""
=============================================================================
🦜 PERIQUITO AI - ORQUESTRADOR UNIFICADO MULTICANAL
=============================================================================
Inicializa e roda de forma concorrente e assíncrona:
1. Telegram Bot (Admin-Only + Botões HITL + Worker IPC)
2. Discord Bot (Social para Terceiros + Controle Privado em DM)
3. Alexa Webhook (FastAPI em porta 8000 + Timeout 5s + Fallback Telegram)
4. Microfone Local (Atalho Global pynput + Faster-Whisper + Edge-TTS)
=============================================================================
"""

import sys
import asyncio
import logging
import uvicorn
from pathlib import Path

from config import config, INBOX_DIR, OUTBOX_DIR, VIKING_DATA_DIR, IPC_DIR
from core.ipc_store import init_ipc_db
from core.brain_bridge import PeriquitoBrain
from channels.telegram_bot import TelegramChannel
from channels.discord_bot import DiscordChannel
from channels.alexa_webhook import alexa_app, set_alexa_brain
from channels.web_cockpit import run_cockpit_server_async, set_cockpit_brain
from channels.local_mic import LocalMicChannel

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.base_dir / "periquito.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("PeriquitoMain")


def ensure_workspace():
    """Garante que as pastas de trabalho existam."""
    for d in [INBOX_DIR, OUTBOX_DIR, VIKING_DATA_DIR, IPC_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    init_ipc_db()


async def run_alexa_server():
    """Roda servidor FastAPI para o Webhook da Alexa em segundo plano."""
    cfg = uvicorn.Config(
        app=alexa_app,
        host="0.0.0.0",
        port=config.alexa.port,
        log_level="warning"
    )
    server = uvicorn.Server(cfg)
    logger.info(f"🌐 [Alexa Webhook] Ativo em http://0.0.0.0:{config.alexa.port}/alexa")
    await server.serve()


async def main():
    print("""
    =====================================================================
    🦜 PERIQUITO AI - ASSISTENTE AUTÔNOMO PESSOAL (WINDOWS)
    100% CUSTO ZERO | DEEPSEEK HARNESS | OPENVIKING | BLINDADO
    =====================================================================
    """)

    ensure_workspace()

    brain = PeriquitoBrain()
    set_alexa_brain(brain)
    set_cockpit_brain(brain)

    telegram_channel = TelegramChannel(brain)
    discord_channel = DiscordChannel(brain)
    local_mic_channel = LocalMicChannel(brain)

    loop = asyncio.get_running_loop()
    local_mic_channel.start(loop)

    try:
        await asyncio.gather(
            telegram_channel.start(),
            discord_channel.start(),
            run_alexa_server(),
            run_cockpit_server_async(port=7860)
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("🛑 Encerrando Periquito AI com segurança...")
    finally:
        local_mic_channel.stop()
        await telegram_channel.stop()
        await discord_channel.stop()
        logger.info("✅ Todos os canais foram desativados.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPrograma finalizado.")
