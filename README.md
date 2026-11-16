<div align="center">
  <img alt="Periquito AI" src="assets/periquito_avatar.jpg" width="300" style="border-radius: 20px;">

  # 🦜 Periquito AI — Assistente Pessoal Nativo

  <p><i>Assistente de Inteligência Artificial Local e Multicanal para Automação, Voz e Produtividade no Windows</i></p>

  <p>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-green.svg" alt="License"></a>
    <img src="https://img.shields.io/badge/python-3.12-blue.svg" alt="Python">
    <img src="https://img.shields.io/badge/plataforma-Windows%2011-0078D4.svg" alt="Windows 11">
    <img src="https://img.shields.io/badge/hardware-GTX%201070%20%7C%2036GB%20RAM-76B900.svg" alt="Nvidia">
    <img src="https://img.shields.io/badge/canais-Discord%20%7C%20Telegram%20%7C%20CLI-5865F2.svg" alt="Canais">
  </p>
</div>

---

## 🎯 Sobre o Projeto

O **Periquito AI** é um ecossistema de assistente pessoal nativo (*on-device personal AI*), projetado para rodar diretamente no computador pessoal com conexão simultânea via **Discord**, **Telegram**, **Central de Comando Web (Cockpit 3D)** e **Terminal Local**.

Inspirado nos conceitos arquiteturais do projeto de pesquisa **[OpenJarvis](https://github.com/open-jarvis/OpenJarvis)** (Stanford University), o Periquito foi adaptado e reescrito em Python para atender com máxima agilidade tarefas de automação, engenharia, consultoria ambiental e controle do sistema.

---

## 🧠 Arquitetura do Cérebro Híbrido (Multi-Engine)

O Periquito opera através de um roteador inteligente de modelos (*Mixture of Engines*), direcionando cada tipo de tarefa para o motor mais adequado:

<div align="center">
  <img alt="Fluxo do Cérebro do Periquito AI" src="assets/fluxo_cerebro.png" width="750" style="border-radius: 12px; margin-bottom: 20px;">
</div>

```mermaid
flowchart TD
    User["Usuário (Discord / Telegram / Console)"] --> Brain["🦜 Cérebro do Periquito (Roteador Inteligente)"]
    
    Brain -->|"1. Conversa rápida e comandos diretos"| Groq["⚡ Groq (LPU - Velocidade da luz ~300 tokens/s)"]
    Brain -->|"2. Raciocínio profundo, resumos e busca"| Gemini["🧠 Google Gemini (Janela gigante e análise profunda)"]
    Brain -->|"3. Tarefas privadas ou internet offline"| Ollama["💻 Ollama Local (GTX 1070 - 100% offline)"]
    
    Groq --> Resposta["💬 Resposta Unificada + Voz do Periquito"]
    Gemini --> Resposta
    Ollama --> Resposta
```

1. **⚡ Groq (LPU - Ultra Velocidade):** Respostas em ~1 segundo para bate-papos rápidos, comandos do dia a dia e conversação contínua.
2. **🧠 Google Gemini (Raciocínio Analítico Profundo):** Processamento de grandes volumes de texto, análise de código e tarefas complexas.
3. **💻 Ollama Local (Privacidade Total & 100% Offline):** Modelo rodando direto na GPU dedicada (GTX 1070) para contingência sem internet e tarefas privadas.
4. **💬 Resposta Unificada & Voz Natural:** Todo texto passa pelo higienizador de fala (`clean_text_for_speech`) e é sintetizado com voz humana via Edge-TTS sem soletração de emojis ou símbolos técnicos.

---

## ✨ Principais Funcionalidades

* 🧠 **Cérebro Unificado:** O Discord, o Telegram e o Console conectam-se ao mesmo motor e compartilham o mesmo estado e contexto.
* 🗣️ **Respostas por Voz (TTS):** Síntese de voz ultranatural em Português do Brasil com entonação humana via Edge-TTS (`pt-BR-AntonioNeural`), sem latência ou custo de API.
* 💾 **Memória Permanente e Aprendizado Contínuo:** Banco de dados SQLite local (`memory.db`) onde fatos, preferências, atalhos e rotinas são gravados para que você nunca precise repetir nada.
* 🛡️ **Segurança Rigorosa e Controle de Permissões:**
  * O assistente **obedece a comandos do sistema exclusivamente quando enviados pelo proprietário autenticado** (ou IDs configurados no `.env`).
  * Usuários convidados podem conversar normalmente na chamada ou chat, mas ações no sistema operacional (abrir programas, ler arquivos, executar scripts) são sumariamente bloqueadas.
* 🖥️ **Automação no PC:**
  * Monitoramento de hardware em tempo real (CPU, RAM, GPU GTX 1070, espaço nos discos C: e D:).
  * Abertura rápida de aplicativos e atalhos (QGIS, RStudio, Steam, Discord, Chrome, Pastas).
  * Captura instantânea de tela (*screenshot*).
  * Integração nativa com o gerador cartográfico **QGIS MapMaker** (`QGIS_Automation`).

---

## 📁 Estrutura do Repositório

```text
Periquito/
├── assets/
│   ├── periquito_avatar.jpg        # Foto de perfil oficial do Periquito
│   └── fluxo_cerebro.png           # Diagrama da arquitetura do cérebro Multi-Engine
├── config/
│   ├── .env.example                # Modelo de variáveis de ambiente
│   └── config.yaml                 # Parâmetros gerais e preferências
├── core/
│   ├── brain.py                    # Cérebro orquestrador (ReAct / CodeAct)
│   ├── memory.py                   # Banco de memória e aprendizado (SQLite)
│   ├── security.py                 # Validação de proprietário e permissões
│   ├── voice.py                    # Motor de síntese de voz (Edge-TTS)
│   └── tools.py                    # Ações no Windows (hardware, apps, QGIS, print)
├── channels/
│   ├── discord_bot.py              # Bot do Discord (texto, áudio e comandos)
│   ├── telegram_bot.py             # Bot do Telegram (mensagens e fotos)
│   └── console_cli.py              # Terminal interativo local
├── data/
│   ├── memory.db                   # Banco de memória persistente (ignorado no Git)
│   └── audio_temp/                 # Cache de áudios gerados
├── main.py                         # Ponto de entrada do sistema
├── requirements.txt                # Dependências Python
├── .gitignore                      # Proteção total contra vazamento de credenciais
├── LICENSE                         # Licença Apache 2.0 com créditos
└── README.md                       # Documentação do projeto
```

---

## 🚀 Como Executar

### 1. Configurar Credenciais Seguras
Copie o modelo de ambiente e preencha seus tokens:
```bash
cp config/.env.example config/.env
```
*(O arquivo `config/.env` é estritamente ignorado pelo `.gitignore` para garantir que nenhum token ou segredo seja vazado).*

### 2. Modos de Execução
* **Terminal Interativo Local:**
  ```bash
  python main.py --cli
  ```
* **Apenas Bot do Discord:**
  ```bash
  python main.py --discord
  ```
* **Apenas Bot do Telegram:**
  ```bash
  python main.py --telegram
  ```
* **Todos os canais simultaneamente:**
  ```bash
  python main.py --all
  ```

---

## 🤝 Créditos e Reconhecimento

Este projeto utiliza conceitos e fundamentos arquiteturais derivados do ecossistema de pesquisa de código aberto **OpenJarvis** (desenvolvido por *Hazy Research* e *Stanford SAIL* na Universidade de Stanford).

* Repositório Original: [https://github.com/open-jarvis/OpenJarvis](https://github.com/open-jarvis/OpenJarvis)
* Artigo Científico: [arXiv:2605.17172](https://arxiv.org/abs/2605.17172)

---

## Citation

Para citar este projeto:

```bibtex
@misc{ferreira2026periquitoai,
  title={Periquito AI: Assistente Pessoal Nativo Multicanal para Automação no Windows},
  author={Lucas Aosf},
  year={2026},
  publisher={GitHub},
  journal={GitHub repository},
  howpublished={\url{https://github.com/lucasaosf/Periquito}},
  url={https://github.com/lucasaosf/Periquito}
}
```

Para citar a base de pesquisa OpenJarvis (Stanford):

```bibtex
@misc{saadfalcon2026openjarvispersonalaipersonal,
  title={OpenJarvis: Personal AI, On Personal Devices}, 
  author={Jon Saad-Falcon and Avanika Narayan and Robby Manihani and Tanvir Bhathal and Herumb Shandilya and Hakki Orhun Akengin and Gabriel Bo and Andrew Park and Matthew Hart and Caia Costello and Chuan Li and Christopher Ré and Azalia Mirhoseini},
  year={2026},
  eprint={2605.17172},
  archivePrefix={arXiv},
  primaryClass={cs.LG},
  url={https://arxiv.org/abs/2605.17172}
}
```

---

## 📄 Licença

Distribuído sob a licença [Apache 2.0](LICENSE).
