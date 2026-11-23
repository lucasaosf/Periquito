"""
Módulo de Segurança e Controle de Acesso do Periquito AI
Garante a integridade do sistema operacional e proteção contra vazamento de dados.
"""

import os
import logging
from typing import List, Optional

logger = logging.getLogger("PeriquitoSecurity")

# Nomes autorizados como proprietário (Lucas / Play / pedrinho macaco)
DEFAULT_OWNER_NAMES = [
    "pedrinho macaco",
    "pedrinho",
    "play",
    "lucas",
    "lucasaosf",
    "macaco opressor",
    "anakin opressor"
]

class SecurityManager:
    def __init__(self):
        self.owner_id_discord = os.getenv("DISCORD_OWNER_ID", "").strip()
        self.owner_id_telegram = os.getenv("TELEGRAM_OWNER_CHAT_ID", "").strip()
        
        # Lista adicional de IDs numéricos autorizados
        env_owner_ids = os.getenv("OWNER_IDS", "")
        self.owner_ids = [i.strip() for i in env_owner_ids.split(",") if i.strip()]

        # Usernames exatos autorizados (opcional, configurado via .env)
        env_names = os.getenv("DISCORD_OWNER_NAMES", "")
        if env_names:
            self.strict_owner_usernames = [n.strip().lower() for n in env_names.split(",") if n.strip()]
        else:
            self.strict_owner_usernames = ["lucasaosf"]

        # Comandos e palavras-chave restritas exclusivamente ao proprietário
        self.restricted_keywords = [
            "executar", "run", "cmd", "powershell", "abrir", "fechar", "kill",
            "desligar", "reiniciar", "apagar", "deletar", "remover", "instalar",
            "mapa", "qgis", "rstudio", "disco", "memoria", "limpar", "status"
        ]

    def is_owner(self, user_id: Optional[str] = None, username: Optional[str] = None, display_name: Optional[str] = None) -> bool:
        """
        Verifica se o usuário é o proprietário com validação segura de identidade.
        Previne forjamento por apelido (display_name spoofing).
        """
        # 1. Checagem por ID de usuário estrito
        if user_id:
            s_id = str(user_id).strip()
            # Acessos locais no PC do Lucas
            if s_id in ["cockpit_user", "console_user", "local_user"]:
                return True
            if self.owner_id_discord and s_id == self.owner_id_discord:
                return True
            if self.owner_id_telegram and s_id == self.owner_id_telegram:
                return True
            if s_id in self.owner_ids:
                return True

        # 2. Checagem por nome de usuário exato (não substring, não display_name)
        if username and self.strict_owner_usernames:
            clean_user = username.lower().strip()
            if clean_user in self.strict_owner_usernames:
                return True

        return False
