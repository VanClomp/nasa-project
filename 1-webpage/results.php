<?php
/**
 * results.php - Podstrona wyników wyszukiwania analogów na Ziemi
 * Otwierana z explorer.php po kliknięciu przycisku "Znajdź analogi na Ziemi"
 */
$selectedBody = strtolower($_GET['body'] ?? 'moon');
if (!in_array($selectedBody, ['moon', 'mars'])) {
    $selectedBody = 'moon';
}

$lat = isset($_GET['lat']) ? floatval($_GET['lat']) : -89.9;
$lon = isset($_GET['lon']) ? floatval($_GET['lon']) : 0.0;
$caves = (isset($_GET['caves']) && $_GET['caves'] === '1');

$defaultWeights = [0.90, 0.70, 0.85, 0.65, 0.80, 0.50, 0.95, 0.60, 0.75];
$weights = $defaultWeights;
if (isset($_GET['w'])) {
    $parts = explode(',', $_GET['w']);
    for ($i = 0; $i < 9; $i++) {
        if (isset($parts[$i]) && is_numeric($parts[$i])) {
            $weights[$i] = max(0.0, min(1.0, floatval($parts[$i])));
        }
    }
}

$backQuery = http_build_query([
    'body'  => $selectedBody,
    'lat'   => $lat,
    'lon'   => $lon,
    'w'     => implode(',', array_map(fn($v) => number_format($v, 2, '.', ''), $weights)),
    'caves' => $caves ? '1' : '0'
]);
?>
<!DOCTYPE html>
<html lang="pl" data-body="<?php echo htmlspecialchars($selectedBody); ?>">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wyniki Analogów Ziemi // Planetary Analog Finder (<?php echo strtoupper($selectedBody); ?>)</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <!-- Three.js & Chart.js -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <link rel="stylesheet" href="style.css">
</head>
<body>

    <div class="hud-bg"></div>

    <!-- GÓRNY PASEK NAWIGACYJNY -->
    <header class="navbar">
        <div class="nav-left">
            <a href="explorer.php?<?php echo htmlspecialchars($backQuery); ?>" class="back-btn">← Konfiguracja</a>
            <a href="index.php" class="back-btn">Zmień planetę</a>
            <span class="app-title">Wyniki analizy</span>
        </div>

        <div class="nav-telemetry">
            <span id="api-latency">-- ms</span>
            <span class="cpp-badge" id="target-summary-badge">
                <?php echo $selectedBody === 'moon' ? 'Księżyc' : 'Mars'; ?> · <?php echo number_format($lat, 1); ?>°, <?php echo number_format($lon, 1); ?>°
            </span>
        </div>
    </header>

    <!-- GŁÓWNA PRZESTRZEŃ ROBOCZA (2 KOLUMNY: GLOBUS ZIEMI + RANKING & WYKRESY) -->
    <main class="workspace workspace-results">

        <!-- LEWA / GŁÓWNA KOLUMNA: GLOBUS ZIEMI Z HEATMAPĄ I PINEZKAMI + PODSUMOWANIE CELU -->
        <section class="center-stage">
            <div class="globe-viewport">
                <div class="globe-hud-overlay">
                    <div class="hud-pill">
                        Ziemia — mapa dopasowania
                    </div>
                    <div class="hud-pill">
                        Najlepszy okres: <strong style="color:var(--emerald);" id="best-month-badge">--</strong>
                    </div>
                </div>
                <div id="main-globe-canvas"></div>
            </div>

            <div class="target-readout-bar">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="section-label" style="margin:0;">
                        Profil celu · <?php echo $selectedBody === 'moon' ? 'Księżyc' : 'Mars'; ?> (<?php echo number_format($lat, 1); ?>°, <?php echo number_format($lon, 1); ?>°)
                    </span>
                    <span style="font-family:'JetBrains Mono'; font-size:0.68rem; color:var(--text-muted);" id="readout-skylight">
                        Najbliższa jaskinia: -- km
                    </span>
                </div>
                <div class="readout-grid">
                    <div class="readout-box"><span>TEMP. ŚREDNIA</span><strong id="raw-temp_mean">-- °C</strong></div>
                    <div class="readout-box"><span>AMPLITUDA DOBOWA</span><strong id="raw-temp_diurnal_amp">-- °C</strong></div>
                    <div class="readout-box"><span>BEZWŁADNOŚĆ CIEPLNA</span><strong id="raw-thermal_inertia">-- TIU</strong></div>
                    <div class="readout-box"><span>CHROPOWATOŚĆ SAR</span><strong id="raw-surface_roughness">--</strong></div>
                    <div class="readout-box"><span>LÓD / WILGOTNOŚĆ</span><strong id="raw-soil_moisture">-- %</strong></div>
                    <div class="readout-box"><span>ZAPYLENIE (AOD)</span><strong id="raw-dust_aerosol">--</strong></div>
                    <div class="readout-box"><span>MAKS. KĄT SŁOŃCA</span><strong id="raw-solar_elevation_max">-- °</strong></div>
                    <div class="readout-box"><span>PROMIENIOWANIE</span><strong id="raw-radiation_proxy">--</strong></div>
                    <div class="readout-box"><span>NACHYLENIE STOKU</span><strong id="raw-slope_deg">-- °</strong></div>
                    <div class="readout-box"><span>FILTR JASKIŃ</span><strong style="color:var(--emerald);"><?php echo $caves ? 'TAK (&lt;15km)' : 'NIE'; ?></strong></div>
                </div>
            </div>
        </section>

        <!-- PRAWA KOLUMNA: RANKING ANALOGÓW NA ZIEMI + WYKRESY PORÓWNAWCZE -->
        <aside class="hud-panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>Najlepsze analogi na Ziemi</span>
                </div>
                <span style="font-family:'JetBrains Mono'; font-size:0.68rem; color:var(--emerald);" id="candidates-count">Ładowanie...</span>
            </div>

            <div class="panel-body">
                <div id="candidates-list"></div>

                <div class="charts-box">
                    <span class="section-label">Porównanie profilu cech</span>
                    <div class="chart-wrap">
                        <canvas id="radar-chart" height="190"></canvas>
                    </div>

                    <span class="section-label">Klimatogram 12-miesięczny</span>
                    <div class="chart-wrap">
                        <canvas id="climatogram-chart" height="155"></canvas>
                    </div>
                </div>
            </div>
        </aside>

    </main>

    <script>
        const SEARCH_PARAMS = {
            body: <?php echo json_encode($selectedBody); ?>,
            lat: <?php echo json_encode($lat); ?>,
            lon: <?php echo json_encode($lon); ?>,
            weights: <?php echo json_encode($weights); ?>,
            require_caves: <?php echo json_encode($caves); ?>
        };
        const MONTH_NAMES = ['STY', 'LUT', 'MAR', 'KWI', 'MAJ', 'CZE', 'LIP', 'SIE', 'WRZ', 'PAŹ', 'LIS', 'GRU'];

        let currentTargetProfile = null;
        let currentCandidates = [];
        let selectedCandidateIndex = 0;

        // =========================================================================
        // 1. SCENA 3D THREE.JS — GLOBUS ZIEMI Z HEATMAPĄ I PINEZKAMI
        // =========================================================================
        const globeContainer = document.getElementById('main-globe-canvas');
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
        camera.position.z = 1.95; // Płynne oddalenie na starcie (efekt wyjścia z podejścia)

        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        globeContainer.appendChild(renderer.domElement);

        const globeGroup = new THREE.Group();
        scene.add(globeGroup);

        const pinsGroup = new THREE.Group();
        globeGroup.add(pinsGroup);

        const earthBaseImg = new Image();
        earthBaseImg.src = 'images/earth_photo.jpg';
        earthBaseImg.onload = () => {
            if (typeof sphereMat !== 'undefined') {
                sphereMat.map = generateEarthHeatmapTexture(currentCandidates);
                sphereMat.needsUpdate = true;
            }
        };

        function generateEarthHeatmapTexture(candidates = []) {
            const c = document.createElement('canvas');
            c.width = 2048;
            c.height = 1024;
            const ctx = c.getContext('2d');

            if (earthBaseImg.complete && earthBaseImg.naturalWidth > 0) {
                ctx.drawImage(earthBaseImg, 0, 0, c.width, c.height);
                ctx.fillStyle = 'rgba(5, 10, 20, 0.18)';
                ctx.fillRect(0, 0, c.width, c.height);
            } else {
                ctx.fillStyle = '#091526';
                ctx.fillRect(0, 0, c.width, c.height);
            }

            ctx.strokeStyle = 'rgba(96, 165, 250, 0.12)';
            ctx.lineWidth = 1;
            for (let x = 0; x < c.width; x += 128) {
                ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, c.height); ctx.stroke();
            }
            for (let y = 0; y < c.height; y += 128) {
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(c.width, y); ctx.stroke();
            }

            // Ważność wyniku = pozycja w rankingu + względny score (min–max w tej odpowiedzi),
            // bo surowe score bywają ściśnięte (np. 0.86–0.93) i same nie różnicują wyników.
            // Rysujemy od najsłabszego do najlepszego, żeby czołówka była na wierzchu.
            const ranked = [...candidates].sort((a, b) => b.score - a.score);
            const n = ranked.length;
            const sMax = n ? ranked[0].score : 0;
            const sSpan = n ? sMax - ranked[n - 1].score : 0;
            const mix = (a, b, t) => Math.round(a + (b - a) * t);

            for (let i = n - 1; i >= 0; i--) {
                const cand = ranked[i];
                const rankT = n > 1 ? 1 - i / (n - 1) : 1;
                const scoreT = sSpan > 1e-9 ? 1 - (sMax - cand.score) / sSpan : 1;
                const imp = Math.pow(0.6 * rankT + 0.4 * scoreT, 1.6); // 0..1, faworyzuje czołówkę

                const px = ((cand.lon + 180) / 360) * c.width;
                const py = ((90 - cand.lat) / 180) * c.height;
                const radius = 6 + 10 * imp; // 6–16 px na teksturze 2048 (wcześniej ~100 px)
                const alpha = 0.12 + 0.78 * imp;
                // Nasycenie: od wyblakłego łupku (słabe wyniki) do pełnego szmaragdu / błękitu (top)
                const core = `rgba(${mix(120, 16, imp)}, ${mix(135, 185, imp)}, ${mix(150, 129, imp)}, ${alpha})`;
                const halo = `rgba(${mix(120, 96, imp)}, ${mix(135, 165, imp)}, ${mix(150, 250, imp)}, ${alpha * 0.4})`;
                const g = ctx.createRadialGradient(px, py, 0, px, py, radius);
                g.addColorStop(0, core);
                g.addColorStop(0.3, core);
                g.addColorStop(0.6, halo);
                g.addColorStop(1, 'rgba(96, 165, 250, 0)');
                ctx.fillStyle = g;
                ctx.beginPath(); ctx.arc(px, py, radius, 0, Math.PI * 2); ctx.fill();
            }

            return new THREE.CanvasTexture(c);
        }

        const sphereGeo = new THREE.SphereGeometry(1.12, 64, 64);
        const sphereMat = new THREE.MeshStandardMaterial({
            map: generateEarthHeatmapTexture([]),
            roughness: 0.78,
            metalness: 0.15
        });
        const globeMesh = new THREE.Mesh(sphereGeo, sphereMat);
        globeGroup.add(globeMesh);

        scene.add(new THREE.AmbientLight(0xffffff, 0.55));
        const sunLight = new THREE.DirectionalLight(0xffffff, 1.4);
        sunLight.position.set(5, 3, 4);
        scene.add(sunLight);

        function resizeGlobe() {
            const rect = globeContainer.getBoundingClientRect();
            renderer.setSize(rect.width, rect.height);
            camera.aspect = rect.width / rect.height;
            camera.updateProjectionMatrix();
        }
        window.addEventListener('resize', resizeGlobe);
        setTimeout(resizeGlobe, 50);

        function latLonToVector3(lat, lon, radius = 1.14) {
            const phi = (90 - lat) * (Math.PI / 180);
            const theta = (lon + 180) * (Math.PI / 180);
            const x = -(radius * Math.sin(phi) * Math.cos(theta));
            const z = (radius * Math.sin(phi) * Math.sin(theta));
            const y = (radius * Math.cos(phi));
            return new THREE.Vector3(x, y, z);
        }

        let isDragging = false;
        let prevMouse = { x: 0, y: 0 };
        let targetCamX = 0;
        let targetCamY = 0;
        let targetCamZ = 3.1;

        renderer.domElement.style.touchAction = 'none';

        function applyZoomAt(clientX, clientY, deltaZ) {
            const rect = renderer.domElement.getBoundingClientRect();
            const ndcX = ((clientX - rect.left) / rect.width) * 2 - 1;
            const ndcY = -((clientY - rect.top) / rect.height) * 2 + 1;

            const oldZ = targetCamZ;
            const newZ = Math.max(1.45, Math.min(4.6, oldZ + deltaZ));

            const vFov = (camera.fov * Math.PI) / 180;
            const halfHOld = oldZ * Math.tan(vFov / 2);
            const halfWOld = halfHOld * camera.aspect;
            const worldX = targetCamX + ndcX * halfWOld;
            const worldY = targetCamY + ndcY * halfHOld;

            const halfHNew = newZ * Math.tan(vFov / 2);
            const halfWNew = halfHNew * camera.aspect;

            targetCamZ = newZ;
            const maxPan = Math.max(0, (3.1 - newZ) * 0.65);
            targetCamX = Math.max(-maxPan, Math.min(maxPan, worldX - ndcX * halfWNew));
            targetCamY = Math.max(-maxPan, Math.min(maxPan, worldY - ndcY * halfHNew));
        }

        renderer.domElement.addEventListener('wheel', (e) => {
            e.preventDefault();
            applyZoomAt(e.clientX, e.clientY, e.deltaY * 0.0022);
        }, { passive: false });

        renderer.domElement.addEventListener('mousedown', (e) => {
            isDragging = true;
            prevMouse = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const dx = e.clientX - prevMouse.x;
            const dy = e.clientY - prevMouse.y;
            const sensitivity = Math.max(0.0018, (camera.position.z - 1.0) * 0.0028);
            globeGroup.rotation.y += dx * sensitivity;
            globeGroup.rotation.x = Math.max(-1.35, Math.min(1.35, globeGroup.rotation.x + dy * sensitivity));
            prevMouse = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener('mouseup', () => {
            isDragging = false;
        });

        // Obsługa dotyku dla Ziemi (obrót 1 palcem, pinch-to-zoom 2 palcami)
        let prevPinchDist = 0;
        renderer.domElement.addEventListener('touchstart', (e) => {
            e.preventDefault();
            isDragging = true;
            if (e.touches.length === 1) {
                prevPinchDist = 0;
                prevMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            } else if (e.touches.length === 2) {
                prevPinchDist = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
            }
        }, { passive: false });

        renderer.domElement.addEventListener('touchmove', (e) => {
            e.preventDefault();
            if (!isDragging) return;
            if (e.touches.length === 1 && prevPinchDist === 0) {
                const dx = e.touches[0].clientX - prevMouse.x;
                const dy = e.touches[0].clientY - prevMouse.y;
                const sensitivity = Math.max(0.0018, (camera.position.z - 1.0) * 0.0028);
                globeGroup.rotation.y += dx * sensitivity;
                globeGroup.rotation.x = Math.max(-1.35, Math.min(1.35, globeGroup.rotation.x + dy * sensitivity));
                prevMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            } else if (e.touches.length === 2) {
                const dist = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
                if (prevPinchDist > 0) {
                    const midX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
                    const midY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
                    applyZoomAt(midX, midY, (prevPinchDist - dist) * 0.012);
                }
                prevPinchDist = dist;
            }
        }, { passive: false });

        renderer.domElement.addEventListener('touchend', (e) => {
            if (e.touches.length === 1) {
                prevPinchDist = 0;
                prevMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                return;
            }
            if (e.touches.length === 0) {
                isDragging = false;
                prevPinchDist = 0;
            }
        }, { passive: false });

        function animateScene() {
            if (!isDragging) {
                globeGroup.rotation.y += 0.0012;
            }
            camera.position.x += (targetCamX - camera.position.x) * 0.065;
            camera.position.y += (targetCamY - camera.position.y) * 0.065;
            camera.position.z += (targetCamZ - camera.position.z) * 0.065;

            const pinScale = Math.max(0.24, (camera.position.z - 1.05) / 2.05);
            pinsGroup.children.forEach(pin => pin.scale.setScalar(pinScale));

            renderer.render(scene, camera);
            requestAnimationFrame(animateScene);
        }
        animateScene();

        // =========================================================================
        // 2. API CALLS (CHARACTERIZE + SEARCH)
        // =========================================================================
        async function callApi(endpoint, payload) {
            try {
                const res = await fetch(`/api/v1/${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.ok) return await res.json();
            } catch (err) {
                // Fallback do mocka w PHP
            }
            const fallbackRes = await fetch(`explorer.php?mock_api=${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            return await fallbackRes.json();
        }

        function refreshEarthGlobePins() {
            sphereMat.map = generateEarthHeatmapTexture(currentCandidates);
            sphereMat.needsUpdate = true;

            pinsGroup.clear();
            currentCandidates.forEach((c, idx) => {
                const pos = latLonToVector3(c.lat, c.lon, 1.125);
                const isSelected = (idx === selectedCandidateIndex);
                const pinGroup = new THREE.Group();
                pinGroup.position.copy(pos);
                pinGroup.quaternion.setFromUnitVectors(
                    new THREE.Vector3(0, 0, 1),
                    pos.clone().normalize()
                );

                const dotGeo = new THREE.CircleGeometry(isSelected ? 0.015 : 0.010, 24);
                const dotMat = new THREE.MeshBasicMaterial({
                    color: isSelected ? 0x10b981 : 0x60a5fa,
                    side: THREE.DoubleSide,
                    transparent: true,
                    opacity: isSelected ? 1.0 : 0.85
                });
                pinGroup.add(new THREE.Mesh(dotGeo, dotMat));

                if (isSelected) {
                    const ringGeo = new THREE.RingGeometry(0.028, 0.034, 32);
                    const ringMat = new THREE.MeshBasicMaterial({
                        color: 0x10b981,
                        side: THREE.DoubleSide,
                        transparent: true,
                        opacity: 0.95
                    });
                    pinGroup.add(new THREE.Mesh(ringGeo, ringMat));
                }

                pinsGroup.add(pinGroup);
            });
        }

        function renderTargetProfileReadout(profile) {
            const r = profile.features_raw;
            document.getElementById('raw-temp_mean').innerText = `${r.temp_mean} °C`;
            document.getElementById('raw-temp_diurnal_amp').innerText = `${r.temp_diurnal_amp} °C`;
            document.getElementById('raw-thermal_inertia').innerText = `${r.thermal_inertia} TIU`;
            document.getElementById('raw-surface_roughness').innerText = r.surface_roughness;
            document.getElementById('raw-soil_moisture').innerText = `${r.soil_moisture} %`;
            document.getElementById('raw-dust_aerosol').innerText = r.dust_aerosol;
            document.getElementById('raw-solar_elevation_max').innerText = `${r.solar_elevation_max} °`;
            document.getElementById('raw-radiation_proxy').innerText = r.radiation_proxy;
            document.getElementById('raw-slope_deg').innerText = `${r.slope_deg} °`;
            document.getElementById('readout-skylight').innerText =
                `Najbliższa jaskinia: ${profile.nearest_skylight_km} km`;
        }

        function renderCandidatesList() {
            const container = document.getElementById('candidates-list');
            document.getElementById('candidates-count').innerText = `${currentCandidates.length} WYNIKÓW`;

            if (currentCandidates.length === 0) {
                container.innerHTML = '<p style="color:var(--text-muted); font-size:0.82rem;">Brak lokalizacji spełniających wybrane kryteria (spróbuj wyłączyć filtr jaskiń).</p>';
                return;
            }

            container.innerHTML = currentCandidates.map((c, idx) => {
                const pct = (c.score * 100).toFixed(1);
                const isSel = idx === selectedCandidateIndex ? 'selected' : '';
                const mName = MONTH_NAMES[(c.best_month || 1) - 1];
                return `
                    <div class="candidate-card ${isSel}" onclick="selectCandidate(${idx})">
                        <div class="cand-top">
                            <span class="cand-rank">RANK #0${c.rank} // ID:${c.id}</span>
                            <span class="cand-score">${pct}% MATCH</span>
                        </div>
                        <div class="cand-name">${c.name_hint}</div>
                        <div class="cand-meta">
                            <span>LAT: ${c.lat}°, LON: ${c.lon}°</span>
                            <span>MIESIĄC: ${mName}</span>
                            <span>JASKINIA: ${c.nearest_cave_km} km</span>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function selectCandidate(idx) {
            selectedCandidateIndex = idx;
            renderCandidatesList();
            refreshEarthGlobePins();
            updateCharts();
        }

        // =========================================================================
        // 3. WYKRESY CHART.JS (RADAR + KLIMATOGRAM 12M)
        // =========================================================================
        let radarChart = null;
        let climatogramChart = null;

        function initCharts() {
            const rCtx = document.getElementById('radar-chart').getContext('2d');
            radarChart = new Chart(rCtx, {
                type: 'radar',
                data: {
                    labels: ['Temp', 'Amplituda', 'Bezwładność', 'Chropowatość', 'Lód/Woda', 'Pył AOD', 'Kąt Słońca', 'Promieniow.', 'Nachylenie'],
                    datasets: [
                        {
                            label: 'Cel (Księżyc/Mars)',
                            data: [0,0,0,0,0,0,0,0,0],
                            borderColor: '#60A5FA',
                            backgroundColor: 'rgba(96, 165, 250, 0.16)',
                            borderWidth: 2
                        },
                        {
                            label: 'Analog na Ziemi',
                            data: [0,0,0,0,0,0,0,0,0],
                            borderColor: '#10B981',
                            backgroundColor: 'rgba(16, 185, 129, 0.16)',
                            borderWidth: 2
                        }
                    ]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { labels: { color: '#cbd5e1', font: { size: 10 } } } },
                    scales: {
                        r: {
                            min: 0, max: 1,
                            grid: { color: 'rgba(255,255,255,0.08)' },
                            angleLines: { color: 'rgba(255,255,255,0.08)' },
                            pointLabels: { color: '#94a3b8', font: { size: 9 } },
                            ticks: { display: false }
                        }
                    }
                }
            });

            const cCtx = document.getElementById('climatogram-chart').getContext('2d');
            climatogramChart = new Chart(cCtx, {
                type: 'line',
                data: {
                    labels: MONTH_NAMES,
                    datasets: [
                        {
                            label: 'Temp. średnia (°C)',
                            data: [],
                            borderColor: '#F97316',
                            backgroundColor: 'rgba(249, 115, 22, 0.15)',
                            tension: 0.35,
                            fill: true
                        },
                        {
                            label: 'Wilgotność (%)',
                            data: [],
                            borderColor: '#60A5FA',
                            tension: 0.35
                        }
                    ]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { labels: { color: '#cbd5e1', font: { size: 10 } } } },
                    scales: {
                        x: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { display: false } },
                        y: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { color: 'rgba(255,255,255,0.06)' } }
                    }
                }
            });
        }

        function updateCharts() {
            if (!radarChart || !climatogramChart || !currentTargetProfile) return;
            const cand = currentCandidates[selectedCandidateIndex];
            if (!cand) return;

            radarChart.data.datasets[0].data = currentTargetProfile.features_norm;
            radarChart.data.datasets[1].data = cand.features_norm || [0.2, 0.5, 0.3, 0.4, 0.1, 0.1, 0.3, 0.8, 0.2];
            radarChart.update();

            if (cand.climatogram_12m) {
                climatogramChart.data.datasets[0].data = cand.climatogram_12m.temp_mean;
                climatogramChart.data.datasets[1].data = cand.climatogram_12m.soil_moisture;
                climatogramChart.update();
            }
        }

        async function loadResults() {
            const profile = await callApi('characterize', {
                target_body: SEARCH_PARAMS.body,
                lat: SEARCH_PARAMS.lat,
                lon: SEARCH_PARAMS.lon,
                timestamp_iso: new Date().toISOString()
            });
            currentTargetProfile = profile;
            renderTargetProfileReadout(profile);

            const searchRes = await callApi('search', {
                features_norm: profile.features_norm,
                weights: SEARCH_PARAMS.weights,
                require_caves: SEARCH_PARAMS.require_caves,
                top_k: 100
            });

            document.getElementById('api-latency').innerText = `${searchRes.execution_time_ms} ms`;
            const bestM = searchRes.best_global_month || 7;
            document.getElementById('best-month-badge').innerText = `${MONTH_NAMES[bestM - 1]} (M${bestM})`;

            currentCandidates = searchRes.candidates || [];
            selectedCandidateIndex = 0;
            renderCandidatesList();
            refreshEarthGlobePins();
            updateCharts();
        }

        window.addEventListener('DOMContentLoaded', () => {
            initCharts();
            loadResults();
        });
    </script>
</body>
</html>
