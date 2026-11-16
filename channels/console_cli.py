"""
Terminal Interativo Local do Periquito AI
Permite testar e interagir diretamente pelo console com respostas de texto e voz.
"""

import sys
import re
from core.brain import PeriquitoBrain

def clean_markdown_for_speech(text: str) -> str:
    """Limpa marcações de markdown e emojis para fala natural."""
    clean = re.sub(r"[*#_`~•]", "", text)
    clean = clean.replace("🦜", "").strip()
    return clean

def run_console():
    brain = PeriquitoBrain()
    voice_active = True

    print("==================================================")
    print("       🦜 PERIQUITO AI - TERMINAL LOCAL           ")
    print("==================================================")
    print("Assistente Nativo Ativo no PC do Lucas.")
    print("Comandos de utilidade:")
    print("  • 'sair'   -> encerra o terminal")
    print("  • 'voz on' / 'voz off' -> ativa/desativa áudio falado")
    print("--------------------------------------------------")

    while True:
        try:
            user_input = input("\nLucas > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["sair", "exit", "quit"]:
                print("🦜 Até logo, Lucas!")
                break
            if user_input.lower() == "voz on":
                voice_active = True
                print("🦜 Respostas por voz ATIVADAS!")
                continue
            if user_input.lower() == "voz off":
                voice_active = False
                print("🦜 Respostas por voz DESATIVADAS (somente texto).")
                continue

            result = brain.process_message(
                text=user_input,
                user_id="local_admin",
                username="Lucas Aosf",
                display_name="Lucas Aosf",
                channel="console"
            )

            text_resp = result.get("text", "")
            print(f"\n{text_resp}")

            if result.get("file"):
                print(f"[Arquivo Anexo gerado]: {result['file']}")

            # Se a voz estiver ativa, sintetiza e reproduz
            if voice_active and text_resp:
                speech_text = clean_markdown_for_speech(text_resp)
                if len(speech_text) > 3:
                    try:
                        audio_path = brain.voice.generate_audio_sync(speech_text[:500])
                        brain.voice.play_audio(audio_path)
                    except Exception:
                        pass

        except (KeyboardInterrupt, EOFError):
            print("\n🦜 Encerrando sessão...")
            break

if __name__ == "__main__":
    run_console()
