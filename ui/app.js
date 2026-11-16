/**
 * Periquito AI - Lógica da Interface da Central de Comando & Modo Voz 3D
 */

document.addEventListener("DOMContentLoaded", () => {
    // Elementos DOM
    const audioElement = document.getElementById("periquito-audio");
    const orbContainer = document.getElementById("orb-container");
    
    // Inicializa o Orbe 3D fluido
    let orb = null;
    try {
        orb = new VoiceOrb3D("orb-container", audioElement);
    } catch (e) {
        console.warn("Falha ao inicializar WebGL:", e);
    }

    // Alternador de Modos
    const btnModeVoice = document.getElementById("btn-mode-voice");
    const btnModeCockpit = document.getElementById("btn-mode-cockpit");
    const viewVoice = document.getElementById("view-voice");
    const viewCockpit = document.getElementById("view-cockpit");

    btnModeVoice.addEventListener("click", () => {
        btnModeVoice.classList.add("active");
        btnModeCockpit.classList.remove("active");
        viewVoice.classList.add("active");
        viewCockpit.classList.remove("active");
        if (orb) setTimeout(() => orb.onResize(), 50);
    });

    btnModeCockpit.addEventListener("click", () => {
        btnModeCockpit.classList.add("active");
        btnModeVoice.classList.remove("active");
        viewCockpit.classList.add("active");
        viewVoice.classList.remove("active");
    });

    // Elementos do Modo Voz
    const voiceCaption = document.getElementById("voice-caption");
    const voiceTextInput = document.getElementById("voice-text-input");
    const voiceSendBtn = document.getElementById("voice-send-btn");
    const voiceMicBtn = document.getElementById("voice-mic-btn");

    // Elementos do Cockpit
    const cockpitInput = document.getElementById("cockpit-input");
    const cockpitSendBtn = document.getElementById("cockpit-send-btn");
    const chatMessages = document.getElementById("chat-messages");

    // ==============================================================================
    // ENVIO E PROCESSAMENTO DE MENSAGENS
    // ==============================================================================
    async function sendMessage(text, mode = "voice") {
        const clean = text.trim();
        if (!clean) return;

        // Limpa campos
        voiceTextInput.value = "";
        cockpitInput.value = "";

        if (mode === "voice") {
            voiceCaption.innerText = `Você: "${clean}"\n(Pensando...)`;
        }

        // Adiciona mensagem do usuário no Cockpit
        appendChatMessage("user", "Lucas Aosf", clean);

        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: clean, voice: true })
            });

            const data = await res.json();
            const respText = data.text || "Sem resposta.";
            const audioUrl = data.audio_url;
            const fileUrl = data.file_url;

            // Atualiza Modo Voz
            if (mode === "voice") {
                voiceCaption.innerText = respText;
            }

            // Atualiza Cockpit
            appendChatMessage("bot", "Periquito AI", respText, audioUrl, fileUrl);

            // Toca áudio automaticamente (isso aciona a deformação 3D do Orbe no ritmo da voz!)
            if (audioUrl) {
                audioElement.src = audioUrl;
                audioElement.play().catch(e => console.warn("Autoplay prevenido pelo navegador:", e));
            }

        } catch (e) {
            console.error("Erro na requisição:", e);
            if (mode === "voice") {
                voiceCaption.innerText = "Erro ao se comunicar com o cérebro do Periquito.";
            }
            appendChatMessage("bot", "Periquito AI", "⚠️ Erro de conexão com a Central.");
        }
    }

    function appendChatMessage(sender, name, content, audioUrl = null, fileUrl = null) {
        const row = document.createElement("div");
        row.className = `msg-row ${sender}`;

        const avatar = sender === "bot" ? "🦜" : "👤";
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        let audioBtnHtml = "";
        if (audioUrl) {
            audioBtnHtml = `<button class="btn-play-audio" data-url="${audioUrl}">▶ Ouvir Áudio</button>`;
        }

        let fileHtml = "";
        if (fileUrl) {
            fileHtml = `<div style="margin-top: 10px;"><img src="${fileUrl}" style="max-width: 100%; border-radius: 8px; border: 1px solid var(--border-color);"></div>`;
        }

        row.innerHTML = `
            <div class="msg-avatar">${avatar}</div>
            <div class="msg-body">
                <div class="msg-header">
                    <strong>${name}</strong>
                    <span class="time">${time}</span>
                </div>
                <div class="msg-content">${content.replace(/\n/g, "<br>")}</div>
                ${fileHtml}
                ${audioBtnHtml}
            </div>
        `;

        chatMessages.appendChild(row);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Event listener para botão de ouvir
        const btnPlay = row.querySelector(".btn-play-audio");
        if (btnPlay) {
            btnPlay.addEventListener("click", () => {
                audioElement.src = btnPlay.getAttribute("data-url");
                audioElement.play();
            });
        }
    }

    // Eventos de envio
    voiceSendBtn.addEventListener("click", () => sendMessage(voiceTextInput.value, "voice"));
    voiceTextInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendMessage(voiceTextInput.value, "voice");
    });

    cockpitSendBtn.addEventListener("click", () => sendMessage(cockpitInput.value, "cockpit"));
    cockpitInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendMessage(cockpitInput.value, "cockpit");
    });

    // Chips Rápidos
    document.querySelectorAll(".chip").forEach(chip => {
        chip.addEventListener("click", () => {
            const cmd = chip.getAttribute("data-cmd");
            sendMessage(cmd, "voice");
        });
    });

    // Ações Rápidas de Ferramentas (QGIS, RStudio, Print)
    document.querySelectorAll(".tool-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
            const action = btn.getAttribute("data-tool");
            try {
                const res = await fetch("/api/tools/run", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ action })
                });
                const data = await res.json();
                appendChatMessage("bot", "Periquito AI", data.message || "Ação executada.", null, data.file_url);
            } catch (e) {
                console.error("Erro na ferramenta:", e);
            }
        });
    });

    // ==============================================================================
    // RECONHECIMENTO DE VOZ (MICROFONE)
    // ==============================================================================
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.lang = "pt-BR";
        recognition.continuous = false;
        recognition.interimResults = false;

        voiceMicBtn.addEventListener("click", () => {
            if (voiceMicBtn.classList.contains("listening")) {
                recognition.stop();
                voiceMicBtn.classList.remove("listening");
            } else {
                voiceMicBtn.classList.add("listening");
                voiceCaption.innerText = "Ouvindo você... Fale agora!";
                recognition.start();
            }
        });

        recognition.onresult = (event) => {
            voiceMicBtn.classList.remove("listening");
            const transcript = event.results[0][0].transcript;
            if (transcript) {
                sendMessage(transcript, "voice");
            }
        };

        recognition.onerror = () => {
            voiceMicBtn.classList.remove("listening");
            voiceCaption.innerText = "Não consegui ouvir. Tente novamente ou digite.";
        };

        recognition.onend = () => {
            voiceMicBtn.classList.remove("listening");
        };
    } else {
        voiceMicBtn.style.display = "none";
    }

    // ==============================================================================
    // MONITORAMENTO DE HARDWARE E DISCORD (POLL PERIÓDICO)
    // ==============================================================================
    const btnToggleDiscord = document.getElementById("btn-toggle-discord");
    const discordBadge = document.getElementById("discord-badge");
    const discordGuilds = document.getElementById("discord-guilds");

    btnToggleDiscord.addEventListener("click", async () => {
        btnToggleDiscord.innerText = "...";
        try {
            await fetch("/api/services/discord/toggle", { method: "POST" });
            updateStatus();
        } catch (e) {
            console.error(e);
        }
    });

    async function updateStatus() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();

            // Hardware
            const hw = data.hardware;
            if (hw) {
                document.getElementById("hw-cpu-val").innerText = `${hw.cpu_percent}%`;
                document.getElementById("hw-cpu-bar").style.width = `${hw.cpu_percent}%`;

                document.getElementById("hw-ram-val").innerText = `${hw.ram_usada_gb} / ${hw.ram_total_gb} GB (${hw.ram_percent}%)`;
                document.getElementById("hw-ram-bar").style.width = `${hw.ram_percent}%`;

                if (hw.gpu) document.getElementById("hw-gpu-val").innerText = hw.gpu;

                const c = hw.discos?.["C:"]?.livre_gb || "--";
                const d = hw.discos?.["D:"]?.livre_gb || "--";
                document.getElementById("hw-disk-c").innerText = `${c} GB livres`;
                document.getElementById("hw-disk-d").innerText = `${d} GB livres`;
            }

            // Discord
            const disc = data.services?.discord;
            if (disc) {
                if (disc.running) {
                    discordBadge.className = "status-pill status-on";
                    discordBadge.innerText = "Online";
                    btnToggleDiscord.innerText = "Desligar";
                    if (disc.guilds && disc.guilds.length > 0) {
                        discordGuilds.innerText = disc.guilds.join(", ");
                    }
                } else {
                    discordBadge.className = "status-pill status-off";
                    discordBadge.innerText = "Offline";
                    btnToggleDiscord.innerText = "Ligar";
                }
            }
        } catch (e) {
            // Ignora falhas pontuais de polling
        }
    }

    // Atualiza a cada 3 segundos
    updateStatus();
    setInterval(updateStatus, 3000);
});
