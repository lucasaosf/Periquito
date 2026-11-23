"""
Ponte Unificada de Inteligência Artificial do Periquito AI (Brain Bridge)
Conecta os canais de entrada (Telegram, Discord, Alexa, Mic) ao cérebro:
- Concorrência protegida via asyncio.Lock()
- Injeção automática de contexto L0/L1 da Memória OpenViking
- Cascata de APIs gratuitas e fallback para Ollama Local
"""

import os
import shutil
import asyncio
import logging
import subprocess
import requests
from typing import Optional, Dict, Any

from config import config
from core.viking_memory import VikingMemory
from core.text_utils import truncate_output

logger = logging.getLogger("BrainBridge")


class PeriquitoBrain:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.memory = VikingMemory()

    async def ask(self, user_prompt: str, user_name: str = "Lucas", channel: str = "telegram") -> str:
        """
        Processa uma mensagem do administrador garantindo ordem e isolamento através de Lock.
        """
        async with self._lock:
            return await self._process_request(user_prompt, user_name, channel)

    async def _process_request(self, prompt: str, user_name: str, channel: str) -> str:
        # 1. Recupera contexto relevante de memória L0/L1 do OpenViking
        viking_context = await asyncio.to_thread(self.memory.get_relevant_context, prompt)

        system_instruction = (
            f"Você é o Periquito, o assistente pessoal de inteligência artificial de {user_name} no Windows.\n"
            f"Você tem controle sobre automação, ferramentas MCP, memória de longo prazo e pesquisa na web.\n"
            f"Responda sempre em português brasileiro de forma direta, prestativa e precisa.\n"
            f"{viking_context}\n"
        )

        full_prompt = f"{prompt}"

        # 2. Tenta executar via DeepSeek Harness (dsh CLI) se instalado
        dsh_bin = shutil.which("dsh")
        if dsh_bin:
            try:
                logger.info("Executando prompt através do dsh CLI...")
                res = await asyncio.to_thread(
                    subprocess.run,
                    ["dsh", "--prompt", full_prompt],
                    capture_output=True,
                    text=True,
                    timeout=45,
                    encoding="utf-8",
                    errors="replace"
                )
                if res.returncode == 0 and res.stdout.strip():
                    return truncate_output(res.stdout.strip())
            except Exception as e:
                logger.warning(f"Falha ao executar dsh: {e}. Recorrendo à cascata direta.")

        # 3. Cascata de APIs Gratuitas Diretas
        # Provedor 1: Groq Cloud (Llama 3.3 70B Versatile)
        if config.models.groq_key:
            try:
                resp = await asyncio.to_thread(
                    requests.post,
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {config.models.groq_key}", "Content-Type": "application/json"},
                    json={
                        "model": config.models.groq_model,
                        "messages": [
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": full_prompt}
                        ],
                        "max_tokens": 1500,
                        "temperature": 0.6
                    },
                    timeout=20
                )
                if resp.status_code == 200:
                    return truncate_output(resp.json()["choices"][0]["message"]["content"].strip())
            except Exception as e:
                logger.warning(f"Cascata Groq falhou: {e}")

        # Provedor 2: Google Gemini (AI Studio Free Tier)
        if config.models.gemini_key:
            try:
                url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
                resp = await asyncio.to_thread(
                    requests.post,
                    url,
                    headers={"Authorization": f"Bearer {config.models.gemini_key}", "Content-Type": "application/json"},
                    json={
                        "model": config.models.gemini_model,
                        "messages": [
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": full_prompt}
                        ],
                        "max_tokens": 1500
                    },
                    timeout=20
                )
                if resp.status_code == 200:
                    return truncate_output(resp.json()["choices"][0]["message"]["content"].strip())
            except Exception as e:
                logger.warning(f"Cascata Gemini falhou: {e}")

        # Provedor 3: SambaNova Cloud (Llama 3.1 70B)
        if config.models.sambanova_key:
            try:
                resp = await asyncio.to_thread(
                    requests.post,
                    "https://api.sambanova.ai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {config.models.sambanova_key}", "Content-Type": "application/json"},
                    json={
                        "model": config.models.sambanova_model,
                        "messages": [
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": full_prompt}
                        ],
                        "max_tokens": 1500
                    },
                    timeout=20
                )
                if resp.status_code == 200:
                    return truncate_output(resp.json()["choices"][0]["message"]["content"].strip())
            except Exception as e:
                logger.warning(f"Cascata SambaNova falhou: {e}")

        # Provedor 4: Ollama Local (100% Offline e Ilimitado)
        try:
            url = f"{config.models.ollama_url.rstrip('/')}/chat/completions"
            resp = await asyncio.to_thread(
                requests.post,
                url,
                json={
                    "model": config.models.ollama_model,
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": full_prompt}
                    ],
                    "max_tokens": 1500
                },
                timeout=30
            )
            if resp.status_code == 200:
                return truncate_output(resp.json()["choices"][0]["message"]["content"].strip())
        except Exception as e:
            logger.warning(f"Fallback Ollama falhou: {e}")

        return "⚠️ Não foi possível obter resposta de nenhum modelo no momento. Verifique sua conexão ou se o Ollama local está ativo."
