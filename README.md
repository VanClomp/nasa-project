# Planetary Analog Finder

**NASA Space Apps 2026** — *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*

Planetary Analog Finder is an interactive web platform that matches any location and mission date on the **Moon** or **Mars** with its closest geological, environmental, and lighting **analogs on Earth** using 9-dimensional satellite feature vectors.

---

## Key Features

- **Dual & Single 3D Globe Views (`1-webpage/`)**
  - **Target selection (`index.php`)**: Interactive 3D Moon and Mars preview cards with orbital/instrument metadata.
  - **Dual view (`dual.php`, default)**: Side-by-side 3D Moon/Mars and Earth globes. Clicking any point or selecting a landing site preset updates the target characterization and refreshes analog pins on Earth in real time.
  - **Single view (`explorer.php`)**: Full-screen target globe with parameter weights, data-source badges, and bottom telemetry readout.
  - **Analysis results (`results.php`)**: Detailed Earth analog ranking, interactive pin selection synced with the candidate list, 9-axis radar comparison, 12-month climatograms, and time-varying `p(t)` charts.
  - **About Us (`aboutus.php`)**: Team and project overview page.
- **9-Dimensional Feature Matching**
  - Evaluates `temp_mean`, `temp_diurnal_amp`, `thermal_inertia`, `surface_roughness`, `soil_moisture`, `dust_aerosol`, `solar_elevation_max`, `radiation_proxy`, and `slope_deg`.
  - User-adjustable weights (`0.0 – 1.0`), parameter info tooltips, and per-feature data provenance badges (`measured`, `local model`, `global model`, `no data`).
  - Optional filter for nearby catalogued caves / lava tubes (`< 15 km`).
- **Date-Dependent Modeling & Fast Vector Search**
  - Computes seasonal and solar-geometry changes for any chosen landing date (`UTC`).
  - Searches precomputed Earth land matrices via `mmap` in RAM (`4-szukacz`), returning diverse Top-K (up to 300) analog sites and match error maps.

---

## Architecture

The system runs as four containerized services orchestrated by `docker-compose.yml`:

```text
Browser ──▶ networker (Nginx :80/:443 + FastAPI gateway)
               ├── /              ──▶ frontend (PHP 8.3 + Apache, 1-webpage/)
               ├── /api/v1/characterize ──▶ charakteryzator (:8001)
               └── /api/v1/search, /error-map ──▶ szukacz (:8002)
```

### Repository Structure

| Path | Description |
| :--- | :--- |
| `1-webpage/` | Frontend application (`index.php`, `dual.php`, `explorer.php`, `results.php`, `aboutus.php`, `style.css`, `feature_info.js`, `site_picker.php`, `param_tooltips.php`, `progress_bar.php`) |
| `2-networker/` | Nginx reverse proxy and FastAPI API gateway (`api.py`, `precomputed_sites.py`, `regions.py`) |
| `3-charakteryzator/` | Moon & Mars site characterization service, station/orbital models, and `PARAMETERS.md` |
| `4-szukacz/` | Vector search engine over memory-mapped Earth feature matrices (`szukacz/data.py`, `szukacz/scoring.py`) |
| `5-precomputer/` | ETL scripts (`fetch_earth.py`, `build_earth.py`) for preparing Earth `.npy` matrices |
| `data/` | Shared read-only data volume (`/data/earth`, `/data/mars`, `/data/moon`) |
| `images/` | Surface textures used by the 3D globes |
| `ARCHITECTURE_SPEC.md` | Technical architecture and data-format specification |
| `LICENCES.md` | Data and software attribution & licenses |

---

## Quick Start

### Run with Docker Compose

From the `nasa-project/` directory (where `docker-compose.yml` is located):

```bash
docker compose up --build
```

Once running, open `http://localhost` in your browser.

- **HTTPS setup (production)**: see `deploy_gcp.sh` and `enable_https.sh`.
- **Standalone frontend preview**: `1-webpage/explorer.php` includes a built-in PHP mock fallback for local UI testing when backend services are not running (`php -S localhost:8080 -t 1-webpage`).

### API Endpoints (`2-networker`)

- `POST /api/v1/characterize` — Characterizes a `(target_body, lat, lon, timestamp_iso)` point (and optional 12-month `series`).
- `POST /api/v1/search` — Finds diverse Top-K Earth analogs and match maps for a normalized feature vector and weights.
- `POST /api/v1/error-map` — Returns a zoomed match error map around a specified region.
- `GET /api/v1/health` — Checks health of `charakteryzator` and `szukacz`.

### Running Tests

```bash
# Networker tests
pytest 2-networker/tests

# Szukacz tests
pytest 4-szukacz/tests
```

---

## Team

Built by first-year students of **Computer Science, Mathematics, Physics, and Geology** at the **University of Warsaw**:

- Adam
- Antoni
- Franek
- Krzysiu
- Mikołaj

---

## Documentation & Licenses

- [ARCHITECTURE_SPEC.md](ARCHITECTURE_SPEC.md) — System design and precomputed data formats
- [3-charakteryzator/PARAMETERS.md](3-charakteryzator/PARAMETERS.md) — Physical meaning and time dependence of all 9 parameters
- [LICENCES.md](LICENCES.md) — Dataset citations and third-party licenses
