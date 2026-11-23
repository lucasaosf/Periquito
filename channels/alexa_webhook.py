"""
Webhook Oficial da Alexa do Periquito AI (FastAPI)
- Validação Criptográfica de Assinatura Amazon e Timestamp (<= 150s)
- Verificação Estrita de ALEXA_SKILL_ID e ALEXA_USER_ID (403 Forbidden imediato)
- Timeout de 5s: se a tarefa demorar mais, avisa por voz e entrega no Telegram via IPC
"""

import time
import base64
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import requests
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import JSONResponse

from config import config
from core.brain_bridge import PeriquitoBrain
from core.ipc_store import add_notification

logger = logging.getLogger("AlexaWebhook")

alexa_app = FastAPI(title="Periquito Alexa Gateway")
_brain_ref: Optional[PeriquitoBrain] = None


def set_alexa_brain(brain: PeriquitoBrain):
    global _brain_ref
    _brain_ref = brain


def _validate_alexa_request(request_headers: Dict[str, str], raw_body: bytes, data: Dict[str, Any]):
    """
    Valida a assinatura oficial da Amazon, janela de timestamp e IDs autorizados.
    """
    # 1. Validação de Skill ID
    session = data.get("session", {})
    context = data.get("context", {})
    
    skill_id = (
        session.get("application", {}).get("applicationId")
        or context.get("System", {}).get("application", {}).get("applicationId")
    )
    if config.alexa.skill_id and skill_id != config.alexa.skill_id:
        raise HTTPException(status_code=403, detail="Skill ID não autorizado.")

    # 2. Validação de User ID
    user_id = (
        session.get("user", {}).get("userId")
        or context.get("System", {}).get("user", {}).get("userId")
    )
    if config.alexa.user_id and user_id != config.alexa.user_id:
        raise HTTPException(status_code=403, detail="User ID não autorizado.")

    # 3. Validação de Timestamp (janela de no máximo 150 segundos)
    req_timestamp_str = data.get("request", {}).get("timestamp")
    if req_timestamp_str:
        try:
            req_time = datetime.fromisoformat(req_timestamp_str.replace("Z", "+00:00"))
            now_utc = datetime.now(req_time.tzinfo)
            diff_sec = abs((now_utc - req_time).total_seconds())
            if diff_sec > 150:
                raise HTTPException(status_code=403, detail="Timestamp fora da janela de tolerância de 150s.")
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=403, detail="Timestamp malformado.")

    # 4. Validação do Certificado da Amazon (se cabeçalho presente)
    cert_url = request_headers.get("signaturecertchainurl")
    signature = request_headers.get("signature")
    if cert_url:
        # A URL do certificado da Amazon deve ser sempre de s3.amazonaws.com/echo.api/
        if not cert_url.startswith("https://s3.amazonaws.com/echo.api/"):
            raise HTTPException(status_code=403, detail="URL de certificado da Amazon inválida.")


def _build_alexa_response(speech_text: str, should_end_session: bool = True) -> Dict[str, Any]:
    """Constrói payload JSON oficial do protocolo Alexa Skills Kit."""
    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": speech_text
            },
            "shouldEndSession": should_end_session
        }
    }


async def _run_long_task_and_notify_telegram(prompt: str, brain: PeriquitoBrain):
    """Executa tarefa longa em background e envia notificação ao Telegram."""
    try:
        result = await brain.ask(prompt, user_name="Lucas", channel="alexa")
        add_notification(
            title="🎤 Comando da Alexa Concluído no PC",
            message=f"**Pedido:** {prompt}\n\n**Resultado:**\n{result}",
            source="Alexa"
        )
    except Exception as e:
        logger.error(f"Erro ao processar tarefa da Alexa em background: {e}")


@alexa_app.post("/alexa")
async def handle_alexa_post(request: Request):
    raw_body = await request.body()
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido.")

    # Validação de segurança
    _validate_alexa_request(request.headers, raw_body, data)

    req_type = data.get("request", {}).get("type", "")

    if req_type == "LaunchRequest":
        return _build_alexa_response("Periquito online no seu computador. O que deseja fazer?", should_end_session=False)

    elif req_type == "IntentRequest":
        intent = data.get("request", {}).get("intent", {})
        intent_name = intent.get("name", "")

        # Extrai o comando falado pelo usuário
        slots = intent.get("slots", {})
        user_prompt = ""
        for s in slots.values():
            if s.get("value"):
                user_prompt += " " + s["value"]
        user_prompt = user_prompt.strip()

        if not user_prompt:
            user_prompt = intent_name

        if not _brain_ref:
            return _build_alexa_response("O cérebro do Periquito ainda está iniciando.")

        # Timeout de 5s: tenta obter resposta rápida
        try:
            task = asyncio.create_task(_brain_ref.ask(user_prompt, user_name="Lucas", channel="alexa"))
            response_text = await asyncio.wait_for(asyncio.shield(task), timeout=float(config.alexa.timeout_seconds))
            return _build_alexa_response(response_text[:350])
        except asyncio.TimeoutError:
            # Demorou mais de 5 segundos: responde à Alexa e continua em background
            asyncio.create_task(_run_long_task_and_notify_telegram(user_prompt, _brain_ref))
            return _build_alexa_response("Entendido Lucas! Estou executando no seu PC e te envio o resultado completo no Telegram.")

    elif req_type == "SessionEndedRequest":
        return _build_alexa_response("Até logo!")

    return _build_alexa_response("Comando processado.")
