"""
Módulo de Memória de Longo Prazo e Aprendizado Contínuo do Periquito AI
Baseado em SQLite local para persistência rápida, confiável e segura.
"""

import os
import sqlite3
import datetime
import re
from typing import Dict, List, Optional, Tuple

class MemoryManager:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_path = os.path.join(base_dir, "data", "memory.db")
        else:
            self.db_path = db_path

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Inicializa o esquema de tabelas do banco de memória."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Tabela de fatos aprendidos permanentemente
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT DEFAULT 'geral',
                    source TEXT DEFAULT 'sistema',
                    updated_at TEXT NOT NULL
                )
            """)
            # Tabela de histórico de conversação entre canais
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

        # Insere conhecimentos fundamentais iniciais
        self._seed_initial_knowledge()

    def _seed_initial_knowledge(self):
        """Fatos pré-definidos essenciais sobre o ambiente do Lucas."""
        initial_facts = [
            ("proprietario_nome", "Lucas Aosf (no Discord: Macaco Opressor ou anakin opressor)", "usuario"),
            ("identidade", "Periquito - Assistente Pessoal Nativo de IA, rápido, inteligente e bem-humorado", "identidade"),
            ("diretorio_projetos", r"C:\Users\Lucas Aosf\Documents\!!!___ANTIGRAVITY___!!!", "sistema"),
            ("pasta_qgis_automacao", r"C:\Users\Lucas Aosf\Documents\!!!___ANTIGRAVITY___!!!\QGIS_Automation", "sistema"),
            ("micheli", "Namorada/parceira do Lucas, usa o Claude Pro no PC", "pessoas"),
            ("especialidade", "Consultoria Ambiental, Engenharia Florestal, Cartografia, QGIS e RStudio", "trabalho"),
            ("placa_video", "NVIDIA GeForce GTX 1070 (8GB VRAM)", "hardware"),
            ("sistema_operacional", "Windows 11 (64-bit)", "sistema")
        ]
        for k, v, cat in initial_facts:
            if not self.get_fact(k):
                self.save_fact(k, v, category=cat, source="seed")

    def save_fact(self, key: str, value: str, category: str = "geral", source: str = "conversa") -> None:
        """Salva ou atualiza um fato aprendido."""
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO facts (key, value, category, source, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    category=excluded.category,
                    source=excluded.source,
                    updated_at=excluded.updated_at
            """, (key.strip().lower(), value.strip(), category, source, now))
            conn.commit()

    def get_fact(self, key: str) -> Optional[str]:
        """Obtém o valor de um fato específico."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM facts WHERE key = ?", (key.strip().lower(),))
            row = cursor.fetchone()
            return row[0] if row else None

    def get_all_facts(self) -> List[Tuple[str, str, str]]:
        """Retorna todos os fatos aprendidos."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value, category FROM facts ORDER BY category, key")
            return cursor.fetchall()

    def search_facts(self, query: str) -> List[Tuple[str, str]]:
        """Busca fatos relacionados a uma consulta."""
        q = f"%{query.strip().lower()}%"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT key, value FROM facts 
                WHERE key LIKE ? OR value LIKE ? OR category LIKE ?
            """, (q, q, q))
            return cursor.fetchall()

    def auto_learn(self, text: str, user_name: str) -> Optional[str]:
        """Detecta instruções de aprendizado automático no texto do Lucas."""
        # Padrão para troca de nome preferido
        name_match = re.search(r"(?:me\s+chame\s+(?:apenas\s+)?de|pode\s+me\s+chamar\s+(?:apenas\s+)?de|meu\s+nome\s+é)\s+([A-Za-zÀ-ÿ\s]+)", text, re.IGNORECASE)
        if name_match:
            new_name = name_match.group(1).strip()
            # Limpa pontuações como 'bele', 'por favor'
            new_name = re.sub(r"[,.!?].*$", "", new_name).strip()
            new_name = re.sub(r"\b(bele|por\s+favor|ok|valeu)\b.*$", "", new_name, flags=re.IGNORECASE).strip()
            if len(new_name) > 1:
                self.save_fact("nome_preferido", new_name, category="usuario", source=user_name)
                return f"Perfeito! A partir de agora vou te chamar de {new_name}."

        # Padrões comuns: "lembre-se que X é Y", "guarde na memória que...", "anote que..."
        patterns = [
            r"lembre(?:-se)?\s+que\s+(.+?)\s+(?:é|e|fica em|fica no|foi|será)\s+(.+)",
            r"anote\s+que\s+(.+?)\s+(?:é|e|fica em|fica no)\s+(.+)",
            r"guarde\s+(?:na memória)?\s+que\s+(.+?)\s+(?:é|e)\s+(.+)"
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                key = match.group(1).strip()
                val = match.group(2).strip()
                self.save_fact(key, val, category="aprendizado_usuario", source=user_name)
                return f"Fato memorizado com sucesso: '{key}' = '{val}'"
        return None

    def log_message(self, channel: str, user_name: str, role: str, content: str) -> None:
        """Registra mensagem no histórico unificado."""
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversations (channel, user_name, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (channel, user_name, role, content, now))
            conn.commit()

    def get_context_summary(self) -> str:
        """Monta um resumo dos fatos memorizados para enriquecer o prompt da IA."""
        facts = self.get_all_facts()
        if not facts:
            return ""
        lines = ["--- MEMÓRIA PERMANENTE DO PERIQUITO (FATOS APRENDIDOS) ---"]
        for key, value, cat in facts:
            lines.append(f"• [{cat}] {key}: {value}")
        lines.append("---------------------------------------------------------")
        return "\n".join(lines)
