<?php
/**
 * dual.php - Alternative comparison view: Moon/Mars on the left + Earth on the right
 * Clicking the Moon/Mars automatically updates the analog pins on Earth.
 */
$selectedBody = strtolower($_GET['body'] ?? 'moon');
if (!in_array($selectedBody, ['moon', 'mars'])) {
    $selectedBody = 'moon';
}
$isMoon = ($selectedBody === 'moon');

$kFeatures = [
    ['idx' => 0, 'key' => 'temp_mean',           'label' => 'Mean surface temp.',        'default_w' => 0.90],
    ['idx' => 1, 'key' => 'temp_diurnal_amp',    'label' => 'Diurnal temp. range',       'default_w' => 0.70],
    ['idx' => 2, 'key' => 'thermal_inertia',     'label' => 'Ground thermal inertia',    'default_w' => 0.85],
    ['idx' => 3, 'key' => 'surface_roughness',   'label' => 'Roughness (SAR / DEM)',     'default_w' => 0.65],
    ['idx' => 4, 'key' => 'soil_moisture',       'label' => 'Moisture / water ice',      'default_w' => 0.80],
    ['idx' => 5, 'key' => 'dust_aerosol',        'label' => 'Atmospheric dust (AOD)',    'default_w' => 0.50],
    ['idx' => 6, 'key' => 'solar_elevation_max', 'label' => 'Max. Sun elevation',        'default_w' => 0.95],
    ['idx' => 7, 'key' => 'radiation_proxy',     'label' => 'Radiation (UV/DEM)',        'default_w' => 0.60],
    ['idx' => 8, 'key' => 'slope_deg',           'label' => 'Terrain slope',             'default_w' => 0.75],
];

// Landing sites: generated from the 3-charakteryzator data (scripts/export_presets.py)
$presets = require __DIR__ . '/presets.php';

$initialLat = isset($_GET['lat']) ? floatval($_GET['lat']) : $presets[$selectedBody][0]['lat'];
$initialLon = isset($_GET['lon']) ? floatval($_GET['lon']) : $presets[$selectedBody][0]['lon'];
$initialCaves = isset($_GET['caves']) && $_GET['caves'] === '1';
$initialDate = (isset($_GET['date']) && preg_match('/^\d{4}-\d{2}-\d{2}$/', $_GET['date']))
    ? $_GET['date'] : gmdate('Y-m-d');   // landing date (UTC), today by default
$initialRotX = isset($_GET['rotX']) && is_numeric($_GET['rotX']) ? floatval($_GET['rotX']) : null;
$initialRotY = isset($_GET['rotY']) && is_numeric($_GET['rotY']) ? floatval($_GET['rotY']) : null;
$initialWeights = [];
if (isset($_GET['w'])) {
    $parts = explode(',', $_GET['w']);
    for ($i = 0; $i < 9; $i++) {
        $initialWeights[$i] = isset($parts[$i]) ? max(0.0, min(1.0, floatval($parts[$i]))) : $kFeatures[$i]['default_w'];
    }
}
?>
<!DOCTYPE html>
<html lang="en" data-body="<?php echo htmlspecialchars($selectedBody); ?>">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Planetary Analog Finder — Two-planet view</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <link rel="stylesheet" href="style.css?v=<?php echo @filemtime(__DIR__ . '/style.css') ?: 1; ?>">
</head>
<body>
    <?php include __DIR__ . '/progress_bar.php'; ?>

    <div class="hud-bg"></div>

    <!-- TOP NAVIGATION BAR -->
    <header class="navbar">
        <div class="nav-left">
            <a href="index.php" class="back-btn">← Back</a>
            <span class="app-title">Planetary Analog Finder</span>
        </div>

        <div class="nav-right">
            <div class="mode-switcher">
                <button class="mode-btn" type="button" onclick="switchToSingleView()">Single</button>
                <button class="mode-btn active" type="button">Two planets</button>
            </div>

            <div class="mode-switcher">
                <button class="mode-btn <?php echo $isMoon ? 'active' : ''; ?>" id="btn-mode-moon" onclick="switchCelestialBody('moon')">
                    Moon
                </button>
                <button class="mode-btn <?php echo !$isMoon ? 'active' : ''; ?>" id="btn-mode-mars" onclick="switchCelestialBody('mars')">
                    Mars
                </button>
            </div>
        </div>
    </header>

    <!-- MAIN WORKSPACE -->
    <main class="workspace workspace-dual" id="dual-workspace">

        <!-- LEFT COLUMN: PARAMETERS AND WEIGHTS -->
        <aside class="hud-panel dual-drawer dual-drawer-left" id="dual-filters-panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>Parameters and weights</span>
                </div>
                <button type="button" class="panel-switch-btn" onclick="toggleDualDrawer('results')">
                    Results →
                </button>
            </div>

            <div class="panel-body">
                <span class="section-label">Landing site</span>
                <button type="button" class="site-picker-btn" id="site-picker-btn" onclick="SitePicker.open()" aria-haspopup="dialog">
                    <span class="site-picker-btn-text">
                        <strong id="site-picker-current">&nbsp;</strong>
                        <span id="site-picker-coords">&nbsp;</span>
                    </span>
                    <span class="site-picker-btn-cta">Change ▾</span>
                </button>

                <span class="section-label">Coordinates</span>
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
                <button type="button" class="center-pin-btn" onclick="centerGlobesOnPins()">Center</button>

                <span class="section-label">Landing date</span>
                <div class="coords-row">
                    <div class="hud-input-group">
                        <label>DATA (UTC)</label>
                        <input type="date" id="input-date" min="1990-01-01" max="2100-12-31" value="<?php echo htmlspecialchars($initialDate); ?>" onchange="triggerCharacterizeAndSearch()">
                    </div>
                </div>

                <span class="section-label">Match weights (0.0 – 1.0)</span>
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
                    <span>Require a nearby cave (&lt; 15 km)</span>
                    <input type="checkbox" id="require-caves" <?php echo $initialCaves ? 'checked' : ''; ?> onchange="triggerSearchOnly()">
                </label>
            </div>

            <div class="dual-match-summary">
                <span>Best analog on Earth</span>
                <strong id="dual-top-match">Loading...</strong>
            </div>

            <div class="panel-footer">
                <button type="button" class="find-analogs-btn" onclick="openResultsPage()">
                    <span>Result details</span>
                    <span>→</span>
                </button>
            </div>
        </aside>

        <!-- RIGHT AREA: TWO PLANETS SIDE BY SIDE, NO FRAMES -->
        <section class="dual-globes-stage">
            <!-- LEFT PLANET: MOON / MARS -->
            <div class="dual-globe-col">
                <div class="globe-hud-overlay">
                    <div class="hud-pill" id="target-globe-pill">
                        <?php echo $isMoon ? 'Moon' : 'Mars'; ?> · click to pick a point
                    </div>
                </div>
                <div class="dual-globe-canvas" id="target-globe-canvas"></div>
            </div>

            <!-- RIGHT PLANET: EARTH WITH ANALOG PINS -->
            <div class="dual-globe-col">
                <div class="globe-hud-overlay">
                    <div class="hud-pill">
                        Earth · analogs found
                    </div>
                </div>
                <div class="dual-globe-canvas" id="earth-globe-canvas"></div>
            </div>
        </section>

        <!-- RIGHT COLUMN: SEARCH RESULTS (SHOWN AFTER SWITCHING) -->
        <aside class="hud-panel dual-drawer dual-drawer-right" id="dual-results-panel">
            <div class="panel-header">
                <button type="button" class="panel-switch-btn" onclick="toggleDualDrawer('filters')">
                    ← Filtry
                </button>
                <div class="panel-title">
                    <span>Search results</span>
                </div>
            </div>

            <div class="panel-body" id="dual-candidates-list">
                <div style="color: var(--text-muted); font-size: 0.78rem; padding: 0.5rem 0;">
                    Loading analogs...
                </div>
            </div>

            <div class="panel-footer">
                <button type="button" class="find-analogs-btn" onclick="openResultsPage()">
                    <span>Result details</span>
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

            // Subtle ring on the planet surface
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

            // Outer halo for the best match
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

            // Slim pin stem pointing perpendicular to the surface (+Z axis)
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

            // 3D pin head
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
        // 1. LEFT SCENE: MOON / MARS (CLICKABLE + ZOOM TO CURSOR)
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
                if (state.isTransitioning) return;
                const rect = container.getBoundingClientRect();
                if (rect.width <= 0 || rect.height <= 0) return;
                renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
                renderer.setSize(rect.width, rect.height);
                camera.aspect = rect.width / rect.height;
                // Fit the FOV so that the sphere (r=1.12) at z=4.3 fills ~95% of the column with some breathing room
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

            // Touch support (1-finger rotate, tap, 2-finger pinch-to-zoom)
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
                if (state.singleTrans) {
                    const tr = state.singleTrans;
                    const elapsed = performance.now() - tr.start;
                    const progress = Math.min(1, elapsed / tr.duration);
                    const eased = 1 - Math.pow(1 - progress, 3);

                    group.position.x = tr.startPosX + (tr.endPosX - tr.startPosX) * eased;
                    group.position.y = tr.startPosY + (tr.endPosY - tr.startPosY) * eased;
                    group.scale.setScalar(tr.startScale + (tr.endScale - tr.startScale) * eased);

                    if (tr.mode === 'out' && elapsed >= tr.reloadAt && !tr.navigated) {
                        tr.navigated = true;
                        try {
                            sessionStorage.setItem('paf_view_transition', JSON.stringify({
                                dir: 'to_single',
                                startEpoch: Date.now() - elapsed,
                                duration: tr.duration,
                                rotX: group.rotation.x,
                                rotY: group.rotation.y
                            }));
                        } catch (e) {}
                        window.location.href = tr.url;
                        return;
                    }

                    if (tr.mode === 'in' && progress >= 1) {
                        if (tr.onFinish) tr.onFinish();
                    }
                } else {
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
                }
                renderer.render(scene, camera);
                requestAnimationFrame(loop);
            }
            loop();

            return state;
        }

        // Initialise the left planet (Moon / Mars)
        const targetGlobe = createGlobeController('target-globe-canvas', {
            initialTexture: getTargetTexture(currentBody),
            onClickPoint: (lat, lon) => {
                document.getElementById('input-lat').value = lat.toFixed(1);
                document.getElementById('input-lon').value = lon.toFixed(1);
                triggerCharacterizeAndSearch();
            }
        });
        const INITIAL_ROT_X = <?php echo json_encode($initialRotX); ?>;
        const INITIAL_ROT_Y = <?php echo json_encode($initialRotY); ?>;
        if (INITIAL_ROT_X !== null && INITIAL_ROT_Y !== null) {
            targetGlobe.group.rotation.x = INITIAL_ROT_X;
            targetGlobe.group.rotation.y = INITIAL_ROT_Y;
        }

        // Pin on the Moon / Mars
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

        // Initialise the right planet (Earth)
        const earthGlobe = createGlobeController('earth-globe-canvas', {
            initialTexture: earthPhotoTexture
        });
        const earthPinsGroup = new THREE.Group();
        earthGlobe.group.add(earthPinsGroup);
        earthGlobe.onPinScale = (s) => {
            earthPinsGroup.children.forEach(pin => pin.scale.setScalar(s));
        };

        // =========================================================================
        // 2. API + AUTOMATIC UPDATE OF THE PINS ON EARTH
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
                summaryEl.innerText = 'No results for the cave filter';
            }

            renderDualCandidatesList();
        }

        function renderDualCandidatesList() {
            const listEl = document.getElementById('dual-candidates-list');
            if (!listEl) return;

            if (currentCandidates.length === 0) {
                listEl.innerHTML = `<div style="color: var(--text-muted); font-size: 0.78rem; padding: 0.75rem 0;">No locations meet the cave filter.</div>`;
                return;
            }

            listEl.innerHTML = currentCandidates.map((c, idx) => {
                const isSel = (idx === selectedCandidateIndex);
                const caveText = c.nearest_skylight_km !== null
                    ? `Cave: ${c.nearest_skylight_km} km`
                    : 'No caves';
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
                top_k: 100,
                include_maps: false   // the pages draw pins only; skip the unused heatmap/error-map images
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
                `${body === 'moon' ? 'Moon' : 'Mars'} · click to pick a point`;

            const pList = PRESETS[body];

            document.getElementById('input-lat').value = pList[0].lat;
            document.getElementById('input-lon').value = pList[0].lon;

            markerRingMat.color.setHex(body === 'moon' ? 0x60a5fa : 0xf97316);
            targetGlobe.sphereMat.map = getTargetTexture(body);
            targetGlobe.sphereMat.needsUpdate = true;

            triggerCharacterizeAndSearch();
        }


        // Landing date from #input-date -> timestamp_iso for /api/v1/characterize (noon UTC that day).
        // Conditions on Mars / the Moon (season Ls, dust, temperatures, Sun position) depend on this date.
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
            if (targetGlobe.isTransitioning) return;
            const rotParams = `&rotX=${targetGlobe.group.rotation.x.toFixed(4)}&rotY=${targetGlobe.group.rotation.y.toFixed(4)}`;
            const targetUrl = `explorer.php?${buildQuery()}${rotParams}`;

            if (window.innerWidth <= 1024) {
                window.location.href = targetUrl;
                return;
            }

            const prefetch = document.createElement('link');
            prefetch.rel = 'prefetch';
            prefetch.href = targetUrl;
            document.head.appendChild(prefetch);

            // Update the active button in the navigation bar
            const modeBtns = document.querySelectorAll('.nav-right .mode-switcher:first-child .mode-btn');
            if (modeBtns.length >= 2) {
                modeBtns[0].classList.add('active');
                modeBtns[1].classList.remove('active');
            }

            const navbar = document.querySelector('.navbar');
            const workspace = document.getElementById('dual-workspace');
            const leftDrawer = document.getElementById('dual-filters-panel');
            const resultsDrawer = document.getElementById('dual-results-panel');
            const cols = document.querySelectorAll('.dual-globe-col');
            const targetCol = cols[0];
            const earthCol = cols[1];
            const hudPills = document.querySelectorAll('.dual-globe-col .globe-hud-overlay');

            const navH = navbar ? navbar.getBoundingClientRect().height : 0;
            const winW = window.innerWidth;
            const winH = window.innerHeight;
            const vpH = winH - navH;

            // Current position and size of the left planet on screen
            const rect = targetGlobe.container.getBoundingClientRect();
            const cam = targetGlobe.camera;
            const curVFov = (cam.fov * Math.PI) / 180;
            const startWorldPerPx = (2 * cam.position.z * Math.tan(curVFov / 2)) / rect.height;
            const startRadiusPx = 1.12 / startWorldPerPx;
            const startCenterX = rect.left + rect.width / 2 - (cam.position.x / startWorldPerPx);
            const startCenterY = rect.top + rect.height / 2 + (cam.position.y / startWorldPerPx);

            // Exact target geometry of the single planet in explorer.php
            const vpSingleW = winW - 418;
            const vpSingleH = Math.max(200, winH - navH - 182);
            const endCenterX = 402 + vpSingleW / 2;
            const endCenterY = navH + 16 + vpSingleH / 2;
            const singleVFov = (42 * Math.PI) / 180;
            const endWorldPerPx = (2 * 3.45 * Math.tan(singleVFov / 2)) / vpSingleH;
            const endRadiusPx = 1.12 / endWorldPerPx;

            // Freeze the left panel's current position before animating to the explorer.php layout
            const showingResults = workspace.classList.contains('show-results');
            if (leftDrawer) {
                const lr = leftDrawer.getBoundingClientRect();
                leftDrawer.style.position = 'fixed';
                leftDrawer.style.top = `${lr.top}px`;
                leftDrawer.style.left = `${showingResults ? -lr.width - 24 : lr.left}px`;
                leftDrawer.style.width = `${lr.width}px`;
                leftDrawer.style.height = `${lr.height}px`;
                leftDrawer.style.bottom = 'auto';
                leftDrawer.style.transform = 'none';
                leftDrawer.style.opacity = showingResults ? '0' : '1';
                leftDrawer.style.zIndex = '25';
            }
            if (resultsDrawer && showingResults) {
                const rr = resultsDrawer.getBoundingClientRect();
                resultsDrawer.style.position = 'fixed';
                resultsDrawer.style.top = `${rr.top}px`;
                resultsDrawer.style.left = `${rr.left}px`;
                resultsDrawer.style.width = `${rr.width}px`;
                resultsDrawer.style.height = `${rr.height}px`;
                resultsDrawer.style.right = 'auto';
                resultsDrawer.style.bottom = 'auto';
                resultsDrawer.style.transform = 'none';
                resultsDrawer.style.zIndex = '24';
            }
            if (navbar) navbar.style.zIndex = '30';

            // Expand the left planet's canvas to the whole area under the navbar without a jump in frame 0
            targetGlobe.isTransitioning = true;
            if (targetCol) targetCol.style.overflow = 'visible';
            const canvasBox = targetGlobe.container;
            canvasBox.style.position = 'fixed';
            canvasBox.style.top = `${navH}px`;
            canvasBox.style.left = '0';
            canvasBox.style.width = `${winW}px`;
            canvasBox.style.height = `${vpH}px`;
            canvasBox.style.zIndex = '5';

            targetGlobe.renderer.setSize(winW, vpH);
            cam.fov = 42;
            cam.aspect = winW / vpH;
            cam.position.set(0, 0, 3.45);
            cam.updateProjectionMatrix();

            const newWorldPerPx = (2 * 3.45 * Math.tan(singleVFov / 2)) / vpH;
            const vpCenterY = navH + vpH / 2;

            const startPosX = (startCenterX - winW / 2) * newWorldPerPx;
            const startPosY = -(startCenterY - vpCenterY) * newWorldPerPx;
            const startScale = (startRadiusPx * newWorldPerPx) / 1.12;

            const endPosX = (endCenterX - winW / 2) * newWorldPerPx;
            const endPosY = -(endCenterY - vpCenterY) * newWorldPerPx;
            const endScale = (endRadiusPx * newWorldPerPx) / 1.12;

            targetGlobe.group.position.set(startPosX, startPosY, 0);
            targetGlobe.group.scale.setScalar(startScale);

            targetGlobe.singleTrans = {
                mode: 'out',
                start: performance.now(),
                duration: 720,
                reloadAt: 220,
                navigated: false,
                startPosX, startPosY, startScale,
                endPosX, endPosY, endScale,
                url: targetUrl
            };

            requestAnimationFrame(() => {
                const panelEase = 'all 0.72s cubic-bezier(0.22, 1, 0.36, 1)';
                if (leftDrawer) {
                    leftDrawer.style.transition = panelEase;
                    leftDrawer.style.left = '16px';
                    leftDrawer.style.top = `${navH + 16}px`;
                    leftDrawer.style.width = '370px';
                    leftDrawer.style.height = `${winH - navH - 32}px`;
                    leftDrawer.style.opacity = '1';
                }
                if (resultsDrawer && showingResults) {
                    resultsDrawer.style.transition = 'transform 0.45s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.35s ease';
                    resultsDrawer.style.transform = 'translateX(110%)';
                    resultsDrawer.style.opacity = '0';
                }
                if (earthCol) {
                    earthCol.style.transition = 'transform 0.56s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.42s ease';
                    earthCol.style.transform = 'translateX(48%) scale(0.92)';
                    earthCol.style.opacity = '0';
                }
                hudPills.forEach(pill => {
                    pill.style.transition = 'opacity 0.25s ease';
                    pill.style.opacity = '0';
                });
            });
        }

        (function initEnterDualTransition() {
            let raw = null;
            try {
                raw = sessionStorage.getItem('paf_view_transition');
                if (raw) sessionStorage.removeItem('paf_view_transition');
            } catch (e) {}
            if (!raw || window.innerWidth <= 1024) return;

            let data = null;
            try { data = JSON.parse(raw); } catch (e) {}
            if (!data || data.dir !== 'to_dual') return;

            const elapsed = Math.max(0, Date.now() - (data.startEpoch || Date.now()));
            if (elapsed > 2200) return;

            if (typeof data.rotX === 'number' && typeof data.rotY === 'number') {
                targetGlobe.group.rotation.x = data.rotX;
                targetGlobe.group.rotation.y = data.rotY;
            }

            const progress0 = Math.min(0.75, elapsed / (data.duration || 720));
            const eased0 = 1 - Math.pow(1 - progress0, 3);
            const remaining = Math.max(300, (data.duration || 720) - elapsed);

            const navbar = document.querySelector('.navbar');
            const leftDrawer = document.getElementById('dual-filters-panel');
            const cols = document.querySelectorAll('.dual-globe-col');
            const targetCol = cols[0];
            const earthCol = cols[1];
            const hudPills = document.querySelectorAll('.dual-globe-col .globe-hud-overlay');

            const navH = navbar ? navbar.getBoundingClientRect().height : 0;
            const winW = window.innerWidth;
            const winH = window.innerHeight;
            const vpH = winH - navH;

            const dualDrawerW = Math.min(310, Math.max(270, winW * 0.19));
            const gap = Math.min(48, Math.max(24, winW * 0.028));
            const colW = (winW - dualDrawerW - 44 - gap) / 2;
            const colH = winH - navH - 16;
            const dualCenterX = dualDrawerW + 24 + colW / 2;
            const dualCenterY = navH + 8 + colH / 2;
            const hHalfDual = 1.22 / Math.min(1, colW / colH);
            const dualRadiusPx = (1.12 / hHalfDual) * (colH / 2);

            const vpSingleW = winW - 418;
            const vpSingleH = Math.max(200, winH - navH - 182);
            const singleCenterX = 402 + vpSingleW / 2;
            const singleCenterY = navH + 16 + vpSingleH / 2;
            const vFov = (42 * Math.PI) / 180;
            const singleWorldPerPx = (2 * 3.45 * Math.tan(vFov / 2)) / vpSingleH;
            const singleRadiusPx = 1.12 / singleWorldPerPx;

            const startCenterX = singleCenterX + (dualCenterX - singleCenterX) * eased0;
            const startCenterY = singleCenterY + (dualCenterY - singleCenterY) * eased0;
            const startRadiusPx = singleRadiusPx + (dualRadiusPx - singleRadiusPx) * eased0;

            if (leftDrawer) {
                const curL = 16 + (8 - 16) * eased0;
                const curT = (navH + 16) + ((navH + 8) - (navH + 16)) * eased0;
                const curW = 370 + (dualDrawerW - 370) * eased0;
                const curH = (winH - navH - 32) + ((winH - navH - 16) - (winH - navH - 32)) * eased0;
                leftDrawer.style.position = 'fixed';
                leftDrawer.style.left = `${curL}px`;
                leftDrawer.style.top = `${curT}px`;
                leftDrawer.style.width = `${curW}px`;
                leftDrawer.style.height = `${curH}px`;
                leftDrawer.style.bottom = 'auto';
                leftDrawer.style.transform = 'none';
                leftDrawer.style.zIndex = '25';
            }
            if (earthCol) {
                const startTx = 42 * (1 - eased0);
                earthCol.style.transition = 'none';
                earthCol.style.transform = `translateX(${startTx}%) scale(${0.92 + 0.08 * eased0})`;
                earthCol.style.opacity = `${Math.min(1, 0.25 + eased0 * 0.75)}`;
            }
            hudPills.forEach(pill => {
                pill.style.opacity = '0';
            });
            if (navbar) navbar.style.zIndex = '30';

            targetGlobe.isTransitioning = true;
            if (targetCol) targetCol.style.overflow = 'visible';
            const canvasBox = targetGlobe.container;
            canvasBox.style.position = 'fixed';
            canvasBox.style.top = `${navH}px`;
            canvasBox.style.left = '0';
            canvasBox.style.width = `${winW}px`;
            canvasBox.style.height = `${vpH}px`;
            canvasBox.style.zIndex = '5';

            const cam = targetGlobe.camera;
            targetGlobe.renderer.setSize(winW, vpH);
            cam.fov = 42;
            cam.aspect = winW / vpH;
            cam.position.set(0, 0, 4.3);
            cam.updateProjectionMatrix();

            const newWorldPerPx = (2 * 4.3 * Math.tan(vFov / 2)) / vpH;
            const vpCenterY = navH + vpH / 2;

            const startPosX = (startCenterX - winW / 2) * newWorldPerPx;
            const startPosY = -(startCenterY - vpCenterY) * newWorldPerPx;
            const startScale = (startRadiusPx * newWorldPerPx) / 1.12;

            const endPosX = (dualCenterX - winW / 2) * newWorldPerPx;
            const endPosY = -(dualCenterY - vpCenterY) * newWorldPerPx;
            const endScale = (dualRadiusPx * newWorldPerPx) / 1.12;

            targetGlobe.group.position.set(startPosX, startPosY, 0);
            targetGlobe.group.scale.setScalar(startScale);

            targetGlobe.singleTrans = {
                mode: 'in',
                start: performance.now(),
                duration: remaining,
                startPosX, startPosY, startScale,
                endPosX, endPosY, endScale,
                onFinish: () => {
                    targetGlobe.singleTrans = null;
                    targetGlobe.isTransitioning = false;
                    if (targetCol) targetCol.style.overflow = '';
                    canvasBox.style.position = '';
                    canvasBox.style.top = '';
                    canvasBox.style.left = '';
                    canvasBox.style.width = '';
                    canvasBox.style.height = '';
                    canvasBox.style.zIndex = '';
                    targetGlobe.group.position.set(0, 0, 0);
                    targetGlobe.group.scale.setScalar(1);
                    targetGlobe.resize();
                    if (leftDrawer) {
                        leftDrawer.style.position = '';
                        leftDrawer.style.left = '';
                        leftDrawer.style.top = '';
                        leftDrawer.style.width = '';
                        leftDrawer.style.height = '';
                        leftDrawer.style.bottom = '';
                        leftDrawer.style.transform = '';
                        leftDrawer.style.zIndex = '';
                        leftDrawer.style.transition = '';
                    }
                    if (earthCol) {
                        earthCol.style.transition = '';
                        earthCol.style.transform = '';
                        earthCol.style.opacity = '';
                    }
                    hudPills.forEach(pill => {
                        pill.style.transition = '';
                        pill.style.opacity = '';
                    });
                }
            };

            requestAnimationFrame(() => {
                const easeStr = `all ${remaining}ms cubic-bezier(0.22, 1, 0.36, 1)`;
                if (leftDrawer) {
                    leftDrawer.style.transition = easeStr;
                    leftDrawer.style.left = '8px';
                    leftDrawer.style.top = `${navH + 8}px`;
                    leftDrawer.style.width = `${dualDrawerW}px`;
                    leftDrawer.style.height = `${winH - navH - 16}px`;
                }
                if (earthCol) {
                    earthCol.style.transition = `transform ${remaining}ms cubic-bezier(0.22, 1, 0.36, 1), opacity ${Math.round(remaining * 0.8)}ms ease`;
                    earthCol.style.transform = 'translateX(0) scale(1)';
                    earthCol.style.opacity = '1';
                }
                hudPills.forEach(pill => {
                    pill.style.transition = `opacity ${Math.round(remaining * 0.6)}ms ease ${Math.round(remaining * 0.35)}ms`;
                    pill.style.opacity = '1';
                });
            });
        })();

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
