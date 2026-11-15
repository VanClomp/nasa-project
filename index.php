<?php
// index.php - Minimalistyczny ekran wyboru celu (SpaceX / Linear / NASA JPL Aesthetic)
?>
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Planetary Analog Finder — Wybór Celu</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <link rel="stylesheet" href="style.css">
</head>
<body>

    <div class="ambient-backdrop"></div>

    <header class="topbar">
        <div class="brand">
            <span class="brand-mark"></span>
            <span class="brand-name">Planetary Analog Finder</span>
            <span class="brand-tag">NASA Space Apps 2026</span>
        </div>
        <div class="topbar-meta">
            <span>DATA: LRO / MOLA / MODIS</span>
            <span>ENGINE: SPARSE MATRIX (9D)</span>
        </div>
    </header>

    <section class="header-section">
        <h1 class="header-title">Wybierz ciało niebieskie</h1>
        <p class="header-subtitle">
            Wyszukiwanie ziemskich analogów geologicznych i środowiskowych na podstawie 9-wymiarowych wektorów satelitarnych.
        </p>
    </section>

    <main class="tiles-grid">

        <!-- KAFELEK 01: KSIĘŻYC -->
        <article class="celestial-card card-moon" id="card-moon" data-target="moon">
            <div class="card-top">
                <span class="card-index"><span class="card-index-dot"></span>01 / LUNA</span>
                <span>LRO LOLA · DIVINER · LEND</span>
            </div>

            <div class="planet-viewport">
                <div class="canvas-holder" id="moon-holder"></div>
            </div>

            <div class="card-bottom">
                <div class="title-row">
                    <h2 class="planet-title">Księżyc</h2>
                    <span class="action-indicator">Otwórz telemetrię →</span>
                </div>
                <p class="planet-summary">
                    Analiza kraterów biegunowych, bazaltowych mórz księżycowych oraz podpowierzchniowych tuneli lawowych pod kątem misji Artemis.
                </p>
                <div class="metrics-bar">
                    <div class="metric-cell">
                        <span class="metric-label">Zakres temp.</span>
                        <span class="metric-value">-180 do +120 °C</span>
                    </div>
                    <div class="metric-cell">
                        <span class="metric-label">Nachylenie osi</span>
                        <span class="metric-value">1.54°</span>
                    </div>
                    <div class="metric-cell">
                        <span class="metric-label">Grawitacja</span>
                        <span class="metric-value">1.62 m/s²</span>
                    </div>
                    <div class="metric-cell">
                        <span class="metric-label">Główne analogi</span>
                        <span class="metric-value">McMurdo · Devon</span>
                    </div>
                </div>
            </div>
        </article>

        <!-- KAFELEK 02: MARS -->
        <article class="celestial-card card-mars" id="card-mars" data-target="mars">
            <div class="card-top">
                <span class="card-index"><span class="card-index-dot"></span>02 / MARS</span>
                <span>MOLA DEM · THEMIS · HiRISE</span>
            </div>

            <div class="planet-viewport">
                <div class="canvas-holder" id="mars-holder"></div>
            </div>

            <div class="card-bottom">
                <div class="title-row">
                    <h2 class="planet-title">Mars</h2>
                    <span class="action-indicator">Otwórz telemetrię →</span>
                </div>
                <p class="planet-summary">
                    Badanie dawnych delt rzecznych, kalder wulkanicznych oraz wpływu burz pyłowych (AOD) i bezwładności cieplnej gruntu.
                </p>
                <div class="metrics-bar">
                    <div class="metric-cell">
                        <span class="metric-label">Średnia temp.</span>
                        <span class="metric-value">-63 °C</span>
                    </div>
                    <div class="metric-cell">
                        <span class="metric-label">Nachylenie osi</span>
                        <span class="metric-value">25.19°</span>
                    </div>
                    <div class="metric-cell">
                        <span class="metric-label">Grawitacja</span>
                        <span class="metric-value">3.72 m/s²</span>
                    </div>
                    <div class="metric-cell">
                        <span class="metric-label">Główne analogi</span>
                        <span class="metric-value">Atacama · Mauna Loa</span>
                    </div>
                </div>
            </div>
        </article>

    </main>

    <script>
        // =========================================================================
        // REALISTYCZNY SHADER GLSL (SZUM FRAKTALNY + OŚWIETLENIE TERMINATORA + FRESNEL)
        // =========================================================================
        const vertexShader = `
            varying vec3 vNormal;
            varying vec3 vPosition;
            varying vec2 vUv;
            void main() {
                vUv = uv;
                vNormal = normalize(normalMatrix * normal);
                vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `;

        // Proceduralny shader powierzchni planetarnej lub tekstura ze zdjęcia
        const fragmentShader = `
            uniform vec3 uBaseColor;
            uniform vec3 uDarkColor;
            uniform vec3 uRimColor;
            uniform vec3 uLightDir;
            uniform float uHover;
            uniform float uSeed;
            uniform float uHasTexture;
            uniform sampler2D uTexture;

            varying vec3 vNormal;
            varying vec3 vPosition;
            varying vec2 vUv;

            // Szybki 3D hash & noise do realistycznej mikro-tekstury powierzchni
            float hash(vec2 p) {
                return fract(sin(dot(p, vec2(127.1 + uSeed, 311.7))) * 43758.5453123);
            }

            float noise(vec2 p) {
                vec2 i = floor(p);
                vec2 f = fract(p);
                f = f * f * (3.0 - 2.0 * f);
                float a = hash(i);
                float b = hash(i + vec2(1.0, 0.0));
                float c = hash(i + vec2(0.0, 1.0));
                float d = hash(i + vec2(1.0, 1.0));
                return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
            }

            float fbm(vec2 p) {
                float v = 0.0;
                float a = 0.5;
                for (int i = 0; i < 5; i++) {
                    v += a * noise(p);
                    p *= 2.15;
                    a *= 0.5;
                }
                return v;
            }

            void main() {
                vec3 albedo;
                if (uHasTexture > 0.5) {
                    albedo = texture2D(uTexture, vUv).rgb;
                } else {
                    // Tekstura geologiczna z 5 oktaw szumu FBM
                    float n = fbm(vUv * vec2(14.0, 7.0));
                    float detail = fbm(vUv * vec2(42.0, 21.0));
                    float surfaceFactor = smoothstep(0.28, 0.72, n * 0.75 + detail * 0.25);
                    albedo = mix(uDarkColor, uBaseColor, surfaceFactor);
                }

                // Oświetlenie kierunkowe Słońca (wyraźny, realistyczny terminator)
                vec3 lightDir = normalize(uLightDir);
                float diff = max(dot(vNormal, lightDir), 0.0);
                float terminator = smoothstep(-0.08, 0.25, dot(vNormal, lightDir));

                vec3 color = albedo * (0.08 + diff * 0.86 * terminator);

                gl_FragColor = vec4(color, 1.0);
            }
        `;

        const textureLoader = new THREE.TextureLoader();

        function createMinimalPlanet(holderId, config) {
            const container = document.getElementById(holderId);
            const scene = new THREE.Scene();
            const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 100);
            camera.position.z = 3.35;

            const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
            renderer.setSize(340, 340);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            container.appendChild(renderer.domElement);

            const group = new THREE.Group();
            scene.add(group);

            const uniforms = {
                uBaseColor:  { value: new THREE.Color(config.baseColor) },
                uDarkColor:  { value: new THREE.Color(config.darkColor) },
                uRimColor:   { value: new THREE.Color(config.rimColor) },
                uLightDir:   { value: new THREE.Vector3(1.2, 0.4, 0.9) },
                uHover:      { value: 0.0 },
                uSeed:       { value: config.seed },
                uHasTexture: { value: 0.0 },
                uTexture:    { value: null }
            };

            if (config.textureUrl) {
                textureLoader.load(config.textureUrl, (tex) => {
                    tex.needsUpdate = true;
                    uniforms.uTexture.value = tex;
                    uniforms.uHasTexture.value = 1.0;
                });
            }

            const geo = new THREE.SphereGeometry(1.04, 64, 64);
            const mat = new THREE.ShaderMaterial({
                vertexShader,
                fragmentShader,
                uniforms
            });

            const sphere = new THREE.Mesh(geo, mat);
            group.add(sphere);

            return {
                scene, camera, renderer, sphere, group, uniforms,
                hovered: false,
                targetRotX: 0,
                targetRotZ: 0
            };
        }

        const moonScene = createMinimalPlanet('moon-holder', {
            baseColor: '#CBD5E1',
            darkColor: '#334155',
            rimColor:  '#60A5FA',
            seed: 1.0,
            textureUrl: 'images/moon_photo.jpg'
        });

        const marsScene = createMinimalPlanet('mars-holder', {
            baseColor: '#EA580C',
            darkColor: '#431407',
            rimColor:  '#F97316',
            seed: 7.4,
            textureUrl: 'images/mars_photo.jpg'
        });

        function animate() {
            [moonScene, marsScene].forEach(p => {
                const rotSpeed = p.hovered ? 0.0065 : 0.0014;
                p.sphere.rotation.y += rotSpeed;

                const targetHover = p.hovered ? 1.0 : 0.0;
                p.uniforms.uHover.value += (targetHover - p.uniforms.uHover.value) * 0.06;

                p.group.rotation.x += (p.targetRotX - p.group.rotation.x) * 0.06;
                p.group.rotation.z += (p.targetRotZ - p.group.rotation.z) * 0.06;

                p.renderer.render(p.scene, p.camera);
            });
            requestAnimationFrame(animate);
        }
        animate();

        function setupCard(cardId, planetObj) {
            const card = document.getElementById(cardId);

            card.addEventListener('mouseenter', () => {
                planetObj.hovered = true;
            });

            card.addEventListener('mousemove', (e) => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;

                card.style.setProperty('--mx', `${x}px`);
                card.style.setProperty('--my', `${y}px`);

                const nx = (x / rect.width - 0.5) * 2;
                const ny = (y / rect.height - 0.5) * 2;
                planetObj.targetRotX = ny * 0.18;
                planetObj.targetRotZ = -nx * 0.15;
                planetObj.uniforms.uLightDir.value.set(1.2 + nx * 0.5, 0.4 - ny * 0.4, 0.9);
            });

            card.addEventListener('mouseleave', () => {
                planetObj.hovered = false;
                planetObj.targetRotX = 0;
                planetObj.targetRotZ = 0;
                planetObj.uniforms.uLightDir.value.set(1.2, 0.4, 0.9);
            });

            card.addEventListener('click', () => {
                const target = card.getAttribute('data-target');
                document.body.classList.add('leaving');
                setTimeout(() => {
                    window.location.href = `explorer.php?body=${encodeURIComponent(target)}`;
                }, 320);
            });
        }

        setupCard('card-moon', moonScene);
        setupCard('card-mars', marsScene);
    </script>
</body>
</html>
