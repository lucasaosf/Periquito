"""
Terminal Interativo Local do Periquito AI
Permite testar e interagir diretamente pelo console com respostas de texto e voz.
"""

import sys
from core.brain import PeriquitoBrain

def run_console():
    brain = PeriquitoBrain()
    print("==================================================")
    print("       🦜 PERIQUITO AI - TERMINAL LOCAL           ")
    print("==================================================")
    print("Assistente Nativo Ativo. Digite 'sair' para encerrar.")
    print("--------------------------------------------------")

    while True:
        try:
            user_input = input("\nLucas > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["sair", "exit", "quit"]:
                print("🦜 Até logo, Lucas!")
                break

            result = brain.process_message(
                text=user_input,
                user_id="local_admin",
                username="Lucas",
                display_name="Macaco Opressor",
                channel="console"
            )

            print(f"\n{result.get('text', '')}")
            if result.get("file"):
                print(f"[Arquivo Anexo gerado]: {result['file']}")

        except (KeyboardInterrupt, EOFError):
            print("\n🦜 Encerrando sessão...")
            break

if __name__ == "__main__":
    run_console()
