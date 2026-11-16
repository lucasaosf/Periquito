/**
 * Periquito AI - 3D Voice Orb Visualizer (Estilo ChatGPT Advanced Voice Mode)
 * Renderizado em WebGL acelerado por hardware via Three.js.
 * Deforma e ondula organicamente em tempo real em sincronia com as frequências da voz!
 */

class VoiceOrb3D {
    constructor(canvasContainerId, audioElement) {
        this.container = document.getElementById(canvasContainerId);
        this.audio = audioElement;
        
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.sphere = null;
        this.origPositions = null;
        this.simplex = new SimplexNoise();
        
        // Estado de áudio
        this.audioCtx = null;
        this.analyser = null;
        this.dataArray = null;
        this.audioConnected = false;
        this.isSpeaking = false;
        
        // Parâmetros de animação
        this.time = 0;
        this.soundIntensity = 0;
        this.targetIntensity = 0;
        this.baseRadius = 2.4;
        
        this.initThree();
        this.setupAudio();
        this.animate();
        
        window.addEventListener('resize', () => this.onResize());
    }

    initThree() {
        const width = this.container.clientWidth || window.innerWidth;
        const height = this.container.clientHeight || (window.innerHeight - 80);

        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x05070a); // Preto profundo cibernético

        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
        this.camera.position.z = 8;

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.2;
        this.container.appendChild(this.renderer.domElement);

        // Geometria da Esfera com alto detalhe para ondas orgânicas fluídas
        const geometry = new THREE.IcosahedronGeometry(this.baseRadius, 48);
        this.origPositions = geometry.attributes.position.clone();

        // Material translúcido líquido com reflexos de luz volumétrica
        const material = new THREE.MeshPhysicalMaterial({
            color: 0x10b981,           // Verde Esmeralda do Periquito
            emissive: 0x064e3b,        // Brilho interno verde escuro
            roughness: 0.15,
            metalness: 0.1,
            clearcoat: 1.0,
            clearcoatRoughness: 0.1,
            transmission: 0.4,          // Efeito fluido translúcido
            ior: 1.33,
            reflectivity: 0.8,
            wireframe: false
        });

        this.sphere = new THREE.Mesh(geometry, material);
        this.scene.add(this.sphere);

        // Sistema de Iluminação Dinâmica 3D
        const ambientLight = new THREE.AmbientLight(0x064e3b, 1.5);
        this.scene.add(ambientLight);

        // Luzes orbitais com cores neon (Verde Periquito, Ciano e Azul Elétrico)
        this.lightGreen = new THREE.PointLight(0x10b981, 4, 15);
        this.lightGreen.position.set(4, 3, 4);
        this.scene.add(this.lightGreen);

        this.lightCyan = new THREE.PointLight(0x06b6d4, 4, 15);
        this.lightCyan.position.set(-4, -3, 3);
        this.scene.add(this.lightCyan);

        this.lightBlue = new THREE.PointLight(0x3b82f6, 3, 15);
        this.lightBlue.position.set(0, 4, -3);
        this.scene.add(this.lightBlue);
    }

    setupAudio() {
        const connect = () => {
            if (this.audioConnected) return;
            try {
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                this.audioCtx = new AudioContext();
                this.analyser = this.audioCtx.createAnalyser();
                this.analyser.fftSize = 256;
                this.analyser.smoothingTimeConstant = 0.8;

                const source = this.audioCtx.createMediaElementSource(this.audio);
                source.connect(this.analyser);
                this.analyser.connect(this.audioCtx.destination);

                this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
                this.audioConnected = true;
            } catch (e) {
                console.warn("Áudio Context já iniciado ou bloqueado até clique:", e);
            }
        };

        // Ativação suave com o clique ou ao tocar o áudio
        this.audio.addEventListener('play', () => {
            if (this.audioCtx && this.audioCtx.state === 'suspended') {
                this.audioCtx.resume();
            }
            connect();
            this.isSpeaking = true;
        });

        this.audio.addEventListener('pause', () => {
            this.isSpeaking = false;
        });

        this.audio.addEventListener('ended', () => {
            this.isSpeaking = false;
        });

        window.addEventListener('click', () => {
            if (this.audioCtx && this.audioCtx.state === 'suspended') {
                this.audioCtx.resume();
            }
        }, { once: true });
    }

    updateDeformation() {
        const positions = this.sphere.geometry.attributes.position;
        const orig = this.origPositions;

        // Leitura de Frequências de Áudio
        let audioVolume = 0;
        let bass = 0;
        let treble = 0;

        if (this.analyser && this.isSpeaking) {
            this.analyser.getByteFrequencyData(this.dataArray);
            let sum = 0;
            const len = this.dataArray.length;
            for (let i = 0; i < len; i++) {
                sum += this.dataArray[i];
                if (i < 8) bass += this.dataArray[i];
                if (i > len - 20) treble += this.dataArray[i];
            }
            audioVolume = sum / len / 255;
            bass = bass / 8 / 255;
            treble = treble / 20 / 255;
            this.targetIntensity = audioVolume * 2.8;
        } else {
            this.targetIntensity = 0.05; // Respiração suave em idle
        }

        // Interpolação suave (lerp) para evitar movimentos bruscos
        this.soundIntensity += (this.targetIntensity - this.soundIntensity) * 0.12;

        const noiseFreq = 0.65 + this.soundIntensity * 0.4;
        const noiseSpeed = this.isSpeaking ? 0.025 : 0.008;
        this.time += noiseSpeed;

        const count = positions.count;
        for (let i = 0; i < count; i++) {
            const ox = orig.getX(i);
            const oy = orig.getY(i);
            const oz = orig.getZ(i);

            // Simplex Noise 3D para relevo ondulado orgânico
            const n = this.simplex.noise3D(
                ox * noiseFreq + this.time,
                oy * noiseFreq + this.time * 0.8,
                oz * noiseFreq + this.time * 1.2
            );

            // Deformação dinâmica: base orgânica + impacto sonoro em tempo real
            const displacement = 1.0 + (n * 0.12) + (n * this.soundIntensity * 0.45) + (this.soundIntensity * 0.15);

            positions.setXYZ(i, ox * displacement, oy * displacement, oz * displacement);
        }

        positions.needsUpdate = true;
        this.sphere.geometry.computeVertexNormals();

        // Rotação suave da esfera
        this.sphere.rotation.y += 0.003;
        this.sphere.rotation.x = Math.sin(this.time * 0.5) * 0.1;

        // Movimento dinâmico das luzes com o som
        const pulse = 1.0 + this.soundIntensity * 2.0;
        this.lightGreen.intensity = 3.5 * pulse;
        this.lightCyan.intensity = 3.0 * pulse;
        this.lightBlue.intensity = 2.5 * pulse;

        // Órbita sutil das luzes
        this.lightGreen.position.x = Math.sin(this.time) * 4;
        this.lightGreen.position.z = Math.cos(this.time) * 4;
        this.lightCyan.position.x = -Math.sin(this.time * 0.8) * 4;
        this.lightCyan.position.y = -Math.cos(this.time * 0.8) * 3;
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        this.updateDeformation();
        this.renderer.render(this.scene, this.camera);
    }

    onResize() {
        if (!this.container) return;
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }
}
