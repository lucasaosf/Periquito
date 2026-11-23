"""
Camada de Memória Hierárquica do Periquito AI (Inspirada no OpenViking)
Estrutura virtual sob 'viking://' com camadas de contexto:
- L0: Resumo de 1 linha (.abstract.md)
- L1: Visão geral e pontos-chave (.overview.md)
- L2: Conteúdo detalhado integral
Suporta 'gemini_free' ou 'ollama_local' (100% gratuito), com fallback autônomo e blindagem anti-poisoning.
"""

import os
import re
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from config import config, VIKING_DATA_DIR
from core.security import resolve_and_check_path, check_memory_poisoning, wrap_untrusted_content

logger = logging.getLogger("VikingMemory")


class VikingMemory:
    """Adaptador de Memória em Camadas L0/L1/L2 com Armazenamento Persistente."""

    def __init__(self, storage_dir: Optional[Path] = None, provider_mode: Optional[str] = None):
        self.storage_dir = Path(storage_dir or VIKING_DATA_DIR).resolve()
        self.provider_mode = (provider_mode or config.viking.provider_mode).lower().strip()
        
        self.user_dir = self.storage_dir / "user" / "default"
        self.memories_dir = self.user_dir / "memories"
        self.prefs_dir = self.memories_dir / "preferences"
        self.facts_dir = self.memories_dir / "facts"
        self.resources_dir = self.storage_dir / "resources"
        self.db_path = self.storage_dir / "viking_index.db"

        self._init_filesystem_and_db()

    def _init_filesystem_and_db(self):
        """Cria estrutura de diretórios e tabela SQLite FTS para indexação rápida."""
        for d in [self.prefs_dir, self.facts_dir, self.resources_dir]:
            d.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uri TEXT UNIQUE NOT NULL,
                    category TEXT NOT NULL,
                    l0_abstract TEXT,
                    l1_overview TEXT,
                    l2_details TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Tabela virtual de busca textual FTS5
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    uri,
                    l0_abstract,
                    l1_overview,
                    l2_details
                );
            """)
            conn.commit()

    def _generate_l0_l1(self, text: str) -> Tuple[str, str]:
        """Gera resumos L0 (uma frase) e L1 (pontos essenciais) de forma leve."""
        clean_text = text.strip()
        first_sentence = clean_text.split(".")[0].strip()
        l0 = first_sentence[:180] + ("..." if len(first_sentence) > 180 else "")

        # Se tiver mais linhas ou conteúdo extenso, extrai primeiros parágrafos
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        l1 = "\n".join(lines[:3])[:500]

        return l0, l1

    def salvar_fato(self, conteudo: str, categoria: str = "facts", uri: str = "") -> str:
        """
        Salva um fato ou preferência pessoal do usuário com verificação estrita anti-poisoning.
        Gera automaticamente as camadas L0, L1 e L2.
        """
        if not conteudo or not conteudo.strip():
            return "Erro: conteúdo do fato está vazio."

        # 1. Verificação contra envenenamento de memória
        is_poison, reason = check_memory_poisoning(conteudo)
        if is_poison:
            logger.warning(f"[Anti-Poisoning] {reason}")
            return f"Segurança: {reason}"

        categoria = "preferences" if "pref" in categoria.lower() else "facts"
        target_dir = self.prefs_dir if categoria == "preferences" else self.facts_dir

        # Cria slug seguro para o arquivo
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", conteudo[:40].lower()).strip("_") or "item"
        file_name = f"{slug}.md"
        file_path = target_dir / file_name

        if not uri:
            uri = f"viking://user/default/memories/{categoria}/{slug}"

        l0, l1 = self._generate_l0_l1(conteudo)
        l2 = conteudo.strip()

        # Salva o arquivo em disco no formato L2 com metadados
        file_content = f"# {uri}\n\n**Resumo L0:** {l0}\n\n**Visão Geral L1:**\n{l1}\n\n---\n\n## Detalhes L2\n{l2}\n"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_content)

        # Atualiza o índice do banco
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT INTO memory_nodes (uri, category, l0_abstract, l1_overview, l2_details, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(uri) DO UPDATE SET
                    l0_abstract = excluded.l0_abstract,
                    l1_overview = excluded.l1_overview,
                    l2_details = excluded.l2_details,
                    updated_at = CURRENT_TIMESTAMP
            """, (uri, categoria, l0, l1, l2))

            # Atualiza FTS
            conn.execute("DELETE FROM memory_fts WHERE uri = ?", (uri,))
            conn.execute("INSERT INTO memory_fts (uri, l0_abstract, l1_overview, l2_details) VALUES (?, ?, ?, ?)",
                         (uri, l0, l1, l2))
            conn.commit()

        return f"✅ Fato registrado com sucesso sob '{uri}' (Camadas L0/L1/L2 geradas)."

    def buscar(self, consulta: str, caminho_ou_uri: str = "", nivel: str = "L1", limit: int = 4) -> str:
        """
        Recupera memórias semanticamente ou via FTS5 de acordo com o nível solicitado:
        - L0: Apenas resumo de uma frase
        - L1: Resumo intermediário (padrão)
        - L2: Conteúdo completo
        """
        if not consulta or not consulta.strip():
            return "Nenhuma consulta fornecida para busca na memória."

        clean_query = re.sub(r"[^\w\s]", " ", consulta).strip()
        words = clean_query.split()
        if not words:
            return "Consulta não contém palavras-chave válidas."

        fts_query = " OR ".join(f"{w}*" for w in words[:6])

        results = []
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute("""
                    SELECT m.uri, m.category, m.l0_abstract, m.l1_overview, m.l2_details
                    FROM memory_fts f
                    JOIN memory_nodes m ON f.uri = m.uri
                    WHERE memory_fts MATCH ?
                    LIMIT ?
                """, (fts_query, limit)).fetchall()
            except Exception:
                # Fallback para LIKE se FTS falhar
                rows = conn.execute("""
                    SELECT uri, category, l0_abstract, l1_overview, l2_details
                    FROM memory_nodes
                    WHERE l2_details LIKE ? OR l0_abstract LIKE ?
                    LIMIT ?
                """, (f"%{words[0]}%", f"%{words[0]}%", limit)).fetchall()

            for r in rows:
                uri = r["uri"]
                if caminho_ou_uri and caminho_ou_uri.lower() not in uri.lower():
                    continue

                if nivel.upper() == "L0":
                    content = r["l0_abstract"]
                elif nivel.upper() == "L2":
                    content = r["l2_details"]
                else:  # L1 por padrão
                    content = r["l1_overview"]

                results.append(f"📌 **{uri}** ({nivel.upper()}):\n{content}")

        if not results:
            return f"Nenhuma memória relevante encontrada para '{consulta}'."

        raw_output = "\n\n".join(results)
        return wrap_untrusted_content(raw_output, source="OpenViking-Local")

    def indexar_caminho(self, caminho: str) -> str:
        """
        Indexa documentos de uma pasta ou arquivo após validação na blocklist de segurança.
        """
        try:
            safe_path = resolve_and_check_path(caminho, operation="read")
        except Exception as e:
            return f"Segurança: Indexação bloqueada - {e}"

        if not safe_path.exists():
            return f"Erro: O caminho '{caminho}' não existe."

        count = 0
        if safe_path.is_file():
            files_to_index = [safe_path]
        else:
            files_to_index = [p for p in safe_path.glob("**/*") if p.is_file() and p.suffix.lower() in [".md", ".txt", ".json", ".py"]]

        for f in files_to_index[:25]:  # Limite de segurança por lote
            try:
                # Garante que cada arquivo passe individualmente pela blocklist
                checked = resolve_and_check_path(f, operation="read")
                with open(checked, "r", encoding="utf-8", errors="replace") as content_file:
                    text = content_file.read(10000)

                uri = f"viking://resources/{checked.stem}"
                l0, l1 = self._generate_l0_l1(text)

                with sqlite3.connect(str(self.db_path)) as conn:
                    conn.execute("""
                        INSERT INTO memory_nodes (uri, category, l0_abstract, l1_overview, l2_details, updated_at)
                        VALUES (?, 'resource', ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(uri) DO UPDATE SET
                            l0_abstract = excluded.l0_abstract,
                            l1_overview = excluded.l1_overview,
                            l2_details = excluded.l2_details,
                            updated_at = CURRENT_TIMESTAMP
                    """, (uri, l0, l1, text))
                    conn.execute("DELETE FROM memory_fts WHERE uri = ?", (uri,))
                    conn.execute("INSERT INTO memory_fts (uri, l0_abstract, l1_overview, l2_details) VALUES (?, ?, ?, ?)",
                                 (uri, l0, l1, text))
                    conn.commit()
                count += 1
            except Exception as e:
                logger.warning(f"Não foi possível indexar {f.name}: {e}")

        return f"✅ Indexação concluída: {count} arquivo(s) mapeados sob viking://resources/."

    def get_relevant_context(self, prompt: str, max_tokens: int = 800) -> str:
        """
        Recupera automaticamente resumos curtos L0/L1 para pré-injetar
        no prompt do modelo antes de cada resposta.
        """
        words = re.findall(r"\w+", prompt.lower())
        if not words:
            return ""

        query_keywords = [w for w in words if len(w) > 3][:4]
        if not query_keywords:
            return ""

        query = " ".join(query_keywords)
        raw_result = self.buscar(query, nivel="L1", limit=2)
        if "Nenhuma memória" in raw_result:
            return ""

        return f"\n--- [MEMÓRIA RELEVANTE OPENVIKING] ---\n{raw_result}\n--------------------------------------\n"
