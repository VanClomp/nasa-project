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

// Miejsca lądowania: generowane z danych 3-charakteryzatora (scripts/export_presets.py)
$presets = require __DIR__ . '/presets.php';

$initialLat = isset($_GET['lat']) ? floatval($_GET['lat']) : $presets[$selectedBody][0]['lat'];
$initialLon = isset($_GET['lon']) ? floatval($_GET['lon']) : $presets[$selectedBody][0]['lon'];
$initialCaves = isset($_GET['caves']) && $_GET['caves'] === '1';
$initialDate = (isset($_GET['date']) && preg_match('/^\d{4}-\d{2}-\d{2}$/', $_GET['date']))
    ? $_GET['date'] : gmdate('Y-m-d');   // data lądowania (UTC), domyślnie dziś
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
    <link rel="stylesheet" href="style.css?v=<?php echo @filemtime(__DIR__ . '/style.css') ?: 1; ?>">
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
    <main class="workspace workspace-dual" id="dual-workspace">

        <!-- LEWA KOLUMNA: PARAMETRY I WAGI -->
        <aside class="hud-panel dual-drawer dual-drawer-left" id="dual-filters-panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>Parametry i wagi</span>
                </div>
                <button type="button" class="panel-switch-btn" onclick="toggleDualDrawer('results')">
                    Wyniki →
                </button>
            </div>

            <div class="panel-body">
                <span class="section-label">Miejsce lądowania</span>
                <button type="button" class="site-picker-btn" id="site-picker-btn" onclick="SitePicker.open()" aria-haspopup="dialog">
                    <span class="site-picker-btn-text">
                        <strong id="site-picker-current">&nbsp;</strong>
                        <span id="site-picker-coords">&nbsp;</span>
                    </span>
                    <span class="site-picker-btn-cta">Zmień ▾</span>
                </button>

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
                </div>
                <button type="button" class="center-pin-btn" onclick="centerGlobesOnPins()">Wyśrodkuj</button>

                <span class="section-label">Data lądowania</span>
                <div class="coords-row">
                    <div class="hud-input-group">
                        <label>DATA (UTC)</label>
                        <input type="date" id="input-date" min="1990-01-01" max="2100-12-31" value="<?php echo htmlspecialchars($initialDate); ?>" onchange="triggerCharacterizeAndSearch()">
                    </div>
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

        <!-- PRAWA KOLUMNA: WYNIKI WYSZUKIWANIA (POKAZYWANA PO PRZEŁĄCZENIU) -->
        <aside class="hud-panel dual-drawer dual-drawer-right" id="dual-results-panel">
            <div class="panel-header">
                <button type="button" class="panel-switch-btn" onclick="toggleDualDrawer('filters')">
                    ← Filtry
                </button>
                <div class="panel-title">
                    <span>Wyniki wyszukiwania</span>
                </div>
            </div>

            <div class="panel-body" id="dual-candidates-list">
                <div style="color: var(--text-muted); font-size: 0.78rem; padding: 0.5rem 0;">
                    Ładowanie analogów...
                </div>
            </div>

            <div class="panel-footer">
                <button type="button" class="find-analogs-btn" onclick="openResultsPage()">
                    <span>Szczegóły wyników</span>
                    <span>→</span>
                </button>
            </div>
        </aside>

    </main>

    <script>
        const PRESETS = <?php echo json_encode($presets); ?>;
        let currentBody = <?php echo json_encode($selectedBody); ?>;
        let currentTargetProfile = null;
        let currentCandidates = [];
        let selectedCandidateIndex = 0;

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

        const earthPhotoTexture = textureLoader.load('images/earth_photo.jpg', (tex) => {
            tex.needsUpdate = true;
            if (typeof earthGlobe !== 'undefined' && earthGlobe && earthGlobe.sphereMat) {
                earthGlobe.sphereMat.needsUpdate = true;
            }
        });

        function createEarthPin(isBest) {
            const pinGroup = new THREE.Group();
            const color = isBest ? 0x10b981 : 0x60a5fa;

            // Subtelny pierścień na powierzchni planety
            const baseRing = new THREE.Mesh(
                new THREE.RingGeometry(isBest ? 0.015 : 0.010, isBest ? 0.021 : 0.014, 32),
                new THREE.MeshBasicMaterial({
                    color,
                    side: THREE.DoubleSide,
                    transparent: true,
                    opacity: isBest ? 0.9 : 0.55
                })
            );
            baseRing.position.z = 0.001;
            pinGroup.add(baseRing);

            // Zewnętrzna aureola dla najlepszego dopasowania
            if (isBest) {
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
            const stemH = isBest ? 0.044 : 0.030;
            const stemGeo = new THREE.CylinderGeometry(0.0016, 0.0010, stemH, 10);
            stemGeo.rotateX(Math.PI / 2);
            const stem = new THREE.Mesh(
                stemGeo,
                new THREE.MeshBasicMaterial({
                    color: 0xe2e8f0,
                    transparent: true,
                    opacity: isBest ? 0.95 : 0.75
                })
            );
            stem.position.z = stemH * 0.5 + 0.001;
            pinGroup.add(stem);

            // Główka pinezki 3D
            const headR = isBest ? 0.012 : 0.0085;
            const head = new THREE.Mesh(
                new THREE.SphereGeometry(headR, 18, 18),
                new THREE.MeshBasicMaterial({
                    color,
                    transparent: true,
                    opacity: isBest ? 1.0 : 0.9
                })
            );
            head.position.z = stemH + headR * 0.7;
            pinGroup.add(head);

            return pinGroup;
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
            renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
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
                pauseAutoRotateUntil: 0,
                isCentering: false, targetCenterRotX: 0, targetCenterRotY: 0,
                onPinScale: null,
                centerOnLatLon: (lat, lon) => {
                    pauseAutoRotate();
                    const p = latLonToVector3(lat, lon, 1);
                    const rXZ = Math.hypot(p.x, p.z);
                    const desiredRotY = -Math.atan2(p.x, p.z);
                    const desiredRotX = Math.atan2(p.y, rXZ);
                    let deltaY = (desiredRotY - group.rotation.y) % (Math.PI * 2);
                    if (deltaY > Math.PI) deltaY -= Math.PI * 2;
                    if (deltaY < -Math.PI) deltaY += Math.PI * 2;
                    state.targetCenterRotX = desiredRotX;
                    state.targetCenterRotY = group.rotation.y + deltaY;
                    state.targetCamX = 0;
                    state.targetCamY = 0;
                    state.isCentering = true;
                }
            };

            function pauseAutoRotate(ms = 8000) {
                state.pauseAutoRotateUntil = performance.now() + ms;
            }

            function resize() {
                const rect = container.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) return;
                renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
                renderer.setSize(rect.width, rect.height);
                camera.aspect = rect.width / rect.height;
                // Dopasowanie FOV tak, aby sfera (r=1.12) przy z=4.3 wypełniała ~95% kolumny z zachowaniem oddechu
                const targetHalfSpan = 1.22;
                const hHalf = targetHalfSpan / Math.min(1, camera.aspect);
                camera.fov = (2 * Math.atan(hHalf / 4.3) * 180) / Math.PI;
                camera.updateProjectionMatrix();
            }
            window.addEventListener('resize', resize);
            if (typeof ResizeObserver !== 'undefined') {
                new ResizeObserver(() => resize()).observe(container);
            }
            resize();
            requestAnimationFrame(resize);
            setTimeout(resize, 50);
            state.resize = resize;

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
                pauseAutoRotate();
                applyZoomAt(e.clientX, e.clientY, e.deltaY * 0.0022);
            }, { passive: false });

            renderer.domElement.addEventListener('mousedown', (e) => {
                pauseAutoRotate();
                state.isCentering = false;
                state.isDragging = true;
                state.dragMoved = false;
                state.prevMouse = { x: e.clientX, y: e.clientY };
            });

            window.addEventListener('mousemove', (e) => {
                if (!state.isDragging) return;
                pauseAutoRotate();
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
                if (state.isDragging) {
                    pauseAutoRotate();
                    if (!state.dragMoved) {
                        pickPointAt(e.clientX, e.clientY);
                    }
                }
                state.isDragging = false;
            });

            // Obsługa dotyku (obrót 1 palcem, tapnięcie, pinch-to-zoom 2 palcami)
            let prevPinchDist = 0;
            renderer.domElement.addEventListener('touchstart', (e) => {
                e.preventDefault();
                pauseAutoRotate();
                state.isCentering = false;
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
                pauseAutoRotate();
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
                    if (state.isDragging) {
                        pauseAutoRotate();
                        if (!state.dragMoved && e.changedTouches.length > 0) {
                            pickPointAt(e.changedTouches[0].clientX, e.changedTouches[0].clientY);
                        }
                    }
                    state.isDragging = false;
                    prevPinchDist = 0;
                }
            }, { passive: false });

            function loop() {
                if (state.isCentering) {
                    group.rotation.x += (state.targetCenterRotX - group.rotation.x) * 0.12;
                    group.rotation.y += (state.targetCenterRotY - group.rotation.y) * 0.12;
                    if (Math.abs(state.targetCenterRotX - group.rotation.x) < 0.001 &&
                        Math.abs(state.targetCenterRotY - group.rotation.y) < 0.001) {
                        group.rotation.x = state.targetCenterRotX;
                        group.rotation.y = state.targetCenterRotY;
                        state.isCentering = false;
                    }
                } else if (!state.isDragging) {
                    const now = performance.now();
                    if (now >= state.pauseAutoRotateUntil) {
                        const resumeFactor = Math.min(1, (now - state.pauseAutoRotateUntil) / 800);
                        group.rotation.y += 0.0008 * resumeFactor;
                    }
                }
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
            initialTexture: earthPhotoTexture
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
            if (selectedCandidateIndex >= currentCandidates.length) {
                selectedCandidateIndex = 0;
            }
            earthPinsGroup.clear();
            const currentScale = Math.max(0.22, (earthGlobe.camera.position.z - 1.05) / 3.25);
            currentCandidates.forEach((c, idx) => {
                const pos = latLonToVector3(c.lat, c.lon, 1.1205);
                const isSelected = (idx === selectedCandidateIndex);
                const pinGroup = createEarthPin(isSelected);
                pinGroup.position.copy(pos);
                pinGroup.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), pos.clone().normalize());
                pinGroup.scale.setScalar(currentScale);
                earthPinsGroup.add(pinGroup);
            });

            const summaryEl = document.getElementById('dual-top-match');
            if (currentCandidates.length > 0) {
                const top = currentCandidates[0];
                summaryEl.innerText = `${top.name_hint} (${(top.score * 100).toFixed(1)}%)`;
            } else {
                summaryEl.innerText = 'Brak wyników dla filtra jaskiń';
            }

            renderDualCandidatesList();
        }

        function renderDualCandidatesList() {
            const listEl = document.getElementById('dual-candidates-list');
            if (!listEl) return;

            if (currentCandidates.length === 0) {
                listEl.innerHTML = `<div style="color: var(--text-muted); font-size: 0.78rem; padding: 0.75rem 0;">Brak lokalizacji spełniających kryteria filtra jaskiń.</div>`;
                return;
            }

            listEl.innerHTML = currentCandidates.map((c, idx) => {
                const isSel = (idx === selectedCandidateIndex);
                const caveText = c.nearest_skylight_km !== null
                    ? `Jaskinia: ${c.nearest_skylight_km} km`
                    : 'Brak jaskiń';
                return `
                    <div class="candidate-card ${isSel ? 'selected' : ''}" onclick="selectDualCandidate(${idx})">
                        <div class="cand-top">
                            <span class="cand-rank">#${idx + 1} · ${c.lat.toFixed(2)}°, ${c.lon.toFixed(2)}°</span>
                            <span class="cand-score">${(c.score * 100).toFixed(1)}%</span>
                        </div>
                        <div class="cand-name">${c.name_hint}</div>
                        <div class="cand-meta" style="font-size: 0.68rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;">
                            ${caveText}
                        </div>
                    </div>
                `;
            }).join('');
        }

        function selectDualCandidate(idx) {
            selectedCandidateIndex = idx;
            refreshEarthPins();
            const cand = currentCandidates[idx];
            if (cand) {
                earthGlobe.centerOnLatLon(cand.lat, cand.lon);
            }
        }

        let drawerResizeRaf = null;
        function toggleDualDrawer(mode) {
            const workspace = document.getElementById('dual-workspace');
            if (mode === 'results') {
                workspace.classList.add('show-results');
            } else {
                workspace.classList.remove('show-results');
            }

            if (drawerResizeRaf) cancelAnimationFrame(drawerResizeRaf);
            const animStart = performance.now();
            const syncResize = (now) => {
                if (typeof targetGlobe !== 'undefined' && targetGlobe.resize) targetGlobe.resize();
                if (typeof earthGlobe !== 'undefined' && earthGlobe.resize) earthGlobe.resize();
                if (now - animStart < 700) {
                    drawerResizeRaf = requestAnimationFrame(syncResize);
                }
            };
            drawerResizeRaf = requestAnimationFrame(syncResize);
        }

        async function triggerCharacterizeAndSearch() {
            const lat = parseFloat(document.getElementById('input-lat').value) || 0;
            const lon = parseFloat(document.getElementById('input-lon').value) || 0;
            updateTargetMarker(lat, lon);

            const profile = await callApi('characterize', {
                target_body: currentBody,
                lat: lat,
                lon: lon,
                timestamp_iso: landingTimestamp()
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

            document.getElementById('input-lat').value = pList[0].lat;
            document.getElementById('input-lon').value = pList[0].lon;

            markerRingMat.color.setHex(body === 'moon' ? 0x60a5fa : 0xf97316);
            targetGlobe.sphereMat.map = getTargetTexture(body);
            targetGlobe.sphereMat.needsUpdate = true;

            triggerCharacterizeAndSearch();
        }


        // Data lądowania z pola #input-date -> timestamp_iso dla /api/v1/characterize (południe UTC tego dnia).
        // Warunki na Marsie / Księżycu (pora roku Ls, pył, temperatury, położenie Słońca) zależą od tej daty.
        function landingTimestamp() {
            const el = document.getElementById('input-date');
            const d = el ? el.value : '';
            return /^\d{4}-\d{2}-\d{2}$/.test(d) ? `${d}T12:00:00Z` : new Date().toISOString();
        }
        function landingDate() {
            return landingTimestamp().slice(0, 10);
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
                caves: caves,
                date: landingDate()
            }).toString();
        }

        function switchToSingleView() {
            window.location.href = `explorer.php?${buildQuery()}`;
        }

        function openResultsPage() {
            window.location.href = `results.php?${buildQuery()}`;
        }

        function centerGlobesOnPins() {
            const lat = parseFloat(document.getElementById('input-lat').value) || 0;
            const lon = parseFloat(document.getElementById('input-lon').value) || 0;
            targetGlobe.centerOnLatLon(lat, lon);
            if (currentCandidates.length > 0) {
                earthGlobe.centerOnLatLon(currentCandidates[0].lat, currentCandidates[0].lon);
            }
        }

        window.addEventListener('DOMContentLoaded', () => {
            const latInput = document.getElementById('input-lat');
            const lonInput = document.getElementById('input-lon');
            let coordsDebounce = null;

            const handleCoordsInput = () => {
                const rawLat = parseFloat(latInput.value);
                const rawLon = parseFloat(lonInput.value);
                if (Number.isNaN(rawLat) || Number.isNaN(rawLon)) return;
                const lat = Math.max(-90, Math.min(90, rawLat));
                const lon = Math.max(-180, Math.min(180, rawLon));
                updateTargetMarker(lat, lon);
                clearTimeout(coordsDebounce);
                coordsDebounce = setTimeout(() => {
                    triggerCharacterizeAndSearch();
                }, 200);
            };

            [latInput, lonInput].forEach(el => {
                el.addEventListener('input', handleCoordsInput);
                el.addEventListener('change', () => {
                    clearTimeout(coordsDebounce);
                    triggerCharacterizeAndSearch();
                });
            });

            triggerCharacterizeAndSearch();
        });
    </script>
    <?php include __DIR__ . '/site_picker.php'; ?>
</body>
</html>
