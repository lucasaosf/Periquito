"""
Módulo de Segurança e Controle de Acesso do Periquito AI
Garante a integridade do sistema operacional e proteção contra vazamento de dados.
"""

import os
import logging
from typing import List, Optional

logger = logging.getLogger("PeriquitoSecurity")

# Nomes padrão de fallback (os nomes reais ficam protegidos no config/.env)
DEFAULT_OWNER_NAMES = [
    "admin",
    "lucas",
    "lucasaosf"
]

class SecurityManager:
    def __init__(self):
        self.owner_id_discord = os.getenv("DISCORD_OWNER_ID", "").strip()
        self.owner_id_telegram = os.getenv("TELEGRAM_OWNER_CHAT_ID", "").strip()
        
        env_names = os.getenv("DISCORD_OWNER_NAMES", "")
        if env_names:
            self.owner_names = [n.strip().lower() for n in env_names.split(",") if n.strip()]
        else:
            self.owner_names = DEFAULT_OWNER_NAMES

        # Comandos e palavras-chave restritas exclusivamente ao proprietário
        self.restricted_keywords = [
            "executar", "run", "cmd", "powershell", "abrir", "fechar", "kill",
            "desligar", "reiniciar", "apagar", "deletar", "remover", "instalar",
            "mapa", "qgis", "rstudio", "disco", "memoria", "limpar", "status"
        ]

    def is_owner(self, user_id: Optional[str] = None, username: Optional[str] = None, display_name: Optional[str] = None) -> bool:
        """Verifica se o usuário é o Lucas (proprietário)."""
        # 1. Checagem por ID numérico estrito
        if user_id:
            s_id = str(user_id).strip()
            if self.owner_id_discord and s_id == self.owner_id_discord:
                return True
            if self.owner_id_telegram and s_id == self.owner_id_telegram:
                return True

        # 2. Checagem por nome de usuário e apelido
        candidates = []
        if username:
            candidates.append(username.lower().strip())
        if display_name:
            candidates.append(display_name.lower().strip())

        for c in candidates:
            for owner in self.owner_names:
                if owner in c:
                    return True

        return False

    def can_execute_action(self, user_id: Optional[str], username: Optional[str], display_name: Optional[str], action_type: str = "system") -> bool:
        """Determina se o usuário pode disparar ações privilegiadas no PC."""
        is_adm = self.is_owner(user_id=user_id, username=username, display_name=display_name)
        if not is_adm:
            logger.warning(f"Tentativa de ação privilegiada bloqueada! Usuário: {username} ({user_id}) - Ação: {action_type}")
        return is_adm

    def sanitize_input(self, text: str) -> str:
        """Remove caracteres potencialmente perigosos para evitar injeções arbitrárias de shell."""
        # Impede encadeamento malicioso
        blocked_chars = [";", "&&", "||", "`", "$("]
        sanitized = text
        for char in blocked_chars:
            if char in sanitized:
                sanitized = sanitized.replace(char, " ")
        return sanitized.strip()
