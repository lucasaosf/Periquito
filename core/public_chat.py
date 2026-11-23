"""
Chat Público Social do Periquito AI (Para Usuários Terceiros no Discord)
Totalmente isolado:
- Zero ferramentas MCP
- Zero acesso à memória OpenViking do Lucas
- Zero acesso ao sistema de arquivos do Windows ou histórico privado
"""

import logging
import requests
from typing import Optional

from config import config

logger = logging.getLogger("PublicChat")

SYSTEM_PROMPT = """Você é o Periquito, um assistente inteligente e prestativo em servidores do Discord.
Seu papel aqui é conversar, tirar dúvidas e ser simpático com os membros do servidor.
Você NÃO tem acesso a comandos de computador, arquivos privados, e-mails ou automações locais.
Responda sempre em português do Brasil de forma concisa, educada e bem-humorada."""


def answer_public_message(prompt: str) -> str:
    """Gera resposta social para terceiros usando provedor gratuito sem ferramentas."""
    # 1. Tenta Groq (rápido e gratuito)
    if config.models.groq_key:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.models.groq_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": config.models.groq_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.7
                },
                timeout=12
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"[PublicChat] Falha no Groq: {e}")

    # 2. Tenta Gemini Oficial se chave disponível
    if config.models.gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {config.models.gemini_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": config.models.gemini_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 500
                },
                timeout=12
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"[PublicChat] Falha no Gemini: {e}")

    # 3. Fallback: Ollama Local
    try:
        url = f"{config.models.ollama_url.rstrip('/')}/chat/completions"
        resp = requests.post(
            url,
            json={
                "model": config.models.ollama_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 500
            },
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"[PublicChat] Falha no Ollama: {e}")

    return "Olá! Sou o Periquito. No momento estou operando em modo de economia de energia. Como posso te ajudar?"
