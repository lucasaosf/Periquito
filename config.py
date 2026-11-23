"""
Configurações Globais Tipadas do Periquito AI
Carrega e valida variáveis de ambiente do .env com valores padrão seguros.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Set
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR / "workspace"
INBOX_DIR = WORKSPACE_DIR / "inbox"
OUTBOX_DIR = WORKSPACE_DIR / "outbox"
VIKING_DATA_DIR = WORKSPACE_DIR / "viking_data"
IPC_DIR = WORKSPACE_DIR / "ipc"
IPC_DB_PATH = IPC_DIR / "periquito.db"

# Carrega .env com prioridade na raiz do projeto
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file, override=True)
else:
    alt_env = BASE_DIR / "config" / ".env"
    if alt_env.exists():
        load_dotenv(dotenv_path=alt_env, override=True)


def _split_str_to_set(val: str) -> Set[str]:
    if not val:
        return set()
    return {item.strip() for item in val.split(",") if item.strip()}


def _split_str_to_int_set(val: str) -> Set[int]:
    if not val:
        return set()
    result = set()
    for item in val.split(","):
        item = item.strip()
        if item.isdigit():
            result.add(int(item))
    return result


@dataclass
class ModelConfig:
    gemini_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    groq_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    sambanova_key: str = os.getenv("SAMBANOVA_API_KEY", "")
    sambanova_model: str = os.getenv("SAMBANOVA_MODEL", "Meta-Llama-3.1-70B-Instruct")
    nvidia_key: str = os.getenv("NVIDIA_NIM_API_KEY", "")
    nvidia_model: str = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
    openrouter_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
    mistral_key: str = os.getenv("MISTRAL_API_KEY", "")
    mistral_model: str = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    github_model: str = os.getenv("GITHUB_MODEL", "gpt-4o-mini")
    ollama_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")


@dataclass
class VikingConfig:
    provider_mode: str = os.getenv("VIKING_PROVIDER_MODE", "gemini_free")  # "gemini_free" ou "ollama_local"
    storage_dir: Path = VIKING_DATA_DIR


@dataclass
class TelegramConfig:
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    admin_id: int = int(os.getenv("TELEGRAM_ADMIN_ID", "0")) if os.getenv("TELEGRAM_ADMIN_ID", "0").isdigit() else 0


@dataclass
class DiscordConfig:
    bot_token: str = os.getenv("DISCORD_BOT_TOKEN", "")
    admin_id: int = int(os.getenv("DISCORD_ADMIN_ID", "0")) if os.getenv("DISCORD_ADMIN_ID", "0").isdigit() else 0
    private_channel_ids: Set[int] = field(default_factory=lambda: _split_str_to_int_set(os.getenv("DISCORD_PRIVATE_CHANNEL_IDS", "")))


@dataclass
class AlexaConfig:
    skill_id: str = os.getenv("ALEXA_SKILL_ID", "")
    user_id: str = os.getenv("ALEXA_USER_ID", "")
    port: int = int(os.getenv("ALEXA_PORT", "8000"))
    timeout_seconds: int = int(os.getenv("ALEXA_WEBHOOK_TIMEOUT_SECONDS", "5"))


@dataclass
class EmailConfig:
    user: str = os.getenv("EMAIL_USER", "")
    app_password: str = os.getenv("EMAIL_APP_PASSWORD", "")
    imap_server: str = os.getenv("EMAIL_IMAP_SERVER", "imap.gmail.com")
    smtp_server: str = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
    trusted_contacts: Set[str] = field(default_factory=lambda: {c.lower() for c in _split_str_to_set(os.getenv("EMAIL_TRUSTED_CONTACTS", ""))})


@dataclass
class LocalMicConfig:
    hotkey: str = os.getenv("LOCAL_MIC_HOTKEY", "<ctrl>+<alt>+p")
    voice_name: str = os.getenv("VOICE_NAME", "pt-BR-FranciscaNeural")
    whisper_model: str = os.getenv("WHISPER_MODEL", "small")


@dataclass
class AppConfig:
    base_dir: Path = BASE_DIR
    workspace_dir: Path = WORKSPACE_DIR
    inbox_dir: Path = INBOX_DIR
    outbox_dir: Path = OUTBOX_DIR
    viking_data_dir: Path = VIKING_DATA_DIR
    ipc_dir: Path = IPC_DIR
    ipc_db_path: Path = IPC_DB_PATH
    models: ModelConfig = field(default_factory=ModelConfig)
    viking: VikingConfig = field(default_factory=VikingConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    alexa: AlexaConfig = field(default_factory=AlexaConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    local_mic: LocalMicConfig = field(default_factory=LocalMicConfig)


# Instância global padrão
config = AppConfig()
