"""
Módulo de Ferramentas e Execução no Sistema do Periquito AI
Fornece capacidades de automação no Windows com checagens de segurança.
"""

import os
import sys
import psutil
import shutil
import datetime
import subprocess
from typing import Dict, Any, Optional

PROJECTS_DIR = r"C:\Users\Lucas Aosf\Documents\!!!___ANTIGRAVITY___!!!"
QGIS_AUTOMATION_DIR = os.path.join(PROJECTS_DIR, "QGIS_Automation")

# Mapeamento de aplicativos para inicialização rápida
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

        # Informações da GPU
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
        except Exception as e:
            return None
