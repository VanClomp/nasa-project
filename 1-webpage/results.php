<?php
/**
 * results.php - Results page of the Earth analog search
 * Opened from explorer.php with the "Find analogs on Earth" button
 */
$selectedBody = strtolower($_GET['body'] ?? 'moon');
if (!in_array($selectedBody, ['moon', 'mars'])) {
    $selectedBody = 'moon';
}

$lat = isset($_GET['lat']) ? floatval($_GET['lat']) : -89.9;
$lon = isset($_GET['lon']) ? floatval($_GET['lon']) : 0.0;
$caves = (isset($_GET['caves']) && $_GET['caves'] === '1');
$date = (isset($_GET['date']) && preg_match('/^\d{4}-\d{2}-\d{2}$/', $_GET['date']))
    ? $_GET['date'] : gmdate('Y-m-d');   // landing date (UTC)

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
<html lang="en" data-body="<?php echo htmlspecialchars($selectedBody); ?>">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Earth Analog Results // Planetary Analog Finder (<?php echo strtoupper($selectedBody); ?>)</title>
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

    <!-- TOP NAVIGATION BAR -->
    <header class="navbar">
        <div class="nav-left">
            <a href="explorer.php?<?php echo htmlspecialchars($backQuery); ?>" class="back-btn" id="btn-back-config" onclick="return returnToConfig(event);">← Setup</a>
            <a href="index.php" class="back-btn">Change planet</a>
            <span class="app-title">Analysis results</span>
        </div>

        <div class="nav-telemetry">
            <span id="api-latency">-- ms</span>
            <span class="cpp-badge" id="target-summary-badge">
                <?php echo $selectedBody === 'moon' ? 'Moon' : 'Mars'; ?> · <?php echo number_format($lat, 1); ?>°, <?php echo number_format($lon, 1); ?>°
            </span>
        </div>
    </header>

    <!-- MAIN WORKSPACE (2 COLUMNS: EARTH GLOBE + RANKING & CHARTS) -->
    <main class="workspace workspace-results">

        <!-- LEFT / MAIN COLUMN: EARTH GLOBE WITH HEATMAP AND PINS + TARGET SUMMARY -->
        <section class="center-stage">
            <div class="globe-viewport">
                <div class="globe-hud-overlay">
                    <div class="hud-pill">
                        Earth — match map
                    </div>
                    <div class="hud-pill">
                        Best period: <strong style="color:var(--emerald);" id="best-month-badge">--</strong>
                    </div>
                </div>
                <div id="main-globe-canvas"></div>
            </div>

            <div class="target-readout-bar">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="section-label" style="margin:0;">
                        Target profile · <?php echo $selectedBody === 'moon' ? 'Moon' : 'Mars'; ?> (<?php echo number_format($lat, 1); ?>°, <?php echo number_format($lon, 1); ?>°) · <?php echo htmlspecialchars($date); ?><span id="readout-season"></span>
                    </span>
                    <div class="readout-meta">
                        <span class="model-badge" id="model-badge" title="Data source">Model: --</span>
                        <span style="font-family:'JetBrains Mono'; font-size:0.68rem; color:var(--text-muted);" id="readout-skylight">
                            Nearest cave: -- km
                        </span>
                    </div>
                </div>
                <div class="readout-grid">
                    <div class="readout-box"><span>MEAN TEMP.</span><strong id="raw-temp_mean">-- °C</strong></div>
                    <div class="readout-box"><span>DIURNAL RANGE</span><strong id="raw-temp_diurnal_amp">-- °C</strong></div>
                    <div class="readout-box"><span>THERMAL INERTIA</span><strong id="raw-thermal_inertia">-- TIU</strong></div>
                    <div class="readout-box"><span>SAR ROUGHNESS</span><strong id="raw-surface_roughness">--</strong></div>
                    <div class="readout-box"><span>ICE / MOISTURE</span><strong id="raw-soil_moisture">-- %</strong></div>
                    <div class="readout-box"><span>DUST (AOD)</span><strong id="raw-dust_aerosol">--</strong></div>
                    <div class="readout-box"><span>MAX. SUN ELEVATION</span><strong id="raw-solar_elevation_max">-- °</strong></div>
                    <div class="readout-box"><span>RADIATION</span><strong id="raw-radiation_proxy">--</strong></div>
                    <div class="readout-box"><span>TERRAIN SLOPE</span><strong id="raw-slope_deg">-- °</strong></div>
                    <div class="readout-box"><span>CAVE FILTER</span><strong style="color:var(--emerald);"><?php echo $caves ? 'YES (&lt;15km)' : 'NO'; ?></strong></div>
                </div>
            </div>
        </section>

        <!-- RIGHT COLUMN: RANKING OF EARTH ANALOGS + COMPARISON CHARTS -->
        <aside class="hud-panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>Best analogs on Earth</span>
                </div>
                <span style="font-family:'JetBrains Mono'; font-size:0.68rem; color:var(--emerald);" id="candidates-count">Loading...</span>
            </div>

            <div class="panel-body">
                <div id="candidates-list"></div>

                <div class="charts-box">
                    <span class="section-label">Feature profile comparison</span>
                    <div class="chart-wrap">
                        <canvas id="radar-chart" height="190"></canvas>
                    </div>

                    <span class="section-label">12-month climatogram</span>
                    <div class="chart-wrap">
                        <canvas id="climatogram-chart" height="155"></canvas>
                    </div>

                    <!-- p(t): parameters of the chosen site that change with the date (extra.series from 3-charakteryzator) -->
                    <div id="time-charts" class="time-charts" hidden>
                        <span class="section-label">Chosen site · parameters that change over time</span>
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
        const MONTH_NAMES = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

        let currentTargetProfile = null;
        let currentCandidates = [];
        let selectedCandidateIndex = 0;

        // =========================================================================
        // 1. THREE.JS 3D SCENE — EARTH GLOBE WITH HEATMAP AND PINS
        // =========================================================================
        const globeContainer = document.getElementById('main-globe-canvas');
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
        camera.position.z = 1.95; // Smooth zoom-out at start (arrival effect)

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

            // Subtle ring on the planet surface
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

            // Slim pin stem pointing perpendicular to the surface (+Z axis)
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

            // 3D pin head
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
        let isReturning = false;
        let retStart = 0;
        let retStartCamX = 0;
        let retStartCamY = 0;
        let retStartZ = 3.1;
        let retStartPosX = 0;
        let retStartPosY = 0;
        let retUrl = '';

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

        // Touch support for the Earth (1-finger rotate, 2-finger pinch-to-zoom)
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

        function easeInOutQuart(t) {
            return t < 0.5 ? 8 * t * t * t * t : 1 - Math.pow(-2 * t + 2, 4) / 2;
        }

        function returnToConfig(e) {
            if (e && (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0)) {
                return true;
            }
            if (e) e.preventDefault();
            if (isReturning) return false;

            const btn = document.getElementById('btn-back-config');
            retUrl = btn ? btn.href : 'explorer.php';

            const prefetch = document.createElement('link');
            prefetch.rel = 'prefetch';
            prefetch.href = retUrl;
            document.head.appendChild(prefetch);

            const viewport = document.querySelector('.globe-viewport');
            const rect = viewport.getBoundingClientRect();
            const winW = window.innerWidth;
            const winH = window.innerHeight;

            retStart = performance.now();
            retStartCamX = camera.position.x;
            retStartCamY = camera.position.y;
            retStartZ = camera.position.z * (winH / rect.height);

            const dxPx = (rect.left + rect.width / 2) - (winW / 2);
            const dyPx = -((rect.top + rect.height / 2) - (winH / 2));
            const vFov = (camera.fov * Math.PI) / 180;
            const worldPerPx = (2 * retStartZ * Math.tan(vFov / 2)) / winH;

            retStartPosX = dxPx * worldPerPx;
            retStartPosY = dyPx * worldPerPx;
            camera.position.z = retStartZ;
            globeGroup.position.set(retStartPosX, retStartPosY, 0);

            const navbar = document.querySelector('.navbar');
            const rightPanel = document.querySelector('aside.hud-panel');
            const bottomBar = document.querySelector('.target-readout-bar');
            const hudOverlay = document.querySelector('.globe-hud-overlay');

            [rightPanel, bottomBar].forEach(el => {
                if (!el) return;
                const r = el.getBoundingClientRect();
                el.style.position = 'fixed';
                el.style.top = `${r.top}px`;
                el.style.left = `${r.left}px`;
                el.style.width = `${r.width}px`;
                el.style.height = `${r.height}px`;
                el.style.zIndex = '25';
            });
            if (navbar) navbar.style.zIndex = '30';

            viewport.style.position = 'fixed';
            viewport.style.inset = '0';
            viewport.style.width = '100vw';
            viewport.style.height = '100vh';
            viewport.style.zIndex = '5';
            resizeGlobe();

            isReturning = true;

            requestAnimationFrame(() => {
                const ease = 'transform 0.72s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.55s ease';
                if (navbar) {
                    navbar.style.transition = ease;
                    navbar.style.transform = 'translateY(-110%)';
                    navbar.style.opacity = '0';
                    navbar.style.pointerEvents = 'none';
                }
                if (bottomBar) {
                    bottomBar.style.transition = ease;
                    bottomBar.style.transform = 'translateY(140%)';
                    bottomBar.style.opacity = '0';
                    bottomBar.style.pointerEvents = 'none';
                }
                if (rightPanel) {
                    rightPanel.style.transition = ease;
                    rightPanel.style.transform = 'translateX(110%)';
                    rightPanel.style.opacity = '0';
                    rightPanel.style.pointerEvents = 'none';
                }
                if (hudOverlay) {
                    hudOverlay.style.transition = ease;
                    hudOverlay.style.transform = 'translateY(-20px)';
                    hudOverlay.style.opacity = '0';
                    hudOverlay.style.pointerEvents = 'none';
                }
            });

            return false;
        }

        function animateScene(now) {
            if (isReturning) {
                const elapsed = now - retStart;
                const progress = Math.min(1, elapsed / 1050);
                const eased = easeInOutQuart(progress);

                camera.position.x = retStartCamX * (1 - eased);
                camera.position.y = retStartCamY * (1 - eased);
                camera.position.z = retStartZ + (1.16 - retStartZ) * eased;
                globeGroup.position.x = retStartPosX * (1 - eased);
                globeGroup.position.y = retStartPosY * (1 - eased);
                globeGroup.rotation.y += 0.0006 * (1 - eased);

                if (progress > 0.88) {
                    document.body.style.transition = 'opacity 0.14s ease';
                    document.body.style.opacity = '0';
                }
                if (progress >= 1) {
                    try {
                        sessionStorage.setItem('paf_view_transition', JSON.stringify({
                            dir: 'from_results',
                            startEpoch: Date.now()
                        }));
                    } catch (e) {}
                    window.location.href = retUrl;
                    return;
                }
            } else {
                if (!isDragging) {
                    const tNow = performance.now();
                    if (tNow >= pauseAutoRotateUntil) {
                        const resumeFactor = Math.min(1, (tNow - pauseAutoRotateUntil) / 800);
                        globeGroup.rotation.y += 0.0012 * resumeFactor;
                    }
                }
                camera.position.x += (targetCamX - camera.position.x) * 0.065;
                camera.position.y += (targetCamY - camera.position.y) * 0.065;
                camera.position.z += (targetCamZ - camera.position.z) * 0.065;
            }

            const pinScale = Math.max(0.24, (camera.position.z - 1.05) / 2.05);
            pinsGroup.children.forEach(pin => pin.scale.setScalar(pinScale));

            renderer.render(scene, camera);
            requestAnimationFrame(animateScene);
        }
        requestAnimationFrame(animateScene);

        (function initResultsEnterAnimation() {
            if (window.innerWidth <= 1024) return;

            const navbar = document.querySelector('.navbar');
            const rightPanel = document.querySelector('aside.hud-panel');
            const bottomBar = document.querySelector('.target-readout-bar');
            const hudOverlay = document.querySelector('.globe-hud-overlay');

            document.body.style.opacity = '0';
            if (navbar) {
                navbar.style.transform = 'translateY(-100%)';
                navbar.style.opacity = '0';
            }
            if (rightPanel) {
                rightPanel.style.transform = 'translateX(110%)';
                rightPanel.style.opacity = '0';
            }
            if (bottomBar) {
                bottomBar.style.transform = 'translateY(125%)';
                bottomBar.style.opacity = '0';
            }
            if (hudOverlay) {
                hudOverlay.style.transform = 'translateY(-16px)';
                hudOverlay.style.opacity = '0';
            }

            requestAnimationFrame(() => {
                document.body.style.transition = 'opacity 0.25s ease';
                document.body.style.opacity = '1';

                const navEase = 'transform 0.6s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.45s ease';
                const panelEase = 'transform 0.68s cubic-bezier(0.22, 1, 0.36, 1) 0.06s, opacity 0.5s ease 0.06s';

                if (navbar) {
                    navbar.style.transition = navEase;
                    navbar.style.transform = 'translate(0, 0)';
                    navbar.style.opacity = '1';
                }
                if (hudOverlay) {
                    hudOverlay.style.transition = navEase;
                    hudOverlay.style.transform = 'translate(0, 0)';
                    hudOverlay.style.opacity = '1';
                }
                [rightPanel, bottomBar].forEach(el => {
                    if (!el) return;
                    el.style.transition = panelEase;
                    el.style.transform = 'translate(0, 0)';
                    el.style.opacity = '1';
                });

                setTimeout(() => {
                    if (isReturning) return;
                    document.body.style.transition = '';
                    document.body.style.opacity = '';
                    [navbar, rightPanel, bottomBar, hudOverlay].forEach(el => {
                        if (!el) return;
                        el.style.transition = '';
                        el.style.transform = '';
                        el.style.opacity = '';
                    });
                }, 780);
            });
        })();

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
                // Fall back to the PHP mock
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


        // Season for the chosen date (extra.season from 3-charakteryzator)
        function renderSeason(profile) {
            const el = document.getElementById('readout-season');
            if (!el) return;
            const s = (profile && profile.extra && profile.extra.season) || null;
            if (s && s.ls !== undefined) {
                el.innerText = ` · Ls ${Number(s.ls).toFixed(0)}° (Mars year ${s.mars_year})`;
            } else if (s && s.local_lunar_hour !== undefined) {
                el.innerText = ` · lunar hour ${Number(s.local_lunar_hour).toFixed(1)}`;
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
                `Nearest cave: ${profile.nearest_skylight_km} km`;
            renderModelBadge(profile);
            renderSeason(profile);
            renderFeatureFlags(profile);
        }

        // extra.model from 3-charakteryzator: "local" = station data for this date (Mars), "orbital" = orbital measurements
        // at this point (Moon), "global" = global model (uncertain). Missing field (e.g. the PHP mock) = global.
        const MODEL_LABELS = {
            local:   'Local model · station data',
            orbital: 'Orbital measurements · this point',
            global:  'Global model · uncertain'
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

        // For every parameter: where the value at THIS place comes from (extra.features_measured) and whether it changes
        // with the landing date (extra.features_time_varying). Parameter docs: 3-charakteryzator/PARAMETERS.md.
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
                    src = '<i class="feat-src none" title="No data for this place">no data</i>';
                } else if (meas[i] === true) {
                    src = '<i class="feat-src local" title="Measured at this place (station, orbital map at this pixel or exact geometry)">measured</i>';
                } else {
                    src = '<i class="feat-src global" title="Predicted by the global model (latitude, elevation, maps) - uncertain">model</i>';
                }
                const time = tv[i] === true
                    ? '<i class="feat-time varies" title="Changes with the landing date (season, Sun position, dust season)">◷ by date</i>'
                    : (tv[i] === false ? '<i class="feat-time fixed" title="Fixed property of the place, does not depend on the date">fixed</i>' : '');
                flags.innerHTML = src + time;
            });
        }

        function renderCandidatesList() {
            const container = document.getElementById('candidates-list');
            document.getElementById('candidates-count').innerText = `${currentCandidates.length} RESULTS`;

            if (currentCandidates.length === 0) {
                container.innerHTML = '<p style="color:var(--text-muted); font-size:0.82rem;">No locations meet the chosen criteria (try turning off the cave filter).</p>';
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
                            <span>MONTH: ${mName}</span>
                            <span>CAVE: ${c.nearest_cave_km} km</span>
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
                    labels: ['Temp', 'Range', 'Inertia', 'Roughness', 'Ice/Water', 'Dust AOD', 'Sun angle', 'Radiation', 'Slope'],
                    datasets: [
                        {
                            label: 'Target (Moon/Mars)',
                            data: [0,0,0,0,0,0,0,0,0],
                            borderColor: '#60A5FA',
                            backgroundColor: 'rgba(96, 165, 250, 0.16)',
                            borderWidth: 2
                        },
                        {
                            label: 'Earth analog',
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
                            label: 'Mean temp. (°C)',
                            data: [],
                            borderColor: '#F97316',
                            backgroundColor: 'rgba(249, 115, 22, 0.15)',
                            tension: 0.35,
                            fill: true
                        },
                        {
                            label: 'Moisture (%)',
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

        // ---- p(t): charts of the time-varying parameters of the chosen site ----
        const TIME_LABELS = {
            temp_mean:           ['Mean ground temperature', '°C'],
            temp_diurnal_amp:    ['Diurnal temperature range', 'K'],
            dust_aerosol:        ['Atmospheric dust (AOD)', ''],
            solar_elevation_max: ['Max. noon Sun elevation', '°'],
            radiation_proxy:     ['Atmospheric shielding (column mass)', 'g/cm²']
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
                ? `Time axis: the 12 Mars months of the landing year, labelled with the Earth month in which each begins (a Mars month lasts about 1.5–2 Earth months). Highlighted point = landing date ${SEARCH_PARAMS.date}.`
                : `Time axis: the 15th of each month of ${SEARCH_PARAMS.date.slice(0, 4)}. Highlighted point = landing month.`;
            const meas = profile.extra.features_measured || [];
            const order = ['temp_mean', 'temp_diurnal_amp', 'thermal_inertia', 'surface_roughness', 'soil_moisture',
                           'dust_aerosol', 'solar_elevation_max', 'radiation_proxy', 'slope_deg'];
            Object.entries(s.values).forEach(([key, values]) => {
                const [label, unit] = TIME_LABELS[key] || [key, ''];
                const measured = meas[order.indexOf(key)] === true;
                const block = document.createElement('div');
                block.className = 'time-chart';
                block.innerHTML = `<h4 class="time-chart-title">${label} – change over time</h4>
                    <span class="time-chart-meta">${unit ? unit + ' · ' : ''}${measured ? 'measured at this place' : 'global model'}</span>
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
                                label: c => `${c.formattedValue}${unit ? ' ' + unit : ''}${c.dataIndex === cur ? ' (landing date)' : ''}` } }
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
            loadTimeCharts();      // separate request: results appear without waiting for the charts

            const searchRes = await callApi('search', {
                features_norm: profile.features_norm,
                weights: SEARCH_PARAMS.weights,
                require_caves: SEARCH_PARAMS.require_caves,
                top_k: 100,
                include_maps: false   // the pages draw pins only; skip the unused heatmap/error-map images
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
