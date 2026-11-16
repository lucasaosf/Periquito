"""
Cérebro Unificado do Periquito AI (Multi-Engine & OpenJarvis Tools)
Orquestra o raciocínio híbrido (Gemini + Groq + Ollama), memória persistente, segurança e execução de ferramentas.
"""

import os
import re
import json
import logging
import requests
from typing import Dict, Any, Optional, Tuple

from core.security import SecurityManager
from core.memory import MemoryManager
from core.tools import SystemTools, safe_math_eval
from core.voice import VoiceEngine

logger = logging.getLogger("PeriquitoBrain")


class PeriquitoBrain:
    def __init__(self):
        self.security = SecurityManager()
        self.memory = MemoryManager()
        self.tools = SystemTools()
        self.voice = VoiceEngine()

        # Configurações de Motores de IA Multi-Engine
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.groq_key = os.getenv("GROQ_API_KEY", "").strip()
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip()

    def _query_gemini(self, prompt: str, system_prompt: str) -> Optional[str]:
        """Consulta a API do Google Gemini 2.0 Flash."""
        if not self.gemini_key:
            return None
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}"
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": prompt}]}
                ],
                "systemInstruction": {
                    "parts": [{"text": system_prompt}]
                },
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 1000
                }
            }
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
            else:
                logger.warning(f"Gemini API returned status {res.status_code}: {res.text}")
        except Exception as e:
            logger.warning(f"Erro ao consultar Gemini: {e}")
        return None

    def _query_groq(self, prompt: str, system_prompt: str) -> Optional[str]:
        """Consulta a API ultra-rápida do Groq (Llama 3.3 70B)."""
        if not self.groq_key:
            return None
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.groq_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 1000
            }
            res = requests.post(url, headers=headers, json=payload, timeout=12)
            if res.status_code == 200:
                data = res.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
            else:
                logger.warning(f"Groq API returned status {res.status_code}: {res.text}")
        except Exception as e:
            logger.warning(f"Erro ao consultar Groq: {e}")
        return None

    def _query_ollama(self, prompt: str, system_prompt: str) -> Optional[str]:
        """Consulta o Ollama local na GTX 1070."""
        try:
            res = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False
                },
                timeout=12
            )
            if res.status_code == 200:
                return res.json().get("response", "").strip()
        except Exception:
            pass
        return None

    def _query_multi_engine(self, prompt: str, system_prompt: str) -> Optional[Tuple[str, str]]:
        """
        Orquestrador de IA Híbrida / Roteamento Multi-Engine:
        1. Tenta Groq (ultra-rápido, ~200ms) se disponível
        2. Tenta Gemini (profundidade analítica superior) se disponível
        3. Tenta Ollama (backup local offline)
        Retorna (texto_resposta, nome_do_motor)
        """
        # Se Groq configurado, testa velocidade primeiro
        if self.groq_key:
            ans = self._query_groq(prompt, system_prompt)
            if ans:
                return ans, "Groq (Llama 3.3)"

        # Se Gemini configurado, consulta
        if self.gemini_key:
            ans = self._query_gemini(prompt, system_prompt)
            if ans:
                return ans, "Google Gemini 2.0"

        # Fallback local Ollama
        ans = self._query_ollama(prompt, system_prompt)
        if ans:
            return ans, "Ollama Local"

        return None

    def process_message(
        self,
        text: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        display_name: Optional[str] = None,
        channel: str = "console"
    ) -> Dict[str, Any]:
        """Processa mensagens recebidas em qualquer canal com roteamento inteligente."""
        clean_text = text.strip()
        if not clean_text:
            return {"text": "🦜 Na escuta! O que manda?", "audio_file": None, "file": None}

        is_owner = self.security.is_owner(user_id=user_id, username=username, display_name=display_name)
        
        # Recupera nome preferido
        preferred_name = self.memory.get_fact("nome_preferido")
        if is_owner or channel == "console":
            effective_name = preferred_name or "Lucas Aosf"
        else:
            effective_name = display_name or username or "Visitante"

        self.memory.log_message(channel, effective_name, "user", clean_text)
        lower = clean_text.lower()

        # 1. Checagem de Auto-aprendizado
        learned_msg = self.memory.auto_learn(clean_text, effective_name)
        if learned_msg:
            resp = f"🦜 {learned_msg}"
            self.memory.log_message(channel, "Periquito", "assistant", resp)
            return {"text": resp, "audio_file": None, "file": None}

        # 2. Segurança: Ações de Sistema Privilegiadas
        is_privileged_request = any(
            kw in lower for kw in self.security.restricted_keywords
        )
        if is_privileged_request and not is_owner:
            resp = (
                f"Olá {effective_name}! Eu sou o Periquito. Posso conversar com você normalmente, "
                f"mas só tenho permissão para executar comandos, abrir programas ou acessar o computador "
                f"quando o Lucas Aosf autorizar!"
            )
            self.memory.log_message(channel, "Periquito", "assistant", resp)
            return {"text": resp, "audio_file": None, "file": None}

        # 3. Ferramentas Integradas (OpenJarvis + Sistema Local)
        
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
                f"Tudo operando suave e em segurança!"
            )
            self.memory.log_message(channel, "Periquito", "assistant", resp)
            return {"text": resp, "audio_file": None, "file": None}

        # Clima / Previsão do tempo
        if lower.startswith("clima") or lower.startswith("tempo em") or "previsão do tempo" in lower or "como tá o tempo" in lower:
            city = re.sub(r"^(clima em|tempo em|previsão do tempo em|como tá o tempo em|clima|tempo)\s*", "", lower).strip()
            weather_info = self.tools.get_weather(city)
            resp = f"🦜 **Previsão do Tempo:** {weather_info}"
            self.memory.log_message(channel, "Periquito", "assistant", resp)
            return {"text": resp, "audio_file": None, "file": None}

        # Calculadora Segura (OpenJarvis AST)
        if lower.startswith("calcula ") or lower.startswith("quanto é ") or lower.startswith("calcule "):
            expr = re.sub(r"^(calcula|calcule|quanto é)\s*", "", lower).strip().rstrip("?")
            calc_res = safe_math_eval(expr)
            resp = f"🦜 O resultado de `{expr}` é: **{calc_res}**"
            self.memory.log_message(channel, "Periquito", "assistant", resp)
            return {"text": resp, "audio_file": None, "file": None}

        # Busca na Web em tempo real (OpenJarvis DuckDuckGo)
        if lower.startswith("pesquisa ") or lower.startswith("pesquise ") or lower.startswith("busca na web ") or lower.startswith("pesquisar "):
            query = re.sub(r"^(pesquisa|pesquise|busca na web|pesquisar)\s*", "", lower).strip()
            results = self.tools.web_search(query)
            resp = f"🦜 **Resultados da Web para:** *{query}*\n\n{results}"
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

        # 4. Raciocínio Geral via Multi-Engine LLM
        memory_context = self.memory.get_context_summary()
        system_prompt = (
            "Você é o Periquito, assistente de IA pessoal nativo que opera no computador do Lucas Aosf. "
            "Você é ágil, altamente inteligente, leal ao Lucas Aosf, bem-humorado e prestativo. "
            "Você tem ferramentas integradas (busca na web, status do hardware, calculadora segura, controle de apps). "
            "Responda sempre em Português do Brasil com clareza e naturalidade. "
            f"{memory_context}"
        )

        multi_res = self._query_multi_engine(clean_text, system_prompt)
        if multi_res:
            llm_text, engine_name = multi_res
            resp = f"🦜 {llm_text}"
        else:
            # Fallback amigável caso nenhuma chave de IA tenha sido inserida ainda
            if any(w in lower for w in ["tudo na paz", "tudo bem", "como vai", "como você tá", "como voce ta", "beleza"]):
                resp = f"🦜 Tudo 100% na paz por aqui, {effective_name}! Monitorando o computador e pronto pras ordens."
            elif any(w in lower for w in ["tá na escuta", "ta na escuta", "na escuta", "tá aí", "ta ai"]):
                resp = f"🦜 Na escuta total, {effective_name}! Alto e claro."
            elif any(w in lower for w in ["salve", "fala periquito", "e aí", "e ai", "olá", "ola", "bom dia", "boa tarde", "boa noite"]):
                resp = f"🦜 Salve, {effective_name}! Tudo certo por aqui. Pode mandar o comando que eu executo."
            elif any(w in lower for w in ["obrigado", "valeu", "show", "perfeito", "tks"]):
                resp = f"🦜 Tamo junto, {effective_name}! Qualquer coisa é só chamar."
            else:
                resp = (
                    f"🦜 Fala, {effective_name}! Estou ativo e as ferramentas já estão funcionando:\n"
                    f"• `pesquisa <termo>` para buscar na web\n"
                    f"• `calcula <expressao>` para matemática\n"
                    f"• `clima <cidade>` para previsão do tempo\n"
                    f"• `status` para ver CPU, RAM e GTX 1070\n"
                    f"Para eu bater papo livre e raciocinar sobre qualquer assunto, basta adicionar sua chave de IA no arquivo .env!"
                )

        self.memory.log_message(channel, "Periquito", "assistant", resp)
        return {"text": resp, "audio_file": None, "file": None}
