# Mars and Moon site characterization (Component 3, Charakteryzator)

Goal: characterize known and candidate Mars landing sites and Moon base sites (atmosphere, surface, terrain,
sunlight, water), for any date, and hand the features to the Earth analog search.

## Start here
- `model/mars_site_conditions_v2.html`  open in a browser: coverage table, seasonal charts and full record per site
- `outputs/coverage.csv`                Full / Partial / Missing for every site and parameter, with the reason
- `outputs/site_summary.csv`            one row per site and parameter, with where the value came from

## Folder layout
- `data/`            raw downloads from the PDS Atmospheres Node, one subfolder per dataset
- `pathfinder_met/`  raw Pathfinder tables (downloaded first, kept where they landed)
- `outputs/`         processed tables
  - `<station>_daily.csv`, `_hourly.csv`, `_seasonal.csv`, `_diurnal_by_season.csv` for vl1, vl2, pathfinder,
    phoenix, curiosity, insight, perseverance
  - `station_series.csv`            all stations in 15-degree Ls bins
  - `site_seasonal_estimates.csv`   all 12 sites: estimated pressure, optical depth, sunlight by season
  - `tes_dust_climatology.csv`, `site_dust_by_season.csv`   dust from orbit (MGS TES, Mars years 24-27)
  - `site_map_values.csv`, `site_gcm_ground_temperature.csv`   Viking-era maps and 1996 Ames climate model at each site
  - `pressure_reference_vl1.csv`, `pressure_model_validation.csv`, `dust_validation.csv`   checks
  - `page_data.json`                everything the page uses
- `scripts/`
  - `fetch_*.sh`        download scripts (run in Terminal); `fetch_gap_fill.sh` has NOT been run yet
  - `reduce_*.py`       raw tables -> per-sol and per-hour tables, one per station
  - `extract_orbital.py`  dust, maps and climate model at each site
  - `build_summary.py`  cross-site tables, coverage, page data (rerun after adding data)
  - `marslib.py`, `solar.py`  shared site list, Mars time and sunlight model
- `model/`           the interactive pages (v1: physics only; v2: built from the data)

## Status (14 Nov 2026)
- Seven stations reduced. Full-year coverage: Viking 2, Curiosity, and Viking 1 for pressure.
- Gap fill done: Perseverance air temperature and InSight now cover all 12 Mars months.
- Geology done: MOLA terrain, TES thermal inertia and albedo, Odyssey water and neutron maps, OMEGA/CRISM hydrated minerals.
- Still missing: cave catalog (USGS server unreachable; download by hand into data/geology/caves), rock abundance, global wind.
- To rebuild after new data: run the relevant `reduce_*.py`, then `extract_orbital.py`, then `build_summary.py`.
- Moon done: LOLA terrain and polar illumination / Earth visibility, Diviner polar temperatures and ice depth, Diviner rock
  abundance, Lunar Prospector hydrogen and FeO/TiO2, LROC pit atlas; 24 sites in `outputs/moon_sites.json`.


## Setting up after cloning
The raw data is not in the repository (4 GB). The characterizer needs the geology maps (~320 MB):
```
pip3 install -r requirements.txt
bash scripts/fetch_geology.sh && bash scripts/fetch_extra.sh     # Mars
bash scripts/fetch_moon.sh                                         # Moon (2.8 GB)
```
The first Moon request near a pole grids the 600 MB Diviner polar tables into `data/moon/diviner/prp_*_grid500m_v3.npz`
(11 MB each, a few seconds). In Docker, where `/data` is read-only, put those two .npz files into `/data/moon/diviner/` first;
the two `.tab` tables are then not needed.
The station tables it uses are already in `outputs/`; the other `fetch_*.sh` scripts are only needed to rebuild them.

## Characterizer: JSON in, JSON out (Mars and Moon)
```
python3 scripts/characterize.py examples/request_example.json -o examples/response_example.json
python3 scripts/characterize.py --all-sites -o outputs/mars_sites.json      # the 12 known sites
python3 scripts/characterize.py --all-sites --body moon -o outputs/moon_sites.json   # the 24 Moon sites
python3 scripts/characterize.py examples/request_moon_example.json          # one Moon point for one date
```
From Python (e.g. inside the team's API service): `from characterize import handle; handle(request_dict)`.

With a `timestamp_iso` the answer is one flat record for that date (`values`, `measured`, `units`); add `"detail": "full"` for all 12 months.
Request: `{"target_body": "mars", "lat": .., "lon": .., "timestamp_iso": ..}` (spec form) or
`{"target_body": "mars", "points": [{"id": .., "lat": .., "lon": .., "months": [..]}], "site_radius_km": 10}`.
Longitude east, -180..180 or 0..360.

Response per point: `site` (if within site_radius_km of a known landing site), `current` (Mars month for the timestamp),
`weights` (importance 0-1 per spec feature, with rationale), `static` (terrain, surface, water, minerals, caves),
`months` 1-12 (Mars months of 30 deg Ls) each with `params`, `storm_year`, and `target_profile`
(spec Component 3 features in spec order and units + `features_measured` yes/no).
Every parameter: `{value, low, high, unit, measured, source}`; `measured` = true for data taken at that place
(station record, orbital map at that point, exact geometry), false for the global predictor.

### Global predictor and its checks
- Pressure: Viking 1 seasonal curve moved to MOLA elevation; 2.3% rms vs six stations.
- Dust: MGS TES zonal climatology (typical year and 2001 storm year), scaled to local pressure.
- Ground temperature: surface energy balance + heat conduction (albedo, thermal inertia, dust, pressure);
  one coefficient calibrated on Curiosity, tested on Perseverance: rms 5-6 K.
- Air temperature: linear link to modelled ground, fitted on 7 stations; leave-one-station-out rms mostly 3-10 K
  (worst: Viking 1 and Curiosity daytime maxima, ~14 K). Polar and high-elevation points are flagged as extrapolated.
- Wind: stations only (null elsewhere). Caves: null until the USGS catalog is in data/geology/caves.

### Moon: base suitability first
Same schema (`{value, low, high, unit, measured, source}`, `measured` yes/no). Without a date: 12 records (15th of each month);
with a date: one flat record. Each point gets a **base-suitability score 0-100**: weighted mean of
power 0.25 (sunlit fraction incl. terrain shadows, best spot within 1 km), water 0.20 (distance to ground where ice is stable
within 1 m), communication 0.15 (Earth visible fraction), terrain 0.15 (slope, relief), thermal 0.10, ISRU oxygen 0.10
(FeO, TiO2), shelter 0.05 (distance to a lava-tube pit). Weights in `moon_model.BASE_WEIGHTS`.
- Measured (true): LOLA elevation/slope/relief and 18.6-year sun and Earth visibility (Mazarico et al. 2011, poleward of 65 deg),
  Diviner polar annual mean/max temperature and ice depth (76-90 deg), Diviner rock abundance (60S-60N),
  Lunar Prospector hydrogen and oxides, LROC pits, ephemeris (sun/Earth elevation, noon sun, flux).
- Predicted (false): flat-ground regolith heat model (Hayne et al. 2017 parameters; equator 94-385 K vs ~95-390 K measured),
  thermal inertia from rock abundance, polar night temperature.
- Spec features: temp_mean in deg C, dust_aerosol 0 and radiation_proxy 0 (no atmosphere), soil_moisture null
  (use ice_depth / ice_within_1m_fraction / hydrogen_index instead).
- Sites (`scripts/moon_sites.py`): 9 Artemis III regions, Shackleton ridge, Apollo 11-17, Chang'e 3-6, Chandrayaan-3, 3 pits.
  Regions without published coordinates are moved to the best-lit spot with slope <= 8 deg and Earth >= 0.3 within 8 km
  (`refined_from` keeps the original); published points stay, with the best spot nearby in `best_nearby`.
- Known limits: polar temperatures are annual values, not a day-by-day cycle among shadows; sun/Earth fractions are
  long-term averages (not month by month); the norm ranges in `service/norm_ranges.json` were set for Mars/Earth, so lunar
  temp_mean and temp_diurnal_amp hit 0 / 1 - agree Moon ranges with Component 5.

### Scripts added in this stage
`reduce_gapfill.py` (Perseverance air, InSight TWINS), `mars_maps.py` (map lookups), `mars_climate.py` (pressure, dust,
thermal model), `calibrate_thermal.py`, `calibrate_air.py`, `mars_model.py` (monthly records, weights), `characterize.py` (JSON I/O).
Moon: `fetch_moon.sh`, `moon_geometry.py` (ephemeris), `moon_thermal.py` (regolith heat model), `moon_maps.py` (map lookups),
`moon_sites.py` (site list), `moon_model.py` (records, score, weights).


## Component 3 service (team spec: POST /characterize on port 8001)
- `service/contract.py`  the spec contract as one function, `characterize_spec(request) -> response`
- `service/app.py`       FastAPI wrapper (spec stack): `uvicorn service.app:app --host 0.0.0.0 --port 8001`
- `service/server_stdlib.py`  same endpoint with no dependencies, for local tests: `python3 service/server_stdlib.py`
- `service/norm_ranges.json`  clamp + min-max ranges behind `features_norm`; Component 5 must use the same ones
- `Dockerfile`, `service/docker-compose.snippet.yml`  container on port 8001 reading maps from `/data/mars` and `/data/moon`
Request and response follow the spec exactly; extra fields (measured yes/no, weights, Mars season, all values) sit under `extra`.
Missing features are `null` in `features_raw` and `features_norm`. Moon answers also carry `extra.base_suitability` and `extra.base_weights`.

## Sources
NASA PDS Atmospheres Node, https://pds-atmospheres.nmsu.edu/PDS/data/ ; PDS Geosciences Node (MOLA, TES, GRS, LOLA, Diviner,
Lunar Prospector), https://pds-geosciences.wustl.edu/ ; NASA PGDA LOLA illumination maps, https://pgda.gsfc.nasa.gov/ ;
LROC Lunar Pit Atlas, https://www.lroc.asu.edu/
