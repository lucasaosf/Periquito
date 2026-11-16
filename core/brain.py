"""
Cérebro Unificado do Periquito AI (Multi-Engine & OpenJarvis Tools)
Orquestra o raciocínio híbrido (Gemini SDK oficial + Groq + Ollama), memória persistente, segurança e execução de ferramentas.
"""

import os
import re
import json
import logging
import requests
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "config", ".env")
load_dotenv(ENV_PATH)

from core.security import SecurityManager
from core.memory import MemoryManager
from core.tools import SystemTools, safe_math_eval
from core.voice import VoiceEngine

logger = logging.getLogger("PeriquitoBrain")


class PeriquitoBrain:
    def __init__(self):
        load_dotenv(ENV_PATH, override=True)
        self.security = SecurityManager()
        self.memory = MemoryManager()
        self.tools = SystemTools()
        self.voice = VoiceEngine()

        # Configurações de Motores de IA Multi-Engine
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
        self.groq_key = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip()

        # Inicializa cliente Gemini oficial se chave disponível
        self._gemini_client = None
        if self.gemini_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.gemini_key)
            except Exception as e:
                logger.warning(f"Não foi possível inicializar genai.Client: {e}")

    def _query_gemini(self, prompt: str, system_prompt: str) -> Optional[str]:
        """Consulta o Google Gemini usando o SDK oficial em alta velocidade."""
        if not self._gemini_client:
            return None
        from google.genai import types

        # Tenta o modelo ultra-rápido (gemini-3.1-flash-lite) ou o configurado
        models_to_try = [self.gemini_model, "gemini-3.5-flash", "gemini-3.8-flash"]
        # Remove duplicatas preservando ordem
        seen = set()
        models_ordered = [m for m in models_to_try if not (m in seen or seen.add(m))]

        for model_name in models_ordered:
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7,
                    max_output_tokens=700,
                )
                response = self._gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                logger.warning(f"Tentativa com Gemini ({model_name}) falhou: {e}")
                continue
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
                "model": self.groq_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 700
            }
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            if res.status_code == 200:
                data = res.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
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
        1. Se Groq disponível, testa primeiro para resposta instantânea
        2. Tenta Gemini (Google Gemini com raciocínio apurado)
        3. Tenta Ollama (backup local offline)
        """
        if self.groq_key:
            ans = self._query_groq(prompt, system_prompt)
            if ans:
                return ans, "Groq (Llama 3.3)"

        if self._gemini_client:
            ans = self._query_gemini(prompt, system_prompt)
            if ans:
                return ans, "Google Gemini"

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
        
        # O dono no Discord é o Play (Pedrinho)
        if is_owner:
            effective_name = "Play"
        else:
            effective_name = display_name or username or "Amigo"

        self.memory.log_message(channel, effective_name, "user", clean_text)
        lower = clean_text.lower()

        # 1. Checagem de Auto-aprendizado
        learned_msg = self.memory.auto_learn(clean_text, effective_name)
        if learned_msg:
            resp = f"🦜 {learned_msg}"
            self.memory.log_message(channel, "Periquito", "assistant", resp)
            return {"text": resp, "audio_file": None, "file": None}

        # 2. Segurança: Ações de Sistema Privilegiadas (Apenas o Play / Pedrinho pode)
        is_privileged_request = any(
            kw in lower for kw in self.security.restricted_keywords
        )
        if is_privileged_request and not is_owner:
            resp = (
                f"Olá {effective_name}! Eu sou o Periquito. Posso conversar com você normalmente na call ou no chat, "
                f"mas só tenho permissão para executar comandos, abrir programas ou mexer no computador "
                f"quando o Play (Pedrinho) autorizar!"
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
        system_prompt = (
            "Você é o Periquito, assistente de IA pessoal do servidor do Discord e do computador do Play (Pedrinho). "
            "Você é gente boa, bem-humorado, perspicaz, divertido e leal ao Play. "
            "O Play (pedrinho macaco) é o seu único chefe com permissão para dar ordens de sistema. "
            "Trate o Play com amizade e respeito. Trate os amigos dele na chamada com simpatia e bom humor. "
            "REGRA ABSOLUTA: NUNCA fale sobre placa de vídeo, peças de computador, hardware, Windows ou especificações técnicas a menos que perguntem especificamente sobre isso! "
            "Fale de forma 100% natural, dinâmica e direta (1 a 3 frases em conversas normais), como alguém conversando por voz com amigos. "
            "NÃO use listas de tópicos, bullets, asteriscos ou formatações visuais em bate-papo casual. "
            "Responda sempre em Português do Brasil com carisma e naturalidade."
        )

        multi_res = self._query_multi_engine(clean_text, system_prompt)
        if multi_res:
            llm_text, engine_name = multi_res
            resp = f"🦜 {llm_text}"
        else:
            # Fallback seguro caso os motores estejam indisponíveis
            resp = f"🦜 Fala, {effective_name}! Estou aqui com você. Como posso te ajudar agora?"

        self.memory.log_message(channel, "Periquito", "assistant", resp)
        return {"text": resp, "audio_file": None, "file": None}
