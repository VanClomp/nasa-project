# Parameters p and their change with time p(t)

What the 9 features returned by `POST /characterize` mean on Mars and the Moon, which of them change with the
landing date, and where each value comes from at a given place. The same feature order is used everywhere
(`service/norm_ranges.json`, the Earth matrices in `data/earth/`, the search).

## Two questions answered for every parameter

1. **Does p change with time?** `extra.features_time_varying[i]` - `true` = the value depends on the landing date
   (season, Sun position, dust season, pressure cycle); `false` = a fixed property of the place.
2. **Where does the value at this place come from?** `extra.features_measured[i]` - `true` = measured at this place
   (a surface station record, an orbital map read at this pixel, or exact orbital geometry); `false` = predicted by
   the global model (latitude, elevation and surface maps), which is less certain.

The pages show both on every parameter tile (`zmierzone` / `model`, `◷ z datą` / `stałe`) and draw a p(t) chart for
each time-varying parameter below the existing charts on the results page.

## Mars

| # | p | Unit | Changes with time? | What drives p(t) | Measured at a place when... | Otherwise |
|---|---|---|---|---|---|---|
| 0 | `temp_mean` | deg C | **yes** | season (Ls), dust | the site has station records for that Mars month | global surface-energy-balance model |
| 1 | `temp_diurnal_amp` | K | **yes** | season, dust, thermal inertia | as above | global model |
| 2 | `thermal_inertia` | SI | no | - | always: TES map at the pixel | (TES gaps infilled; flagged) |
| 3 | `surface_roughness` | m | no | - | always: MOLA, 7x7 px (~13 km) | - |
| 4 | `soil_moisture` | wt% | no | - | GRS water map covers the point (+-~60 deg) | null at high latitude |
| 5 | `dust_aerosol` | optical depth | **yes** | dust season (Ls 180-360 dusty) | never (global TES climatology) | TES zonal climatology |
| 6 | `solar_elevation_max` | deg | **yes** | Sun declination for the date | always (exact geometry) | - |
| 7 | `radiation_proxy` | g/cm2 | **yes** | seasonal CO2 pressure cycle (~25 %) | the site has station pressure for that month | Viking 1 pressure curve scaled to MOLA elevation |
| 8 | `slope_deg` | deg | no | - | always: MOLA 3x3 px (~1.85 km) | - |

**Local vs global model on Mars** (`extra.model`): `local` when the date's surface weather comes from station records
(at least one of air/ground temperature, pressure, wind measured for that Mars month), else `global`. Station records
do not cover every month:

| Site | Mars months with station data |
|---|---|
| Viking 1, Viking 2, Curiosity, Perseverance | all 12 |
| InSight | 11 (not month 9, Ls 240-270) |
| Pathfinder | 5-7 (Ls 120-210) |
| Phoenix | 3-5 (Ls 60-150) |
| Spirit, Opportunity, Zhurong, Oxia Planum, Arcadia Planitia | none - global model all year |

## Moon

| # | p | Unit | Changes with time? | What drives p(t) | Measured at a place when... | Otherwise |
|---|---|---|---|---|---|---|
| 0 | `temp_mean` | deg C | **yes** away from the poles; **no** at the poles | Sun elevation over the lunar day / season | poles (|lat| >= 76 deg, Diviner polar product): annual mean, fixed | regolith heat model for the date |
| 1 | `temp_diurnal_amp` | K | **yes** | Sun elevation (season, libration) | never | regolith heat model (Hayne et al. 2017) |
| 2 | `thermal_inertia` | SI | no | - | never | regolith 55 blended with rock 2200 by Diviner rock abundance |
| 3 | `surface_roughness` | m | no | - | always: LOLA DEM | - |
| 4 | `soil_moisture` | - | no | - | null (no defensible value); see ice_depth, hydrogen_index | - |
| 5 | `dust_aerosol` | - | no | - | always 0 (vacuum) | - |
| 6 | `solar_elevation_max` | deg | **yes** | Sun declination on the Moon for the date | always (ephemeris) | - |
| 7 | `radiation_proxy` | g/cm2 | no | - | always 0 (no atmosphere) | - |
| 8 | `slope_deg` | deg | no | - | always: LOLA (40 m poles, 240 m to 75 deg, 16 ppd elsewhere) | - |

**Model label on the Moon** (`extra.model = "orbital"`, blue badge "Pomiary orbitalne · ten punkt"): there are no
surface weather stations, but terrain, sunlight, rocks and hydrogen are measured from orbit at the exact pixel
(LOLA, Diviner, Lunar Prospector) - more certain than the Mars global model, so it is not shown as "uncertain".
A green local model on the Moon would need surface records (Apollo 15/17 heat-flow experiments, Chandrayaan-3
ChaSTE); they are not in this component yet.

## p(t) series

`POST /characterize` with `"series": true` adds `extra.series`:

| Field | Meaning |
|---|---|
| `axis` | `mars_month` (12 Mars months, Ls 30 deg each, 46-67 Earth days long) or `calendar_month_15th` (Moon: 15th of each month of the landing year) |
| `labels` | one label per month; on Mars the Earth month in which that Mars month starts, within the Mars year of the landing date |
| `detail_labels` | Mars only: `Mars month k (Ls a-b deg), from YYYY-MM-DD` |
| `current_index` | the month of the landing date (0-11) |
| `values` | `{p: [12 values]}` for the time-varying parameters only, in the units of `norm_ranges.json` |
| `units` | unit text per p |

On Mars the series comes from the same model run as the dated answer (no extra cost); on the Moon it computes 12
dates of the landing year. The results page requests it separately after the main result, so results appear first.
