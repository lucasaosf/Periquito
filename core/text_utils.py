"""
Utilitários de Texto do Periquito AI
Responsável por truncamento de segurança (limite de 10.000 caracteres)
e fatiamento inteligente de mensagens para Telegram e Discord.
"""

from typing import List


def truncate_output(text: str, max_length: int = 10000, suffix: str = "\n... [Saída truncada por limite de segurança (10.000 caracteres)]") -> str:
    """Garante que saídas de arquivos, terminal ou web não estourem o contexto do modelo."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length] + suffix


def slice_message(text: str, max_length: int = 4000) -> List[str]:
    """
    Divide textos longos preservando quebras de linha ou parágrafos para
    envio perfeito no Telegram (<= 4000 chars) ou Discord (<= 1900 chars).
    """
    if not text:
        return [""]
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = []
    current_len = 0

    lines = text.splitlines(keepends=True)
    for line in lines:
        if current_len + len(line) <= max_length:
            current_chunk.append(line)
            current_len += len(line)
        else:
            if current_chunk:
                chunks.append("".join(current_chunk))
                current_chunk = []
                current_len = 0

            # Se uma única linha for maior que max_length, fatia forçadamente
            if len(line) > max_length:
                for i in range(0, len(line), max_length):
                    chunks.append(line[i:i + max_length])
            else:
                current_chunk.append(line)
                current_len += len(line)

    if current_chunk:
        chunks.append("".join(current_chunk))

    return chunks
