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
            <a href="explorer.php?<?php echo htmlspecialchars($backQuery); ?>" class="back-btn">← WRÓĆ DO KONFIGURACJI</a>
            <a href="index.php" class="back-btn">ZMIEŃ CEL</a>
            <span class="app-title">WYNIKI WYSZUKIWANIA // ANALOGI NA ZIEMI</span>
        </div>

        <div class="nav-telemetry">
            <span id="api-latency">CZAS SZUKACZA: -- ms</span>
            <span class="cpp-badge" id="target-summary-badge">
                <?php echo strtoupper($selectedBody); ?> · <?php echo number_format($lat, 1); ?>°, <?php echo number_format($lon, 1); ?>°
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
                        ZIEMIA // <strong style="color:var(--emerald);">HEATMAPA TOP ANALOGÓW</strong>
                    </div>
                    <div class="hud-pill">
                        NAJLEPSZY MIESIĄC GLOBALNIE: <strong style="color:var(--emerald);" id="best-month-badge">--</strong>
                    </div>
                </div>
                <div id="main-globe-canvas"></div>
            </div>

            <div class="target-readout-bar">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="section-label" style="margin:0;">
                        PROFIL CELU (<?php echo strtoupper($selectedBody); ?> // <?php echo number_format($lat, 1); ?>°, <?php echo number_format($lon, 1); ?>°)
                    </span>
                    <span style="font-family:'JetBrains Mono'; font-size:0.7rem; color:var(--cyan);" id="readout-skylight">
                        NAJBLIŻSZY SKYLIGHT / LAVA TUBE: -- km
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
                <div class="panel-title" style="color:var(--emerald);">
                    <span>◉ TOP ANALOGI NA ZIEMI (SZUKACZ)</span>
                </div>
                <span style="font-family:'JetBrains Mono'; font-size:0.68rem; color:var(--emerald);" id="candidates-count">ŁADOWANIE...</span>
            </div>

            <div class="panel-body">
                <div id="candidates-list"></div>

                <div class="charts-box">
                    <span class="section-label">PORÓWNANIE PROFILU CECH (CEL vs ZIEMIA):</span>
                    <div class="chart-wrap">
                        <canvas id="radar-chart" height="190"></canvas>
                    </div>

                    <span class="section-label">KLIMATOGRAM 12-MIESIĘCZNY WYBRANEGO ANALOGU:</span>
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
        camera.position.z = 3.1;

        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        globeContainer.appendChild(renderer.domElement);

        const globeGroup = new THREE.Group();
        scene.add(globeGroup);

        const pinsGroup = new THREE.Group();
        globeGroup.add(pinsGroup);

        function generateEarthHeatmapTexture(candidates = []) {
            const c = document.createElement('canvas');
            c.width = 1024;
            c.height = 512;
            const ctx = c.getContext('2d');

            ctx.fillStyle = '#091526';
            ctx.fillRect(0, 0, 1024, 512);

            ctx.strokeStyle = 'rgba(96, 165, 250, 0.14)';
            ctx.lineWidth = 1;
            for (let x = 0; x < 1024; x += 64) {
                ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, 512); ctx.stroke();
            }
            for (let y = 0; y < 512; y += 64) {
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(1024, y); ctx.stroke();
            }

            candidates.forEach(cand => {
                const px = ((cand.lon + 180) / 360) * 1024;
                const py = ((90 - cand.lat) / 180) * 512;
                const radius = 55 * cand.score;
                const g = ctx.createRadialGradient(px, py, 2, px, py, radius);
                g.addColorStop(0, `rgba(16, 185, 129, ${cand.score * 0.95})`);
                g.addColorStop(0.5, `rgba(96, 165, 250, ${cand.score * 0.45})`);
                g.addColorStop(1, 'rgba(96, 165, 250, 0)');
                ctx.fillStyle = g;
                ctx.beginPath(); ctx.arc(px, py, radius, 0, Math.PI * 2); ctx.fill();
            });

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

        renderer.domElement.addEventListener('mousedown', (e) => {
            isDragging = true;
            prevMouse = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const dx = e.clientX - prevMouse.x;
            const dy = e.clientY - prevMouse.y;
            globeGroup.rotation.y += dx * 0.006;
            globeGroup.rotation.x = Math.max(-1.2, Math.min(1.2, globeGroup.rotation.x + dy * 0.006));
            prevMouse = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener('mouseup', () => {
            isDragging = false;
        });

        function animateScene() {
            if (!isDragging) {
                globeGroup.rotation.y += 0.0012;
            }
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
                const pos = latLonToVector3(c.lat, c.lon, 1.14);
                const pinGeo = new THREE.SphereGeometry(idx === selectedCandidateIndex ? 0.036 : 0.022, 16, 16);
                const pinMat = new THREE.MeshBasicMaterial({
                    color: idx === selectedCandidateIndex ? 0x10b981 : 0x60a5fa
                });
                const pin = new THREE.Mesh(pinGeo, pinMat);
                pin.position.copy(pos);
                pinsGroup.add(pin);
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
                `NAJBLIŻSZY SKYLIGHT / LAVA TUBE: ${profile.nearest_skylight_km} km`;
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

            document.getElementById('api-latency').innerText = `CZAS SZUKACZA: ${searchRes.execution_time_ms} ms`;
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
