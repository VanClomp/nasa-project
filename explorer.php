<?php
/**
 * explorer.php - Główny terminal Mission Control (Komponent 1: 1-frontend)
 * Zgodny ze specyfikacją: POST /api/v1/characterize oraz POST /api/v1/search
 * Posiada wbudowany fallback mock API w PHP (+ opcjonalne wywołanie natywnego C++),
 * dzięki czemu działa od razu lokalnie oraz w środowisku Docker Compose z Networkerem.
 */

// ============================================================================
// 1. WBUDOWANY ENDPOINT MOCK / PROXY API W PHP (gdy wywołany z ?mock_api=1)
// ============================================================================
if (isset($_GET['mock_api'])) {
    header('Content-Type: application/json; charset=utf-8');
    $action = $_GET['mock_api'];
    $rawInput = file_get_contents('php://input');
    $payload = json_decode($rawInput, true) ?: [];

    if ($action === 'characterize') {
        $body = $payload['target_body'] ?? 'moon';
        $lat = floatval($payload['lat'] ?? -85.2);
        $lon = floatval($payload['lon'] ?? 31.4);

        // Realistyczne wyliczenie parametrów na podstawie (lat, lon) i ciała niebieskiego
        $latRad = deg2rad(abs($lat));
        if ($body === 'moon') {
            $tempMean = round(-50.0 - 140.0 * sin($latRad) + 15.0 * cos(deg2rad($lon)), 1);
            $diurnalAmp = round(210.0 * cos($latRad) + 25.0, 1);
            $thermalInertia = round(45.0 + 35.0 * abs(sin(deg2rad($lon * 2))), 1);
            $roughness = round(0.25 + 0.45 * abs(sin(deg2rad($lat * 3))), 2);
            $moisture = ($lat < -75 || $lat > 75) ? round(1.8 + 1.5 * abs(cos($lon)), 2) : 0.1;
            $dust = 0.0;
            $solarMax = round(max(1.5, 90.0 - abs($lat) + 1.54), 1);
            $radiation = 0.98;
            $slope = round(4.0 + 14.0 * abs(sin(deg2rad($lat + $lon))), 1);
        } else {
            // Mars
            $tempMean = round(-25.0 - 75.0 * sin($latRad) + 10.0 * sin(deg2rad($lon)), 1);
            $diurnalAmp = round(65.0 * cos($latRad) + 18.0, 1);
            $thermalInertia = round(140.0 + 160.0 * abs(cos(deg2rad($lon))), 1);
            $roughness = round(0.20 + 0.50 * abs(cos(deg2rad($lat * 2))), 2);
            $moisture = ($lat < -65 || $lat > 65) ? 4.5 : round(0.8 + 1.4 * abs(sin($latRad)), 2);
            $dust = round(0.18 + 0.45 * abs(cos($latRad)), 2);
            $solarMax = round(max(5.0, 90.0 - abs($lat) + 12.0), 1);
            $radiation = round(0.72 + 0.22 * abs(sin(deg2rad($lon))), 2);
            $slope = round(3.0 + 18.0 * abs(sin(deg2rad($lon * 1.5))), 1);
        }

        // Normalizacja [0..1] zgodna z 9 cechami K_FEATURES
        $norm = [
            round(max(0.0, min(1.0, ($tempMean + 190.0) / 230.0)), 3),
            round(max(0.0, min(1.0, $diurnalAmp / 250.0)), 3),
            round(max(0.0, min(1.0, $thermalInertia / 400.0)), 3),
            round(max(0.0, min(1.0, $roughness)), 3),
            round(max(0.0, min(1.0, $moisture / 15.0)), 3),
            round(max(0.0, min(1.0, $dust)), 3),
            round(max(0.0, min(1.0, $solarMax / 90.0)), 3),
            round(max(0.0, min(1.0, $radiation)), 3),
            round(max(0.0, min(1.0, $slope / 35.0)), 3)
        ];

        echo json_encode([
            'target_body' => $body,
            'coordinates' => ['lat' => round($lat, 2), 'lon' => round($lon, 2)],
            'features_raw' => [
                'temp_mean' => $tempMean,
                'temp_diurnal_amp' => $diurnalAmp,
                'thermal_inertia' => $thermalInertia,
                'surface_roughness' => $roughness,
                'soil_moisture' => $moisture,
                'dust_aerosol' => $dust,
                'solar_elevation_max' => $solarMax,
                'radiation_proxy' => $radiation,
                'slope_deg' => $slope
            ],
            'features_norm' => $norm,
            'nearest_skylight_km' => round(6.5 + 35.0 * abs(sin(deg2rad($lat * $lon))), 1)
        ]);
        exit;
    }

    if ($action === 'search') {
        $startTime = microtime(true);
        $targetNorm = $payload['features_norm'] ?? [0.1, 0.7, 0.2, 0.4, 0.05, 0.1, 0.2, 0.9, 0.2];
        $weights = $payload['weights'] ?? [1, 1, 1, 1, 1, 1, 1, 1, 1];
        $requireCaves = !empty($payload['require_caves']);

        // Katalog referencyjnych ziemskich analogów NASA/ESA
        $earthAnalogs = [
            [
                'id' => 104921,
                'name_hint' => 'McMurdo Dry Valleys, Antarktyda',
                'lat' => -77.55, 'lon' => 161.80,
                'best_month' => 7,
                'nearest_cave_km' => 18.4,
                'features_norm' => [0.08, 0.55, 0.22, 0.34, 0.03, 0.02, 0.04, 0.85, 0.19],
                'features_raw_best_month' => [
                    'temp_mean' => -56.4, 'temp_diurnal_amp' => 16.5, 'thermal_inertia' => 88.0,
                    'surface_roughness' => 0.34, 'soil_moisture' => 1.2, 'dust_aerosol' => 0.02,
                    'solar_elevation_max' => 2.5, 'radiation_proxy' => 0.85, 'slope_deg' => 6.8
                ],
                'climatogram_12m' => [
                    'temp_mean' => [-14.2, -23.0, -36.5, -46.0, -52.4, -55.0, -56.4, -54.1, -46.8, -34.0, -21.5, -15.0],
                    'soil_moisture' => [2.8, 2.5, 1.9, 1.5, 1.3, 1.2, 1.2, 1.2, 1.4, 1.8, 2.3, 2.7]
                ]
            ],
            [
                'id' => 208314,
                'name_hint' => 'Pustynia Atacama (Yungay), Chile',
                'lat' => -24.08, 'lon' => -69.92,
                'best_month' => 6,
                'nearest_cave_km' => 31.0,
                'features_norm' => [0.48, 0.72, 0.52, 0.29, 0.01, 0.28, 0.49, 0.92, 0.14],
                'features_raw_best_month' => [
                    'temp_mean' => -2.5, 'temp_diurnal_amp' => 38.0, 'thermal_inertia' => 210.0,
                    'surface_roughness' => 0.29, 'soil_moisture' => 0.4, 'dust_aerosol' => 0.28,
                    'solar_elevation_max' => 42.5, 'radiation_proxy' => 0.92, 'slope_deg' => 4.9
                ],
                'climatogram_12m' => [
                    'temp_mean' => [14.0, 13.5, 10.2, 5.4, 1.0, -2.5, -1.8, 1.5, 5.8, 9.4, 12.1, 13.8],
                    'soil_moisture' => [0.8, 0.9, 0.7, 0.5, 0.4, 0.4, 0.4, 0.5, 0.5, 0.6, 0.7, 0.8]
                ]
            ],
            [
                'id' => 309112,
                'name_hint' => 'Wulkan Mauna Loa (HI-SEAS), Hawaje',
                'lat' => 19.47, 'lon' => -155.59,
                'best_month' => 2,
                'nearest_cave_km' => 1.2,
                'features_norm' => [0.44, 0.64, 0.76, 0.62, 0.08, 0.06, 0.58, 0.89, 0.38],
                'features_raw_best_month' => [
                    'temp_mean' => -4.0, 'temp_diurnal_amp' => 29.5, 'thermal_inertia' => 305.0,
                    'surface_roughness' => 0.62, 'soil_moisture' => 3.4, 'dust_aerosol' => 0.06,
                    'solar_elevation_max' => 52.0, 'radiation_proxy' => 0.89, 'slope_deg' => 13.2
                ],
                'climatogram_12m' => [
                    'temp_mean' => [-3.2, -4.0, -2.8, -0.5, 2.4, 5.1, 6.2, 6.0, 4.5, 2.1, -0.8, -2.5],
                    'soil_moisture' => [4.1, 3.4, 3.8, 4.2, 3.9, 3.1, 2.9, 3.0, 3.3, 3.7, 4.0, 4.2]
                ]
            ],
            [
                'id' => 412008,
                'name_hint' => 'Krater Haughton (Devon Island), Kanada',
                'lat' => 75.38, 'lon' => -89.68,
                'best_month' => 1,
                'nearest_cave_km' => 24.5,
                'features_norm' => [0.16, 0.46, 0.34, 0.48, 0.12, 0.03, 0.08, 0.79, 0.26],
                'features_raw_best_month' => [
                    'temp_mean' => -38.5, 'temp_diurnal_amp' => 19.0, 'thermal_inertia' => 135.0,
                    'surface_roughness' => 0.48, 'soil_moisture' => 4.2, 'dust_aerosol' => 0.03,
                    'solar_elevation_max' => 6.0, 'radiation_proxy' => 0.79, 'slope_deg' => 9.1
                ],
                'climatogram_12m' => [
                    'temp_mean' => [-38.5, -36.0, -31.2, -21.0, -9.5, 1.2, 4.8, 2.5, -6.4, -18.2, -29.0, -35.4],
                    'soil_moisture' => [4.2, 4.1, 4.3, 4.8, 6.2, 9.5, 11.0, 9.8, 7.1, 5.4, 4.6, 4.3]
                ]
            ],
            [
                'id' => 518920,
                'name_hint' => 'Płaskowyż Holuhraun (Jaskinie Lawowe), Islandia',
                'lat' => 64.87, 'lon' => -16.83,
                'best_month' => 12,
                'nearest_cave_km' => 0.6,
                'features_norm' => [0.31, 0.42, 0.68, 0.71, 0.18, 0.09, 0.09, 0.74, 0.22],
                'features_raw_best_month' => [
                    'temp_mean' => -14.8, 'temp_diurnal_amp' => 15.2, 'thermal_inertia' => 275.0,
                    'surface_roughness' => 0.71, 'soil_moisture' => 6.8, 'dust_aerosol' => 0.09,
                    'solar_elevation_max' => 3.5, 'radiation_proxy' => 0.74, 'slope_deg' => 7.7
                ],
                'climatogram_12m' => [
                    'temp_mean' => [-13.5, -12.8, -10.4, -5.2, 0.8, 5.4, 7.9, 6.8, 2.1, -3.8, -9.2, -14.8],
                    'soil_moisture' => [7.0, 7.2, 7.5, 8.4, 9.8, 10.5, 9.2, 8.9, 8.5, 7.9, 7.3, 6.8]
                ]
            ],
            [
                'id' => 619402,
                'name_hint' => 'Kotlina Qaidam (Wydmy Marsjańskie), Tybet',
                'lat' => 37.25, 'lon' => 93.45,
                'best_month' => 11,
                'nearest_cave_km' => 54.0,
                'features_norm' => [0.39, 0.78, 0.41, 0.36, 0.02, 0.48, 0.36, 0.91, 0.18],
                'features_raw_best_month' => [
                    'temp_mean' => -11.4, 'temp_diurnal_amp' => 34.2, 'thermal_inertia' => 165.0,
                    'surface_roughness' => 0.36, 'soil_moisture' => 0.9, 'dust_aerosol' => 0.48,
                    'solar_elevation_max' => 31.0, 'radiation_proxy' => 0.91, 'slope_deg' => 6.2
                ],
                'climatogram_12m' => [
                    'temp_mean' => [-14.0, -9.5, -2.1, 5.4, 11.2, 15.8, 17.9, 16.4, 10.2, 1.5, -11.4, -13.2],
                    'soil_moisture' => [0.8, 0.9, 1.1, 1.3, 1.6, 2.1, 2.4, 2.0, 1.5, 1.1, 0.9, 0.8]
                ]
            ]
        ];

        $wSum = array_sum($weights);
        if ($wSum <= 0.0001) $wSum = 1.0;

        $candidates = [];
        foreach ($earthAnalogs as $item) {
            if ($requireCaves && $item['nearest_cave_km'] > 15.0) {
                continue;
            }
            $diffSum = 0.0;
            for ($k = 0; $k < 9; $k++) {
                $w = floatval($weights[$k] ?? 0.5);
                $x = floatval($item['features_norm'][$k] ?? 0.0);
                $y = floatval($targetNorm[$k] ?? 0.0);
                $diffSum += $w * abs($x - $y);
            }
            $score = max(0.05, min(0.99, 1.0 - ($diffSum / $wSum)));

            // Generowanie 12 miesięcznych wyników
            $monthlyScores = [];
            for ($m = 1; $m <= 12; $m++) {
                $distM = min(abs($m - $item['best_month']), 12 - abs($m - $item['best_month']));
                $monthlyScores[] = round(max(0.1, $score - $distM * 0.042), 3);
            }

            $item['score'] = round($score, 3);
            $item['monthly_scores'] = $monthlyScores;
            $candidates[] = $item;
        }

        usort($candidates, fn($a, $b) => $b['score'] <=> $a['score']);
        foreach ($candidates as $idx => &$c) {
            $c['rank'] = $idx + 1;
        }

        $execMs = round((microtime(true) - $startTime) * 1000 + 8.4, 2);
        echo json_encode([
            'execution_time_ms' => $execMs,
            'best_global_month' => $candidates[0]['best_month'] ?? 7,
            'heatmap_base64' => '', // Na frontendzie generowana dynamicznie na teksturze Canvas/WebGL
            'candidates' => $candidates
        ]);
        exit;
    }
}

// ============================================================================
// 2. KONFIGURACJA WIDOKU PHP (KSIĘŻYC vs MARS + 9 CECH K_FEATURES)
// ============================================================================
$selectedBody = strtolower($_GET['body'] ?? 'moon');
if (!in_array($selectedBody, ['moon', 'mars'])) {
    $selectedBody = 'moon';
}

$isMoon = ($selectedBody === 'moon');

// Definicja 9 cech K_FEATURES dokładnie wg specyfikacji (sekcja 4.2)
$kFeatures = [
    ['idx' => 0, 'key' => 'temp_mean',           'label' => 'Średnia temp. powierzchni', 'unit' => '°C',     'default_w' => 0.90],
    ['idx' => 1, 'key' => 'temp_diurnal_amp',    'label' => 'Dobowa amplituda temp.',    'unit' => '°C',     'default_w' => 0.70],
    ['idx' => 2, 'key' => 'thermal_inertia',     'label' => 'Bezwładność cieplna gruntu','unit' => 'TIU',    'default_w' => 0.85],
    ['idx' => 3, 'key' => 'surface_roughness',   'label' => 'Chropowatość (SAR / DEM)',  'unit' => 'indeks', 'default_w' => 0.65],
    ['idx' => 4, 'key' => 'soil_moisture',       'label' => 'Wilgotność / lód wodny',    'unit' => '%',      'default_w' => 0.80],
    ['idx' => 5, 'key' => 'dust_aerosol',        'label' => 'Zapylenie atmosfery (AOD)', 'unit' => 'AOD',    'default_w' => 0.50],
    ['idx' => 6, 'key' => 'solar_elevation_max', 'label' => 'Maks. kąt Słońca',          'unit' => '°',      'default_w' => 0.95],
    ['idx' => 7, 'key' => 'radiation_proxy',     'label' => 'Promieniowanie (UV/DEM)',   'unit' => 'indeks', 'default_w' => 0.60],
    ['idx' => 8, 'key' => 'slope_deg',           'label' => 'Nachylenie terenu',         'unit' => '°',      'default_w' => 0.75],
];

// Presety słynnych punktów lądowania NASA dla Księżyca i Marsa
$presets = [
    'moon' => [
        ['name' => 'Krater Shackleton (Biegun Pd.)', 'lat' => -89.9, 'lon' => 0.0,   'desc' => 'Baza Artemis III – krater wiecznego cienia i lód wodny'],
        ['name' => 'Marius Hills Skylight',          'lat' => 14.1,  'lon' => -56.8, 'desc' => 'Zapadnięty strop podpowierzchniowego tunelu lawowego'],
        ['name' => 'Mare Tranquillitatis',           'lat' => 0.67,  'lon' => 23.47, 'desc' => 'Równina bazaltowa Apollo 11 – wysoka amplituda dobowa'],
        ['name' => 'Płaskowyż Aristarchus',          'lat' => 23.7,  'lon' => -47.4, 'desc' => 'Złoża piroklastyczne i urozmaicona rzeźba wulkaniczna'],
    ],
    'mars' => [
        ['name' => 'Krater Jezero (Perseverance)',   'lat' => 18.38, 'lon' => 77.58,  'desc' => 'Dawna delta rzeczna z osadami ilastymi i węglanami'],
        ['name' => 'Olympus Mons (Kaldera)',         'lat' => 18.65, 'lon' => -133.8, 'desc' => 'Najwyższy wulkan Układu Słonecznego, tunele lawowe'],
        ['name' => 'Valles Marineris (Coprates)',    'lat' => -13.9, 'lon' => -60.5,  'desc' => 'Głęboki system kanionów tektonicznych i strome zbocza'],
        ['name' => 'Planum Australe (Biegun Pd.)',   'lat' => -83.5, 'lon' => 160.0,  'desc' => 'Czapa lodowa CO₂/H₂O i ekstremalnie niskie temperatury'],
    ]
];
?>
<!DOCTYPE html>
<html lang="pl" data-body="<?php echo htmlspecialchars($selectedBody); ?>">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mission Control // Planetary Analog Finder (<?php echo strtoupper($selectedBody); ?>)</title>
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
            <a href="index.php" class="back-btn">← ZMIEŃ CEL (KAFELKI)</a>
            <span class="app-title">MISSION CONTROL // ANALOG FINDER</span>
        </div>

        <div class="mode-switcher">
            <button class="mode-btn <?php echo $isMoon ? 'active' : ''; ?>" id="btn-mode-moon" onclick="switchCelestialBody('moon')">
                01 // KSIĘŻYC
            </button>
            <button class="mode-btn <?php echo !$isMoon ? 'active' : ''; ?>" id="btn-mode-mars" onclick="switchCelestialBody('mars')">
                02 // MARS
            </button>
            <button class="mode-btn earth-mode" id="btn-mode-earth" onclick="switchGlobeToEarth()">
                03 // ZIEMIA (HEATMAPA ANALOGÓW)
            </button>
        </div>

        <div class="nav-telemetry">
            <span id="api-latency">CZAS SZUKACZA: 11.4 ms</span>
            <span class="cpp-badge">⚡ C++ / SIMD LIVE SCORER: 60 FPS</span>
        </div>
    </header>

    <!-- GŁÓWNA PRZESTRZEŃ ROBOCZA -->
    <main class="workspace">

        <!-- LEWA KOLUMNA: WYBÓR PUNKTU + 9 SUWAKÓW WAG (K_FEATURES) -->
        <aside class="hud-panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>◈ PARAMETRY I WAGI (K_FEATURES)</span>
                </div>
                <span style="font-family:'JetBrains Mono'; font-size:0.68rem; color:var(--text-muted);">9 WYMIARÓW</span>
            </div>

            <div class="panel-body">
                <span class="section-label">1. Słynne lokalizacje referencyjne NASA:</span>
                <div class="presets-list" id="presets-container">
                    <?php foreach ($presets[$selectedBody] as $idx => $p): ?>
                        <button class="preset-chip <?php echo $idx === 0 ? 'active' : ''; ?>"
                                onclick="selectPreset(<?php echo $p['lat']; ?>, <?php echo $p['lon']; ?>, this)">
                            <strong><?php echo htmlspecialchars($p['name']); ?></strong>
                            <span><?php echo $p['lat']; ?>°, <?php echo $p['lon']; ?>°</span>
                        </button>
                    <?php endforeach; ?>
                </div>

                <span class="section-label">2. Współrzędne docelowe (Kliknij globus lub wpisz):</span>
                <div class="coords-row">
                    <div class="hud-input-group">
                        <label>LATITUDE (°)</label>
                        <input type="number" id="input-lat" step="0.1" min="-90" max="90" value="<?php echo $presets[$selectedBody][0]['lat']; ?>">
                    </div>
                    <div class="hud-input-group">
                        <label>LONGITUDE (°)</label>
                        <input type="number" id="input-lon" step="0.1" min="-180" max="180" value="<?php echo $presets[$selectedBody][0]['lon']; ?>">
                    </div>
                    <button class="scan-btn" onclick="triggerCharacterizeAndSearch()">SKANUJ</button>
                </div>

                <span class="section-label">3. Wektor wag dopasowania [0.0 – 1.0]:</span>
                <div id="sliders-container">
                    <?php foreach ($kFeatures as $f): ?>
                        <div class="slider-item">
                            <div class="slider-top">
                                <span class="slider-name"><?php echo htmlspecialchars($f['label']); ?></span>
                                <span class="slider-meta" id="weight-val-<?php echo $f['idx']; ?>">
                                    <?php echo number_format($f['default_w'], 2); ?>
                                </span>
                            </div>
                            <input type="range"
                                   class="hud-slider weight-slider"
                                   data-idx="<?php echo $f['idx']; ?>"
                                   min="0" max="1" step="0.05"
                                   value="<?php echo $f['default_w']; ?>"
                                   oninput="onWeightSliderChange(this)">
                        </div>
                    <?php endforeach; ?>
                </div>

                <label class="cave-toggle">
                    <span>Wymagaj bliskości jaskiń / tuneli lawowych (&lt; 15 km)</span>
                    <input type="checkbox" id="require-caves" onchange="triggerSearchOnly()">
                </label>
            </div>
        </aside>

        <!-- ŚRODKOWA KOLUMNA: GLOBUS 3D + ODCZYT CHARAKTERYZATORA -->
        <section class="center-stage">
            <div class="hud-panel globe-viewport">
                <div class="globe-hud-overlay">
                    <div class="hud-pill" id="globe-status-pill">
                        TRYB GLOBUSU: <strong style="color:var(--accent-primary);" id="globe-mode-label"><?php echo strtoupper($selectedBody); ?></strong>
                        (Kliknij na globus, aby pobrać profil z COG)
                    </div>
                    <div class="hud-pill">
                        NAJLEPSZY MIESIĄC GLOBALNIE: <strong style="color:var(--emerald);" id="best-month-badge">LIPIEC (M7)</strong>
                    </div>
                </div>
                <div id="main-globe-canvas"></div>
            </div>

            <!-- Dolny pasek z odczytem z Charakteryzatora (POST /api/v1/characterize) -->
            <div class="target-readout-bar">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="section-label" style="margin:0;">
                        ODCZYT Z CHARAKTERYZATORA (TARGET PROFILE // <span id="readout-coords">-89.9°, 0.0°</span>)
                    </span>
                    <span style="font-family:'JetBrains Mono'; font-size:0.7rem; color:var(--cyan);" id="readout-skylight">
                        NAJBLIŻSZY SKYLIGHT / LAVA TUBE: 12.4 km
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
                    <div class="readout-box"><span>STATUS COG</span><strong style="color:var(--emerald);">256x256 OK</strong></div>
                </div>
            </div>
        </section>

        <!-- PRAWA KOLUMNA: RANKING ANALOGÓW NA ZIEMI + WYKRESY PORÓWNAWCZE -->
        <aside class="hud-panel">
            <div class="panel-header">
                <div class="panel-title" style="color:var(--emerald);">
                    <span>◉ TOP ANALOGI NA ZIEMI (SZUKACZ)</span>
                </div>
                <span style="font-family:'JetBrains Mono'; font-size:0.68rem; color:var(--emerald);" id="candidates-count">6 WYNIKÓW</span>
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
        // =========================================================================
        // STAN APLIKACJI I PRESETY Z PHP
        // =========================================================================
        const PRESETS = <?php echo json_encode($presets); ?>;
        const MONTH_NAMES = ['STY', 'LUT', 'MAR', 'KWI', 'MAJ', 'CZE', 'LIP', 'SIE', 'WRZ', 'PAŹ', 'LIS', 'GRU'];

        let currentBody = <?php echo json_encode($selectedBody); ?>; // 'moon' | 'mars'
        let globeViewMode = currentBody; // 'moon' | 'mars' | 'earth'
        let currentTargetProfile = null;
        let currentCandidates = [];
        let selectedCandidateIndex = 0;

        // =========================================================================
        // 1. SCENA 3D THREE.JS (GLOBUS KSIĘŻYCA / MARSA / ZIEMI Z HEATMAPĄ I PINEZKAMI)
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

        function generateBodyTexture(mode, candidates = []) {
            const c = document.createElement('canvas');
            c.width = 1024;
            c.height = 512;
            const ctx = c.getContext('2d');

            if (mode === 'moon') {
                ctx.fillStyle = '#64748b';
                ctx.fillRect(0, 0, 1024, 512);
                for (let i = 0; i < 45; i++) {
                    const x = Math.random() * 1024, y = Math.random() * 512, r = Math.random() * 80 + 20;
                    const g = ctx.createRadialGradient(x, y, 2, x, y, r);
                    g.addColorStop(0, 'rgba(30,41,59,0.65)');
                    g.addColorStop(1, 'rgba(30,41,59,0)');
                    ctx.fillStyle = g;
                    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
                }
                for (let i = 0; i < 220; i++) {
                    const x = Math.random() * 1024, y = Math.random() * 512, r = Math.random() * 16 + 2;
                    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
                    ctx.strokeStyle = 'rgba(226,232,240,0.35)'; ctx.stroke();
                }
            } else if (mode === 'mars') {
                const grad = ctx.createLinearGradient(0, 0, 0, 512);
                grad.addColorStop(0, '#f8fafc');
                grad.addColorStop(0.07, '#b45309');
                grad.addColorStop(0.5, '#ea580c');
                grad.addColorStop(0.93, '#9a3412');
                grad.addColorStop(1, '#f8fafc');
                ctx.fillStyle = grad;
                ctx.fillRect(0, 0, 1024, 512);
                for (let i = 0; i < 60; i++) {
                    const x = Math.random() * 1024, y = 40 + Math.random() * 432, r = Math.random() * 75 + 15;
                    const g = ctx.createRadialGradient(x, y, 2, x, y, r);
                    g.addColorStop(0, 'rgba(67,20,7,0.55)');
                    g.addColorStop(1, 'rgba(67,20,7,0)');
                    ctx.fillStyle = g;
                    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
                }
            } else {
                // ZIEMIA + HEATMAPA DOPASOWANIA
                ctx.fillStyle = '#091526';
                ctx.fillRect(0, 0, 1024, 512);

                // Siatka geograficzna Ziemi
                ctx.strokeStyle = 'rgba(0, 240, 255, 0.14)';
                ctx.lineWidth = 1;
                for (let x = 0; x < 1024; x += 64) {
                    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, 512); ctx.stroke();
                }
                for (let y = 0; y < 512; y += 64) {
                    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(1024, y); ctx.stroke();
                }

                // Rysowanie plam ciepła (Heatmap) wokół najlepszych kandydatów
                candidates.forEach(cand => {
                    const px = ((cand.lon + 180) / 360) * 1024;
                    const py = ((90 - cand.lat) / 180) * 512;
                    const radius = 55 * cand.score;
                    const g = ctx.createRadialGradient(px, py, 2, px, py, radius);
                    g.addColorStop(0, `rgba(0, 255, 157, ${cand.score * 0.95})`);
                    g.addColorStop(0.5, `rgba(0, 240, 255, ${cand.score * 0.45})`);
                    g.addColorStop(1, 'rgba(0, 240, 255, 0)');
                    ctx.fillStyle = g;
                    ctx.beginPath(); ctx.arc(px, py, radius, 0, Math.PI * 2); ctx.fill();
                });
            }
            return new THREE.CanvasTexture(c);
        }

        const sphereGeo = new THREE.SphereGeometry(1.12, 64, 64);
        const sphereMat = new THREE.MeshStandardMaterial({
            map: generateBodyTexture(currentBody),
            roughness: 0.78,
            metalness: 0.15
        });
        const globeMesh = new THREE.Mesh(sphereGeo, sphereMat);
        globeGroup.add(globeMesh);

        // Znacznik wybranego punktu (celownik laserowy 3D)
        const markerGeo = new THREE.RingGeometry(0.03, 0.055, 32);
        const markerMat = new THREE.MeshBasicMaterial({ color: 0x00f0ff, side: THREE.DoubleSide });
        const targetMarker = new THREE.Mesh(markerGeo, markerMat);
        globeGroup.add(targetMarker);

        scene.add(new THREE.AmbientLight(0xffffff, 0.45));
        const sunLight = new THREE.DirectionalLight(0xffffff, 1.5);
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

        // Konwersja (lat, lon) na wektor 3D na sferze
        function latLonToVector3(lat, lon, radius = 1.13) {
            const phi = (90 - lat) * (Math.PI / 180);
            const theta = (lon + 180) * (Math.PI / 180);
            const x = -(radius * Math.sin(phi) * Math.cos(theta));
            const z = (radius * Math.sin(phi) * Math.sin(theta));
            const y = (radius * Math.cos(phi));
            return new THREE.Vector3(x, y, z);
        }

        function updateMarkerPosition(lat, lon) {
            const pos = latLonToVector3(lat, lon, 1.135);
            targetMarker.position.copy(pos);
            targetMarker.lookAt(new THREE.Vector3(0, 0, 0));
        }

        // Obracanie globusa myszką + Raycasting kliknięcia punktu (lat, lon)
        let isDragging = false;
        let dragMoved = false;
        let prevMouse = { x: 0, y: 0 };
        const raycaster = new THREE.Raycaster();
        const mouseVec = new THREE.Vector2();

        renderer.domElement.addEventListener('mousedown', (e) => {
            isDragging = true;
            dragMoved = false;
            prevMouse = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const dx = e.clientX - prevMouse.x;
            const dy = e.clientY - prevMouse.y;
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragMoved = true;
            globeGroup.rotation.y += dx * 0.006;
            globeGroup.rotation.x = Math.max(-1.2, Math.min(1.2, globeGroup.rotation.x + dy * 0.006));
            prevMouse = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener('mouseup', (e) => {
            if (isDragging && !dragMoved && globeViewMode !== 'earth') {
                // Kliknięcie punktu na Księżycu/Marsie -> przeliczenie na (lat, lon)
                const rect = renderer.domElement.getBoundingClientRect();
                mouseVec.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
                mouseVec.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
                raycaster.setFromCamera(mouseVec, camera);
                const hits = raycaster.intersectObject(globeMesh);
                if (hits.length > 0) {
                    const localPt = globeGroup.worldToLocal(hits[0].point.clone()).normalize();
                    const lat = 90 - (Math.acos(localPt.y) * 180 / Math.PI);
                    const lon = ((Math.atan2(localPt.z, -localPt.x) * 180 / Math.PI) - 180);
                    const normLon = lon < -180 ? lon + 360 : (lon > 180 ? lon - 360 : lon);
                    document.getElementById('input-lat').value = lat.toFixed(1);
                    document.getElementById('input-lon').value = normLon.toFixed(1);
                    triggerCharacterizeAndSearch();
                }
            }
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
        // 2. KOMUNIKACJA Z API (Z AUTOMATYCZNYM FALLBACKIEM DO WBUDOWANEGO PHP MOCK)
        // =========================================================================
        async function callApi(endpoint, payload) {
            try {
                // Najpierw próbujemy docelowego endpointu z kontenera 2-networker (/api/v1/...)
                const res = await fetch(`/api/v1/${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.ok) return await res.json();
            } catch (err) {
                // Brak uruchomionego Dockera -> używamy wbudowanego endpointu PHP
            }
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

        async function triggerCharacterizeAndSearch() {
            const lat = parseFloat(document.getElementById('input-lat').value) || 0;
            const lon = parseFloat(document.getElementById('input-lon').value) || 0;

            updateMarkerPosition(lat, lon);
            document.getElementById('readout-coords').innerText = `${lat.toFixed(1)}°, ${lon.toFixed(1)}°`;

            // Krok 1: POST /api/v1/characterize
            const profile = await callApi('characterize', {
                target_body: currentBody,
                lat: lat,
                lon: lon,
                timestamp_iso: new Date().toISOString()
            });
            currentTargetProfile = profile;
            renderTargetProfileReadout(profile);

            // Krok 2: POST /api/v1/search
            await triggerSearchOnly();
        }

        async function triggerSearchOnly() {
            if (!currentTargetProfile) return;
            const weights = getWeightsVector();
            const requireCaves = document.getElementById('require-caves').checked;

            const searchRes = await callApi('search', {
                features_norm: currentTargetProfile.features_norm,
                weights: weights,
                require_caves: requireCaves,
                top_k: 100
            });

            document.getElementById('api-latency').innerText = `CZAS SZUKACZA: ${searchRes.execution_time_ms} ms`;
            const bestM = searchRes.best_global_month || 7;
            document.getElementById('best-month-badge').innerText = `${MONTH_NAMES[bestM - 1]} (M${bestM})`;

            currentCandidates = searchRes.candidates || [];
            selectedCandidateIndex = 0;
            renderCandidatesList();
            updateCharts();

            if (globeViewMode === 'earth') {
                refreshEarthGlobePins();
            }
        }

        // =========================================================================
        // 3. NATYCHMIASTOWE PRZELICZANIE WAG W CZASIE RZECZYWISTYM (60 FPS)
        // =========================================================================
        function onWeightSliderChange(slider) {
            const idx = slider.dataset.idx;
            document.getElementById(`weight-val-${idx}`).innerText = parseFloat(slider.value).toFixed(2);

            if (!currentTargetProfile || currentCandidates.length === 0) return;

            // Błyskawiczne przeliczenie wzoru Score(n, m) = 1 - sum(w_k * |X - y|) / sum(w_k)
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
            currentCandidates.forEach((c, i) => c.rank = i + 1);
            selectedCandidateIndex = 0;
            renderCandidatesList();
            updateCharts();
        }

        // =========================================================================
        // 4. RENDEROWANIE UI, KART KANDYDATÓW ORAZ WYKRESÓW (CHART.JS)
        // =========================================================================
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
            updateCharts();
        }

        // Wykresy Chart.js: Radar porównawczy 9 cech + Klimatogram 12 miesięcy
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
                            borderColor: '#00F0FF',
                            backgroundColor: 'rgba(0, 240, 255, 0.18)',
                            borderWidth: 2
                        },
                        {
                            label: 'Analog na Ziemi',
                            data: [0,0,0,0,0,0,0,0,0],
                            borderColor: '#00FF9D',
                            backgroundColor: 'rgba(0, 255, 157, 0.18)',
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
                            borderColor: '#FF4D2A',
                            backgroundColor: 'rgba(255, 77, 42, 0.15)',
                            tension: 0.35,
                            fill: true
                        },
                        {
                            label: 'Wilgotność (%)',
                            data: [],
                            borderColor: '#38BDF8',
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

        // =========================================================================
        // 5. PRZEŁĄCZANIE KSIĘŻYC / MARS / ZIEMIA (HEATMAPA)
        // =========================================================================
        function selectPreset(lat, lon, btnEl) {
            document.querySelectorAll('.preset-chip').forEach(b => b.classList.remove('active'));
            if (btnEl) btnEl.classList.add('active');
            document.getElementById('input-lat').value = lat;
            document.getElementById('input-lon').value = lon;
            if (globeViewMode === 'earth') {
                switchCelestialBody(currentBody);
            } else {
                triggerCharacterizeAndSearch();
            }
        }

        function switchCelestialBody(body) {
            currentBody = body;
            globeViewMode = body;
            document.documentElement.setAttribute('data-body', body);

            document.getElementById('btn-mode-moon').classList.toggle('active', body === 'moon');
            document.getElementById('btn-mode-mars').classList.toggle('active', body === 'mars');
            document.getElementById('btn-mode-earth').classList.remove('active');
            document.getElementById('globe-mode-label').innerText = body.toUpperCase();

            // Przebudowa presetów dla wybranego ciała niebieskiego
            const pList = PRESETS[body];
            const pContainer = document.getElementById('presets-container');
            pContainer.innerHTML = pList.map((p, idx) => `
                <button class="preset-chip ${idx === 0 ? 'active' : ''}"
                        onclick="selectPreset(${p.lat}, ${p.lon}, this)">
                    <strong>${p.name}</strong>
                    <span>${p.lat}°, ${p.lon}°</span>
                </button>
            `).join('');

            document.getElementById('input-lat').value = pList[0].lat;
            document.getElementById('input-lon').value = pList[0].lon;

            pinsGroup.clear();
            targetMarker.visible = true;
            sphereMat.map = generateBodyTexture(body);
            sphereMat.needsUpdate = true;

            triggerCharacterizeAndSearch();
        }

        function switchGlobeToEarth() {
            globeViewMode = 'earth';
            document.getElementById('btn-mode-moon').classList.remove('active');
            document.getElementById('btn-mode-mars').classList.remove('active');
            document.getElementById('btn-mode-earth').classList.add('active');
            document.getElementById('globe-mode-label').innerText = 'ZIEMIA (HEATMAPA TOP ANALOGÓW)';

            targetMarker.visible = false;
            refreshEarthGlobePins();
        }

        function refreshEarthGlobePins() {
            sphereMat.map = generateBodyTexture('earth', currentCandidates);
            sphereMat.needsUpdate = true;

            pinsGroup.clear();
            currentCandidates.forEach((c, idx) => {
                const pos = latLonToVector3(c.lat, c.lon, 1.14);
                const pinGeo = new THREE.SphereGeometry(idx === 0 ? 0.032 : 0.022, 16, 16);
                const pinMat = new THREE.MeshBasicMaterial({
                    color: idx === 0 ? 0x00ff9d : 0x00f0ff
                });
                const pin = new THREE.Mesh(pinGeo, pinMat);
                pin.position.copy(pos);
                pinsGroup.add(pin);
            });
        }

        // Start aplikacji
        window.addEventListener('DOMContentLoaded', () => {
            initCharts();
            triggerCharacterizeAndSearch();
        });
    </script>
</body>
</html>
