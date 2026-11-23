"""
Armazenamento IPC Concorrente via SQLite WAL do Periquito AI
Comunica de forma atômica e segura os processos isolados:
1. FastMCP (executando como stdio subprocess do dsh)
2. main.py (rodando os bots de Telegram, Discord, Alexa e Mic Local)
"""

import time
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any

from config import config, IPC_DB_PATH, IPC_DIR


def get_ipc_connection() -> sqlite3.Connection:
    """Cria uma conexão com o banco de dados IPC em modo WAL e busy_timeout."""
    IPC_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(IPC_DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def init_ipc_db():
    """Inicializa as tabelas de IPC para HITL, Outbox e Notificações."""
    with get_ipc_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS hitl_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                description TEXT NOT NULL,
                details_json TEXT,
                status TEXT DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                resolved_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS outbox_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                caption TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                message TEXT NOT NULL,
                source TEXT DEFAULT 'system',
                delivered INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()


# ==============================================================================
# FLUXO HUMAN-IN-THE-LOOP (HITL) VIA TELEGRAM
# ==============================================================================

def request_hitl(action_type: str, description: str, details: Optional[Dict[str, Any]] = None, timeout_seconds: int = 60) -> Tuple[bool, str]:
    """
    Registra solicitação de aprovação crítica e aguarda até timeout_seconds pela
    confirmação interativa do administrador no Telegram.
    """
    init_ipc_db()
    details_str = json.dumps(details or {}, ensure_ascii=False)
    now = datetime.now()
    expires = now + timedelta(seconds=timeout_seconds)

    approval_id = None
    with get_ipc_connection() as conn:
        cur = conn.execute("""
            INSERT INTO hitl_approvals (action_type, description, details_json, status, expires_at)
            VALUES (?, ?, ?, 'pending', ?)
        """, (action_type, description, details_str, expires.isoformat()))
        approval_id = cur.lastrowid
        conn.commit()

    if not approval_id:
        return False, "Erro interno ao enfileirar aprovação HITL."

    # Aguarda ativamente com intervalos pequenos
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        with get_ipc_connection() as conn:
            row = conn.execute("SELECT status FROM hitl_approvals WHERE id = ?", (approval_id,)).fetchone()
            if row:
                st = row["status"]
                if st == "approved":
                    return True, "Ação aprovada pelo administrador via Telegram."
                elif st == "rejected":
                    return False, "Ação RECUSADA expressamente pelo administrador via Telegram."
                elif st == "expired":
                    return False, "Solicitação de aprovação expirada sem resposta."

        time.sleep(0.5)

    # Marca como expirada se o tempo esgotou
    with get_ipc_connection() as conn:
        conn.execute("""
            UPDATE hitl_approvals 
            SET status = 'expired', resolved_at = ?
            WHERE id = ? AND status = 'pending'
        """, (datetime.now().isoformat(), approval_id))
        conn.commit()

    return False, f"Tempo limite de {timeout_seconds}s para aprovação do administrador foi excedido. Ação cancelada por segurança."


def get_pending_hitl() -> List[Dict[str, Any]]:
    """Recupera solicitações pendentes e ainda não expiradas para o bot enviar no Telegram."""
    init_ipc_db()
    now_iso = datetime.now().isoformat()
    with get_ipc_connection() as conn:
        rows = conn.execute("""
            SELECT id, action_type, description, details_json, requested_at, expires_at
            FROM hitl_approvals
            WHERE status = 'pending' AND expires_at > ?
            ORDER BY id ASC
        """, (now_iso,)).fetchall()
        return [dict(r) for r in rows]


def resolve_hitl(approval_id: int, approved: bool) -> bool:
    """Atualiza o estado de uma aprovação quando o usuário clica no botão do Telegram."""
    init_ipc_db()
    new_status = "approved" if approved else "rejected"
    now_iso = datetime.now().isoformat()
    with get_ipc_connection() as conn:
        res = conn.execute("""
            UPDATE hitl_approvals
            SET status = ?, resolved_at = ?
            WHERE id = ? AND status = 'pending'
        """, (new_status, now_iso, approval_id))
        conn.commit()
        return res.rowcount > 0


# ==============================================================================
# FILA DE ENVIO DE ARQUIVOS (PC -> CELULAR)
# ==============================================================================

def queue_outbox_file(file_path: str, caption: str = "") -> int:
    """Enfileira um arquivo gerado para entrega automática no Telegram do admin."""
    init_ipc_db()
    with get_ipc_connection() as conn:
        cur = conn.execute("""
            INSERT INTO outbox_files (file_path, caption, status)
            VALUES (?, ?, 'pending')
        """, (str(file_path), caption))
        conn.commit()
        return cur.lastrowid


def get_pending_outbox_files() -> List[Dict[str, Any]]:
    """Recupera arquivos prontos para entrega no Telegram."""
    init_ipc_db()
    with get_ipc_connection() as conn:
        rows = conn.execute("""
            SELECT id, file_path, caption, created_at
            FROM outbox_files
            WHERE status = 'pending'
            ORDER BY id ASC
        """).fetchall()
        return [dict(r) for r in rows]


def mark_outbox_file_sent(file_id: int, success: bool = True):
    """Marca arquivo como enviado ou com falha."""
    init_ipc_db()
    status = "sent" if success else "failed"
    with get_ipc_connection() as conn:
        conn.execute("UPDATE outbox_files SET status = ? WHERE id = ?", (status, file_id))
        conn.commit()


# ==============================================================================
# NOTIFICAÇÕES ASSÍNCRONAS (ALEXA -> TELEGRAM)
# ==============================================================================

def add_notification(title: str, message: str, source: str = "system") -> int:
    """Registra notificação (por exemplo, tarefa da Alexa concluída no PC)."""
    init_ipc_db()
    with get_ipc_connection() as conn:
        cur = conn.execute("""
            INSERT INTO notifications (title, message, source, delivered)
            VALUES (?, ?, ?, 0)
        """, (title, message, source))
        conn.commit()
        return cur.lastrowid


def get_pending_notifications() -> List[Dict[str, Any]]:
    """Recupera notificações não entregues."""
    init_ipc_db()
    with get_ipc_connection() as conn:
        rows = conn.execute("""
            SELECT id, title, message, source, created_at
            FROM notifications
            WHERE delivered = 0
            ORDER BY id ASC
        """).fetchall()
        return [dict(r) for r in rows]


def mark_notification_delivered(notif_id: int):
    """Marca notificação como entregue."""
    init_ipc_db()
    with get_ipc_connection() as conn:
        conn.execute("UPDATE notifications SET delivered = 1 WHERE id = ?", (notif_id,))
        conn.commit()
