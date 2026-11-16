"""
Cérebro Unificado do Periquito AI
Orquestra o raciocínio, memória persistente, segurança e execução de ferramentas.
"""

import os
import re
import json
import logging
import requests
from typing import Dict, Any, Optional, Tuple

from core.security import SecurityManager
from core.memory import MemoryManager
from core.tools import SystemTools
from core.voice import VoiceEngine

logger = logging.getLogger("PeriquitoBrain")

class PeriquitoBrain:
    def __init__(self):
        self.security = SecurityManager()
        self.memory = MemoryManager()
        self.tools = SystemTools()
        self.voice = VoiceEngine()

        # Configurações do modelo de linguagem (se disponível)
        self.llm_provider = os.getenv("LLM_PROVIDER", "ollama")
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    def _query_local_llm(self, prompt: str, system_prompt: str) -> Optional[str]:
        """Tenta consultar o Ollama se estiver rodando localmente."""
        try:
            res = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False
                },
                timeout=10
            )
            if res.status_code == 200:
                return res.json().get("response", "").strip()
        except Exception:
            pass
        return None

    def process_message(
        self,
        text: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        display_name: Optional[str] = None,
        channel: str = "console"
    ) -> Dict[str, Any]:
        """
        Processa uma mensagem recebida de qualquer canal (Discord, Telegram ou Console).
        Retorna um dicionário com a resposta em texto, áudio opcional e arquivos anexos.
        """
        clean_text = text.strip()
        is_owner = self.security.is_owner(user_id=user_id, username=username, display_name=display_name)
        effective_name = display_name or username or "Usuário"

        # Registrar no histórico de conversas
        self.memory.log_message(channel, effective_name, "user", clean_text)

        # 1. Checar se é uma instrução de aprendizado ("lembre-se que...", "anote que...")
        learned_msg = self.memory.auto_learn(clean_text, effective_name)
        if learned_msg:
            resp = f"🦜 Entendido, {effective_name}! {learned_msg}"
            self.memory.log_message(channel, "Periquito", "assistant", resp)
            return {"text": resp, "audio_file": None, "file": None}

        # 2. Verificação de Ações Privilegiadas no Sistema
        is_privileged_request = any(
            kw in clean_text.lower() for kw in self.security.restricted_keywords
        )

        # Se for comando de sistema e NÃO for o Lucas:
        if is_privileged_request and not is_owner:
            resp = (
                f"Olá {effective_name}! Eu sou o Periquito. Posso conversar com você normalmente, "
                f"mas só tenho permissão para executar comandos, abrir programas ou acessar o computador "
                f"quando o Lucas (Macaco Opressor) autorizar!"
            )
            self.memory.log_message(channel, "Periquito", "assistant", resp)
            return {"text": resp, "audio_file": None, "file": None}

        # 3. Execução de Ferramentas Nativas (Quando autorizado pelo Lucas)
        lower = clean_text.lower()

        # Status do computador
        if any(w in lower for w in ["status", "hardware", "cpu", "memoria", "memória", "disco", "como tá o pc", "como esta o pc"]):
            status = self.tools.get_system_status()
            d_c = status["discos"].get("C:", {})
            d_d = status["discos"].get("D:", {})
            resp = (
                f"🦜 **Status do PC do Lucas:**\n"
                f"• **Processador (CPU):** {status['cpu_percent']}%\n"
                f"• **Memória RAM:** {status['ram_usada_gb']} GB usados de {status['ram_total_gb']} GB ({status['ram_percent']}%)\n"
                f"• **Placa de Vídeo:** {status['gpu']}\n"
                f"• **Disco C:** {d_c.get('livre_gb', 0)} GB livres de {d_c.get('total_gb', 0)} GB ({d_c.get('percent_livre', 0)}% livre)\n"
                f"• **Disco D:** {d_d.get('livre_gb', 0)} GB livres de {d_d.get('total_gb', 0)} GB ({d_d.get('percent_livre', 0)}% livre)\n"
                f"Tudo rodando suave e em segurança!"
            )
            self.memory.log_message(channel, "Periquito", "assistant", resp)
            return {"text": resp, "audio_file": None, "file": None}

        # Abrir programas
        if lower.startswith("abrir ") or lower.startswith("abre o ") or lower.startswith("inicia o ") or lower.startswith("iniciar "):
            app_target = re.sub(r"^(abrir|abre o|inicia o|iniciar)\s+", "", lower).strip()
            resp = self.tools.open_application(app_target)
            self.memory.log_message(channel, "Periquito", "assistant", resp)
            return {"text": f"🦜 {resp}", "audio_file": None, "file": None}

        # Listar projetos
        if any(w in lower for w in ["quais projetos", "listar projetos", "meus projetos", "pasta projetos"]):
            resp = self.tools.list_projects()
            self.memory.log_message(channel, "Periquito", "assistant", resp)
            return {"text": f"🦜 {resp}", "audio_file": None, "file": None}

        # Print da tela
        if any(w in lower for w in ["tira um print", "print da tela", "screenshot", "foto da tela"]):
            img_path = self.tools.take_screenshot()
            if img_path:
                resp = "🦜 Aqui está a captura de tela do seu computador!"
                self.memory.log_message(channel, "Periquito", "assistant", resp)
                return {"text": resp, "audio_file": None, "file": img_path}
            else:
                resp = "🦜 Não consegui tirar o print da tela no momento."
                return {"text": resp, "audio_file": None, "file": None}

        # 4. Resposta Geral de Conversação (Com contexto de memória)
        memory_context = self.memory.get_context_summary()
        system_prompt = (
            "Você é o Periquito, um assistente de IA pessoal nativo que roda no computador do Lucas Aosf. "
            "Você é ágil, prestativo, bem-humorado e inteligente. "
            "Responda sempre em Português do Brasil com clareza. "
            f"{memory_context}"
        )

        llm_response = self._query_local_llm(clean_text, system_prompt)
        if llm_response:
            resp = f"🦜 {llm_response}"
        else:
            # Fallback inteligente quando nenhum modelo pesado de LLM está em execução
            resp = (
                f"🦜 Fala, {effective_name}! Estou ativo e monitorando o computador. "
                f"Você pode me pedir para verificar o status do PC, abrir programas (QGIS, RStudio, Steam, Chrome), "
                f"tirar print da tela, consultar projetos ou guardar coisas na memória permanente!"
            )

        self.memory.log_message(channel, "Periquito", "assistant", resp)
        return {"text": resp, "audio_file": None, "file": None}
