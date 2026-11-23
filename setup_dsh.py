"""
Script de Configuração e Provisionamento do DeepSeek Harness (dsh)
Gera automaticamente ~/.dsh/settings.yaml e ~/.dsh/.credentials.yaml
a partir das variáveis do seu .env local.
"""

import os
import sys
import yaml
from pathlib import Path

from config import config, BASE_DIR, WORKSPACE_DIR

DSH_DIR = Path.home() / ".dsh"


def setup_dsh_configuration():
    DSH_DIR.mkdir(parents=True, exist_ok=True)
    settings_file = DSH_DIR / "settings.yaml"
    credentials_file = DSH_DIR / ".credentials.yaml"

    python_executable = sys.executable
    mcp_server_script = str(BASE_DIR / "mcp_server.py")
    workspace_path = str(WORKSPACE_DIR.resolve())

    # Estrutura do settings.yaml
    settings_data = {
        "profile": "minimal",
        "providers": {
            "gemini": {
                "type": "openai-completions",
                "baseURL": "https://generativelanguage.googleapis.com/v1beta/openai/",
                "model": config.models.gemini_model,
            },
            "groq": {
                "type": "openai-completions",
                "baseURL": "https://api.groq.com/openai/v1",
                "model": config.models.groq_model,
            },
            "sambanova": {
                "type": "openai-completions",
                "baseURL": "https://api.sambanova.ai/v1",
                "model": config.models.sambanova_model,
            },
            "nvidia": {
                "type": "openai-completions",
                "baseURL": "https://integrate.api.nvidia.com/v1",
                "model": config.models.nvidia_model,
            },
            "openrouter": {
                "type": "openai-completions",
                "baseURL": "https://openrouter.ai/api/v1",
                "model": config.models.openrouter_model,
            },
            "mistral": {
                "type": "openai-completions",
                "baseURL": "https://api.mistral.ai/v1",
                "model": config.models.mistral_model,
            },
            "github": {
                "type": "openai-completions",
                "baseURL": "https://models.github.ai/inference",
                "model": config.models.github_model,
            },
            "ollama": {
                "type": "openai-completions",
                "baseURL": config.models.ollama_url,
                "model": config.models.ollama_model,
            }
        },
        "mcpServers": {
            "periquito": {
                "command": python_executable,
                "args": [mcp_server_script],
                "cwd": workspace_path
            }
        }
    }

    # Estrutura do .credentials.yaml
    credentials_data = {
        "gemini": config.models.gemini_key,
        "groq": config.models.groq_key,
        "sambanova": config.models.sambanova_key,
        "nvidia": config.models.nvidia_key,
        "openrouter": config.models.openrouter_key,
        "mistral": config.models.mistral_key,
        "github": config.models.github_token,
        "ollama": "ollama-local"
    }

    with open(settings_file, "w", encoding="utf-8") as f:
        yaml.dump(settings_data, f, sort_keys=False, allow_unicode=True)

    with open(credentials_file, "w", encoding="utf-8") as f:
        yaml.dump(credentials_data, f, sort_keys=False, allow_unicode=True)

    print(f"✅ Configurações do dsh geradas com sucesso!")
    print(f"   📁 {settings_file}")
    print(f"   📁 {credentials_file}")


if __name__ == "__main__":
    setup_dsh_configuration()
