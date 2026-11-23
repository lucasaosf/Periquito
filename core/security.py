"""
Módulo Central de Segurança e Blindagem do Periquito AI
Aplica regras determinísticas de segurança, resolução de caminhos canônicos (Path.resolve),
prevenção contra Path Traversal, SSRF, bloqueio de segredos e sanitização anti-injection.
"""

import os
import re
import socket
import ipaddress
import urllib.parse
from pathlib import Path
from typing import Tuple, Optional, Set

from config import config, BASE_DIR, IPC_DIR, WORKSPACE_DIR


class SecurityError(PermissionError):
    """Exceção levantada quando uma regra de segurança do Periquito é violada."""
    pass


class SSRFError(ValueError):
    """Exceção levantada quando uma URL aponta para redes privadas ou proibidas."""
    pass


# Subpastas ou nomes de arquivo sensíveis que NUNCA podem ser lidos, alterados ou indexados
BLOCKED_EXACT_NAMES: Set[str] = {
    ".env",
    ".env.example",
    "settings.yaml",
    ".credentials.yaml",
    "periquito.db",
    "periquito.db-wal",
    "periquito.db-shm",
    "sam",
    "system",
    "security"
}

BLOCKED_NAME_PATTERNS = [
    re.compile(r"^\.env(\..+)?$", re.IGNORECASE),
    re.compile(r"^.*\.credentials\.yaml$", re.IGNORECASE),
    re.compile(r"^.*\.(token|key|pem|pfx|pkcs12)$", re.IGNORECASE),
    re.compile(r"^.*\.db(-wal|-shm)?$", re.IGNORECASE),
]

# Padrões destrutivos no PowerShell/CMD permanentemente proibidos (mesmo com HITL)
CRITICAL_COMMAND_PATTERNS = [
    re.compile(r"\bformat\b", re.IGNORECASE),
    re.compile(r"\bdiskpart\b", re.IGNORECASE),
    re.compile(r"remove-item\s+.*-(recurse|force)\s+[c-zC-Z]:\\?$", re.IGNORECASE),
    re.compile(r"\brmdir\s+/[sS]\s+/[qQ]\s+[c-zC-Z]:\\?$", re.IGNORECASE),
    re.compile(r"\bdel\s+/[fF]\s+/[sS]\s+/[qQ]\s+[c-zC-Z]:\\?$", re.IGNORECASE),
    re.compile(r"\b(hklm|hkey_local_machine)\\sam\b", re.IGNORECASE),
    re.compile(r"periquito\.db", re.IGNORECASE),
    re.compile(r"\.credentials\.yaml", re.IGNORECASE),
    re.compile(r"\.env\b", re.IGNORECASE),
]

# Padrões de envenenamento de memória (tentativas de injeção de prompt permanente)
MEMORY_POISON_PATTERNS = [
    re.compile(r"\b(ignore|esque(ça|ca)|desconsidere)\s+.*?\b(instru(ções|coes)|diretrizes|regras)\b", re.IGNORECASE),
    re.compile(r"\b(você|voce)\s+agora\s+(é|e)\s+(dan|root|admin|modo)\b", re.IGNORECASE),
    re.compile(r"\bdesative\s+todas?\s+as?\s+(prote(ções|coes)|regras|seguran(ça|ca))\b", re.IGNORECASE),
    re.compile(r"\bsystem\s+prompt\s*:\b", re.IGNORECASE),
    re.compile(r"<\s*conteudo_externo_nao_confiavel", re.IGNORECASE),
]


def resolve_and_check_path(target_path: str | Path, operation: str = "read") -> Path:
    """
    Resolve o caminho canônico absoluto (bloqueando '..' e symlinks maliciosos)
    e valida contra a blocklist rígida de segredos e infraestrutura.
    """
    if isinstance(target_path, str):
        target_path = target_path.strip().strip("'\"")
    
    path_obj = Path(target_path).expanduser().resolve()
    path_str = str(path_obj).lower()
    file_name = path_obj.name.lower()

    # 1. Checagem de nomes exatos de arquivo bloqueados
    if file_name in BLOCKED_EXACT_NAMES:
        raise SecurityError(f"Acesso negado: o arquivo '{path_obj.name}' está na blocklist de segurança.")

    for pat in BLOCKED_NAME_PATTERNS:
        if pat.match(file_name):
            raise SecurityError(f"Acesso negado: o arquivo '{path_obj.name}' corresponde a padrão de credencial/banco bloqueado.")

    # 2. Bloqueio de pastas de infraestrutura pessoal sensível
    forbidden_directories = [
        "\\.git",
        "\\.ssh",
        "\\.aws",
        "\\.gnupg",
        "\\system32\\config",
        "\\appdata\\local\\google\\chrome",
        "\\appdata\\local\\microsoft\\edge",
        "\\appdata\\local\\bravesoftware",
        "\\appdata\\roaming\\mozilla\\firefox",
    ]
    for fdir in forbidden_directories:
        if fdir in path_str:
            raise SecurityError(f"Acesso negado: o diretório '{fdir.replace('\\', '/')}' é estritamente confidencial.")

    # 3. Bloqueio do diretório de IPC e bancos de aprovação
    resolved_ipc = IPC_DIR.resolve()
    if path_obj == resolved_ipc or resolved_ipc in path_obj.parents:
        raise SecurityError("Acesso negado: o diretório de IPC e banco HITL é inviolável para ferramentas do agente.")

    # 4. Bloqueio de modificação do próprio código-fonte do Periquito
    if operation in ("write", "edit", "delete"):
        resolved_base = BASE_DIR.resolve()
        core_dir = (BASE_DIR / "core").resolve()
        channels_dir = (BASE_DIR / "channels").resolve()
        
        # O agente não pode sobrescrever arquivos de código Python do Periquito
        if core_dir in path_obj.parents or channels_dir in path_obj.parents:
            raise SecurityError("Acesso negado: ferramentas não têm permissão para sobrescrever módulos internos do Periquito.")
        
        if path_obj in [
            (BASE_DIR / "main.py").resolve(),
            (BASE_DIR / "mcp_server.py").resolve(),
            (BASE_DIR / "config.py").resolve(),
            (BASE_DIR / "setup_dsh.py").resolve(),
        ]:
            raise SecurityError("Acesso negado: o código-fonte principal do assistente é protegido contra auto-modificação.")

    return path_obj


def validate_url_ssrf(url: str) -> str:
    """
    Valida URLs contra SSRF (Server-Side Request Forgery).
    Permite apenas HTTP e HTTPS e resolve DNS para bloquear IPs privados, loopback e reservados.
    """
    if not url or not isinstance(url, str):
        raise SSRFError("URL inválida ou vazia.")

    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme.lower() not in ("http", "https"):
        raise SSRFError(f"Esquema de URL não permitido: '{parsed.scheme}'. Apenas http e https são aceitos.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("A URL fornecida não contém um hostname válido.")

    # Bloqueio direto de localhost por nome
    if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise SSRFError("Acesso bloqueado: requisições para localhost não são permitidas.")

    # Resolução de DNS e verificação de cada IP retornado
    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise SSRFError(f"Falha ao resolver endereço DNS para '{hostname}': {e}")

    for family, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            raise SSRFError(f"IP inválido detectado: {ip_str}")

        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
        ):
            raise SSRFError(f"Acesso bloqueado por SSRF: o host '{hostname}' resolve para IP protegido ({ip_str}).")

    return url.strip()


def wrap_untrusted_content(content: str, source: str) -> str:
    """
    Encapsula conteúdo externo com tags anti-prompt injection.
    Garante que o modelo processe os dados como texto não confiável.
    """
    safe_source = source.replace('"', '&quot;').replace(">", "&gt;")
    return f'<conteudo_externo_nao_confiavel fonte="{safe_source}">\n{content}\n</conteudo_externo_nao_confiavel>'


def is_destructive_command(command: str) -> Tuple[bool, str]:
    """
    Verifica se um comando shell contém padrões destrutivos críticos
    permanentemente proibidos no sistema.
    """
    clean_cmd = command.strip()
    for pat in CRITICAL_COMMAND_PATTERNS:
        if pat.search(clean_cmd):
            return True, f"Comando bloqueado permanentemente por segurança: violação de integridade do sistema ({pat.pattern})."
    return False, ""


def check_memory_poisoning(text: str) -> Tuple[bool, str]:
    """
    Avalia se um texto submetido para salvar na memória contém padrões
    de envenenamento ou sobrescrita de regras de sistema.
    """
    for pat in MEMORY_POISON_PATTERNS:
        if pat.search(text):
            return True, "Conteúdo rejeitado: detectada tentativa de envenenamento de memória ou override de regras do assistente."
    return False, ""


def sanitize_log(text: str) -> str:
    """Oculta tokens, chaves de API e senhas em mensagens de log."""
    if not text:
        return ""
    # Redata tokens de bot do Telegram (ex: 123456:ABC-DEF...)
    sanitized = re.sub(r"\b\d{8,11}:[a-zA-Z0-9_-]{35}\b", "[TELEGRAM_TOKEN_REDACTED]", text)
    # Redata chaves alfanuméricas longas (OpenAI/Gemini/Groq keys)
    sanitized = re.sub(r"(AIzaSy[a-zA-Z0-9_-]{33}|gsk_[a-zA-Z0-9]{48,})", "[API_KEY_REDACTED]", sanitized)
    return sanitized
