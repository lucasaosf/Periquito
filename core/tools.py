"""
Módulo de Ferramentas e Execução no Sistema do Periquito AI
Adaptado e enriquecido com módulos de alta performance do OpenJarvis (Stanford SAIL / Hazy Research).
Fornece capacidades de automação no Windows, busca na web, matemática segura e checagens de integridade.
"""

import os
import sys
import ast
import math
import psutil
import shutil
import operator
import datetime
import requests
import subprocess
from typing import Dict, Any, Optional, List

PROJECTS_DIR = r"C:\Users\Lucas Aosf\Documents\!!!___ANTIGRAVITY___!!!"
QGIS_AUTOMATION_DIR = os.path.join(PROJECTS_DIR, "QGIS_Automation")

# ==============================================================================
# 1. CALCULADORA MATEMÁTICA SEGURA (Portada do OpenJarvis)
# ==============================================================================
_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_MATH_FUNCS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "log": math.log,
    "ln": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "pi": math.pi,
    "e": math.e,
    "ceil": math.ceil,
    "floor": math.floor,
}

def _safe_eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, complex)):
            return node.value
        raise ValueError(f"Tipo não suportado: {type(node.value).__name__}")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BINOPS:
            raise ValueError(f"Operador binário não suportado: {op_type.__name__}")
        return _BINOPS[op_type](_safe_eval_node(node.left), _safe_eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARYOPS:
            raise ValueError(f"Operador unário não suportado: {op_type.__name__}")
        return _UNARYOPS[op_type](_safe_eval_node(node.operand))
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Apenas chamadas simples de função são permitidas")
        fname = node.func.id
        if fname not in _MATH_FUNCS:
            raise ValueError(f"Função matemática desconhecida: {fname}")
        args = [_safe_eval_node(a) for a in node.args]
        return _MATH_FUNCS[fname](*args)
    if isinstance(node, ast.Name):
        name = node.id
        if name in _MATH_FUNCS:
            val = _MATH_FUNCS[name]
            if isinstance(val, (int, float)):
                return val
        raise ValueError(f"Variável desconhecida: {name}")
    raise ValueError(f"Expressão inválida: {type(node).__name__}")


def safe_math_eval(expression: str) -> str:
    """Calcula expressões matemáticas com total segurança contra injeção de código."""
    clean_expr = expression.replace("^", "**").replace("x", "*").replace("X", "*")
    try:
        tree = ast.parse(clean_expr, mode="eval")
        res = _safe_eval_node(tree.body)
        return f"{res}"
    except ZeroDivisionError:
        return "Erro: divisão por zero."
    except Exception as e:
        return f"Erro de cálculo: {e}"


# ==============================================================================
# 2. MAPEAMENTO DE APLICATIVOS
# ==============================================================================
APPS_MAP = {
    "qgis": r"D:\QGIS\bin\qgis-ltr.bat",
    "rstudio": r"C:\Program Files\RStudio\rstudio.exe",
    "discord": r"C:\Users\Lucas Aosf\AppData\Local\Discord\Update.exe --processStart Discord.exe",
    "steam": r"C:\Program Files (x86)\Steam\steam.exe",
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "antigravity": r"C:\Users\Lucas Aosf\AppData\Local\Programs\antigravity\Antigravity.exe",
    "explorer": "explorer.exe",
    "projetos": f"explorer.exe \"{PROJECTS_DIR}\""
}


class SystemTools:
    @staticmethod
    def get_system_status() -> Dict[str, Any]:
        """Obtém informações em tempo real de hardware, uso de disco e memória."""
        cpu_usage = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        
        disks = {}
        for d in ["C:", "D:"]:
            if os.path.exists(d):
                usage = shutil.disk_usage(d)
                disks[d] = {
                    "livre_gb": round(usage.free / (1024**3), 1),
                    "total_gb": round(usage.total / (1024**3), 1),
                    "percent_livre": round((usage.free / usage.total) * 100, 1)
                }

        gpu_info = "NVIDIA GeForce GTX 1070 (8 GB VRAM)"
        try:
            out = subprocess.check_output("wmic path win32_VideoController get name", shell=True).decode()
            names = [l.strip() for l in out.splitlines() if l.strip() and "Name" not in l]
            if names:
                gpu_info = ", ".join(names)
        except Exception:
            pass

        return {
            "cpu_percent": cpu_usage,
            "ram_total_gb": round(mem.total / (1024**3), 1),
            "ram_usada_gb": round(mem.used / (1024**3), 1),
            "ram_percent": mem.percent,
            "gpu": gpu_info,
            "discos": disks,
            "horario": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }

    @staticmethod
    def open_application(app_name: str) -> str:
        """Abre um aplicativo configurado."""
        name_clean = app_name.lower().strip()
        for key, path in APPS_MAP.items():
            if key in name_clean:
                try:
                    subprocess.Popen(path, shell=True)
                    return f"Aplicativo '{key.upper()}' iniciado com sucesso!"
                except Exception as e:
                    return f"Erro ao iniciar '{key}': {e}"
        return f"Aplicativo '{app_name}' não reconhecido na lista de atalhos rápidos."

    @staticmethod
    def list_projects() -> str:
        """Lista os projetos na pasta central do Lucas."""
        if not os.path.exists(PROJECTS_DIR):
            return "Pasta de projetos não encontrada."
        items = os.listdir(PROJECTS_DIR)
        dirs = [d for d in items if os.path.isdir(os.path.join(PROJECTS_DIR, d))]
        return f"Projetos encontrados em {PROJECTS_DIR}:\n" + "\n".join([f"📁 {d}" for d in dirs])

    @staticmethod
    def generate_qgis_map(input_file: Optional[str] = None, title: str = "MAPA TEMÁTICO", basemap: str = "google_satellite") -> str:
        """Executa a engine QGIS MapMaker para gerar um mapa."""
        script_path = os.path.join(QGIS_AUTOMATION_DIR, "gerar_mapa.py")
        if not os.path.exists(script_path):
            return "Módulo QGIS_Automation não encontrado."

        cmd = [sys.executable, script_path, "--title", title, "--basemap", basemap]
        if input_file:
            cmd.extend(["--input", input_file])

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode == 0:
                return f"Mapa gerado com sucesso pelo PyQGIS!\n{res.stdout[-300:]}"
            return f"Erro na geração do mapa: {res.stderr}"
        except Exception as e:
            return f"Falha ao executar gerador de mapa: {e}"

    @staticmethod
    def take_screenshot(output_path: Optional[str] = None) -> Optional[str]:
        """Tira um print da tela do computador."""
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            if not output_path:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                output_path = os.path.join(base_dir, "data", "audio_temp", f"print_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            screenshot.save(output_path)
            return output_path
        except Exception:
            return None

    @staticmethod
    def web_search(query: str, max_results: int = 4) -> str:
        """Busca na web em tempo real usando DuckDuckGo (OpenJarvis engine)."""
        try:
            from ddgs import DDGS
            ddgs = DDGS()
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "Nenhum resultado encontrado para a busca."
            
            snippets = []
            for r in results:
                title = r.get("title", "Sem título")
                url = r.get("href", "")
                snippet = r.get("body", "")
                snippets.append(f"• **{title}**\n  {snippet}\n  Fonte: {url}")
            return "\n\n".join(snippets)
        except Exception as e:
            return f"Erro ao realizar pesquisa na web: {e}"

    @staticmethod
    def get_weather(location: str = "") -> str:
        """Consulta previsão do tempo instantânea."""
        try:
            loc = location.strip().replace(" ", "+") if location.strip() else ""
            url = f"https://wttr.in/{loc}?format=3"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return r.text.strip()
            return "Não foi possível obter dados meteorológicos no momento."
        except Exception as e:
            return f"Erro ao consultar clima: {e}"
