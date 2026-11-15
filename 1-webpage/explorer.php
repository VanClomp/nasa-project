<?php
/**
 * explorer.php - Main Mission Control terminal (Component 1: 1-frontend)
 * Follows the spec: POST /api/v1/characterize and POST /api/v1/search
 * Has a built-in fallback mock API in PHP (+ an optional native C++ call),
 * so it works straight away locally and under Docker Compose with the Networker.
 */

// ============================================================================
// 1. BUILT-IN MOCK / PROXY API ENDPOINT IN PHP (when called with ?mock_api=1)
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

        // Realistic parameter estimate from (lat, lon) and the celestial body
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

        // [0..1] normalisation matching the 9 K_FEATURES
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

        // Catalogue of reference Earth analogs (NASA/ESA)
        $earthAnalogs = [
            [
                'id' => 104921,
                'name_hint' => 'McMurdo Dry Valleys, Antarctica',
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
                'name_hint' => 'Atacama Desert (Yungay), Chile',
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
                'name_hint' => 'Mauna Loa volcano (HI-SEAS), Hawaii',
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
                'name_hint' => 'Haughton Crater (Devon Island), Canada',
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
                'name_hint' => 'Holuhraun lava plateau (lava caves), Iceland',
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
                'name_hint' => 'Qaidam Basin (Martian dunes), Tibet',
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

            // Generate 12 monthly results
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
            'heatmap_base64' => '', // generated dynamically on the frontend as a Canvas/WebGL texture
            'candidates' => $candidates
        ]);
        exit;
    }
}

// ============================================================================
// 2. PHP VIEW SETUP (MOON vs MARS + 9 K_FEATURES)
// ============================================================================
$selectedBody = strtolower($_GET['body'] ?? 'moon');
if (!in_array($selectedBody, ['moon', 'mars'])) {
    $selectedBody = 'moon';
}

$isMoon = ($selectedBody === 'moon');

// The 9 K_FEATURES exactly as in the spec (section 4.2)
$kFeatures = [
    ['idx' => 0, 'key' => 'temp_mean',           'label' => 'Mean surface temp.',        'unit' => '°C',     'default_w' => 0.90, 'desc' => 'Average surface temperature at the site for the selected landing date (°C).'],
    ['idx' => 1, 'key' => 'temp_diurnal_amp',    'label' => 'Diurnal temp. range',       'unit' => '°C',     'default_w' => 0.70, 'desc' => 'Day-to-night surface temperature swing over a solar day (°C / K).'],
    ['idx' => 2, 'key' => 'thermal_inertia',     'label' => 'Ground thermal inertia',    'unit' => 'TIU',    'default_w' => 0.85, 'desc' => 'Resistance of the ground to temperature change; reflects regolith vs. exposed rock (TIU).'],
    ['idx' => 3, 'key' => 'surface_roughness',   'label' => 'Roughness (SAR / DEM)',     'unit' => 'index',  'default_w' => 0.65, 'desc' => 'Sub-kilometer surface roughness derived from orbital radar and elevation models.'],
    ['idx' => 4, 'key' => 'soil_moisture',       'label' => 'Moisture / water ice',      'unit' => '%',      'default_w' => 0.80, 'desc' => 'Near-surface water or water-ice content (wt% / %).'],
    ['idx' => 5, 'key' => 'dust_aerosol',        'label' => 'Atmospheric dust (AOD)',    'unit' => 'AOD',    'default_w' => 0.50, 'desc' => 'Atmospheric dust optical depth; varies by season on Mars and is zero on the Moon.'],
    ['idx' => 6, 'key' => 'solar_elevation_max', 'label' => 'Max. Sun elevation',        'unit' => '°',      'default_w' => ($isMoon ? 1.00 : 0.40), 'desc' => 'Peak Sun angle above the horizon on the selected landing date (°).'],
    ['idx' => 7, 'key' => 'radiation_proxy',     'label' => 'Radiation (UV/DEM)',        'unit' => 'index',  'default_w' => 0.60, 'desc' => 'Surface radiation exposure proxy based on atmospheric shielding column density.'],
    ['idx' => 8, 'key' => 'slope_deg',           'label' => 'Terrain slope',             'unit' => '°',      'default_w' => 0.75, 'desc' => 'Local terrain steepness computed from orbital elevation data (°).'],
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
    <title>Mission Control // Planetary Analog Finder (<?php echo strtoupper($selectedBody); ?>)</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <!-- Three.js -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <link rel="stylesheet" href="style.css?v=<?php echo @filemtime(__DIR__ . '/style.css') ?: 1; ?>">
</head>
<body>
    <?php include __DIR__ . '/progress_bar.php'; ?>
    <script src="feature_info.js?v=3"></script>

    <div class="hud-bg"></div>

    <!-- TOP NAVIGATION BAR -->
    <header class="navbar">
        <div class="nav-left">
            <a href="index.php" class="back-btn">Home</a>
            <span class="app-title">Planetary Analog Finder</span>
        </div>

        <div class="nav-right">
            <div class="mode-switcher">
                <button class="mode-btn" type="button" onclick="switchToDualView()">Dual</button>
                <button class="mode-btn active" type="button">Single</button>
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

    <!-- MAIN WORKSPACE (2 COLUMNS: SETUP + 3D GLOBE) -->
    <main class="workspace workspace-config">

        <!-- LEFT COLUMN: POINT SELECTION + 9 WEIGHT SLIDERS (K_FEATURES) + RESULTS BUTTON -->
        <aside class="hud-panel">
            <div class="panel-header">
                <div class="panel-title">
                    <span>Parameters and weights</span>
                </div>
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
                <button type="button" class="center-pin-btn" onclick="centerGlobeOnPin()">Center</button>

                <span class="section-label">Landing date</span>
                <div class="coords-row">
                    <div class="hud-input-group">
                        <label>DATA (UTC)</label>
                        <input type="date" id="input-date" min="1990-01-01" max="2100-12-31" value="<?php echo htmlspecialchars($initialDate); ?>" onchange="triggerCharacterize()">
                    </div>
                </div>

                <span class="section-label">Match weights (0.0 – 1.0)</span>
                <div id="sliders-container">
                    <?php foreach ($kFeatures as $f): ?>
                        <?php $wVal = $initialWeights[$f['idx']] ?? $f['default_w']; ?>
                        <div class="slider-item">
                            <div class="slider-top">
                                <span class="slider-name">
                                    <?php echo htmlspecialchars($f['label']); ?>
                                    <button type="button" class="info-icon-btn" data-tooltip="<?php echo htmlspecialchars($f['desc']); ?>" aria-label="Info: <?php echo htmlspecialchars($f['label']); ?>">i</button>
                                </span>
                                <span class="slider-right">
                                    <span class="feat-src" id="filter-src-<?php echo $f['idx']; ?>"></span>
                                    <span class="slider-meta" id="weight-val-<?php echo $f['idx']; ?>">
                                        <?php echo number_format($wVal, 2); ?>
                                    </span>
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
                    <span>
                        Require a nearby cave / lava tube (&lt; 15 km)
                        <button type="button" class="info-icon-btn" data-tooltip="Restrict Earth analog results to sites within 15 km of documented caves or lava tubes." aria-label="Info: Require a nearby cave">i</button>
                    </span>
                    <input type="checkbox" id="require-caves" <?php echo $initialCaves ? 'checked' : ''; ?>>
                </label>
            </div>

            <div class="panel-footer">
                <button type="button" class="find-analogs-btn" onclick="openResultsPage()">
                    <span>Find analogs on Earth</span>
                    <span>→</span>
                </button>
            </div>
        </aside>

        <!-- MIDDLE COLUMN: 3D GLOBE + CHARACTERIZER READOUT -->
        <section class="center-stage">
            <div class="globe-viewport">
                <div class="globe-hud-overlay">
                    <div class="hud-pill" id="globe-status-pill">
                        Click the surface to pick a point · Scroll to zoom
                    </div>
                </div>
                <div id="main-globe-canvas"></div>
            </div>

            <!-- Bottom bar with the Characterizer readout (POST /api/v1/characterize) -->
            <div class="target-readout-bar">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="section-label" style="margin:0;">
                        Location data · <span id="readout-coords"><?php echo $initialLat; ?>°, <?php echo $initialLon; ?>°</span><span id="readout-season"></span>
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
                    <div class="readout-box"><span>ROUGHNESS</span><strong id="raw-surface_roughness">--</strong></div>
                    <div class="readout-box"><span>MOISTURE / ICE</span><strong id="raw-soil_moisture">-- %</strong></div>
                    <div class="readout-box"><span>DUST (AOD)</span><strong id="raw-dust_aerosol">--</strong></div>
                    <div class="readout-box"><span>MAX. SUN ELEVATION</span><strong id="raw-solar_elevation_max">-- °</strong></div>
                    <div class="readout-box"><span>RADIATION</span><strong id="raw-radiation_proxy">--</strong></div>
                    <div class="readout-box"><span>TERRAIN SLOPE</span><strong id="raw-slope_deg">-- °</strong></div>
                    <div class="readout-box"><span>STATUS</span><strong style="color:var(--emerald);">Ready</strong></div>
                </div>
            </div>
        </section>

    </main>

    <script>
        // =========================================================================
        // APP STATE AND PRESETS FROM PHP
        // =========================================================================
        const PRESETS = <?php echo json_encode($presets); ?>;
        const MONTH_NAMES = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];

        let currentBody = <?php echo json_encode($selectedBody); ?>; // 'moon' | 'mars'
        let globeViewMode = currentBody; // 'moon' | 'mars' | 'earth'
        let currentTargetProfile = null;
        let currentCandidates = [];
        let selectedCandidateIndex = 0;

        // =========================================================================
        // 1. THREE.JS 3D SCENE (MOON / MARS / EARTH GLOBE WITH HEATMAP AND PINS)
        // =========================================================================
        const globeContainer = document.getElementById('main-globe-canvas');
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
        camera.position.z = 3.45;

        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        globeContainer.appendChild(renderer.domElement);

        const globeGroup = new THREE.Group();
        scene.add(globeGroup);

        const pinsGroup = new THREE.Group();
        globeGroup.add(pinsGroup);

        const textureLoader = new THREE.TextureLoader();
        function loadBodyTexture(url) {
            return textureLoader.load(url, (tex) => {
                tex.needsUpdate = true;
                if (typeof sphereMat !== 'undefined' && sphereMat) {
                    sphereMat.needsUpdate = true;
                }
            });
        }
        let moonPhotoTexture = loadBodyTexture('images/moon_photo.jpg');
        let marsPhotoTexture = loadBodyTexture('images/mars_photo.jpg');
        const earthPhotoTexture = textureLoader.load('images/earth_photo.jpg');

        function generateBodyTexture(mode, candidates = []) {
            if (mode === 'moon') {
                if (!moonPhotoTexture) {
                    moonPhotoTexture = loadBodyTexture('images/moon_photo.jpg');
                }
                return moonPhotoTexture;
            }
            if (mode === 'mars') {
                if (!marsPhotoTexture) {
                    marsPhotoTexture = loadBodyTexture('images/mars_photo.jpg');
                }
                return marsPhotoTexture;
            }

            return loadBodyTexture('images/earth_photo.jpg');
        }

        const sphereGeo = new THREE.SphereGeometry(1.12, 64, 64);
        const sphereMat = new THREE.MeshStandardMaterial({
            map: generateBodyTexture(currentBody),
            roughness: 0.96,
            metalness: 0.0
        });
        const globeMesh = new THREE.Mesh(sphereGeo, sphereMat);
        globeGroup.add(globeMesh);

        const INITIAL_ROT_X = <?php echo json_encode($initialRotX); ?>;
        const INITIAL_ROT_Y = <?php echo json_encode($initialRotY); ?>;
        if (INITIAL_ROT_X !== null && INITIAL_ROT_Y !== null) {
            globeGroup.rotation.x = INITIAL_ROT_X;
            globeGroup.rotation.y = INITIAL_ROT_Y;
        }

        // Subtle but clear surface pin (dot + thin ring)
        const targetMarker = new THREE.Group();
        const markerDotGeo = new THREE.CircleGeometry(0.013, 24);
        const markerDotMat = new THREE.MeshBasicMaterial({ color: 0xf4f4f6, side: THREE.DoubleSide });
        const markerDot = new THREE.Mesh(markerDotGeo, markerDotMat);
        targetMarker.add(markerDot);

        const markerRingGeo = new THREE.RingGeometry(0.028, 0.034, 36);
        const markerRingMat = new THREE.MeshBasicMaterial({
            color: currentBody === 'moon' ? 0x60a5fa : 0xf97316,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.95
        });
        const markerRing = new THREE.Mesh(markerRingGeo, markerRingMat);
        targetMarker.add(markerRing);
        globeGroup.add(targetMarker);

        scene.add(new THREE.AmbientLight(0xffffff, 0.40));
        const sunLight = new THREE.DirectionalLight(0xffffff, 0.55);
        sunLight.position.set(5, 3, 4);
        scene.add(sunLight);

        function resizeGlobe() {
            // Collapse the canvas first, so the page layout (not the canvas's previous size) decides the container
            // size. Without this, after the two-planet -> single transition (canvas full-screen) the grid cell kept
            // the 1440 px canvas width and pushed the readout bar below the screen.
            renderer.domElement.style.width = '0px';
            renderer.domElement.style.height = '0px';
            renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));   // browser zoom changes the ratio
            const rect = globeContainer.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) return;
            renderer.setSize(rect.width, rect.height);
            camera.aspect = rect.width / rect.height;
            camera.updateProjectionMatrix();
        }
        window.addEventListener('resize', resizeGlobe);
        setTimeout(resizeGlobe, 50);
        // Re-fit the globe when the readout bar changes height (e.g. the per-parameter flags appear after the first
        // characterize), otherwise the bar is pushed partly below the screen. Skipped during view transitions.
        if (window.ResizeObserver) {
            const readoutBar = document.querySelector('.target-readout-bar');
            let lastBarH = 0;
            if (readoutBar) new ResizeObserver(entries => {
                const h = Math.round(entries[0].contentRect.height);
                if (h !== lastBarH && !(typeof dualTrans !== 'undefined' && dualTrans)) { lastBarH = h; resizeGlobe(); }
            }).observe(readoutBar);
        }

        // Convert (lat, lon) to a 3D vector on the sphere
        function latLonToVector3(lat, lon, radius = 1.13) {
            const phi = (90 - lat) * (Math.PI / 180);
            const theta = (lon + 180) * (Math.PI / 180);
            const x = -(radius * Math.sin(phi) * Math.cos(theta));
            const z = (radius * Math.sin(phi) * Math.sin(theta));
            const y = (radius * Math.cos(phi));
            return new THREE.Vector3(x, y, z);
        }

        function updateMarkerPosition(lat, lon) {
            const pos = latLonToVector3(lat, lon, 1.124);
            targetMarker.position.copy(pos);
            targetMarker.quaternion.setFromUnitVectors(
                new THREE.Vector3(0, 0, 1),
                pos.clone().normalize()
            );
        }

        // Rotate the globe with the mouse, smooth zoom towards the cursor (like Google Maps) + click raycasting
        let isDragging = false;
        let dragMoved = false;
        let prevMouse = { x: 0, y: 0 };
        let targetCamX = 0;
        let targetCamY = 0;
        let targetCamZ = 3.45;
        let isDiving = false;
        let diveStart = 0;
        let diveStartCamX = 0;
        let diveStartCamY = 0;
        let diveStartZ = 3.45;
        let diveStartPosX = 0;
        let diveStartPosY = 0;
        let diveStartRotX = 0;
        let diveStartRotY = 0;
        let diveTargetRotX = 0;
        let diveTargetRotY = 0;
        let diveUrl = '';
        let dualTrans = null;
        let earthTransGroup = null;
        let earthTransMat = null;

        const raycaster = new THREE.Raycaster();
        const mouseVec = new THREE.Vector2();

        renderer.domElement.style.touchAction = 'none';

        function applyZoomAt(clientX, clientY, deltaZ) {
            const rect = renderer.domElement.getBoundingClientRect();
            const ndcX = ((clientX - rect.left) / rect.width) * 2 - 1;
            const ndcY = -((clientY - rect.top) / rect.height) * 2 + 1;

            const oldZ = targetCamZ;
            const newZ = Math.max(1.42, Math.min(4.6, oldZ + deltaZ));

            const vFov = (camera.fov * Math.PI) / 180;
            const halfHOld = oldZ * Math.tan(vFov / 2);
            const halfWOld = halfHOld * camera.aspect;
            const worldX = targetCamX + ndcX * halfWOld;
            const worldY = targetCamY + ndcY * halfHOld;

            const halfHNew = newZ * Math.tan(vFov / 2);
            const halfWNew = halfHNew * camera.aspect;

            targetCamZ = newZ;
            const maxPan = Math.max(0, (3.45 - newZ) * 0.65);
            targetCamX = Math.max(-maxPan, Math.min(maxPan, worldX - ndcX * halfWNew));
            targetCamY = Math.max(-maxPan, Math.min(maxPan, worldY - ndcY * halfHNew));
        }

        renderer.domElement.addEventListener('wheel', (e) => {
            if (isDiving) return;
            e.preventDefault();
            pauseAutoRotate();
            applyZoomAt(e.clientX, e.clientY, e.deltaY * 0.0022);
        }, { passive: false });

        let isCentering = false;
        let targetCenterRotX = 0;
        let targetCenterRotY = 0;
        let pauseAutoRotateUntil = 0;

        function pauseAutoRotate(ms = 8000) {
            pauseAutoRotateUntil = performance.now() + ms;
        }

        function centerGlobeOnPin() {
            if (isDiving) return;
            pauseAutoRotate();
            const lat = parseFloat(document.getElementById('input-lat').value) || 0;
            const lon = parseFloat(document.getElementById('input-lon').value) || 0;
            const p = latLonToVector3(lat, lon, 1);
            const rXZ = Math.hypot(p.x, p.z);
            const desiredRotY = -Math.atan2(p.x, p.z);
            const desiredRotX = Math.atan2(p.y, rXZ);

            let deltaY = (desiredRotY - globeGroup.rotation.y) % (Math.PI * 2);
            if (deltaY > Math.PI) deltaY -= Math.PI * 2;
            if (deltaY < -Math.PI) deltaY += Math.PI * 2;

            targetCenterRotX = desiredRotX;
            targetCenterRotY = globeGroup.rotation.y + deltaY;
            targetCamX = 0;
            targetCamY = 0;
            isCentering = true;
        }

        renderer.domElement.addEventListener('mousedown', (e) => {
            if (isDiving) return;
            isCentering = false;
            pauseAutoRotate();
            isDragging = true;
            dragMoved = false;
            prevMouse = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener('mousemove', (e) => {
            if (!isDragging || isDiving) return;
            pauseAutoRotate();
            const dx = e.clientX - prevMouse.x;
            const dy = e.clientY - prevMouse.y;
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragMoved = true;
            const sensitivity = Math.max(0.0018, (camera.position.z - 1.0) * 0.0028);
            globeGroup.rotation.y += dx * sensitivity;
            globeGroup.rotation.x = Math.max(-1.35, Math.min(1.35, globeGroup.rotation.x + dy * sensitivity));
            prevMouse = { x: e.clientX, y: e.clientY };
        });

        function pickPointAt(clientX, clientY) {
            if (isDiving || globeViewMode === 'earth') return;
            const rect = renderer.domElement.getBoundingClientRect();
            mouseVec.x = ((clientX - rect.left) / rect.width) * 2 - 1;
            mouseVec.y = -((clientY - rect.top) / rect.height) * 2 + 1;
            raycaster.setFromCamera(mouseVec, camera);
            const hits = raycaster.intersectObject(globeMesh);
            if (hits.length > 0) {
                const localPt = globeGroup.worldToLocal(hits[0].point.clone()).normalize();
                const lat = 90 - (Math.acos(localPt.y) * 180 / Math.PI);
                const lon = ((Math.atan2(localPt.z, -localPt.x) * 180 / Math.PI) - 180);
                const normLon = lon < -180 ? lon + 360 : (lon > 180 ? lon - 360 : lon);
                document.getElementById('input-lat').value = lat.toFixed(1);
                document.getElementById('input-lon').value = normLon.toFixed(1);
                triggerCharacterize();
            }
        }

        window.addEventListener('mouseup', (e) => {
            if (isDragging) {
                pauseAutoRotate();
                if (!dragMoved) {
                    pickPointAt(e.clientX, e.clientY);
                }
            }
            isDragging = false;
        });

        // Touch support (1-finger rotate, tap, 2-finger pinch-to-zoom)
        let prevPinchDist = 0;
        renderer.domElement.addEventListener('touchstart', (e) => {
            if (isDiving) return;
            e.preventDefault();
            isCentering = false;
            pauseAutoRotate();
            isDragging = true;
            if (e.touches.length === 1) {
                dragMoved = false;
                prevPinchDist = 0;
                prevMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            } else if (e.touches.length === 2) {
                dragMoved = true;
                prevPinchDist = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
            }
        }, { passive: false });

        renderer.domElement.addEventListener('touchmove', (e) => {
            if (!isDragging || isDiving) return;
            e.preventDefault();
            pauseAutoRotate();
            if (e.touches.length === 1 && prevPinchDist === 0) {
                const dx = e.touches[0].clientX - prevMouse.x;
                const dy = e.touches[0].clientY - prevMouse.y;
                if (Math.abs(dx) > 4 || Math.abs(dy) > 4) dragMoved = true;
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
                dragMoved = true;
                prevMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
                return;
            }
            if (e.touches.length === 0) {
                if (isDragging) {
                    pauseAutoRotate();
                    if (!dragMoved && e.changedTouches.length > 0) {
                        pickPointAt(e.changedTouches[0].clientX, e.changedTouches[0].clientY);
                    }
                }
                isDragging = false;
                prevPinchDist = 0;
            }
        }, { passive: false });

        function easeInOutQuart(t) {
            return t < 0.5 ? 8 * t * t * t * t : 1 - Math.pow(-2 * t + 2, 4) / 2;
        }

        function animateScene(now) {
            if (dualTrans) {
                const elapsed = now - dualTrans.start;
                const progress = Math.min(1, elapsed / dualTrans.duration);
                const eased = 1 - Math.pow(1 - progress, 3);

                globeGroup.position.x = dualTrans.startPosX + (dualTrans.endPosX - dualTrans.startPosX) * eased;
                globeGroup.position.y = dualTrans.startPosY + (dualTrans.endPosY - dualTrans.startPosY) * eased;
                const curScale = dualTrans.startScale + (dualTrans.endScale - dualTrans.startScale) * eased;
                globeGroup.scale.setScalar(curScale);

                if (earthTransGroup) {
                    earthTransGroup.position.x = dualTrans.earthStartX + (dualTrans.earthEndX - dualTrans.earthStartX) * eased;
                    earthTransGroup.position.y = dualTrans.endPosY;
                    earthTransGroup.scale.setScalar(dualTrans.endScale * (0.9 + 0.1 * eased));
                    earthTransGroup.rotation.y += 0.0008;
                    earthTransMat.opacity = Math.min(1, eased * 1.45);
                }

                if (dualTrans.mode === 'out' && elapsed >= dualTrans.reloadAt && !dualTrans.navigated) {
                    dualTrans.navigated = true;
                    try {
                        sessionStorage.setItem('paf_view_transition', JSON.stringify({
                            dir: 'to_dual',
                            startEpoch: Date.now() - elapsed,
                            duration: dualTrans.duration,
                            rotX: globeGroup.rotation.x,
                            rotY: globeGroup.rotation.y
                        }));
                    } catch (e) {}
                    window.location.href = dualTrans.url;
                    return;
                }

                if (dualTrans.mode === 'in' && progress >= 1) {
                    finishEnterSingleView();
                }
            } else if (isDiving) {
                const elapsed = now - diveStart;
                const progress = Math.min(1, elapsed / 1250);
                const eased = easeInOutQuart(progress);

                camera.position.x = diveStartCamX * (1 - eased);
                camera.position.y = diveStartCamY * (1 - eased);
                camera.position.z = diveStartZ + (1.16 - diveStartZ) * eased;
                globeGroup.position.x = diveStartPosX * (1 - eased);
                globeGroup.position.y = diveStartPosY * (1 - eased);
                globeGroup.rotation.x = diveStartRotX + (diveTargetRotX - diveStartRotX) * eased;
                globeGroup.rotation.y = diveStartRotY + (diveTargetRotY - diveStartRotY) * eased;

                if (progress > 0.94) {
                    document.body.style.transition = 'opacity 0.14s ease';
                    document.body.style.opacity = '0';
                }
                if (progress >= 1) {
                    window.location.href = diveUrl;
                    return;
                }
            } else {
                if (isCentering) {
                    globeGroup.rotation.x += (targetCenterRotX - globeGroup.rotation.x) * 0.12;
                    globeGroup.rotation.y += (targetCenterRotY - globeGroup.rotation.y) * 0.12;
                    if (Math.abs(targetCenterRotX - globeGroup.rotation.x) < 0.001 &&
                        Math.abs(targetCenterRotY - globeGroup.rotation.y) < 0.001) {
                        globeGroup.rotation.x = targetCenterRotX;
                        globeGroup.rotation.y = targetCenterRotY;
                        isCentering = false;
                    }
                } else if (!isDragging) {
                    const now = performance.now();
                    if (now >= pauseAutoRotateUntil) {
                        const resumeFactor = Math.min(1, (now - pauseAutoRotateUntil) / 800);
                        globeGroup.rotation.y += 0.0008 * resumeFactor;
                    }
                }
                camera.position.x += (targetCamX - camera.position.x) * 0.08;
                camera.position.y += (targetCamY - camera.position.y) * 0.08;
                camera.position.z += (targetCamZ - camera.position.z) * 0.08;
            }
            // Scale the pin with the planet view's zoom level
            const markerScale = isDiving
                ? Math.max(0.12, (camera.position.z - 1.05) / 2.05)
                : Math.max(0.22, (camera.position.z - 1.05) / 2.05);
            targetMarker.scale.setScalar(markerScale);

            renderer.render(scene, camera);
            requestAnimationFrame(animateScene);
        }
        requestAnimationFrame(animateScene);

        // =========================================================================
        // 2. KOMUNIKACJA Z API (Z AUTOMATYCZNYM FALLBACKIEM DO WBUDOWANEGO PHP MOCK)
        // =========================================================================
        async function callApi(endpoint, payload) {
            try {
                // First try the real endpoint of the 2-networker container (/api/v1/...)
                const res = await fetch(`/api/v1/${endpoint}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.ok) return await res.json();
            } catch (err) {
                // Docker not running -> use the built-in PHP endpoint
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

        async function triggerCharacterize() {
            const lat = parseFloat(document.getElementById('input-lat').value) || 0;
            const lon = parseFloat(document.getElementById('input-lon').value) || 0;

            updateMarkerPosition(lat, lon);
            document.getElementById('readout-coords').innerText = `${lat.toFixed(1)}°, ${lon.toFixed(1)}°`;

            const profile = await callApi('characterize', {
                target_body: currentBody,
                lat: lat,
                lon: lon,
                timestamp_iso: landingTimestamp()
            });
            currentTargetProfile = profile;
            if (window.updateFilterSourceBadges) window.updateFilterSourceBadges(profile);
            renderTargetProfileReadout(profile);
        }

        function onWeightSliderChange(slider) {
            const idx = slider.dataset.idx;
            document.getElementById(`weight-val-${idx}`).innerText = parseFloat(slider.value).toFixed(2);
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

        // renderTargetProfileReadout / renderModelBadge / renderFeatureFlags (values, source tags and the info box
        // for each parameter) are shared with the other page: feature_info.js

        function selectPreset(lat, lon, btnEl) {
            document.querySelectorAll('.preset-chip').forEach(b => b.classList.remove('active'));
            if (btnEl) btnEl.classList.add('active');
            document.getElementById('input-lat').value = lat;
            document.getElementById('input-lon').value = lon;
            centerGlobeOnPin();
            triggerCharacterize();
        }

        function switchCelestialBody(body) {
            // Max. Sun elevation weight follows module 3's suggestion for the body (Moon 1.00: sunlight is power;
            // Mars 0.40: mostly latitude/season), unless the user has moved that slider.
            const SUN_W = { moon: 1.00, mars: 0.40 };
            const sunSlider = document.querySelector('.weight-slider[data-idx="6"]');
            if (sunSlider && body !== currentBody && Math.abs(parseFloat(sunSlider.value) - SUN_W[currentBody]) < 1e-6) {
                sunSlider.value = SUN_W[body];
                onWeightSliderChange(sunSlider);
            }
            currentBody = body;
            globeViewMode = body;
            document.documentElement.setAttribute('data-body', body);

            document.getElementById('btn-mode-moon').classList.toggle('active', body === 'moon');
            document.getElementById('btn-mode-mars').classList.toggle('active', body === 'mars');

            const pList = PRESETS[body];

            document.getElementById('input-lat').value = pList[0].lat;
            document.getElementById('input-lon').value = pList[0].lon;

            pinsGroup.clear();
            targetMarker.visible = true;
            markerRingMat.color.setHex(body === 'moon' ? 0x60a5fa : 0xf97316);
            sphereMat.map = generateBodyTexture(body);
            sphereMat.needsUpdate = true;

            triggerCharacterize();
        }

        function switchToDualView() {
            if (isDiving || dualTrans) return;
            const lat = parseFloat(document.getElementById('input-lat').value) || 0;
            const lon = parseFloat(document.getElementById('input-lon').value) || 0;
            const weights = getWeightsVector().map(w => w.toFixed(2)).join(',');
            const caves = document.getElementById('require-caves').checked ? '1' : '0';
            const params = new URLSearchParams({
                body: currentBody,
                lat: lat.toFixed(2),
                lon: lon.toFixed(2),
                w: weights,
                caves: caves,
                date: landingDate(),
                rotX: globeGroup.rotation.x.toFixed(4),
                rotY: globeGroup.rotation.y.toFixed(4)
            });
            const targetUrl = `dual.php?${params.toString()}`;

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
                modeBtns[0].classList.remove('active');
                modeBtns[1].classList.add('active');
            }

            const navbar = document.querySelector('.navbar');
            const leftPanel = document.querySelector('aside.hud-panel');
            const bottomBar = document.querySelector('.target-readout-bar');
            const hudOverlay = document.querySelector('.globe-hud-overlay');
            const viewport = document.querySelector('.globe-viewport');

            const rect = viewport.getBoundingClientRect();
            const navH = navbar ? navbar.getBoundingClientRect().height : 0;
            const winW = window.innerWidth;
            const winH = window.innerHeight;

            // Current planet position and size in pixels before the layout change
            const vFov = (camera.fov * Math.PI) / 180;
            const startWorldPerPx = (2 * camera.position.z * Math.tan(vFov / 2)) / rect.height;
            const startRadiusPx = 1.12 / startWorldPerPx;
            const startCenterX = rect.left + rect.width / 2 - (camera.position.x / startWorldPerPx);
            const startCenterY = rect.top + rect.height / 2 + (camera.position.y / startWorldPerPx);

            // Exact target geometry of the left and right columns in dual.php
            const dualDrawerW = Math.min(310, Math.max(270, winW * 0.19));
            const gap = Math.min(48, Math.max(24, winW * 0.028));
            const innerStageW = winW - dualDrawerW - 44;
            const colW = (innerStageW - gap) / 2;
            const colH = winH - navH - 16;
            const leftColCenterX = dualDrawerW + 24 + colW / 2;
            const leftColCenterY = navH + 8 + colH / 2;
            const rightColCenterX = leftColCenterX + colW + gap;
            const hHalfDual = 1.22 / Math.min(1, colW / colH);
            const targetRadiusPx = (1.12 / hHalfDual) * (colH / 2);

            // Freeze the current panel positions before taking the viewport out of the grid
            const frozenRects = [leftPanel, bottomBar].map(el => el ? el.getBoundingClientRect() : null);
            [leftPanel, bottomBar].forEach((el, i) => {
                const r = frozenRects[i];
                if (!el || !r) return;
                el.style.position = 'fixed';
                el.style.top = `${r.top}px`;
                el.style.left = `${r.left}px`;
                el.style.width = `${r.width}px`;
                el.style.height = `${r.height}px`;
                el.style.zIndex = '25';
            });
            if (navbar) navbar.style.zIndex = '30';

            const vpH = winH - navH;
            viewport.style.position = 'fixed';
            viewport.style.top = `${navH}px`;
            viewport.style.left = '0';
            viewport.style.width = `${winW}px`;
            viewport.style.height = `${vpH}px`;
            viewport.style.zIndex = '5';

            renderer.setSize(winW, vpH);
            camera.aspect = winW / vpH;
            camera.position.set(0, 0, 4.3);
            camera.updateProjectionMatrix();

            const newWorldPerPx = (2 * 4.3 * Math.tan(vFov / 2)) / vpH;
            const vpCenterY = navH + vpH / 2;
            const startPosX = (startCenterX - winW / 2) * newWorldPerPx;
            const startPosY = -(startCenterY - vpCenterY) * newWorldPerPx;
            const startScale = (startRadiusPx * newWorldPerPx) / 1.12;

            const endPosX = (leftColCenterX - winW / 2) * newWorldPerPx;
            const endPosY = -(leftColCenterY - vpCenterY) * newWorldPerPx;
            const endScale = (targetRadiusPx * newWorldPerPx) / 1.12;

            const earthEndX = (rightColCenterX - winW / 2) * newWorldPerPx;
            const earthStartX = (winW + targetRadiusPx * 1.4 - winW / 2) * newWorldPerPx;

            globeGroup.position.set(startPosX, startPosY, 0);
            globeGroup.scale.setScalar(startScale);

            earthTransGroup = new THREE.Group();
            earthTransMat = new THREE.MeshStandardMaterial({
                map: earthPhotoTexture,
                roughness: 0.96,
                metalness: 0.0,
                transparent: true,
                opacity: 0
            });
            earthTransGroup.add(new THREE.Mesh(sphereGeo, earthTransMat));
            earthTransGroup.position.set(earthStartX, endPosY, 0);
            earthTransGroup.scale.setScalar(endScale * 0.9);
            scene.add(earthTransGroup);

            dualTrans = {
                mode: 'out',
                start: performance.now(),
                duration: 720,
                reloadAt: 220,
                navigated: false,
                startPosX, startPosY, startScale,
                endPosX, endPosY, endScale,
                earthStartX, earthEndX,
                url: targetUrl
            };

            requestAnimationFrame(() => {
                const panelEase = 'all 0.72s cubic-bezier(0.22, 1, 0.36, 1)';
                if (leftPanel) {
                    leftPanel.style.transition = panelEase;
                    leftPanel.style.left = '8px';
                    leftPanel.style.top = `${navH + 8}px`;
                    leftPanel.style.width = `${dualDrawerW}px`;
                    leftPanel.style.height = `${winH - navH - 16}px`;
                }
                if (bottomBar) {
                    bottomBar.style.transition = 'transform 0.32s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.25s ease';
                    bottomBar.style.transform = 'translateY(125%)';
                    bottomBar.style.opacity = '0';
                    bottomBar.style.pointerEvents = 'none';
                }
                if (hudOverlay) {
                    hudOverlay.style.transition = 'opacity 0.2s ease';
                    hudOverlay.style.opacity = '0';
                }
            });
        }

        function finishEnterSingleView() {
            const leftPanel = document.querySelector('aside.hud-panel');
            const bottomBar = document.querySelector('.target-readout-bar');
            const hudOverlay = document.querySelector('.globe-hud-overlay');
            const viewport = document.querySelector('.globe-viewport');

            if (leftPanel) {
                leftPanel.style.position = '';
                leftPanel.style.top = '';
                leftPanel.style.left = '';
                leftPanel.style.width = '';
                leftPanel.style.height = '';
                leftPanel.style.zIndex = '';
                leftPanel.style.transition = '';
            }
            if (bottomBar) {
                bottomBar.style.position = '';
                bottomBar.style.top = '';
                bottomBar.style.left = '';
                bottomBar.style.width = '';
                bottomBar.style.height = '';
                bottomBar.style.zIndex = '';
                bottomBar.style.transition = '';
                bottomBar.style.transform = '';
                bottomBar.style.opacity = '';
            }
            if (hudOverlay) {
                hudOverlay.style.transition = '';
                hudOverlay.style.opacity = '';
            }
            if (viewport) {
                viewport.style.position = '';
                viewport.style.top = '';
                viewport.style.left = '';
                viewport.style.width = '';
                viewport.style.height = '';
                viewport.style.zIndex = '';
            }
            globeGroup.position.set(0, 0, 0);
            globeGroup.scale.setScalar(1);
            dualTrans = null;
            resizeGlobe();
        }

        (function initEnterSingleTransition() {
            let raw = null;
            try {
                raw = sessionStorage.getItem('paf_view_transition');
                if (raw) sessionStorage.removeItem('paf_view_transition');
            } catch (e) {}
            if (!raw || window.innerWidth <= 1024) return;

            let data = null;
            try { data = JSON.parse(raw); } catch (e) {}
            if (!data) return;

            if (data.dir === 'from_results') {
                const elapsedRes = Math.max(0, Date.now() - (data.startEpoch || Date.now()));
                if (elapsedRes > 2500) return;

                const lat = parseFloat(document.getElementById('input-lat').value) || 0;
                const lon = parseFloat(document.getElementById('input-lon').value) || 0;
                const pt = latLonToVector3(lat, lon, 1.0);
                globeGroup.rotation.y = Math.atan2(-pt.x, pt.z);
                globeGroup.rotation.x = Math.atan2(pt.y, Math.hypot(pt.x, pt.z));
                camera.position.z = 1.75;
                pauseAutoRotate(1200);

                const navbar = document.querySelector('.navbar');
                const leftPanel = document.querySelector('aside.hud-panel');
                const bottomBar = document.querySelector('.target-readout-bar');
                const hudOverlay = document.querySelector('.globe-hud-overlay');

                document.body.style.opacity = '0';
                if (navbar) {
                    navbar.style.transform = 'translateY(-100%)';
                    navbar.style.opacity = '0';
                }
                if (leftPanel) {
                    leftPanel.style.transform = 'translateX(-110%)';
                    leftPanel.style.opacity = '0';
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
                    const ease = 'transform 0.65s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.5s ease';
                    [navbar, leftPanel, bottomBar, hudOverlay].forEach(el => {
                        if (!el) return;
                        el.style.transition = ease;
                        el.style.transform = 'translate(0, 0)';
                        el.style.opacity = '1';
                    });
                    setTimeout(() => {
                        document.body.style.transition = '';
                        document.body.style.opacity = '';
                        [navbar, leftPanel, bottomBar, hudOverlay].forEach(el => {
                            if (!el) return;
                            el.style.transition = '';
                            el.style.transform = '';
                            el.style.opacity = '';
                        });
                    }, 680);
                });
                return;
            }

            if (data.dir !== 'to_single') return;

            const elapsed = Math.max(0, Date.now() - (data.startEpoch || Date.now()));
            if (elapsed > 2200) return;

            if (typeof data.rotX === 'number' && typeof data.rotY === 'number') {
                globeGroup.rotation.x = data.rotX;
                globeGroup.rotation.y = data.rotY;
            }

            const progress0 = Math.min(0.75, elapsed / (data.duration || 720));
            const eased0 = 1 - Math.pow(1 - progress0, 3);
            const remaining = Math.max(300, (data.duration || 720) - elapsed);

            const navbar = document.querySelector('.navbar');
            const leftPanel = document.querySelector('aside.hud-panel');
            const bottomBar = document.querySelector('.target-readout-bar');
            const hudOverlay = document.querySelector('.globe-hud-overlay');
            const viewport = document.querySelector('.globe-viewport');

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

            const startCenterX = dualCenterX + (singleCenterX - dualCenterX) * eased0;
            const startCenterY = dualCenterY + (singleCenterY - dualCenterY) * eased0;
            const startRadiusPx = dualRadiusPx + (singleRadiusPx - dualRadiusPx) * eased0;

            const br = bottomBar ? bottomBar.getBoundingClientRect() : null;

            if (leftPanel) {
                const curL = 8 + (16 - 8) * eased0;
                const curT = (navH + 8) + ((navH + 16) - (navH + 8)) * eased0;
                const curW = dualDrawerW + (370 - dualDrawerW) * eased0;
                const curH = (winH - navH - 16) + ((winH - navH - 32) - (winH - navH - 16)) * eased0;
                leftPanel.style.position = 'fixed';
                leftPanel.style.left = `${curL}px`;
                leftPanel.style.top = `${curT}px`;
                leftPanel.style.width = `${curW}px`;
                leftPanel.style.height = `${curH}px`;
                leftPanel.style.zIndex = '25';
            }
            if (bottomBar && br) {
                bottomBar.style.position = 'fixed';
                bottomBar.style.top = `${br.top}px`;
                bottomBar.style.left = `${br.left}px`;
                bottomBar.style.width = `${br.width}px`;
                bottomBar.style.height = `${br.height}px`;
                bottomBar.style.transition = 'none';
                bottomBar.style.transform = 'translateY(120%)';
                bottomBar.style.opacity = '0';
                bottomBar.style.zIndex = '25';
                void bottomBar.offsetHeight;
            }
            if (hudOverlay) {
                hudOverlay.style.opacity = '0';
            }
            if (navbar) navbar.style.zIndex = '30';

            if (viewport) {
                viewport.style.position = 'fixed';
                viewport.style.top = `${navH}px`;
                viewport.style.left = '0';
                viewport.style.width = `${winW}px`;
                viewport.style.height = `${vpH}px`;
                viewport.style.zIndex = '5';
            }

            renderer.setSize(winW, vpH);
            camera.aspect = winW / vpH;
            camera.position.set(0, 0, 3.45);
            camera.updateProjectionMatrix();

            const newWorldPerPx = (2 * 3.45 * Math.tan(vFov / 2)) / vpH;
            const vpCenterY = navH + vpH / 2;

            const startPosX = (startCenterX - winW / 2) * newWorldPerPx;
            const startPosY = -(startCenterY - vpCenterY) * newWorldPerPx;
            const startScale = (startRadiusPx * newWorldPerPx) / 1.12;

            const endPosX = (singleCenterX - winW / 2) * newWorldPerPx;
            const endPosY = -(singleCenterY - vpCenterY) * newWorldPerPx;
            const endScale = (singleRadiusPx * newWorldPerPx) / 1.12;

            globeGroup.position.set(startPosX, startPosY, 0);
            globeGroup.scale.setScalar(startScale);

            dualTrans = {
                mode: 'in',
                start: performance.now(),
                duration: remaining,
                startPosX, startPosY, startScale,
                endPosX, endPosY, endScale
            };
            // Safety net: the render loop normally finishes the transition, but browsers pause animation frames in
            // background tabs; never leave the panels pinned in their transition styles.
            setTimeout(() => { if (dualTrans && dualTrans.mode === 'in') finishEnterSingleView(); }, remaining + 500);

            requestAnimationFrame(() => {
                const easeStr = `all ${remaining}ms cubic-bezier(0.22, 1, 0.36, 1)`;
                if (leftPanel) {
                    leftPanel.style.transition = easeStr;
                    leftPanel.style.left = '16px';
                    leftPanel.style.top = `${navH + 16}px`;
                    leftPanel.style.width = '370px';
                    leftPanel.style.height = `${winH - navH - 32}px`;
                }
                if (bottomBar) {
                    bottomBar.style.transition = `transform ${Math.round(remaining * 0.95)}ms cubic-bezier(0.22, 1, 0.36, 1), opacity ${Math.round(remaining * 0.75)}ms ease`;
                    bottomBar.style.transform = 'translateY(0)';
                    bottomBar.style.opacity = '1';
                }
                if (hudOverlay) {
                    hudOverlay.style.transition = `opacity ${Math.round(remaining * 0.6)}ms ease ${Math.round(remaining * 0.35)}ms`;
                    hudOverlay.style.opacity = '1';
                }
            });
        })();

        function openResultsPage() {
            if (isDiving) return;
            const lat = parseFloat(document.getElementById('input-lat').value) || 0;
            const lon = parseFloat(document.getElementById('input-lon').value) || 0;
            const weights = getWeightsVector().map(w => w.toFixed(2)).join(',');
            const caves = document.getElementById('require-caves').checked ? '1' : '0';

            const params = new URLSearchParams({
                body: currentBody,
                lat: lat.toFixed(2),
                lon: lon.toFixed(2),
                w: weights,
                caves: caves,
                date: landingDate(),
                from: 'single'
            });
            diveUrl = `results.php?${params.toString()}`;

            // Prefetch results.php during the animation to minimise the black screen during the transition
            const prefetch = document.createElement('link');
            prefetch.rel = 'prefetch';
            prefetch.href = diveUrl;
            document.head.appendChild(prefetch);

            // Work out the target planet rotation so that the chosen (lat, lon) faces the camera
            const pt = latLonToVector3(lat, lon, 1.0);
            const desiredRotY = Math.atan2(-pt.x, pt.z);
            const horiz = Math.sqrt(pt.x * pt.x + pt.z * pt.z);
            const desiredRotX = Math.atan2(pt.y, horiz);

            let dy = (desiredRotY - globeGroup.rotation.y) % (Math.PI * 2);
            if (dy > Math.PI) dy -= Math.PI * 2;
            if (dy < -Math.PI) dy += Math.PI * 2;

            // Expand the planet viewport to the full screen (100vw x 100vh) without a jump in position or size
            const viewport = document.querySelector('.globe-viewport');
            const rect = viewport.getBoundingClientRect();
            const winW = window.innerWidth;
            const winH = window.innerHeight;

            diveStart = performance.now();
            diveStartCamX = camera.position.x;
            diveStartCamY = camera.position.y;
            diveStartZ = camera.position.z * (winH / rect.height);
            diveStartRotX = globeGroup.rotation.x;
            diveStartRotY = globeGroup.rotation.y;
            diveTargetRotX = desiredRotX;
            diveTargetRotY = globeGroup.rotation.y + dy;

            const dxPx = (rect.left + rect.width / 2) - (winW / 2);
            const dyPx = -((rect.top + rect.height / 2) - (winH / 2));
            const vFov = (camera.fov * Math.PI) / 180;
            const worldPerPx = (2 * diveStartZ * Math.tan(vFov / 2)) / winH;

            diveStartPosX = dxPx * worldPerPx;
            diveStartPosY = dyPx * worldPerPx;
            camera.position.z = diveStartZ;
            globeGroup.position.set(diveStartPosX, diveStartPosY, 0);

            // Save the current panel positions before .globe-viewport switches to position: fixed,
            // so that no container jumps in the page layout
            const navbar = document.querySelector('.navbar');
            const leftPanel = document.querySelector('aside.hud-panel');
            const bottomBar = document.querySelector('.target-readout-bar');
            const hudOverlay = document.querySelector('.globe-hud-overlay');

            [leftPanel, bottomBar].forEach(el => {
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

            isDiving = true;

            // Smoothly slide the containers off the screen edges (in the next frame)
            requestAnimationFrame(() => {
                const ease = 'transform 0.8s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.65s ease';
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
                if (leftPanel) {
                    leftPanel.style.transition = ease;
                    leftPanel.style.transform = 'translateX(-110%)';
                    leftPanel.style.opacity = '0';
                    leftPanel.style.pointerEvents = 'none';
                }
                if (hudOverlay) {
                    hudOverlay.style.transition = ease;
                    hudOverlay.style.transform = 'translateY(-20px)';
                    hudOverlay.style.opacity = '0';
                    hudOverlay.style.pointerEvents = 'none';
                }
            });
        }

        // Start the app + automatic recalculation after the coordinates change
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
                updateMarkerPosition(lat, lon);
                document.getElementById('readout-coords').innerText = `${lat.toFixed(1)}°, ${lon.toFixed(1)}°`;
                clearTimeout(coordsDebounce);
                coordsDebounce = setTimeout(() => {
                    triggerCharacterize();
                }, 200);
            };

            [latInput, lonInput].forEach(el => {
                el.addEventListener('input', handleCoordsInput);
                el.addEventListener('change', () => {
                    clearTimeout(coordsDebounce);
                    triggerCharacterize();
                });
            });

            triggerCharacterize();
        });
    </script>
    <?php include __DIR__ . '/site_picker.php'; ?>
    <?php include __DIR__ . '/param_tooltips.php'; ?>
</body>
</html>
