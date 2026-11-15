# Project Context – Planetary Analog Finder (NASA Space Apps 2026)

## 1. Project description and role
**Planetary Analog Finder** is an analysis and visualisation tool that searches Earth for the locations and the times of year (months) that best match a chosen point on the **Moon** or **Mars** physically, geologically and orbitally.

## 2. Art direction and design system (Minimalist Aerospace / Linear / SpaceX UI)

We are moving away from a "gamey", over-the-top sci-fi/cyberpunk style (no gaming fonts like *Orbitron*, no fake lasers, game-style corners or garish rainbow frames). We aim for a **mature, minimal, engineering-grade premium design** inspired by the interfaces of **SpaceX Crew Dragon, Linear.app, Vercel and NASA JPL Eyes**.

### Guiding principles:
1. **Minimalism and space (negative space):**
   * Clean geometry, plenty of breathing room around elements, thin dividers (`1px solid rgba(255, 255, 255, 0.07)`), no unnecessary ornament.
2. **Colour palette (Matte Obsidian & Precision Accents):**
   * **Base background:** deep, matte obsidian `#050507` and `#090A0F` (no loud gradients).
   * **Surfaces (cards / panels):** subtle, semi-transparent layers `rgba(17, 19, 24, 0.72)` with a soft `backdrop-filter: blur(20px)` and a thin `1px` border that lights up only on interaction.
   * **Text:**
     * Primary: `#F4F4F6` (clean, slightly broken white)
     * Secondary: `#8E929F` (cool, technical grey)
     * Labels / metadata: `#525665`
   * **Muted, precise light accents (only where they carry information):**
     * **Moon (Lunar Ice / Silver):** `#E2E8F0` and a cool, subtle blue `#60A5FA`
     * **Mars (Ember / Terracotta):** `#F97316` and a warm amber `#FB923C`
     * **Earth match indicator (Signal Emerald):** `#10B981`
3. **Typography (engineering precision):**
   * **Headings and UI:** *Inter* or *Plus Jakarta Sans* (weights `400`, `500`, `600`, tight kerning `letter-spacing: -0.03em`).
   * **Numbers, coordinates and telemetry:** *JetBrains Mono* (`font-variant-numeric: tabular-nums`) – guarantees perfectly aligned number columns and no jumping UI during animations.

---

## 3. Modern, subtle animation (High-Craft Motion)

Animations should feel like a precise scientific instrument:

1. **Realistic 3D lighting (Terminator & Fresnel Rim Glow):**
   * The Moon and Mars globes in Three.js are lit by directional sunlight with a clear day–night boundary (*terminator line*) and a subtle rim glow (*Fresnel shader*).
   * When hovering over a tile, the camera and the light source react smoothly, with *damped inertia*, to mouse movement, and the globe gently speeds up its rotation.
2. **Subtle edge spotlight (`1px Border Glow`):**
   * Instead of lighting up the whole tile, the cursor lights only the thin (`1px`) card edge plus a soft highlight where the pointer is (Linear / Vercel style).
3. **Smooth transition physics (`cubic-bezier(0.22, 1, 0.36, 1)`):**
   * All transitions (card changes, expanding parameters, updating charts and match bars) use soft easing curves.
4. **Data animation (`Tabular Number Transitions`):**
   * Smooth real-time (60 FPS) interpolation of numbers (e.g. `94.2%`) and match-bar widths while the weight sliders move.

---

## 4. Modern animation and micro-interactions (key priority)

1. **Dynamic theme transformation (`Moon` ↔ `Mars` ↔ `Earth`):**
   * Smooth change of the CSS variables (`--accent-glow`, `--accent-primary`) and the 3D scene lighting when switching globes.
2. **Scan effect after clicking coordinates (`lat`, `lon`):**
   * An animated ring / radar wave spreading from the clicked point on the Moon or Mars while `/api/v1/characterize` is queried.
3. **Telemetry counters (Scramble Text & Number Ticker):**
   * While the `features_raw` and `score` values load (e.g. `94.2% MATCH`), the digits count up smoothly or "decode" like a space terminal.
4. **Cascading entrances and spotlight hover:**
   * The Top candidate cards appear in a cascade (`staggered animation`), and on hover a neon glow follows the cursor (`radial-gradient` tracking `clientX/clientY`).
5. **Interactive weight sliders (`K_FEATURES`) with instant feedback:**
   * Moving a slider smoothly animates the radar chart and the match bar.

---

## 5. API contract (the 9 `K_FEATURES`)

The order of the features in the `features_norm` and `weights` arrays (indices `0..8`) is fixed across the whole system:

| Index | Key | Description | Unit |
| :--- | :--- | :--- | :--- |
| `0` | `temp_mean` | Mean surface temperature | `°C` |
| `1` | `temp_diurnal_amp` | Diurnal temperature range ($T_{\max} - T_{\min}$) | `°C` |
| `2` | `thermal_inertia` | Ground thermal inertia (loose dust vs solid rock) | $\text{J}\cdot\text{m}^{-2}\cdot\text{K}^{-1}\cdot\text{s}^{-1/2}$ |
| `3` | `surface_roughness` | Surface roughness (SAR / altimeter) | `m / index` |
| `4` | `soil_moisture` | Soil moisture / water-ice content | `%` |
| `5` | `dust_aerosol` | Atmospheric dust (AOD) | `dimensionless` |
| `6` | `solar_elevation_max` | Maximum daily Sun elevation | `°` (degrees) |
| `7` | `radiation_proxy` | Radiation exposure (elevation + UV) | `index` |
| `8` | `slope_deg` | Terrain slope | `°` (degrees) |

(Exact units and definitions as implemented: `3-charakteryzator/service/norm_ranges.json` and `3-charakteryzator/PARAMETERS.md`.)

### Endpoints your frontend talks to:
1. **`POST /api/v1/characterize`**
   * You send: `{"target_body": "moon" | "mars", "lat": -85.2, "lon": 31.4, "timestamp_iso": "2026-11-14T12:00:00Z"}`
   * You get: `features_raw` (to show in the HUD), `features_norm` (an array of 9 floats `[0..1]`), `nearest_skylight_km`.
2. **`POST /api/v1/search`**
   * You send: `{"features_norm": [...], "weights": [...], "require_caves": false, "top_k": 100}`
   * You get: `execution_time_ms`, `best_global_month`, `heatmap_base64` (a `1024x512` image laid over the Earth globe) and a list of `candidates` (the top locations on Earth with their `climatogram_12m`, `monthly_scores` and `features_raw_best_month`).

---

## 6. CSS organisation
* All `.php` files use one shared stylesheet, [1-webpage/style.css](1-webpage/style.css).
* For every new `.php` page, link `<link rel="stylesheet" href="style.css">` and add new classes to that file.

## 7. Licences
Record every source in `LICENCES.md` whenever we use something from the internet.
