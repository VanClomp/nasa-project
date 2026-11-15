# Szukacz (component 4)

The search engine for Earth analogs. It takes the profile of a point on the Moon or
Mars (K normalised features) and K weights, and returns the `top_k` (default 100)
locations on Earth that match it best, together with the best
month and a match map.

The returned locations are diverse: if two points lie closer together than
`min_distance_km`, only the better one counts, and the freed slot goes to the
next point in the ranking. The result still has `top_k` entries.

The result includes an **error map** of the whole Earth: for every place, the
weighted difference between the target profile and what is at that place. A separate
endpoint returns the same map at high magnification for the area around a chosen
point.

For now the Szukacz only returns these points and maps. Further study of the results
(DEM raycasting, item 5.4 of the tasks in the spec) is not implemented.

## Files

| File | Contents |
| :--- | :--- |
| `szukacz/data.py` | Loading the Earth data from `/data/earth` (mmap) and the point metadata. |
| `szukacz/scoring.py` | Match scoring and selection of a diverse Top-K. Pure maths, no files or JSON. |
| `szukacz/maps.py` | Maps: match heatmap, whole-Earth error map, detailed error map around a point. Numpy grids and images, no JSON. |
| `szukacz/engine.py` | The `search()` and `error_map_detail()` functions: they assemble results shaped like the `POST /search` and `POST /error-map` responses. |
| `szukacz/api.py` | HTTP service (FastAPI), port 8002. |
| `tests/test_szukacz.py` | Tests on synthetic data. |

## What it offers

### HTTP

**`POST /search`**

Request:

| Field | Type | Description |
| :--- | :--- | :--- |
| `features_norm` | K numbers | Normalised target profile from the Charakteryzator. |
| `weights` | K numbers `>= 0` | Feature weights. Only their proportions matter. |
| `require_caves` | bool, default `false` | Return only points with a cave no farther than 15 km. |
| `top_k` | int 1..1000, default 100 | How many locations to return. |
| `min_distance_km` | number `>= 0`, optional | Minimum distance between returned locations. A missing field means 100 km, `0` turns the filtering off. **Field outside the spec.** |

K is the number of features in the data matrix (9 per the spec).

Response:

| Field | Description |
| :--- | :--- |
| `execution_time_ms` | Computation time on the Szukacz side. |
| `best_global_month` | The month `1..12` with the highest mean match among the returned locations; `null` when the list is empty. |
| `heatmap_base64` | `data:image/webp;base64,...`, an RGBA 1024x512 image (described below). |
| `error_map` | Whole-Earth error map, an object described in "Error map format". **Field outside the spec.** |
| `candidates` | List of locations, best first. |

Candidate fields:

| Field | Description |
| :--- | :--- |
| `rank` | Position from 1. |
| `id`, `lat`, `lon` | From the Earth metadata. |
| `score` | Match in the best month. |
| `best_month` | Best month, `1..12`. |
| `monthly_scores` | 12 scores, index 0 is January. |
| `features_norm` | The point's K normalised features in its best month. **Field outside the spec**, needed by the frontend for live re-scoring. |
| `features_raw_best_month` | Dictionary `feature name -> physical value` in the best month. |
| `climatogram_12m` | Dictionary `feature name -> 12 physical values`, for all features (the spec shows two). |
| `nearest_cave_km` | From the Earth metadata. |

Differences from the spec example:

- There is no `name_hint` field. The Szukacz does not know region names (the Networker adds them).
- There is an extra `error_map` field and an extra `POST /error-map` endpoint.
- The list can have fewer than `top_k` entries when Earth has fewer points
  meeting the conditions (cave filter, large `min_distance_km`).
- Missing data (NaN in the matrices) comes out in the JSON as `null`.

Invalid input (wrong number of features, a negative weight, NaN) gives status `422`
with a description in the `detail` field.

**`POST /error-map`** (endpoint outside the spec)

A detailed error map for the area around a chosen point on Earth. It shows the
same error as `error_map` from `/search`, on the same colour scale, but at much
higher magnification: with the default values about 1 km per pixel, while the
whole-Earth map has about 39 km per pixel (at the equator).

Request:

| Field | Type | Description |
| :--- | :--- | :--- |
| `features_norm`, `weights` | as in `/search` | The same values `/search` was called with. |
| `lat` | number -90..90 | Latitude of the map centre (y coordinate). |
| `lon` | number -180..180 | Longitude of the map centre (x coordinate). |
| `radius_km` | number 1..2000, default 250 | The map reaches this many km from the point to the north, south, east and west. |
| `size_px` | int 64..1024, default 512 | Map width in pixels. |

The point is given in geographic coordinates. A pixel `(px_x, px_y)` of the
whole-Earth map converts to them like this:
`lon = (px_x + 0.5) / 1024 * 360 - 180`, `lat = 90 - (px_y + 0.5) / 512 * 180`.

Response:

| Field | Description |
| :--- | :--- |
| `execution_time_ms` | Computation time on the Szukacz side. |
| `center` | `{"lat": ..., "lon": ...}` from the request. |
| `radius_km` | Radius from the request (or the default). |
| `km_per_px` | Map scale, `2 * radius_km / size_px`. |
| `error_map` | The map, an object described in "Error map format". |

Example:

```json
// Request:
{
  "features_norm": [0.0, 0.85, 0.12, 0.40, 0.02, 0.0, 0.05, 1.0, 0.16],
  "weights": [1.0, 0.5, 0.8, 0.4, 0.9, 0.2, 1.0, 0.3, 0.5],
  "lat": -77.55,
  "lon": 161.80
}

// Response:
{
  "execution_time_ms": 27.4,
  "center": {"lat": -77.55, "lon": 161.8},
  "radius_km": 250.0,
  "km_per_px": 0.9766,
  "error_map": {
    "image_base64": "data:image/png;base64,iVBORw0KGgo...",
    "width": 512,
    "height": 512,
    "bounds": {"lat_min": -79.7983, "lat_max": -75.3017, "lon_min": 151.37129, "lon_max": 172.22871},
    "scale": {
      "min": 0.0,
      "max": 0.5,
      "colors": ["#371300", "#582300", "#7B3401", "#A04502", "#C65803", "#EE6B03", "#FF9257", "#FFBE9E", "#FFE5D9"]
    },
    "stats": {"n_points": 152, "min": 0.0745, "mean": 0.2206, "max": 0.2546}
  }
}
```

Invalid input gives status `422`, as in `/search`.

**Error map format** (the `error_map` field in both responses)

The error is a number from 0 to 1: `0` means a place with a profile identical to the target,
the higher the worse. For every point `error = 1 - score`.

| Field | Description |
| :--- | :--- |
| `image_base64` | `data:image/png;base64,...`, an image with transparency. The pixel colour is the error at that place, a transparent pixel means no data. Note: this is PNG, not WebP like the heatmap. |
| `width`, `height` | Image size in pixels. The whole-Earth map is 1024x512. The detailed map is `size_px` x `size_px`; it is shorter only when the window reaches a pole. |
| `bounds` | `lat_min`, `lat_max`, `lon_min`, `lon_max`: the image edges in degrees. Projection as in the heatmap (equirectangular, north up): the columns split the longitude range evenly, the rows the latitude range. In the detailed map `lon_min` and `lon_max` go beyond `[-180, 180]` when the window crosses the 180th meridian (e.g. `170..190`). |
| `scale` | `min` (always 0), `max` and `colors`: 9 colours spread evenly from `min` to `max`, from dark (small error) to bright (large). An error of `max` or more gets the last colour. The scale is fixed: the same colour means the same error in every query and on both maps. |
| `stats` | `n_points`: how many data points lie on the map; `min`, `mean`, `max`: their error (`null` when there are no points). |

**`GET /health`** returns `{"status": "ok", "n_points": ..., "n_features": ...}`.

### Python

The same functions can be called without HTTP:

```python
from szukacz import error_map_detail, load_earth_data, search

earth = load_earth_data("/data/earth")
result = search(earth, features_norm, weights, top_k=100, min_distance_km=100.0)
result["error_map"]  # whole-Earth error map

best = result["candidates"][0]
detail = error_map_detail(earth, features_norm, weights, best["lat"], best["lon"], radius_km=250.0)
detail["error_map"]  # error map around the best location
```

| Function | Description |
| :--- | :--- |
| `data.load_earth_data(data_dir) -> EarthData` | Memory-maps the `.npy` matrices and loads the metadata. Checks shapes and columns. |
| `engine.search(data, features_norm, weights, *, top_k, min_distance_km, require_caves, cave_max_km, error_scale_max) -> dict` | Full search, returns the `POST /search` response dictionary. |
| `engine.error_map_detail(data, features_norm, weights, lat, lon, *, radius_km, size_px, error_scale_max) -> dict` | Detailed error map around a point, returns the `POST /error-map` response dictionary. |
| `maps.global_error_grid(data, point_scores) -> ndarray (512, 1024)` | Whole-Earth error as numbers; `NaN` where there is no data. |
| `maps.detail_error_grid(data, target, weights_norm, lat, lon, radius_km, size_px) -> DetailGrid` | Detailed error grid as numbers (`errors`), with the window bounds and the errors of the points inside it. |
| `maps.colorize_error(grid, scale_max)`, `maps.render_error_map(grid, scale_max)` | Error grid as an RGBA image or a PNG data URI. |
| `maps.render_heatmap(data, point_scores) -> str` | Heatmap as a WebP data URI. |
| `maps.pixel_best_scores(data, point_scores)` | Best score in each pixel of the 1024x512 grid; a step shared by the heatmap and the error map. |
| `scoring.normalize_weights(weights)` | Weights divided by their sum. |
| `scoring.score_block(block, target, weights_norm)` | Match for any block of features `(..., K)`. |
| `scoring.score_all(features, target, weights_norm) -> (best_score, best_month)` | Match of all points, the best month of each (months from 0). |
| `scoring.select_diverse_top_k(scores, unit_xyz, top_k, min_distance_km, eligible=None)` | Indices of the best points, pairwise farther apart than `min_distance_km`. |
| `scoring.latlon_to_unit_xyz(lat, lon)`, `scoring.great_circle_km(a, b)` | Helpers: points on the sphere and the distance between them. |

`render_heatmap` used to be in `engine.py`; it can still be imported from
there.

## What it uses

**Other project modules.** The Szukacz calls no functions or endpoints of
other components. All it needs are the files from the Precomputer
in the `SZUKACZ_DATA_DIR` folder (default `/data/earth`):

| File | Requirements |
| :--- | :--- |
| `earth_features_norm.npy` | `(N_POINTS, 12, K)`, float32, values in `[0, 1]`. |
| `earth_features_raw.npy` | The same shape, physical values. |
| `earth_metadata.parquet` or `earth_metadata.npy` | Columns `id`, `lat`, `lon`, `px_x` (0..1023), `px_y` (0..511), `nearest_cave_km`; one row per point, in the same order as the matrices. When both files exist, the `.parquet` is read. |

**External libraries** (licences in `LICENCES.md` in the root folder):

| Library | Functions used |
| :--- | :--- |
| `numpy` | `load(mmap_mode="r")`, `subtract`, `abs`, matrix multiplication `@`, `argmax`, `argpartition`, `argsort`, `fmax.reduceat`, `unique`; in the error maps also `minimum.accumulate`, `partition`, `lexsort`, `interp`, `flatnonzero`. |
| `pillow` | `Image.fromarray`, `Image.save(format="WEBP", lossless=True)` for the heatmap; `Image.putpalette`, `Image.save(format="PNG")` for the error maps. |
| `fastapi`, `pydantic` | `FastAPI`, `HTTPException`, `JSONResponse`, `BaseModel`, `Field`. |
| `uvicorn` | The server that runs the app. |
| `pyarrow` | `parquet.read_table`, only when the metadata is in `.parquet`. |
| standard library | `concurrent.futures.ThreadPoolExecutor`, `base64`, `io`, `math`, `time`. |

The error maps need no new library. The spec also lists
`numba` and `rasterio`. They are not used.

## How it computes

**Match** of point `n` in month `m` (formula from the spec):

    Score(n, m) = 1 - sum_k(w_k * |X[n, m, k] - y_k|) / sum_k(w_k)

A point's score is its best month. When all weights are zero,
every point gets `1.0` (the frontend computes it the same way). A month with missing data
(NaN in any feature, even one with weight 0) loses to any other, and a point
without a single complete month is left out of the results.

The **error** of a point is the weighted difference between the target profile and the point's features
in its best month, i.e. the second term of the match formula:

    Error(n) = min_m sum_k(w_k * |X[n, m, k] - y_k|) / sum_k(w_k) = 1 - Score(n)

A point without a single complete month has no error and does not appear on the maps.

**Diverse Top-K.** Points are scanned from the best. A point enters the
result if it is more than `min_distance_km` from every one already chosen
(distance along the surface of a sphere of radius 6371 km); otherwise it is
skipped. The scan continues until `top_k` points are collected or the
points run out.

**Cave filter.** With `require_caves: true` only points with
`nearest_cave_km <= 15` take part in the ranking. The heatmap and error maps still show
all points.

**Heatmap.** Every pixel of the 1024x512 grid (`px_x`, `px_y` from the metadata)
gets the best score of the points inside it. The colour is constant
(`#10B981`) and the opacity changes. The scale is relative to the query: the weakest
point on the map is transparent, the best fully opaque, and the opacity grows
with the square of the position between them. Pixels without points are transparent.

**Whole-Earth error map.** The same 1024x512 grid as the heatmap. A pixel
gets the smallest error of the points inside it, i.e. the error of the
same point that sets the heatmap pixel. It differs from the heatmap in the scale:

- The scale is absolute. The colour depends only on the error value, not on
  how the other points did in this query, so maps from different queries
  (other weights, another target) can be compared.
- The opacity is constant and the colour changes: one hue (a shade of Ember `#F97316`
  from CONTEXT.md) in 255 tones, from dark at error 0 to bright at
  error `scale.max`. Every place with data is visible, including the best.
- The scale ends at `0.5` (the `SZUKACZ_ERROR_SCALE_MAX` variable). On the mock
  data the error with a few weighted features lies in `0.07..0.47`; with
  one feature it reaches `0.74`, and then the worst places get the last colour.

**Detailed map.** The window is a square in kilometres: `radius_km` from the
point in every direction, so the longitude range grows with latitude
(`radius_km / 111.195 / cos(lat)` degrees). The whole-Earth map keeps only
the best point in a pixel; here every data point is separate and at its
exact position:

- A pixel gets the error of the nearest data point (distance `|dlon| + |dlat|`
  in degrees).
- If that point lies farther than 0.75 of the typical spacing between points
  (in either axis), the pixel stays transparent: there is no data there
  (ocean, forest).
- The typical spacing is the median distance to the third nearest neighbour
  among the window's points (computed on a sample).
- When several points fall into one pixel, the smallest error stays, as
  on the whole-Earth map.

On a regular lat/lon grid every point fills exactly its own cell
(with a quarter-cell margin at the coastline), and holes the size of a cell or larger
stay visible.

Limits of the detailed map:

- It does not interpolate or add detail that is not in the data. How much
  you see depends on the point density from the Precomputer. The 60,000-point mock has
  about 1.4 per pixel of the whole-Earth map, so the detailed map shows little more
  than it; with 400,000 points there are about 3.7 per pixel.
- It assumes points spread evenly in degrees. With random points
  (the mock) about 10% of land pixels stay empty, because they fall in gaps between
  points.
- A single point fills at most 1/8 of the map width in each direction.
- A window reaching a pole is clipped (`height < size_px`) and covers the full
  longitude range; the left and right image edges are then the same meridian,
  and the filling does not cross that edge.

## Running

```bash
cd 4-szukacz
pip install -r requirements.txt
SZUKACZ_DATA_DIR=/data/earth uvicorn szukacz.api:app --host 0.0.0.0 --port 8002
```

Or through the `Dockerfile` in this folder (data mounted as `/data`).

| Variable | Default | Meaning |
| :--- | :--- | :--- |
| `SZUKACZ_DATA_DIR` | `/data/earth` | Folder with the Earth data. |
| `SZUKACZ_MIN_DISTANCE_KM` | `100` | Distance used when the request gives no `min_distance_km`. |
| `SZUKACZ_CAVE_MAX_KM` | `15` | `require_caves` filter threshold. |
| `SZUKACZ_ERROR_SCALE_MAX` | `0.5` | Error at which the colour scale of the error maps ends (both). |
| `SZUKACZ_THREADS` | number of cores, at most 16 | Threads that compute the match. |

## Tests

```bash
cd 4-szukacz
python -m unittest discover -s tests -v
```

The tests create their own small data in a temporary folder. The two HTTP endpoint tests
are skipped when the `fastapi` and `httpx` packages are missing.

## Verification status and performance

Checked by tests (numpy + pillow): the match formula, the best month,
filtering of nearby points (compared with a simple reference implementation),
the cave filter, the response shape, the heatmap, handling of missing data and invalid
input. For the error maps: the whole-Earth map compared with the formula pixel by
pixel, the detailed map compared with a simple reference implementation that
checks all points for every pixel (random points, a regular grid
with a hole, a window across the 180th meridian, a window near a pole, an area without data).

Run on 2026-11-14 in a separate environment (Python 3.13, fastapi 0.163,
httpx 0.28, numpy 2.5, pillow 13, pyarrow 26):

- The `/search` and `/error-map` endpoint tests pass.
- The `uvicorn` server started and answered `/health`, `/search`
  and `/error-map`. Data: 60,000 points from the Precomputer's mock generator,
  metadata in `.parquet`. The generator as it stood then failed
  (`todo_list.txt`, item 12); for this trial it was run with a fix
  in memory, without changing the file.
- Reading the metadata from `.parquet` works, but there is no automated test.

Not run at the time: building the image from the `Dockerfile` (no Docker on the machine).

Times measured on 400,000 points from the mock generator, 8 cores. The machine was
busy with other processes at the time, so mainly the comparison counts:

| What | Time (median) | Response size |
| :--- | :--- | :--- |
| `POST /search` before adding the error map | about 92 ms | 335 kB |
| `POST /search` with the error map | about 105 ms | 465 kB |
| `POST /search`, `min_distance_km` = 500 | about 160 ms | |
| `POST /error-map`, default values (250 km, 512 px) | about 27 ms | 33-43 kB |
| `POST /error-map`, 250 km, 256 px | about 10 ms | |
| `POST /error-map`, 2000 km, 512 px | about 85 ms | 115 kB |
| `POST /error-map`, 2000 km, 1024 px | about 160 ms | |

Within `/search`, the match computation is 40-50 ms, the heatmap about 23 ms and
the error map about 11 ms. The spec assumes under 15 ms per query; the
current version does not meet that target.

Update 2026-11-15: with the real Earth data (551,832 points, 0.2 deg grid) a `/search` takes about
370 ms on the 2-vCPU production server.
