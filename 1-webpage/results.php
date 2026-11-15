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
$date = (isset($_GET['date']) && preg_match('/^\d{4}-\d{2}-\d{2}$/', $_GET['date']))
    ? $_GET['date'] : gmdate('Y-m-d');   // data lądowania (UTC)

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
    'caves' => $caves ? '1' : '0',
    'date'  => $date
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
    <link rel="stylesheet" href="style.css?v=<?php echo @filemtime(__DIR__ . '/style.css') ?: 1; ?>">
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
                        Profil celu · <?php echo $selectedBody === 'moon' ? 'Księżyc' : 'Mars'; ?> (<?php echo number_format($lat, 1); ?>°, <?php echo number_format($lon, 1); ?>°) · <?php echo htmlspecialchars($date); ?><span id="readout-season"></span>
                    </span>
                    <div class="readout-meta">
                        <span class="model-badge" id="model-badge" title="Pochodzenie danych">Model: --</span>
                        <span style="font-family:'JetBrains Mono'; font-size:0.68rem; color:var(--text-muted);" id="readout-skylight">
                            Najbliższa jaskinia: -- km
                        </span>
                    </div>
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

                    <!-- p(t): parametry wybranego miejsca, które zmieniają się z datą (extra.series z 3-charakteryzatora) -->
                    <div id="time-charts" class="time-charts" hidden>
                        <span class="section-label">Wybrane miejsce · parametry zmienne w czasie</span>
                        <p class="time-charts-note" id="time-charts-note"></p>
                        <div id="time-charts-list"></div>
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
            require_caves: <?php echo json_encode($caves); ?>,
            date: <?php echo json_encode($date); ?>
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

        const textureLoader = new THREE.TextureLoader();
        const earthPhotoTexture = textureLoader.load('images/earth_photo.jpg', (tex) => {
            tex.needsUpdate = true;
            if (typeof sphereMat !== 'undefined') {
                sphereMat.needsUpdate = true;
            }
        });

        function createEarthPin(isSelected) {
            const pinGroup = new THREE.Group();
            const color = isSelected ? 0x10b981 : 0x60a5fa;

            // Subtelny pierścień na powierzchni planety
            const baseRing = new THREE.Mesh(
                new THREE.RingGeometry(isSelected ? 0.015 : 0.010, isSelected ? 0.021 : 0.014, 32),
                new THREE.MeshBasicMaterial({
                    color,
                    side: THREE.DoubleSide,
                    transparent: true,
                    opacity: isSelected ? 0.9 : 0.55
                })
            );
            baseRing.position.z = 0.001;
            pinGroup.add(baseRing);

            if (isSelected) {
                const outerRing = new THREE.Mesh(
                    new THREE.RingGeometry(0.028, 0.032, 36),
                    new THREE.MeshBasicMaterial({
                        color,
                        side: THREE.DoubleSide,
                        transparent: true,
                        opacity: 0.45
                    })
                );
                outerRing.position.z = 0.001;
                pinGroup.add(outerRing);
            }

            // Smukła nóżka pinezki skierowana prostopadle do powierzchni (oś +Z)
            const stemH = isSelected ? 0.044 : 0.030;
            const stemGeo = new THREE.CylinderGeometry(0.0016, 0.0010, stemH, 10);
            stemGeo.rotateX(Math.PI / 2);
            const stem = new THREE.Mesh(
                stemGeo,
                new THREE.MeshBasicMaterial({
                    color: 0xe2e8f0,
                    transparent: true,
                    opacity: isSelected ? 0.95 : 0.75
                })
            );
            stem.position.z = stemH * 0.5 + 0.001;
            pinGroup.add(stem);

            // Główka pinezki 3D
            const headR = isSelected ? 0.012 : 0.0085;
            const head = new THREE.Mesh(
                new THREE.SphereGeometry(headR, 18, 18),
                new THREE.MeshBasicMaterial({
                    color,
                    transparent: true,
                    opacity: isSelected ? 1.0 : 0.9
                })
            );
            head.position.z = stemH + headR * 0.7;
            pinGroup.add(head);

            return pinGroup;
        }

        const sphereGeo = new THREE.SphereGeometry(1.12, 64, 64);
        const sphereMat = new THREE.MeshStandardMaterial({
            map: earthPhotoTexture,
            roughness: 0.88,
            metalness: 0.05
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
        let pauseAutoRotateUntil = 0;

        function pauseAutoRotate(ms = 8000) {
            pauseAutoRotateUntil = performance.now() + ms;
        }

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
            pauseAutoRotate();
            applyZoomAt(e.clientX, e.clientY, e.deltaY * 0.0022);
        }, { passive: false });

        renderer.domElement.addEventListener('mousedown', (e) => {
            pauseAutoRotate();
            isDragging = true;
            prevMouse = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            pauseAutoRotate();
            const dx = e.clientX - prevMouse.x;
            const dy = e.clientY - prevMouse.y;
            const sensitivity = Math.max(0.0018, (camera.position.z - 1.0) * 0.0028);
            globeGroup.rotation.y += dx * sensitivity;
            globeGroup.rotation.x = Math.max(-1.35, Math.min(1.35, globeGroup.rotation.x + dy * sensitivity));
            prevMouse = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener('mouseup', () => {
            if (isDragging) pauseAutoRotate();
            isDragging = false;
        });

        // Obsługa dotyku dla Ziemi (obrót 1 palcem, pinch-to-zoom 2 palcami)
        let prevPinchDist = 0;
        renderer.domElement.addEventListener('touchstart', (e) => {
            e.preventDefault();
            pauseAutoRotate();
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
            pauseAutoRotate();
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
                if (isDragging) pauseAutoRotate();
                isDragging = false;
                prevPinchDist = 0;
            }
        }, { passive: false });

        function animateScene() {
            if (!isDragging) {
                const now = performance.now();
                if (now >= pauseAutoRotateUntil) {
                    const resumeFactor = Math.min(1, (now - pauseAutoRotateUntil) / 800);
                    globeGroup.rotation.y += 0.0012 * resumeFactor;
                }
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
            pinsGroup.clear();
            const currentScale = Math.max(0.24, (camera.position.z - 1.05) / 2.05);
            currentCandidates.forEach((c, idx) => {
                const pos = latLonToVector3(c.lat, c.lon, 1.1205);
                const isSelected = (idx === selectedCandidateIndex);
                const pinGroup = createEarthPin(isSelected);
                pinGroup.position.copy(pos);
                pinGroup.quaternion.setFromUnitVectors(
                    new THREE.Vector3(0, 0, 1),
                    pos.clone().normalize()
                );
                pinGroup.scale.setScalar(currentScale);
                pinsGroup.add(pinGroup);
            });
        }


        // Pora roku dla wybranej daty (extra.season z 3-charakteryzator)
        function renderSeason(profile) {
            const el = document.getElementById('readout-season');
            if (!el) return;
            const s = (profile && profile.extra && profile.extra.season) || null;
            if (s && s.ls !== undefined) {
                el.innerText = ` · Ls ${Number(s.ls).toFixed(0)}° (rok marsjański ${s.mars_year})`;
            } else if (s && s.local_lunar_hour !== undefined) {
                el.innerText = ` · godz. księżycowa ${Number(s.local_lunar_hour).toFixed(1)}`;
            } else {
                el.innerText = '';
            }
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
            renderModelBadge(profile);
            renderSeason(profile);
            renderFeatureFlags(profile);
        }

        // extra.model z 3-charakteryzator: "local" = dane stacji dla tej daty (Mars), "orbital" = pomiary orbitalne
        // w tym punkcie (Księżyc), "global" = model globalny (niepewny). Brak pola (np. mock w PHP) = globalny.
        const MODEL_LABELS = {
            local:   'Model lokalny · dane stacji',
            orbital: 'Pomiary orbitalne · ten punkt',
            global:  'Model globalny · niepewny'
        };
        function renderModelBadge(profile) {
            const badge = document.getElementById('model-badge');
            if (!badge) return;
            const extra = (profile && profile.extra) || {};
            const model = MODEL_LABELS[extra.model] ? extra.model : 'global';
            ['local', 'orbital', 'global'].forEach(m => badge.classList.toggle(m, m === model));
            badge.innerText = MODEL_LABELS[model];
            badge.title = extra.model_basis || MODEL_LABELS[model];
        }

        // Przy każdym parametrze: skąd pochodzi wartość w TYM miejscu (extra.features_measured) i czy zmienia się
        // z datą lądowania (extra.features_time_varying). Opis parametrów: 3-charakteryzator/PARAMETERS.md.
        const FEATURE_KEYS = ['temp_mean', 'temp_diurnal_amp', 'thermal_inertia', 'surface_roughness', 'soil_moisture',
                              'dust_aerosol', 'solar_elevation_max', 'radiation_proxy', 'slope_deg'];
        function renderFeatureFlags(profile) {
            const extra = (profile && profile.extra) || {};
            const meas = extra.features_measured || [];
            const tv = extra.features_time_varying || [];
            const raw = (profile && profile.features_raw) || {};
            FEATURE_KEYS.forEach((k, i) => {
                const valueEl = document.getElementById(`raw-${k}`);
                if (!valueEl) return;
                const box = valueEl.parentElement;
                let flags = box.querySelector('.feat-flags');
                if (!flags) { flags = document.createElement('span'); flags.className = 'feat-flags'; box.appendChild(flags); }
                let src;
                if (raw[k] === null || raw[k] === undefined || (extra.null_features || []).includes(k)) {
                    src = '<i class="feat-src none" title="Brak danych dla tego miejsca">brak danych</i>';
                } else if (meas[i] === true) {
                    src = '<i class="feat-src local" title="Zmierzone w tym miejscu (stacja, mapa orbitalna w tym pikselu lub dokładna geometria)">zmierzone</i>';
                } else {
                    src = '<i class="feat-src global" title="Przewidywane przez model globalny (szerokość, wysokość, mapy) - niepewne">model</i>';
                }
                const time = tv[i] === true
                    ? '<i class="feat-time varies" title="Zmienia się z datą lądowania (pora roku, położenie Słońca, sezon pyłowy)">◷ z datą</i>'
                    : (tv[i] === false ? '<i class="feat-time fixed" title="Stała cecha miejsca, nie zależy od daty">stałe</i>' : '');
                flags.innerHTML = src + time;
            });
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

        // ---- p(t): wykresy parametrów zmiennych w czasie dla wybranego miejsca ----
        const TIME_LABELS = {
            temp_mean:           ['Średnia temperatura gruntu', '°C'],
            temp_diurnal_amp:    ['Dobowa amplituda temperatury', 'K'],
            dust_aerosol:        ['Zapylenie atmosfery (AOD)', ''],
            solar_elevation_max: ['Maks. wysokość Słońca w południe', '°'],
            radiation_proxy:     ['Osłona atmosfery (masa kolumny)', 'g/cm²']
        };
        let timeCharts = [];
        async function loadTimeCharts() {
            let profile;
            try {
                profile = await callApi('characterize', {
                    target_body: SEARCH_PARAMS.body, lat: SEARCH_PARAMS.lat, lon: SEARCH_PARAMS.lon,
                    timestamp_iso: `${SEARCH_PARAMS.date}T12:00:00Z`, series: true
                });
            } catch (e) { return; }
            renderTimeCharts(profile);
        }
        function renderTimeCharts(profile) {
            const box = document.getElementById('time-charts');
            const list = document.getElementById('time-charts-list');
            const s = profile && profile.extra && profile.extra.series;
            timeCharts.forEach(c => c.destroy()); timeCharts = [];
            list.innerHTML = '';
            if (!s || !Object.keys(s.values || {}).length) { box.hidden = true; return; }
            const isMars = s.axis === 'mars_month';
            const accent = isMars ? '#F97316' : '#60A5FA';
            document.getElementById('time-charts-note').innerText = isMars
                ? `Oś czasu: 12 miesięcy marsjańskich roku lądowania, opisanych miesiącem ziemskim, w którym się zaczynają (miesiąc marsjański trwa ok. 1,5–2 miesięcy ziemskich). Zaznaczony punkt = data lądowania ${SEARCH_PARAMS.date}.`
                : `Oś czasu: 15. dzień każdego miesiąca roku ${SEARCH_PARAMS.date.slice(0, 4)}. Zaznaczony punkt = miesiąc lądowania.`;
            const meas = profile.extra.features_measured || [];
            const order = ['temp_mean', 'temp_diurnal_amp', 'thermal_inertia', 'surface_roughness', 'soil_moisture',
                           'dust_aerosol', 'solar_elevation_max', 'radiation_proxy', 'slope_deg'];
            Object.entries(s.values).forEach(([key, values]) => {
                const [label, unit] = TIME_LABELS[key] || [key, ''];
                const measured = meas[order.indexOf(key)] === true;
                const block = document.createElement('div');
                block.className = 'time-chart';
                block.innerHTML = `<h4 class="time-chart-title">${label} – zmiana w czasie</h4>
                    <span class="time-chart-meta">${unit ? unit + ' · ' : ''}${measured ? 'zmierzone w tym miejscu' : 'model globalny'}</span>
                    <div class="chart-wrap"><canvas height="120"></canvas></div>`;
                list.appendChild(block);
                const cur = s.current_index;
                timeCharts.push(new Chart(block.querySelector('canvas').getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: s.labels,
                        datasets: [{
                            label, data: values, borderColor: accent, backgroundColor: accent + '22', fill: true,
                            tension: 0.35, borderWidth: 1.5,
                            pointRadius: values.map((_, i) => i === cur ? 4.5 : 1.5),
                            pointBackgroundColor: values.map((_, i) => i === cur ? '#F4F4F6' : accent),
                            pointBorderColor: accent
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { display: false },
                            tooltip: { callbacks: {
                                title: items => (s.detail_labels || s.labels)[items[0].dataIndex],
                                label: c => `${c.formattedValue}${unit ? ' ' + unit : ''}${c.dataIndex === cur ? ' (data lądowania)' : ''}` } }
                        },
                        scales: {
                            x: { ticks: { color: '#94a3b8', font: { size: 8 }, maxRotation: 0, autoSkip: true,
                                          callback: function (v) { const [m, y] = this.getLabelForValue(v).split(' '); return `${m} '${String(y).slice(2)}`; } },
                                 grid: { display: false } },
                            y: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { color: 'rgba(255,255,255,0.06)' } }
                        }
                    }
                }));
            });
            box.hidden = false;
        }

        async function loadResults() {
            const profile = await callApi('characterize', {
                target_body: SEARCH_PARAMS.body,
                lat: SEARCH_PARAMS.lat,
                lon: SEARCH_PARAMS.lon,
                timestamp_iso: `${SEARCH_PARAMS.date}T12:00:00Z`
            });
            currentTargetProfile = profile;
            renderTargetProfileReadout(profile);
            loadTimeCharts();      // osobne zapytanie: wyniki pokazują się bez czekania na wykresy

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
