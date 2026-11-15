# Parameters p and their change with time p(t)

What the 9 features returned by `POST /characterize` mean on Mars and the Moon, which of them change with the
landing date, and where each value comes from at a given place. The same feature order is used everywhere
(`service/norm_ranges.json`, the Earth matrices in `data/earth/`, the search).

## Two questions answered for every parameter

1. **Does p change with time?** `extra.features_time_varying[i]` - `true` = the value depends on the landing date
   (season, Sun position, dust season, pressure cycle); `false` = a fixed property of the place.
2. **Where does the value at this place come from?** `extra.features_source[i]`, one of four labels:

| Label | Meaning | Examples |
|---|---|---|
| `measured` | read at this exact point: an orbital map pixel, exact orbital geometry, or a physical fact | slope, roughness, TES thermal inertia (direct retrieval), GRS water, noon Sun elevation, Moon dust 0 / shielding 0 |
| `local` | **local model**: forecast for the date from a seasonal fit to *this landing site's own* station records only (`scripts/station_model.py`) | temperatures / pressure / dust at Curiosity, Perseverance, Viking 1/2, Phoenix, Pathfinder, InSight in seasons they observed |
| `global` | **global model**: physics calibrated on all stations, applied from latitude, elevation and maps; an approximation | time-varying values everywhere else (most of both bodies); Moon thermal inertia from rock abundance |
| `none` | no data at this point; value `null`, the search gives it weight 0 | Mars water poleward of the GRS map, Mars thermal-inertia pixels TES gap-filled, Moon soil moisture |

`extra.features_detail[i]` is a one-line source for the value; `extra.features_measured[i]` is kept for older
clients (`true` where the label is `measured`). Values that are fixed (not time-varying) are never modelled: if they
are not measured at the point they are `none`. The gateway keeps `null` (it no longer turns missing values into 0).

The pages show both tags on every parameter tile. Hovering a tile (mouse) or tapping it (touch) opens an info box:
what the parameter measures, what its label means, and the source of the value at this place
(`1-webpage/feature_info.js`, shared by `explorer.php` and `results.php`). The results page also draws a p(t) chart
for each time-varying parameter.

## Mars

| # | p | Unit | Changes with time? | What drives p(t) | Label |
|---|---|---|---|---|---|
| 0 | `temp_mean` | deg C | **yes** | season (Ls), dust | `local` where the site's ground-temperature model covers the season (Curiosity, Perseverance), else `global` |
| 1 | `temp_diurnal_amp` | K | **yes** | season, dust, thermal inertia | as above |
| 2 | `thermal_inertia` | SI | no | - | `measured` for a direct TES retrieval; `none` where TES gap-filled the pixel or it has no value (about 8 % of the planet) |
| 3 | `surface_roughness` | m | no | - | `measured`: MOLA, 7x7 px (~13 km) |
| 4 | `soil_moisture` | wt% | no | - | `measured` where the GRS map covers the point (+-~60 deg), else `none` |
| 5 | `dust_aerosol` | optical depth | **yes** | dust season (Ls 180-360 dusty) | `local` at Viking 1/2 and Phoenix (sky optical depth records), else `global` (TES zonal climatology) |
| 6 | `solar_elevation_max` | deg | **yes** | Sun declination for the date | `measured` (exact geometry) |
| 7 | `radiation_proxy` | g/cm2 | **yes** | seasonal CO2 pressure cycle (~25 %) | follows pressure: `local` where the site's pressure model covers the season, else `global` (Viking 1 curve scaled to MOLA elevation) |
| 8 | `slope_deg` | deg | no | - | `measured`: MOLA 3x3 px (~1.85 km) |

**Local model** (`scripts/station_model.py`): for every station and quantity (air / ground temperature min, max,
mean; pressure; wind; dust optical depth) the daily values of all its Mars years are fitted with
`y(Ls) = a0 + sum_n (a_n cos nLs + b_n sin nLs)`, order 1-3 chosen by leave-one-Mars-year-out cross-validation.
No other site and no global parameter enters the fit. The forecast for a date is the curve at that date's Ls; its
band is the 10-90 % range of past departures from the curve in that Mars month. Only seasons the station observed
(>= 3 sols) are forecast. Validation (`python3 scripts/station_model.py` -> `outputs/local_model_validation.csv`,
forecasting each held-out Mars year from the others), mean absolute error local vs global predictor:

| Site, quantity | local | global |
|---|---|---|
| Curiosity air max / ground max | 2.0 K / 3.2 K | 11.4 K / 6.2 K |
| Curiosity pressure | 5.5 Pa | 22.1 Pa |
| Perseverance ground min / max | 2.6 K / 6.6 K | 5.5 K / 5.3 K |
| Viking 1 pressure | 3.6 Pa | 4.4 Pa |
| Viking 2 air min / max | 2.2 K / 3.3 K | 2.2 K / 3.4 K |

**Badge** (`extra.model`): `local` when at least one surface quantity for the date comes from the local model, else
`global`. Seasons covered (Mars months, Ls 30 deg each):

| Site | Pressure | Temperature | Dust |
|---|---|---|---|
| Curiosity | all 12 | air + ground, all 12 | - |
| Perseverance | 1-4, 6, 9, 11 | air + ground, all 12 | - |
| Viking 1 | all 12 | air 4-10 | all 12 |
| Viking 2 | all 12 | air, all 12 | 1-9, 12 |
| InSight | 1-5, 7, 10-12 | air 2, 4-6, 8, 11, 12 | - |
| Pathfinder | 5-7 | air 5-6 | - |
| Phoenix | 3-5 | air 3-5 | 3-5 |
| Spirit, Opportunity, Zhurong, Oxia Planum, Arcadia Planitia | - | - | - (global model all year) |

## Moon

| # | p | Unit | Changes with time? | What drives p(t) | Label |
|---|---|---|---|---|---|
| 0 | `temp_mean` | deg C | **yes** away from the poles; **no** at the poles | Sun elevation over the lunar day / season | `measured` at the poles (Diviner annual mean, fixed); else `global` (regolith heat model) |
| 1 | `temp_diurnal_amp` | K | **yes** | Sun elevation (season, libration) | `global` (regolith heat model, Hayne et al. 2017) |
| 2 | `thermal_inertia` | SI | no | - | `global`: regolith 55 blended with rock 2200 by Diviner rock abundance |
| 3 | `surface_roughness` | m | no | - | `measured`: LOLA DEM |
| 4 | `soil_moisture` | - | no | - | `none` (no defensible value); see ice_depth, hydrogen_index |
| 5 | `dust_aerosol` | - | no | - | `measured`: 0, no atmosphere |
| 6 | `solar_elevation_max` | deg | **yes** | Sun declination on the Moon for the date | `measured` (ephemeris) |
| 7 | `radiation_proxy` | g/cm2 | no | - | `measured`: 0, no atmosphere |
| 8 | `slope_deg` | deg | no | - | `measured`: LOLA (40 m poles, 240 m to 75 deg, 16 ppd elsewhere) |

**Badge on the Moon**: always `global`. There are no lunar surface station time series in this component, so no
local model; a local model would need surface records (Apollo 15/17 heat-flow experiments, Chandrayaan-3 ChaSTE).

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
