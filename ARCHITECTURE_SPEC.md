# Technical Specification: Planetary Analog Finder (NASA Space Apps 2026)
**Challenge:** *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*

> This is the original architecture plan written at the start of the hackathon. Where the implementation differs,
> the component READMEs, `3-charakteryzator/PARAMETERS.md` and `LICENCES.md` describe what was actually built.

---

## 1. System goal and data flow
The system searches Earth for the locations and the times of year (months) that best match the physical, geological and lighting conditions of a chosen point on the Moon or Mars. The architecture relies on a two-stage search: a very fast global precomputed search in RAM, and an exact local lookup for the best candidates.

### Request flow:
1. The **client (browser)** sends the **Networker** an initial request: the chosen body (`moon` | `mars`), the coordinates (`lat`, `lon`), the target time and the parameter weight vector `weights` (values in `[0.0, 1.0]`).
2. The **Networker** queries the **Charakteryzator** internally (`POST /characterize`).
3. The **Charakteryzator** reads the point's physical parameters from local planetary maps (COG format) and astronomical models and returns a JSON object (`TargetProfile`).
4. The **Networker**:
   - Immediately sends the `TargetProfile` back to the **client** (via Server-Sent Events or a two-step REST call), so the interface can show the parameters of the chosen place on the Moon/Mars at once.
   - In parallel, forwards the `TargetProfile` together with the user's weights to the **Szukacz** (`POST /search`).
5. The **Szukacz** runs a vector operation in RAM over the precomputed Earth matrices (`.npy`), finds the Top 100 land locations and the best month of the year, and generates simplified match maps (heatmaps). For the best points it looks up details (e.g. Sun visibility and terrain shadows).
6. The **Networker** receives the result from the **Szukacz** and sends it to the **client**.

---

## 2. Technical rationale and low-level architecture decisions

### 2.1. Why a `.npy` land matrix (`mmap`) instead of full 4K images?
- **Cost of 4K maps:** a 4K equirectangular image ($4096 \times 2048$) has $8\,388\,608$ pixels ($33.55\text{ MB}$ in `float32`). With 240 yearly layers that is about $8\text{ GB}$ of data to crunch per query, and about 90% of those pixels are oceans and dense forests ($\text{NDVI} > 0.25$) that will never be an analog of the Moon or Mars.
- **Solution (Sparse Land Matrix):** oceans and forests are dropped during precomputing. About $400\,000$ active land cells remain. A NumPy tensor of shape `(400000, 12, 9)` in `float32` takes only about **$173\text{ MB}$** of RAM.
- **Memory mapping (`mmap_mode='r'`):** a `.npy` file is one contiguous C-array block. Opening it with `mmap` maps the file straight into the Linux kernel's **page cache**. The container starts in $0\text{ ms}$, and the CPU reads the data linearly at RAM bus speed ($\sim 40\text{ GB/s}$) using **SIMD (AVX2/AVX-512)** vector instructions. A query over the whole world and 12 months takes **under $15\text{ ms}$**.

### 2.2. Why Cloud-Optimized GeoTIFF (COG) for the Moon and Mars?
A COG file has an internal tile index (`256x256`). The `rasterio` library (GDAL) computes the exact byte offset on disk for the clicked point $(lat, lon)$ from the affine transform and does a single `pread()` (or a network `HTTP Range: bytes=start-end` request) of a few kilobytes. Reading all of a point's features from an NVMe disk takes **under $2\text{ ms}$**.

### 2.3. Parameter physics and algorithmic simplifications
- **Normalisation:** directly subtracting Earth and Moon temperatures ($-233^\circ\text{C}$ in polar craters vs. $-89^\circ\text{C}$ in Antarctica) would dominate the other features. All parameters in the search matrix are normalised with outlier clipping (`Clamping + Min-Max`) to the dimensionless range $[0, 1]$.
- **Sun angle and visibility:** the Sun's angle follows directly from orbital geometry (axial tilt: Earth $\pm 23.44^\circ$, Mars $\pm 25.19^\circ$, Moon $\pm 1.54^\circ$) and is computed analytically. Satellite data is used only for **cloud cover** (MODIS) and **mountain shadows** (raycasting over a DEM: 360 rays around the point looking for the maximum horizon elevation angle $\alpha(\phi) = \max_d \arctan(\frac{h(d) - h_0}{d})$).
- **Surface type (loose/hard):** represented physically by **thermal inertia**, derived from the diurnal temperature range $\Delta T = T_{\text{day}} - T_{\text{night}}$ (loose dust heats and cools fast, solid rock slowly), and by SAR radar backscatter (surface roughness).
- **Cosmic radiation:** on the Earth's surface it depends on the thickness of the atmospheric column overhead – computed as a function of elevation from the DEM and the UV index.
- **Caves (lava tubes):** treated as a point layer (distance in km to the nearest catalogued lava tube / volcanic cave), not as a continuous heatmap.

---

## 3. Infrastructure and repository structure (Docker Compose + VPS)
Everything runs on a single Linux VPS under Docker Compose. Traffic from the domain goes to the `networker` container. All containers share the `/data` volume (mounted `read-only` for the API services).

```text
/
├── docker-compose.yml
├── ARCHITECTURE_SPEC.md
├── data/                      # Shared data volume (.npy, .tif, .parquet)
│   ├── moon/
│   ├── mars/
│   └── earth/
├── 1-frontend/                # Web app (PHP 8 + HTML5/CSS3/JS + Three.js + C++/Wasm)  [built as 1-webpage/]
├── 2-networker/               # API gateway and reverse proxy to 1-frontend
├── 3-charakteryzator/         # Moon and Mars feature extraction service
├── 4-szukacz/                 # Earth vector search engine
└── 5-precomputer/             # ETL scripts that prepare the data (and, originally, the mocks)
```

---

## 4. Precomputed data format (the `/data` volume)

### 4.1. Earth data (`/data/earth/`) – for the Szukacz
1. `earth_features_norm.npy`:
   - Type: `float32`, C-contiguous memory layout (`mmap_mode='r'`).
   - Shape: `(N_POINTS, 12, K_FEATURES)`, where `N_POINTS` (~400,000) are land cells, `12` are the months (`0..11`) and `K_FEATURES` (`9`) are the normalised features `[0.0, 1.0]`.
2. `earth_features_raw.npy`:
   - Type: `float32`, shape `(N_POINTS, 12, K_FEATURES)`.
   - Real physical values (°C, m, %) for drawing climatograms and showing statistics in the UI.
3. `earth_metadata.parquet` (or a structured `.npy`):
   - Columns for every index `i` (`0..N_POINTS-1`):
     - `id` (`int32`), `lat` (`float32`), `lon` (`float32`),
     - `px_x` (`int32`), `px_y` (`int32`) – coordinates on the `1024x512` grid for fast heatmap projection,
     - `elevation_m` (`float32`), `nearest_cave_km` (`float32`).

### 4.2. Feature dictionary (`K_FEATURES`) – indices of axis `2`:
Every component of the system uses the same feature order:
- `0`: `temp_mean` – Mean surface temperature [$^\circ\text{C}$]
- `1`: `temp_diurnal_amp` – Diurnal temperature range $T_{\text{max}} - T_{\text{min}}$ [$^\circ\text{C}$]
- `2`: `thermal_inertia` – Ground thermal inertia [$\text{J}\cdot\text{m}^{-2}\cdot\text{K}^{-1}\cdot\text{s}^{-1/2}$]
- `3`: `surface_roughness` – Surface roughness from SAR radar / altimeter [m / index]
- `4`: `soil_moisture` – Soil moisture / water-ice content [%]
- `5`: `dust_aerosol` – Atmospheric dust / aerosol optical depth (AOD) [dimensionless]
- `6`: `solar_elevation_max` – Maximum daily Sun elevation above the horizon [degrees]
- `7`: `radiation_proxy` – Radiation exposure (function of elevation and UV) [index]
- `8`: `slope_deg` – Terrain slope [degrees]

### 4.3. Moon and Mars data (`/data/moon/`, `/data/mars/`) – for the Charakteryzator
A set of Cloud-Optimized GeoTIFF files (`.tif`) with internal tiling (`TILED=YES`, `BLOCKXSIZE=256`, `BLOCKYSIZE=256`).

---

## 5. Work split across 5 people (component specs and API contracts)

### Component 1: Frontend (`1-frontend`)
- **Stack:** PHP 8.x + HTML5 / modern CSS (neon dark UI + animations), vanilla JS (ES modules) + Three.js (WebGL) + Chart.js (from a CDN/locally) + an optional **C++ module (WebAssembly / Emscripten or a CLI binary)** for fast computation on the client/UI-server side.
- **Compatibility with the rest of the system:** full. Communication with the rest of the team happens only through the standard JSON contracts (`POST /api/v1/characterize` and `POST /api/v1/search`), regardless of the view being built in PHP and HTML instead of Vite/TypeScript.
- **Tasks:**
  1. A modular PHP interface template (`index.php` + PHP components for the `K_FEATURES` slider panel, candidate cards, NASA mission presets and comparison views).
  2. 3D globe visualisation in Three.js (switching Moon / Mars / Earth) with modern transition animations and a dark, neon HUD style.
  3. Picking a point on the Moon/Mars -> querying the API (`fetch` from JS or a PHP proxy to the `networker`) -> showing the features read by the `Charakteryzator`.
  4. A panel of `[0.0 - 1.0]` weight sliders for the `K_FEATURES` and a cave filter.
  5. Rendering the returned heatmap on the Earth globe (`heatmap_base64` as a `THREE.Texture` / `THREE.DataTexture`) plus pins for the Top 100 places.
  6. **Role of C++ (bonus / high-performance UI):**
     - **Option A (C++ -> WebAssembly via Emscripten):** instant real-time re-weighting (60 FPS while moving a slider, without waiting for the network) for the loaded Top 100 candidates, generating a 3D terrain mesh (DEM mesh) or simulating the Sun angle and horizon shadows directly in the browser.
     - **Option B (native C++ micro-module called from PHP):** very fast horizon-profile generation / geometric analysis or image-buffer processing inside the `1-frontend` container.
  7. Candidate detail view: satellite imagery (WMS Sentinel-2 / NASA GIBS), 12-month climatogram, Sun-angle and horizon-profile visualisation.

### Component 2: Networker (`2-networker`)
- **Stack:** Nginx + Python (FastAPI + async `httpx`) or Go (Fiber).
- **Ports:** external `80`/`443` -> internal `8000` (API), plus a proxy to the `1-frontend:80` container (PHP/Apache).
- **Tasks:**
  1. Routing web traffic (`/`) to the `1-frontend` container (or serving the generated assets).
  2. Orchestrating requests between the client, the `charakteryzator` (`http://charakteryzator:8001`) and the `szukacz` (`http://szukacz:8002`).
- **Public endpoints:**
  - `POST /api/v1/characterize` -> returns the `TargetProfile`.
  - `POST /api/v1/search` -> takes the `TargetProfile` + `weights`, returns the `Szukacz` result.

### Component 3: Charakteryzator (`3-charakteryzator`)
- **Stack:** Python 3.12, FastAPI, `rasterio`, `numpy`, `ephem` / `astropy`.
- **Internal port:** `8001`.
- **Tasks:**
  1. Reading pixel values from the COG files in `/data/moon/` or `/data/mars/` for the given `(lat, lon)`.
  2. Computing the Sun's angle for the given time.
  3. Returning the physical values (`features_raw`) and the values normalised to the Earth scale (`features_norm`).
- **API contract (`POST /characterize`):**
```json
// Request:
{
  "target_body": "moon",
  "lat": -85.2,
  "lon": 31.4,
  "timestamp_iso": "2026-11-14T12:00:00Z"
}

// Response:
{
  "target_body": "moon",
  "coordinates": {"lat": -85.2, "lon": 31.4},
  "features_raw": {
    "temp_mean": -180.5,
    "temp_diurnal_amp": 45.0,
    "thermal_inertia": 55.0,
    "surface_roughness": 0.35,
    "soil_moisture": 2.1,
    "dust_aerosol": 0.0,
    "solar_elevation_max": 4.8,
    "radiation_proxy": 1.0,
    "slope_deg": 7.2
  },
  "features_norm": [0.0, 0.85, 0.12, 0.40, 0.02, 0.0, 0.05, 1.0, 0.16],
  "nearest_skylight_km": 14.2
}
```

### Component 4: Szukacz (`4-szukacz`)
- **Stack:** Python 3.12, FastAPI, `numpy`, `numba`, `pillow` / `rasterio`.
- **Internal port:** `8002`.
- **Tasks:**
  1. Mapping the `.npy` matrices from `/data/earth/` into RAM at start-up.
  2. Vectorised match computation for all points $n$ and months $m$:
     $$\text{Score}(n, m) = 1 - \frac{\sum_{k} w_k \cdot |X_{n, m, k} - y_k|}{\sum_{k} w_k}$$
  3. Choosing the best month for each point, picking the Top 100 candidates and projecting the results onto a `1024x512` bitmap (`uint8` WebP/PNG in Base64).
  4. For the Top 5–10 candidates: fast raycasting on a local DEM tile to return the profile of mountains blocking the Sun.
- **API contract (`POST /search`):**
```json
// Request:
{
  "features_norm": [0.0, 0.85, 0.12, 0.40, 0.02, 0.0, 0.05, 1.0, 0.16],
  "weights": [1.0, 0.5, 0.8, 0.4, 0.9, 0.2, 1.0, 0.3, 0.5],
  "require_caves": false,
  "top_k": 100
}

// Response:
{
  "execution_time_ms": 14.2,
  "best_global_month": 7,
  "heatmap_base64": "data:image/webp;base64,UklGR...",
  "candidates": [
    {
      "rank": 1,
      "id": 104921,
      "lat": -77.55,
      "lon": 161.80,
      "name_hint": "McMurdo Dry Valleys, Antarctica",
      "score": 0.942,
      "best_month": 7,
      "monthly_scores": [0.61, 0.65, 0.78, 0.85, 0.91, 0.93, 0.94, 0.92, 0.84, 0.72, 0.64, 0.60],
      "features_raw_best_month": {
        "temp_mean": -58.2,
        "temp_diurnal_amp": 12.0,
        "thermal_inertia": 85.0,
        "surface_roughness": 0.31,
        "soil_moisture": 1.5,
        "dust_aerosol": 0.02,
        "solar_elevation_max": 0.0,
        "radiation_proxy": 0.78,
        "slope_deg": 6.5
      },
      "climatogram_12m": {
        "temp_mean": [-15.2, -22.1, -35.0, -45.2, -52.0, -55.1, -58.2, -56.0, -48.1, -36.0, -24.0, -16.1],
        "soil_moisture": [3.1, 2.8, 2.1, 1.8, 1.6, 1.5, 1.5, 1.5, 1.7, 2.0, 2.5, 3.0]
      },
      "nearest_cave_km": 42.0
    }
  ]
}
```

### Component 5: Precomputer (`5-precomputer`)
- **Stack:** Python 3.12, `earthaccess`, `xarray`, `rasterio`, `scipy`, `pyarrow`.
- **Tasks:**
  1. **PRIORITY 0 (first 15 minutes of the hackathon):** write and run a `generate_mock_data.py` script that produces synthetic `.npy`, `.parquet` and `.tif` files with the target shapes and structure. This lets the other 4 people test their containers immediately.
  2. Download real satellite data from the space agencies' APIs, apply a land mask ($\text{NDVI} < 0.25$), normalise, and overwrite the mock files with the real matrices.

---

## 6. Catalogue of space-agency resources (what we take from them and how we connect)

### 6.1. NASA resources – Earth
1. **NASA Earthdata Search (`earthaccess` / CMR API / Harmony API):**
   - *Physics:* measurements of reflected and emitted radiation (infrared, microwave, laser).
   - *What we download:* monthly MODIS Land Surface Temperature products (day/night temperature, for thermal inertia), SMAP Soil Moisture, MODIS Aerosol Optical Depth (atmospheric dust), MODIS NDVI (vegetation mask). Formats: HDF5, NetCDF, Cloud-Optimized GeoTIFF (streamed from AWS S3).
2. **NASA Worldview (GIBS API – WMTS/WMS):**
   - *Physics:* ready-made, coloured map tiles rendered from raw satellite data.
   - *What we download:* image tiles loaded directly in the frontend to visualise chosen locations and to quickly preview ice cover and dust storms.

### 6.2. NASA resources – Moon and Mars
3. **NASA Planetary Data System – PDS (PDS API / NASA Trek WMTS):**
   - *Physics:* archive of telemetry and readings from orbiter and rover instruments (PDS4 standard).
   - *What we download:* global Mars elevation maps (MOLA DEM), thermal inertia (TES/THEMIS) and high-resolution images (HiRISE), converted to COG for the `Charakteryzator`.
4. **NASA Lunar Reconnaissance Orbiter – LRO:**
   - *Physics:* a set of sensors in a low polar orbit around the Moon:
     - **LROC:** optical cameras (resolution down to $0.5\text{ m/px}$, polar illumination maps).
     - **LOLA:** a laser altimeter timing the pulse return – provides an accurate DEM terrain model, slopes and roughness.
     - **LEND:** a neutron detector – measures the drop in fast neutrons knocked out by cosmic rays, which indicates hydrogen nuclei (water ice) in the top metre of regolith.
     - **Mini-RF:** an S/X-band SAR radar analysing the polarisation of the reflected wave (tells rock from subsurface ice).
5. **NASA LRO Diviner Lunar Data:**
   - *Physics:* a 9-channel infrared radiometer measuring the ground's thermal emission.
   - *What we download:* global maps of the Moon's minimum/maximum temperatures (including extremely cold polar craters at $\sim 40\text{ K}$) and regolith thermal inertia (`Polar Resource Products`).

### 6.3. CSA resources (Canadian Space Agency)
6. **RADARSAT Constellation Mission (RCM) & RADARSAT-1 (STAC API / AWS):**
   - *Physics:* an active C-band synthetic aperture radar (SAR) ($5.405\text{ GHz}$). It sends its own microwave beam through clouds and at night; the strength and polarisation of the return depend on geometric roughness and soil moisture.
   - *What we download:* radar images (GeoTIFF) to derive the `surface_roughness` parameter and the ice structure in Earth's polar regions.
7. **SAR Python Tutorial:**
   - *Use:* ready Python code showing how to download RADARSAT tiles with `HTTP Range Requests`, apply radiometric calibration and filter speckle noise.

### 6.4. ESA resources (European Space Agency)
8. **Copernicus Data Space Ecosystem – CDSE (Sentinel Hub API / openEO / STAC):**
   - *Physics:* the Sentinel-1 constellation (C-band SAR radar) and Sentinel-2 (a multispectral camera with 13 optical and near-infrared bands).
   - *What we download:* the global **Copernicus DEM** elevation model (for slopes, radiation exposure and horizon shadows), the **WorldCover** land-cover map (to exclude water, cities and forests) and cloud-free Sentinel-2 optical images for the Top 100 candidates.
9. **ESA Open Science Catalog (EarthCODE):**
   - *What we download:* ready, aggregated geophysical datasets (cryosphere, soil moisture) and processing notebooks.

### 6.5. JAXA resources (Japan Aerospace Exploration Agency)
10. **JAXA G-Portal (OpenSearch API / HDF5 / GeoTIFF):**
    - *Physics:* microwave radiometers (AMSR2 on GCOM-W), optical sensors (SGLI on GCOM-C) and an **L-band** SAR radar (ALOS/ALOS-2 – a $\sim 23\text{ cm}$ wave that penetrates deeper into dry sand and ice than C-band, reflecting off hard bedrock).
    - *What we download:* ready level-3 monthly statistics (land surface temperature LST, snow water equivalent, L-band ground roughness).
