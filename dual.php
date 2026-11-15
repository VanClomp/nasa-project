<?php
/**
 * dual.php - Alternatywny widok porównawczy: Księżyc/Mars po lewej + Ziemia po prawej
 * Kliknięcie w Księżyc/Marsa automatycznie aktualizuje pinezki analogów na Ziemi.
 */
$selectedBody = strtolower($_GET['body'] ?? 'moon');
if (!in_array($selectedBody, ['moon', 'mars'])) {
    $selectedBody = 'moon';
}
$isMoon = ($selectedBody === 'moon');

$kFeatures = [
    ['idx' => 0, 'key' => 'temp_mean',           'label' => 'Średnia temp. powierzchni', 'default_w' => 0.90],
    ['idx' => 1, 'key' => 'temp_diurnal_amp',    'label' => 'Dobowa amplituda temp.',    'default_w' => 0.70],
    ['idx' => 2, 'key' => 'thermal_inertia',     'label' => 'Bezwładność cieplna gruntu','default_w' => 0.85],
    ['idx' => 3, 'key' => 'surface_roughness',   'label' => 'Chropowatość (SAR / DEM)',  'default_w' => 0.65],
    ['idx' => 4, 'key' => 'soil_moisture',       'label' => 'Wilgotność / lód wodny',    'default_w' => 0.80],
    ['idx' => 5, 'key' => 'dust_aerosol',        'label' => 'Zapylenie atmosfery (AOD)', 'default_w' => 0.50],
    ['idx' => 6, 'key' => 'solar_elevation_max', 'label' => 'Maks. kąt Słońca',          'default_w' => 0.95],
    ['idx' => 7, 'key' => 'radiation_proxy',     'label' => 'Promieniowanie (UV/DEM)',   'default_w' => 0.60],
    ['idx' => 8, 'key' => 'slope_deg',           'label' => 'Nachylenie terenu',         'default_w' => 0.75],
];

$presets = [
    'moon' => [
        ['name' => 'Krater Shackleton',     'lat' => -89.9, 'lon' => 0.0],
        ['name' => 'Marius Hills Skylight', 'lat' => 14.1,  'lon' => -56.8],
        ['name' => 'Mare Tranquillitatis',  'lat' => 0.67,  'lon' => 23.47],
        ['name' => 'Płaskowyż Aristarchus', 'lat' => 23.7,  'lon' => -47.4],
    ],
    'mars' => [
        ['name' => 'Krater Jezero',         'lat' => 18.38, 'lon' => 77.58],
        ['name' => 'Olympus Mons',          'lat' => 18.65, 'lon' => -133.8],
        ['name' => 'Valles Marineris',      'lat' => -13.9, 'lon' => -60.5],
        ['name' => 'Planum Australe',       'lat' => -83.5, 'lon' => 160.0],
    ]
];

$initialLat = isset($_GET['lat']) ? floatval($_GET['lat']) : $presets[$selectedBody][0]['lat'];
$initialLon = isset($_GET['lon']) ? floatval($_GET['lon']) : $presets[$selectedBody][0]['lon'];
$initialCaves = isset($_GET['caves']) && $_GET['caves'] === '1';
$initialWeights = [];
if (isset($_GET['w'])) {
    $parts = explode(',', $_GET['w']);
    for ($i = 0; $i < 9; $i++) {
        $initialWeights[$i] = isset($parts[$i]) ? max(0.0, min(1.0, floatval($parts[$i]))) : $kFeatures[$i]['default_w'];
    }
}
?>
<!DOCTYPE html>
<html lang="pl" data-body="<?php echo htmlspecialchars($selectedBody); ?>">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Planetary Analog Finder — Widok dwóch planet</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <link rel="stylesheet" href="style.css">
</head>
<body>

    <div class="hud-bg"></div>

    <!-- GÓRNY PASEK NAWIGACYJNY -->
    <header class="navbar">
        <div class="nav-left">
            <a href="index.php" class="back-btn">← Powrót</a>
            <span class="app-title">Planetary Analog Finder</span>
        </div>

        <div class="nav-right">
            <div class="mode-switcher">
                <button class="mode-btn" type="button" onclick="switchToSingleView()">Pojedynczy</button>
                <button class="mode-btn active" type="button">Dwie planety</button>
            </div>

            <div class="mode-switcher">
                <button class="mode-btn <?php echo $isMoon ? 'active' : ''; ?>" id="btn-mode-moon" onclick="switchCelestialBody('moon')">
                    Księżyc
                </button>
                <button class="mode-btn <?php echo !$isMoon ? 'active' : ''; ?>" id="btn-mode-mars" onclick="switchCelestialBody('mars')">
                    Mars
                </button>
            </div>
        </div>
    </header>

    <!-- GŁÓWNA PRZESTRZEŃ ROBOCZA -->
    <main class="workspace workspace-config">

        <!-- LEWA KOLUMNA: PARAMETRY I WAGI -->
        <aside class="hud-panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>Parametry i wagi</span>
                </div>
            </div>

            <div class="panel-body">
                <span class="section-label">Lokalizacje referencyjne</span>
                <div class="presets-list" id="presets-container">
                    <?php foreach ($presets[$selectedBody] as $idx => $p): ?>
                        <button class="preset-chip <?php echo $idx === 0 ? 'active' : ''; ?>"
                                onclick="selectPreset(<?php echo $p['lat']; ?>, <?php echo $p['lon']; ?>, this)">
                            <strong><?php echo htmlspecialchars($p['name']); ?></strong>
                            <span><?php echo $p['lat']; ?>°, <?php echo $p['lon']; ?>°</span>
                        </button>
                    <?php endforeach; ?>
                </div>

                <span class="section-label">Współrzędne</span>
                <div class="coords-row">
                    <div class="hud-input-group">
                        <label>LAT (°)</label>
                        <input type="number" id="input-lat" step="0.1" min="-90" max="90" value="<?php echo $initialLat; ?>">
                    </div>
                    <div class="hud-input-group">
                        <label>LON (°)</label>
                        <input type="number" id="input-lon" step="0.1" min="-180" max="180" value="<?php echo $initialLon; ?>">
                    </div>
                    <button class="scan-btn" onclick="triggerCharacterizeAndSearch()">Pobierz</button>
                </div>

                <span class="section-label">Wagi dopasowania (0.0 – 1.0)</span>
                <div id="sliders-container">
                    <?php foreach ($kFeatures as $f): ?>
                        <?php $wVal = $initialWeights[$f['idx']] ?? $f['default_w']; ?>
                        <div class="slider-item">
                            <div class="slider-top">
                                <span class="slider-name"><?php echo htmlspecialchars($f['label']); ?></span>
                                <span class="slider-meta" id="weight-val-<?php echo $f['idx']; ?>">
                                    <?php echo number_format($wVal, 2); ?>
                                </span>
                            </div>
                            <input type="range"
                                   class="hud-slider weight-slider"
                                   data-idx="<?php echo $f['idx']; ?>"
                                   min="0" max="1" step="0.05"
                                   value="<?php echo $wVal; ?>"
                                   oninput="onWeightSliderChange(this)">
                        </div>
                    <?php endforeach; ?>
                </div>

                <label class="cave-toggle">
                    <span>Wymagaj bliskości jaskiń (&lt; 15 km)</span>
                    <input type="checkbox" id="require-caves" <?php echo $initialCaves ? 'checked' : ''; ?> onchange="triggerSearchOnly()">
                </label>
            </div>

            <div class="dual-match-summary">
                <span>Najlepszy analog na Ziemi</span>
                <strong id="dual-top-match">Ładowanie...</strong>
            </div>

            <div class="panel-footer">
                <button type="button" class="find-analogs-btn" onclick="openResultsPage()">
                    <span>Szczegóły wyników</span>
                    <span>→</span>
                </button>
            </div>
        </aside>

        <!-- PRAWA PRZESTRZEŃ: DWIE PLANETY OBOK SIEBIE BEZ RAMEK -->
        <section class="dual-globes-stage">
            <!-- LEWA PLANETA: KSIĘŻYC / MARS -->
            <div class="dual-globe-col">
                <div class="globe-hud-overlay">
                    <div class="hud-pill" id="target-globe-pill">
                        <?php echo $isMoon ? 'Księżyc' : 'Mars'; ?> · kliknij, aby wybrać punkt
                    </div>
                </div>
                <div class="dual-globe-canvas" id="target-globe-canvas"></div>
            </div>

            <!-- PRAWA PLANETA: ZIEMIA Z PINEZKAMI ANALOGÓW -->
            <div class="dual-globe-col">
                <div class="globe-hud-overlay">
                    <div class="hud-pill">
                        Ziemia · znalezione analogi
                    </div>
                </div>
                <div class="dual-globe-canvas" id="earth-globe-canvas"></div>
            </div>
        </section>

    </main>

    <script>
        const PRESETS = <?php echo json_encode($presets); ?>;
        let currentBody = <?php echo json_encode($selectedBody); ?>;
        let currentTargetProfile = null;
        let currentCandidates = [];

        const textureLoader = new THREE.TextureLoader();
        function loadBodyTexture(url) {
            return textureLoader.load(url, (tex) => {
                tex.needsUpdate = true;
                if (typeof targetGlobe !== 'undefined' && targetGlobe && targetGlobe.sphereMat) {
                    targetGlobe.sphereMat.needsUpdate = true;
                }
            });
        }
        let moonPhotoTexture = loadBodyTexture('images/moon_photo.jpg');
        let marsPhotoTexture = loadBodyTexture('images/mars_photo.jpg');

        function getTargetTexture(body) {
            if (body === 'moon') {
                if (!moonPhotoTexture) moonPhotoTexture = loadBodyTexture('images/moon_photo.jpg');
                return moonPhotoTexture;
            }
            if (!marsPhotoTexture) marsPhotoTexture = loadBodyTexture('images/mars_photo.jpg');
            return marsPhotoTexture;
        }

        const earthBaseImg = new Image();
        earthBaseImg.src = 'images/earth_photo.jpg';
        earthBaseImg.onload = () => {
            if (typeof earthGlobe !== 'undefined' && earthGlobe.sphereMat) {
                earthGlobe.sphereMat.map = generateEarthHeatmapTexture(currentCandidates);
                earthGlobe.sphereMat.needsUpdate = true;
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

            candidates.forEach(cand => {
                const px = ((cand.lon + 180) / 360) * c.width;
                const py = ((90 - cand.lat) / 180) * c.height;
                const radius = 110 * cand.score;
                const g = ctx.createRadialGradient(px, py, 4, px, py, radius);
                g.addColorStop(0, `rgba(16, 185, 129, ${cand.score * 0.9})`);
                g.addColorStop(0.5, `rgba(96, 165, 250, ${cand.score * 0.45})`);
                g.addColorStop(1, 'rgba(96, 165, 250, 0)');
                ctx.fillStyle = g;
                ctx.beginPath(); ctx.arc(px, py, radius, 0, Math.PI * 2); ctx.fill();
            });

            return new THREE.CanvasTexture(c);
        }

        function latLonToVector3(lat, lon, radius = 1.124) {
            const phi = (90 - lat) * (Math.PI / 180);
            const theta = (lon + 180) * (Math.PI / 180);
            const x = -(radius * Math.sin(phi) * Math.cos(theta));
            const z = (radius * Math.sin(phi) * Math.sin(theta));
            const y = (radius * Math.cos(phi));
            return new THREE.Vector3(x, y, z);
        }

        // =========================================================================
        // 1. SCENA LEWA: KSIĘŻYC / MARS (KLIKALNA + ZOOM DO KURSORA)
        // =========================================================================
        function createGlobeController(containerId, options) {
            const container = document.getElementById(containerId);
            const scene = new THREE.Scene();
            const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
            camera.position.z = 4.3;

            const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
            container.appendChild(renderer.domElement);

            const group = new THREE.Group();
            scene.add(group);

            const sphereGeo = new THREE.SphereGeometry(1.12, 64, 64);
            const sphereMat = new THREE.MeshStandardMaterial({
                map: options.initialTexture,
                roughness: 0.96,
                metalness: 0.0
            });
            const mesh = new THREE.Mesh(sphereGeo, sphereMat);
            group.add(mesh);

            scene.add(new THREE.AmbientLight(0xffffff, 0.35));
            const sunLight = new THREE.DirectionalLight(0xffffff, 1.05);
            sunLight.position.set(5, 3, 4);
            scene.add(sunLight);

            const state = {
                container, scene, camera, renderer, group, mesh, sphereMat,
                isDragging: false, dragMoved: false,
                prevMouse: { x: 0, y: 0 },
                targetCamX: 0, targetCamY: 0, targetCamZ: 4.3,
                onPinScale: null
            };

            function resize() {
                const rect = container.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) return;
                renderer.setSize(rect.width, rect.height);
                camera.aspect = rect.width / rect.height;
                camera.updateProjectionMatrix();
            }
            window.addEventListener('resize', resize);
            setTimeout(resize, 50);

            renderer.domElement.style.touchAction = 'none';

            function applyZoomAt(clientX, clientY, deltaZ) {
                const rect = renderer.domElement.getBoundingClientRect();
                const ndcX = ((clientX - rect.left) / rect.width) * 2 - 1;
                const ndcY = -((clientY - rect.top) / rect.height) * 2 + 1;

                const oldZ = state.targetCamZ;
                const newZ = Math.max(1.45, Math.min(5.8, oldZ + deltaZ));

                const vFov = (camera.fov * Math.PI) / 180;
                const halfHOld = oldZ * Math.tan(vFov / 2);
                const halfWOld = halfHOld * camera.aspect;
                const worldX = state.targetCamX + ndcX * halfWOld;
                const worldY = state.targetCamY + ndcY * halfHOld;

                const halfHNew = newZ * Math.tan(vFov / 2);
                const halfWNew = halfHNew * camera.aspect;

                state.targetCamZ = newZ;
                const maxPan = Math.max(0, (4.3 - newZ) * 0.65);
                state.targetCamX = Math.max(-maxPan, Math.min(maxPan, worldX - ndcX * halfWNew));
                state.targetCamY = Math.max(-maxPan, Math.min(maxPan, worldY - ndcY * halfHNew));
            }

            renderer.domElement.addEventListener('wheel', (e) => {
                e.preventDefault();
                applyZoomAt(e.clientX, e.clientY, e.deltaY * 0.0022);
            }, { passive: false });

            renderer.domElement.addEventListener('mousedown', (e) => {
                state.isDragging = true;
                state.dragMoved = false;
                state.prevMouse = { x: e.clientX, y: e.clientY };
            });

            window.addEventListener('mousemove', (e) => {
                if (!state.isDragging) return;
                const dx = e.clientX - state.prevMouse.x;
                const dy = e.clientY - state.prevMouse.y;
                if (Math.abs(dx) > 3 || Math.abs(dy) > 3) state.dragMoved = true;
                const sens = Math.max(0.0018, (camera.position.z - 1.0) * 0.0028);
                group.rotation.y += dx * sens;
                group.rotation.x = Math.max(-1.35, Math.min(1.35, group.rotation.x + dy * sens));
                state.prevMouse = { x: e.clientX, y: e.clientY };
            });

            const raycaster = new THREE.Raycaster();
            const mouseVec = new THREE.Vector2();
            function pickPointAt(clientX, clientY) {
                if (!options.onClickPoint) return;
                const rect = renderer.domElement.getBoundingClientRect();
                mouseVec.x = ((clientX - rect.left) / rect.width) * 2 - 1;
                mouseVec.y = -((clientY - rect.top) / rect.height) * 2 + 1;
                raycaster.setFromCamera(mouseVec, camera);
                const hits = raycaster.intersectObject(mesh);
                if (hits.length > 0) {
                    const localPt = group.worldToLocal(hits[0].point.clone()).normalize();
                    const lat = 90 - (Math.acos(localPt.y) * 180 / Math.PI);
                    const lon = ((Math.atan2(localPt.z, -localPt.x) * 180 / Math.PI) - 180);
                    const normLon = lon < -180 ? lon + 360 : (lon > 180 ? lon - 360 : lon);
                    options.onClickPoint(lat, normLon);
                }
            }

            window.addEventListener('mouseup', (e) => {
                if (state.isDragging && !state.dragMoved) {
                    pickPointAt(e.clientX, e.clientY);
                }
                state.isDragging = false;
            });

            // Obsługa dotyku (obrót 1 palcem, tapnięcie, pinch-to-zoom 2 palcami)
            let prevPinchDist = 0;
            renderer.domElement.addEventListener('touchstart', (e) => {
                e.preventDefault();
                state.isDragging = true;
                if (e.touches.length === 1) {
                    state.dragMoved = false;
                    prevPinchDist = 0;
                    state.prevMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                } else if (e.touches.length === 2) {
                    state.dragMoved = true;
                    prevPinchDist = Math.hypot(
                        e.touches[0].clientX - e.touches[1].clientX,
                        e.touches[0].clientY - e.touches[1].clientY
                    );
                }
            }, { passive: false });

            renderer.domElement.addEventListener('touchmove', (e) => {
                e.preventDefault();
                if (!state.isDragging) return;
                if (e.touches.length === 1 && prevPinchDist === 0) {
                    const dx = e.touches[0].clientX - state.prevMouse.x;
                    const dy = e.touches[0].clientY - state.prevMouse.y;
                    if (Math.abs(dx) > 4 || Math.abs(dy) > 4) state.dragMoved = true;
                    const sens = Math.max(0.0018, (camera.position.z - 1.0) * 0.0028);
                    group.rotation.y += dx * sens;
                    group.rotation.x = Math.max(-1.35, Math.min(1.35, group.rotation.x + dy * sens));
                    state.prevMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
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
                    state.dragMoved = true;
                    state.prevMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                    return;
                }
                if (e.touches.length === 0) {
                    if (state.isDragging && !state.dragMoved && e.changedTouches.length > 0) {
                        pickPointAt(e.changedTouches[0].clientX, e.changedTouches[0].clientY);
                    }
                    state.isDragging = false;
                    prevPinchDist = 0;
                }
            }, { passive: false });

            function loop() {
                if (!state.isDragging) group.rotation.y += 0.0008;
                camera.position.x += (state.targetCamX - camera.position.x) * 0.08;
                camera.position.y += (state.targetCamY - camera.position.y) * 0.08;
                camera.position.z += (state.targetCamZ - camera.position.z) * 0.08;
                if (state.onPinScale) {
                    state.onPinScale(Math.max(0.22, (camera.position.z - 1.05) / 3.25));
                }
                renderer.render(scene, camera);
                requestAnimationFrame(loop);
            }
            loop();

            return state;
        }

        // Inicjalizacja lewej planety (Księżyc / Mars)
        const targetGlobe = createGlobeController('target-globe-canvas', {
            initialTexture: getTargetTexture(currentBody),
            onClickPoint: (lat, lon) => {
                document.getElementById('input-lat').value = lat.toFixed(1);
                document.getElementById('input-lon').value = lon.toFixed(1);
                triggerCharacterizeAndSearch();
            }
        });

        // Pinezka na Księżycu / Marsie
        const targetMarker = new THREE.Group();
        targetMarker.add(new THREE.Mesh(
            new THREE.CircleGeometry(0.013, 24),
            new THREE.MeshBasicMaterial({ color: 0xf4f4f6, side: THREE.DoubleSide })
        ));
        const markerRingMat = new THREE.MeshBasicMaterial({
            color: currentBody === 'moon' ? 0x60a5fa : 0xf97316,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.95
        });
        targetMarker.add(new THREE.Mesh(new THREE.RingGeometry(0.028, 0.034, 36), markerRingMat));
        targetGlobe.group.add(targetMarker);
        targetGlobe.onPinScale = (s) => targetMarker.scale.setScalar(s);

        // Inicjalizacja prawej planety (Ziemia)
        const earthGlobe = createGlobeController('earth-globe-canvas', {
            initialTexture: generateEarthHeatmapTexture([])
        });
        const earthPinsGroup = new THREE.Group();
        earthGlobe.group.add(earthPinsGroup);
        earthGlobe.onPinScale = (s) => {
            earthPinsGroup.children.forEach(pin => pin.scale.setScalar(s));
        };

        // =========================================================================
        // 2. API + AUTOMATYCZNA AKTUALIZACJA PINEZEK NA ZIEMI
        // =========================================================================
        async function callApi(endpoint, payload) {
            try {
                const res = await fetch(`/api/v1/${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.ok) return await res.json();
            } catch (err) {}
            const fallbackRes = await fetch(`explorer.php?mock_api=${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            return await fallbackRes.json();
        }

        function getWeightsVector() {
            const sliders = document.querySelectorAll('.weight-slider');
            const weights = new Array(9).fill(0.5);
            sliders.forEach(s => {
                weights[parseInt(s.dataset.idx, 10)] = parseFloat(s.value);
            });
            return weights;
        }

        function updateTargetMarker(lat, lon) {
            const pos = latLonToVector3(lat, lon, 1.124);
            targetMarker.position.copy(pos);
            targetMarker.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), pos.clone().normalize());
        }

        function refreshEarthPins() {
            earthGlobe.sphereMat.map = generateEarthHeatmapTexture(currentCandidates);
            earthGlobe.sphereMat.needsUpdate = true;

            earthPinsGroup.clear();
            currentCandidates.forEach((c, idx) => {
                const pos = latLonToVector3(c.lat, c.lon, 1.125);
                const isBest = (idx === 0);
                const pinGroup = new THREE.Group();
                pinGroup.position.copy(pos);
                pinGroup.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), pos.clone().normalize());

                pinGroup.add(new THREE.Mesh(
                    new THREE.CircleGeometry(isBest ? 0.015 : 0.010, 24),
                    new THREE.MeshBasicMaterial({
                        color: isBest ? 0x10b981 : 0x60a5fa,
                        side: THREE.DoubleSide,
                        transparent: true,
                        opacity: isBest ? 1.0 : 0.85
                    })
                ));

                if (isBest) {
                    pinGroup.add(new THREE.Mesh(
                        new THREE.RingGeometry(0.028, 0.034, 32),
                        new THREE.MeshBasicMaterial({
                            color: 0x10b981,
                            side: THREE.DoubleSide,
                            transparent: true,
                            opacity: 0.95
                        })
                    ));
                }

                earthPinsGroup.add(pinGroup);
            });

            const summaryEl = document.getElementById('dual-top-match');
            if (currentCandidates.length > 0) {
                const top = currentCandidates[0];
                summaryEl.innerText = `${top.name_hint} (${(top.score * 100).toFixed(1)}%)`;
            } else {
                summaryEl.innerText = 'Brak wyników dla filtra jaskiń';
            }
        }

        async function triggerCharacterizeAndSearch() {
            const lat = parseFloat(document.getElementById('input-lat').value) || 0;
            const lon = parseFloat(document.getElementById('input-lon').value) || 0;
            updateTargetMarker(lat, lon);

            const profile = await callApi('characterize', {
                target_body: currentBody,
                lat: lat,
                lon: lon,
                timestamp_iso: new Date().toISOString()
            });
            currentTargetProfile = profile;
            await triggerSearchOnly();
        }

        async function triggerSearchOnly() {
            if (!currentTargetProfile) return;
            const res = await callApi('search', {
                features_norm: currentTargetProfile.features_norm,
                weights: getWeightsVector(),
                require_caves: document.getElementById('require-caves').checked,
                top_k: 100
            });
            currentCandidates = res.candidates || [];
            refreshEarthPins();
        }

        function onWeightSliderChange(slider) {
            const idx = slider.dataset.idx;
            document.getElementById(`weight-val-${idx}`).innerText = parseFloat(slider.value).toFixed(2);

            if (!currentTargetProfile || currentCandidates.length === 0) return;
            const weights = getWeightsVector();
            let wSum = weights.reduce((a, b) => a + b, 0);
            if (wSum <= 0.0001) wSum = 1.0;

            const y = currentTargetProfile.features_norm;
            currentCandidates.forEach(c => {
                let diff = 0.0;
                for (let k = 0; k < 9; k++) {
                    diff += weights[k] * Math.abs((c.features_norm[k] || 0) - (y[k] || 0));
                }
                c.score = Math.max(0.05, Math.min(0.99, 1.0 - (diff / wSum)));
            });
            currentCandidates.sort((a, b) => b.score - a.score);
            refreshEarthPins();
        }

        function selectPreset(lat, lon, btnEl) {
            document.querySelectorAll('.preset-chip').forEach(b => b.classList.remove('active'));
            if (btnEl) btnEl.classList.add('active');
            document.getElementById('input-lat').value = lat;
            document.getElementById('input-lon').value = lon;
            triggerCharacterizeAndSearch();
        }

        function switchCelestialBody(body) {
            currentBody = body;
            document.documentElement.setAttribute('data-body', body);

            document.getElementById('btn-mode-moon').classList.toggle('active', body === 'moon');
            document.getElementById('btn-mode-mars').classList.toggle('active', body === 'mars');
            document.getElementById('target-globe-pill').innerText =
                `${body === 'moon' ? 'Księżyc' : 'Mars'} · kliknij, aby wybrać punkt`;

            const pList = PRESETS[body];
            document.getElementById('presets-container').innerHTML = pList.map((p, idx) => `
                <button class="preset-chip ${idx === 0 ? 'active' : ''}"
                        onclick="selectPreset(${p.lat}, ${p.lon}, this)">
                    <strong>${p.name}</strong>
                    <span>${p.lat}°, ${p.lon}°</span>
                </button>
            `).join('');

            document.getElementById('input-lat').value = pList[0].lat;
            document.getElementById('input-lon').value = pList[0].lon;

            markerRingMat.color.setHex(body === 'moon' ? 0x60a5fa : 0xf97316);
            targetGlobe.sphereMat.map = getTargetTexture(body);
            targetGlobe.sphereMat.needsUpdate = true;

            triggerCharacterizeAndSearch();
        }

        function buildQuery() {
            const lat = parseFloat(document.getElementById('input-lat').value) || 0;
            const lon = parseFloat(document.getElementById('input-lon').value) || 0;
            const weights = getWeightsVector().map(w => w.toFixed(2)).join(',');
            const caves = document.getElementById('require-caves').checked ? '1' : '0';
            return new URLSearchParams({
                body: currentBody,
                lat: lat.toFixed(2),
                lon: lon.toFixed(2),
                w: weights,
                caves: caves
            }).toString();
        }

        function switchToSingleView() {
            window.location.href = `explorer.php?${buildQuery()}`;
        }

        function openResultsPage() {
            window.location.href = `results.php?${buildQuery()}`;
        }

        window.addEventListener('DOMContentLoaded', () => {
            triggerCharacterizeAndSearch();
        });
    </script>
</body>
</html>
