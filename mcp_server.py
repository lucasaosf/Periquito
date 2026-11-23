"""
Servidor MCP Enxuto e 100% Blindado do Periquito AI (10 Ferramentas Consolidadas)
Executa como processo stdio independente com validação determinística de segurança em todas as chamadas.
"""

import os
import sys
import json
import psutil
import shutil
import smtplib
import imaplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

from config import config, BASE_DIR, WORKSPACE_DIR, OUTBOX_DIR
from core.security import (
    resolve_and_check_path,
    validate_url_ssrf,
    wrap_untrusted_content,
    is_destructive_command,
    SecurityError,
    SSRFError
)
from core.ipc_store import request_hitl, queue_outbox_file
from core.viking_memory import VikingMemory
from core.text_utils import truncate_output

# Tenta importar FastMCP
try:
    from fastmcp import FastMCP
    mcp = FastMCP("Periquito MCP Server", dependencies=["psutil", "requests", "duckduckgo-search"])
    USE_FASTMCP = True
except ImportError:
    USE_FASTMCP = False
    mcp = None

viking_mem = VikingMemory()

# Mapeamento de aplicativos para inicialização rápida segura
APPS_MAP = {
    "qgis": r"D:\QGIS\bin\qgis-ltr.bat",
    "rstudio": r"C:\Program Files\RStudio\rstudio.exe",
    "discord": r"C:\Users\Lucas Aosf\AppData\Local\Discord\Update.exe --processStart Discord.exe",
    "steam": r"C:\Program Files (x86)\Steam\steam.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "antigravity": r"C:\Users\Lucas Aosf\AppData\Local\Programs\antigravity\Antigravity.exe",
    "notepad": "notepad.exe",
    "calc": "calc.exe",
    "explorer": "explorer.exe",
}


# ==============================================================================
# FERRAMENTA 1: PESQUISAR NA WEB (GRATUITO)
# ==============================================================================
def pesquisar_web(query: str, max_resultados: int = 5) -> str:
    """Realiza pesquisa gratuita em tempo real na web usando DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_resultados))
        if not results:
            return "Nenhum resultado encontrado na web."
        
        snippets = []
        for r in results:
            title = r.get("title", "")
            snippet = r.get("body", "")
            href = r.get("href", "")
            snippets.append(f"• **{title}**\n  {snippet}\n  Fonte: {href}")
        
        output = "\n\n".join(snippets)
        return wrap_untrusted_content(truncate_output(output), source="DuckDuckGo")
    except Exception as e:
        return f"Erro na pesquisa web: {e}"


# ==============================================================================
# FERRAMENTA 2: LER PÁGINA WEB (ANTI-SSRF)
# ==============================================================================
def ler_pagina_web(url: str) -> str:
    """Extrai conteúdo de página web com proteção anti-SSRF e truncamento em 10.000 chars."""
    try:
        safe_url = validate_url_ssrf(url)
    except SSRFError as e:
        return f"Segurança: Acesso bloqueado - {e}"

    try:
        import requests
        resp = requests.get(safe_url, timeout=12, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        if resp.status_code != 200:
            return f"Erro HTTP {resp.status_code} ao acessar {url}"

        text = ""
        try:
            import trafilatura
            extracted = trafilatura.extract(resp.text)
            if extracted:
                text = extracted
        except ImportError:
            pass

        if not text:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)

        truncated = truncate_output(text, max_length=10000)
        return wrap_untrusted_content(truncated, source=url)
    except Exception as e:
        return f"Erro ao extrair conteúdo da página: {e}"


# ==============================================================================
# FERRAMENTA 3: EXECUTAR COMANDO DE SISTEMA (HITL + POWERSHELL UTF-8)
# ==============================================================================
def executar_comando_sistema(comando: str, motivo: str) -> str:
    """Executa comando no PowerShell com aprovação obrigatória do admin via Telegram."""
    # 1. Bloqueio permanente de comandos destrutivos
    is_dest, reason = is_destructive_command(comando)
    if is_dest:
        return f"Segurança: {reason}"

    # 2. Solicitação de aprovação HITL via Telegram
    aprovado, msg = request_hitl(
        action_type="executar_comando_sistema",
        description=f"Execução de Comando PowerShell\nMotivo: {motivo}\nComando:\n`{comando}`",
        details={"comando": comando, "motivo": motivo},
        timeout_seconds=60
    )
    if not aprovado:
        return f"Ação abortada: {msg}"

    # 3. Execução segura com timeout e UTF-8
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace"
        )
        out = res.stdout if res.returncode == 0 else f"Código de saída: {res.returncode}\n{res.stderr}"
        return wrap_untrusted_content(truncate_output(out), source="PowerShell")
    except subprocess.TimeoutExpired:
        return "Erro: O comando excedeu o tempo limite de execução de 30 segundos."
    except Exception as e:
        return f"Falha na execução: {e}"


# ==============================================================================
# FERRAMENTA 4: CONTROLAR PC (VOLUME, APPS, TELAS, STATUS & HITL PARA CRÍTICOS)
# ==============================================================================
def controlar_pc(acao: str, valor: str = "") -> str:
    """Controla aspectos do PC: ações seguras imediatas e ações críticas via HITL."""
    act = acao.lower().strip()

    # Ações críticas requerem aprovação expressa
    critical_actions = ["desligar", "reiniciar", "suspender", "bloquear", "fechar_app", "wifi", "bluetooth"]
    if act in critical_actions:
        aprovado, msg = request_hitl(
            action_type="controlar_pc",
            description=f"Ação Crítica de Sistema: {act.upper()} {valor}",
            details={"acao": act, "valor": valor},
            timeout_seconds=60
        )
        if not aprovado:
            return f"Ação abortada: {msg}"

        if act == "desligar":
            subprocess.run(["shutdown", "/s", "/t", "10"], shell=False)
            return "Comando de desligamento enviado (10s)."
        elif act == "reiniciar":
            subprocess.run(["shutdown", "/r", "/t", "10"], shell=False)
            return "Comando de reinicialização enviado (10s)."
        elif act == "bloquear":
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], shell=False)
            return "Estação de trabalho bloqueada com sucesso."
        elif act == "fechar_app":
            target = valor.lower().strip()
            closed = 0
            for p in psutil.process_iter(['name']):
                if target in p.info['name'].lower():
                    p.kill()
                    closed += 1
            return f"Finalizados {closed} processo(s) correspondente(s) a '{valor}'."

    # Ações imediatas seguras
    if act == "volume":
        try:
            import comtypes
            comtypes.CoInitialize()
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from ctypes import cast, POINTER
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
            vol_ctrl = cast(interface, POINTER(IAudioEndpointVolume))
            
            val = float(valor.replace("%", "").strip()) / 100.0
            vol_ctrl.SetMasterVolumeLevelScalar(max(0.0, min(1.0, val)), None)
            comtypes.CoUninitialize()
            return f"Volume ajustado para {valor}%."
        except Exception as e:
            return f"Erro ao ajustar volume: {e}"

    elif act == "abrir_app":
        name = valor.lower().strip()
        for key, path in APPS_MAP.items():
            if key in name:
                try:
                    if os.path.exists(path):
                        os.startfile(path)
                    else:
                        subprocess.Popen([path], shell=False)
                    return f"Aplicativo '{key.upper()}' aberto com sucesso."
                except Exception as e:
                    return f"Erro ao abrir {key}: {e}"
        return f"Aplicativo '{valor}' não encontrado nos atalhos."

    elif act == "capturar_tela":
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
            shot_path = OUTBOX_DIR / f"screenshot_{os.getpid()}_{int(psutil.time.time())}.png"
            img.save(shot_path)
            queue_outbox_file(str(shot_path), caption="📸 Captura de tela do seu PC")
            return f"Screenshot capturado com sucesso e enfileirado para o Telegram: {shot_path.name}"
        except Exception as e:
            return f"Falha ao capturar tela: {e}"

    elif act == "listar_processos":
        procs = sorted(psutil.process_iter(['name', 'cpu_percent']), key=lambda p: p.info['cpu_percent'] or 0, reverse=True)[:10]
        lines = [f"• {p.info['name']} (CPU: {p.info['cpu_percent']}%)" for p in procs]
        return "Top 10 processos ativos por uso de CPU:\n" + "\n".join(lines)

    return f"Ação '{acao}' não suportada."


# ==============================================================================
# FERRAMENTA 5: LER OU BUSCAR ARQUIVO (SEGURANÇA + FORMATOS DIVERSOS + OCR)
# ==============================================================================
def ler_ou_buscar_arquivo(acao: str, caminho: str, padrao: str = "") -> str:
    """Busca ou lê arquivos no computador respeitando estritamente a blocklist de segredos."""
    try:
        safe_path = resolve_and_check_path(caminho, operation="read")
    except SecurityError as e:
        return f"Segurança: Acesso negado - {e}"

    act = acao.lower().strip()
    if act == "buscar":
        if not safe_path.is_dir():
            return f"Erro: '{caminho}' não é um diretório."
        matches = []
        pattern = padrao or "*"
        for p in safe_path.glob(f"**/{pattern}"):
            try:
                # Checa cada item retornado
                resolve_and_check_path(p, operation="read")
                matches.append(str(p))
            except SecurityError:
                continue
            if len(matches) >= 30:
                break
        return "Arquivos encontrados:\n" + "\n".join(matches) if matches else "Nenhum arquivo encontrado."

    elif act == "ler":
        if not safe_path.is_file():
            return f"Erro: '{caminho}' não é um arquivo."

        ext = safe_path.suffix.lower()
        try:
            # 1. Arquivos de texto e código
            if ext in [".txt", ".md", ".json", ".csv", ".py", ".yaml", ".yml", ".html", ".css", ".js"]:
                with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(10000)
                return wrap_untrusted_content(truncate_output(content), source=safe_path.name)

            # 2. Arquivos PDF
            elif ext == ".pdf":
                try:
                    import fitz  # PyMuPDF
                    doc = fitz.open(str(safe_path))
                    text = "".join([page.get_text() for page in doc])
                    return wrap_untrusted_content(truncate_output(text), source=safe_path.name)
                except ImportError:
                    return "Biblioteca PyMuPDF indisponível para leitura de PDF."

            # 3. Documentos DOCX
            elif ext == ".docx":
                try:
                    import docx
                    doc = docx.Document(str(safe_path))
                    text = "\n".join([p.text for p in doc.paragraphs])
                    return wrap_untrusted_content(truncate_output(text), source=safe_path.name)
                except ImportError:
                    return "Biblioteca python-docx indisponível."

            # 4. Planilhas Excel
            elif ext in [".xlsx", ".xls"]:
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(str(safe_path), data_only=True)
                    sheet = wb.active
                    rows = []
                    for r in sheet.iter_rows(values_only=True):
                        rows.append(" | ".join([str(v) if v is not None else "" for v in r]))
                        if len(rows) >= 50:
                            break
                    return wrap_untrusted_content(truncate_output("\n".join(rows)), source=safe_path.name)
                except Exception as e:
                    return f"Erro na leitura Excel: {e}"

            # 5. Imagens com OCR
            elif ext in [".png", ".jpg", ".jpeg"]:
                try:
                    from PIL import Image
                    import pytesseract
                    img = Image.open(str(safe_path))
                    text = pytesseract.image_to_string(img, lang="por+eng")
                    return wrap_untrusted_content(truncate_output(text), source=safe_path.name)
                except Exception as e:
                    return f"OCR indisponível ou falhou: {e}"

            return f"Formato de arquivo '{ext}' não suportado para leitura direta."
        except Exception as e:
            return f"Erro ao ler arquivo: {e}"

    return f"Ação '{acao}' inválida. Use 'ler' ou 'buscar'."


# ==============================================================================
# FERRAMENTA 6: EDITAR DOCUMENTO (.DOCX, .XLSX, .PDF)
# ==============================================================================
def editar_documento(tipo: str, caminho: str, dados_json: str) -> str:
    """Cria ou edita documentos .docx, .xlsx ou .pdf com proteção de sobrescrita fora do outbox."""
    try:
        safe_path = resolve_and_check_path(caminho, operation="write")
    except SecurityError as e:
        return f"Segurança: Escrita bloqueada - {e}"

    # Se estiver fora de outbox e o arquivo já existir, exige aprovação HITL
    resolved_outbox = OUTBOX_DIR.resolve()
    if safe_path.exists() and resolved_outbox not in safe_path.parents:
        aprovado, msg = request_hitl(
            action_type="editar_documento",
            description=f"Sobrescrita de arquivo fora da pasta outbox: {safe_path}",
            details={"caminho": str(safe_path)},
            timeout_seconds=60
        )
        if not aprovado:
            return f"Ação cancelada: {msg}"

    try:
        dados = json.loads(dados_json)
    except Exception:
        dados = {"conteudo": dados_json}

    t = tipo.lower().strip()
    safe_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if t == "docx":
            import docx
            doc = docx.Document()
            doc.add_heading(dados.get("titulo", "Documento Periquito"), level=1)
            paragraphs = dados.get("paragrafos", [dados.get("conteudo", "")])
            for p in paragraphs:
                doc.add_paragraph(str(p))
            doc.save(str(safe_path))
            return f"Arquivo DOCX gerado com sucesso em: {safe_path}"

        elif t == "xlsx":
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = dados.get("titulo", "Planilha")
            linhas = dados.get("linhas", [])
            for row in linhas:
                ws.append(row if isinstance(row, list) else [row])
            wb.save(str(safe_path))
            return f"Planilha XLSX gerada com sucesso em: {safe_path}"

        elif t == "pdf":
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            c = canvas.Canvas(str(safe_path), pagesize=letter)
            c.drawString(100, 750, dados.get("titulo", "Documento PDF"))
            text_lines = str(dados.get("conteudo", "")).splitlines()
            y = 720
            for line in text_lines:
                c.drawString(100, y, line[:90])
                y -= 20
                if y < 50:
                    c.showPage()
                    y = 750
            c.save()
            return f"Arquivo PDF gerado com sucesso em: {safe_path}"

        return f"Tipo de documento '{tipo}' não suportado."
    except Exception as e:
        return f"Erro ao criar/editar documento: {e}"


# ==============================================================================
# FERRAMENTA 7: EDITAR IMAGEM (PILLOW & REMBG LAZY)
# ==============================================================================
def editar_imagem(caminho_entrada: str, caminho_saida: str, operacao: str, parametros_json: str = "{}") -> str:
    """Aplica operações em imagens (redimensionar, converter, remover fundo)."""
    try:
        in_path = resolve_and_check_path(caminho_entrada, operation="read")
        out_path = resolve_and_check_path(caminho_saida, operation="write")
    except SecurityError as e:
        return f"Segurança: Operação bloqueada - {e}"

    if not in_path.exists():
        return f"Erro: Imagem de entrada '{caminho_entrada}' não encontrada."

    try:
        params = json.loads(parametros_json)
    except Exception:
        params = {}

    op = operacao.lower().strip()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from PIL import Image, ImageEnhance

        if op == "remover_fundo":
            from rembg import remove
            with open(in_path, "rb") as f_in:
                input_bytes = f_in.read()
            output_bytes = remove(input_bytes)
            with open(out_path, "wb") as f_out:
                f_out.write(output_bytes)
            return f"Fundo removido com sucesso via rembg: {out_path}"

        img = Image.open(in_path)
        if op == "redimensionar":
            w = params.get("largura", img.width)
            h = params.get("altura", img.height)
            resized = img.resize((int(w), int(h)))
            resized.save(out_path)
            return f"Imagem redimensionada para {w}x{h} salva em {out_path}"

        elif op == "girar":
            ang = params.get("angulo", 90)
            rotated = img.rotate(int(ang), expand=True)
            rotated.save(out_path)
            return f"Imagem girada em {ang}° salva em {out_path}"

        elif op == "brilho_contraste":
            b_factor = params.get("brilho", 1.0)
            c_factor = params.get("contraste", 1.0)
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(float(b_factor))
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(float(c_factor))
            img.save(out_path)
            return f"Brilho e contraste ajustados salvos em {out_path}"

        elif op == "converter":
            img.save(out_path)
            return f"Imagem convertida salva em {out_path}"

        return f"Operação '{operacao}' não suportada."
    except Exception as e:
        return f"Erro no processamento da imagem: {e}"


# ==============================================================================
# FERRAMENTA 8: GERENCIAR E-MAIL (LEITURA LIMPA E ENVIO COM HITL)
# ==============================================================================
def gerenciar_email(acao: str, destinatario: str = "", assunto: str = "", corpo: str = "", anexo: str = "", quantidade: int = 5) -> str:
    """Lê e-mails recentes ou envia mensagens com verificação HITL para destinatários não confiáveis/anexos."""
    act = acao.lower().strip()

    if not config.email.user or not config.email.app_password:
        return "Erro: Credenciais de e-mail (EMAIL_USER e EMAIL_APP_PASSWORD) não configuradas no .env."

    if act == "ler":
        try:
            mail = imaplib.IMAP4_SSL(config.email.imap_server)
            mail.login(config.email.user, config.email.app_password)
            mail.select("inbox")

            _, data = mail.search(None, "ALL")
            mail_ids = data[0].split()
            recent_ids = mail_ids[-quantidade:] if len(mail_ids) >= quantidade else mail_ids

            emails_list = []
            for m_id in reversed(recent_ids):
                _, msg_data = mail.fetch(m_id, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                
                subject, encoding = decode_header(msg["Subject"])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors="replace")
                
                sender = msg.get("From", "Desconhecido")
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="replace")
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="replace")

                emails_list.append(f"📧 **De:** {sender}\n**Assunto:** {subject}\n**Mensagem:**\n{body[:350]}...\n")

            mail.close()
            mail.logout()
            out = "\n---\n".join(emails_list) if emails_list else "Nenhum e-mail encontrado na caixa de entrada."
            return wrap_untrusted_content(truncate_output(out), source="Gmail-IMAP")
        except Exception as e:
            return f"Erro ao consultar e-mails: {e}"

    elif act == "enviar":
        if not destinatario:
            return "Erro: Destinatário não informado."

        dest_clean = destinatario.lower().strip()
        is_trusted = dest_clean in config.email.trusted_contacts
        has_attachment = bool(anexo)

        # Exige aprovação HITL se não for contato confiável ou se tiver anexo
        if not is_trusted or has_attachment:
            aprovado, msg = request_hitl(
                action_type="enviar_email",
                description=f"Envio de E-mail\nPara: {destinatario}\nAssunto: {assunto}\nAnexo: {anexo or 'Nenhum'}",
                details={"destinatario": destinatario, "assunto": assunto, "anexo": anexo},
                timeout_seconds=60
            )
            if not aprovado:
                return f"Envio cancelado: {msg}"

        # Valida anexo se informado
        safe_att = None
        if anexo:
            try:
                safe_att = resolve_and_check_path(anexo, operation="read")
                if not safe_att.exists():
                    return f"Erro: Arquivo anexo '{anexo}' não existe."
            except SecurityError as e:
                return f"Segurança: Anexo bloqueado - {e}"

        try:
            msg = MIMEMultipart()
            msg["From"] = config.email.user
            msg["To"] = destinatario
            msg["Subject"] = assunto
            msg.attach(MIMEText(corpo, "plain", "utf-8"))

            if safe_att:
                with open(safe_att, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename= {safe_att.name}")
                msg.attach(part)

            server = smtplib.SMTP_SSL(config.email.smtp_server, 465)
            server.login(config.email.user, config.email.app_password)
            server.send_message(msg)
            server.quit()
            return f"✅ E-mail enviado com sucesso para {destinatario}!"
        except Exception as e:
            return f"Falha no envio do e-mail: {e}"

    return f"Ação '{acao}' inválida. Use 'ler' ou 'enviar'."


# ==============================================================================
# FERRAMENTA 9: ENVIAR ARQUIVO PARA CELULAR (IPC OUTBOX VIA TELEGRAM)
# ==============================================================================
def enviar_arquivo_para_celular(caminho_arquivo: str, legenda: str = "") -> str:
    """Envia documento ou arquivo gerado para o celular do administrador pelo Telegram."""
    try:
        safe_path = resolve_and_check_path(caminho_arquivo, operation="read")
    except SecurityError as e:
        return f"Segurança: Envio bloqueado - {e}"

    if not safe_path.exists():
        return f"Erro: Arquivo '{caminho_arquivo}' não encontrado."

    # Validação de limite de 50 MB
    size_mb = safe_path.stat().st_size / (1024 * 1024)
    if size_mb > 50.0:
        return f"Erro: O arquivo tem {size_mb:.1f} MB, excedendo o limite de envio de 50 MB do Telegram."

    file_id = queue_outbox_file(str(safe_path), caption=legenda)
    return f"✅ Arquivo '{safe_path.name}' ({size_mb:.1f} MB) enfileirado para entrega no Telegram (ID #{file_id})."


# ==============================================================================
# FERRAMENTA 10: GERENCIAR MEMÓRIA (OPENVIKING L0/L1/L2)
# ==============================================================================
def gerenciar_memoria(acao: str, consulta_ou_conteudo: str, caminho_ou_uri: str = "", nivel: str = "L1") -> str:
    """Gerencia a memória hierárquica OpenViking (buscar resumos, salvar fatos, indexar caminhos)."""
    act = acao.lower().strip()

    if act == "buscar":
        return viking_mem.buscar(consulta=consulta_ou_conteudo, caminho_ou_uri=caminho_ou_uri, nivel=nivel)
    elif act in ["salvar_fato", "salvar"]:
        return viking_mem.salvar_fato(conteudo=consulta_ou_conteudo, uri=caminho_ou_uri)
    elif act in ["indexar", "indexar_caminho"]:
        return viking_mem.indexar_caminho(caminho=consulta_ou_conteudo)

    return f"Ação '{acao}' não suportada. Use 'buscar', 'salvar_fato' ou 'indexar_caminho'."


# ==============================================================================
# REGISTRO NO FASTMCP OU RUNNER STDIO
# ==============================================================================
if USE_FASTMCP and mcp is not None:
    mcp.tool()(pesquisar_web)
    mcp.tool()(ler_pagina_web)
    mcp.tool()(executar_comando_sistema)
    mcp.tool()(controlar_pc)
    mcp.tool()(ler_ou_buscar_arquivo)
    mcp.tool()(editar_documento)
    mcp.tool()(editar_imagem)
    mcp.tool()(gerenciar_email)
    mcp.tool()(enviar_arquivo_para_celular)
    mcp.tool()(gerenciar_memoria)


if __name__ == "__main__":
    if USE_FASTMCP and mcp is not None:
        mcp.run()
    else:
        # Fallback simples de inicialização se executado avulso
        print("Servidor MCP Periquito carregado (Modo Standalone).")
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
            except KeyboardInterrupt:
                break
