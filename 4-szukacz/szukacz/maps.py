"""Result maps: match heatmap and error maps (whole Earth, area around a point).

A point's error is the weighted difference between the target profile and the point's features in its
best month, i.e. the complement of the match:

    Error(n) = min_m sum_k(w_k * |X[n, m, k] - y_k|) / sum_k(w_k) = 1 - Score(n)

The functions return numpy grids and finished images; they know nothing about the API response format.
"""

from __future__ import annotations

import base64
import io
import math
from dataclasses import dataclass

import numpy as np
from PIL import Image

from .data import HEATMAP_HEIGHT, HEATMAP_WIDTH, EarthData
from .scoring import EARTH_RADIUS_KM, score_block

# Heatmap colour: Signal Emerald from the site's colour palette (#10B981).
_HEATMAP_RGB = (16, 185, 129)
# An exponent > 1 dims average matches and keeps only the best ones bright.
_HEATMAP_GAMMA = 2.0

# Error-map scale: one hue (a shade of Ember #F97316 from the site's colour palette), 9 colours
# evenly spaced in OKLCH lightness (0.24 -> 0.94). Dark = small error, bright = large.
ERROR_COLORS = (
    "#371300", "#582300", "#7B3401", "#A04502", "#C65803", "#EE6B03", "#FF9257", "#FFBE9E", "#FFE5D9",
)
# Error at which the scale ends; larger errors get the last colour.
# On the mock data the error with a few features lies in 0.07..0.47.
DEFAULT_ERROR_SCALE_MAX = 0.5

DEFAULT_DETAIL_RADIUS_KM = 250.0
MIN_DETAIL_RADIUS_KM = 1.0
MAX_DETAIL_RADIUS_KM = 2000.0
DEFAULT_DETAIL_SIZE_PX = 512
MIN_DETAIL_SIZE_PX = 64
MAX_DETAIL_SIZE_PX = 1024

_KM_PER_DEG = math.pi * EARTH_RADIUS_KM / 180.0

# The detailed map also loads points outside the window, up to this fraction of its half
# in every direction; thanks to them the pixels at the edge have all their neighbours.
_DETAIL_MARGIN = 0.5
# A point fills pixels at most this fraction of the typical point spacing away from it
# (in each axis). 0.5 is exactly its own cell of a regular grid;
# the margin closes gaps when the points are unevenly spread.
_REACH_FACTOR = 0.75
# The point spacing is measured to this neighbour, on a sample of this size.
# Third neighbour: a point on the edge of a regular grid has three of them one cell away.
_SPACING_NEIGHBOUR = 3
_SPACING_PAIR_BUDGET = 2_000_000
_SPACING_MIN_SAMPLE = 16
_SPACING_MAX_SAMPLE = 128

# Pixel key in _nearest_source: distance * 2^22 + source number.
# The grid has at most (1.5 * 1024 + 4)^2 < 2^22 pixels, so the number fits.
_ID_BITS = 22
_EMPTY = 1 << 61
# Axis step in distance units: the shorter axis gets 256, the longer one proportionally more
# (axis ratio accurate to 0.2%). With the step capped, the key fits in int64.
_SUBPIXEL = 256
_MAX_STEP = 1 << 23


def _data_uri(image: Image.Image, mime: str, **save_options) -> str:
    buffer = io.BytesIO()
    image.save(buffer, **save_options)
    return f"data:{mime};base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def pixel_best_scores(data: EarthData, point_scores: np.ndarray) -> np.ndarray:
    """Best score in each occupied pixel of the 1024x512 grid, in the order of data.pixel_flat.

    Infinite and NaN scores are skipped; a pixel without a valid score gets NaN.
    Shared step of the heatmap and the error map: pass the result to both to avoid computing it twice.
    """
    if not data.pixel_starts.size:
        return np.empty(0, dtype=np.float32)
    ordered = np.where(np.isfinite(point_scores), point_scores, np.nan)[data.pixel_order]
    return np.fmax.reduceat(ordered, data.pixel_starts)


def render_heatmap(
    data: EarthData, point_scores: np.ndarray, pixel_scores: np.ndarray | None = None
) -> str:
    """Projects the point scores onto a 1024x512 bitmap and returns it as a WebP data URI.

    A pixel gets the best score of the points inside it. The image is
    RGBA: a constant #10B981 colour whose opacity grows with the match. The scale is
    relative to the query: the weakest point is transparent,
    the best fully opaque. Pixels without points (oceans, forests) are transparent.

    pixel_scores: optionally the ready result of pixel_best_scores(data, point_scores).
    """
    rgba = np.zeros((HEATMAP_HEIGHT * HEATMAP_WIDTH, 4), dtype=np.uint8)
    rgba[:, :3] = _HEATMAP_RGB
    if pixel_scores is None:
        pixel_scores = pixel_best_scores(data, point_scores)
    valid = np.isfinite(pixel_scores)
    if valid.any():
        low = float(pixel_scores[valid].min())
        span = float(pixel_scores[valid].max()) - low
        if span > 1e-9:
            level = (pixel_scores[valid] - low) / span
        else:
            level = np.ones(int(valid.sum()))
        rgba[data.pixel_flat[valid], 3] = np.rint(255.0 * level**_HEATMAP_GAMMA)
    image = Image.fromarray(rgba.reshape(HEATMAP_HEIGHT, HEATMAP_WIDTH, 4))
    # Lossless and with exact=True, so the alpha channel and the colour under it stay unchanged.
    return _data_uri(image, "image/webp", format="WEBP", lossless=True, quality=0, method=0, exact=True)


def global_error_grid(
    data: EarthData, point_scores: np.ndarray, pixel_scores: np.ndarray | None = None
) -> np.ndarray:
    """Error over the whole Earth: a (512, 1024) float32 grid, NaN where there is no data.

    point_scores: (N,) match of the points (best_score from scoring.score_all).
    pixel_scores: optionally the ready result of pixel_best_scores(data, point_scores).
    A pixel gets the smallest error of the points inside it, i.e. the
    same point that sets the heatmap pixel. Row 0 is north (lat 90),
    column 0 is lon -180.
    """
    if pixel_scores is None:
        pixel_scores = pixel_best_scores(data, point_scores)
    grid = np.full(HEATMAP_HEIGHT * HEATMAP_WIDTH, np.nan, dtype=np.float32)
    grid[data.pixel_flat] = 1.0 - pixel_scores
    return grid.reshape(HEATMAP_HEIGHT, HEATMAP_WIDTH)


# The error-map image has a 256-entry palette: 255 scale colours and one for "no data".
_ERROR_LEVELS = 255
_NO_DATA = 255


def _color_table(colors: tuple[str, ...]) -> np.ndarray:
    """(256, 4) RGBA palette: 255 colours spread linearly between the scale colours.

    The last entry is the no-data pixel: transparent, in the first scale colour.
    """
    stops = np.array([[int(c[i : i + 2], 16) for i in (1, 3, 5)] for c in colors], dtype=np.float64)
    at = np.linspace(0.0, 1.0, _ERROR_LEVELS)
    where = np.linspace(0.0, 1.0, len(colors))
    table = np.full((_ERROR_LEVELS + 1, 4), 255, dtype=np.uint8)
    for channel in range(3):
        table[:_ERROR_LEVELS, channel] = np.interp(at, where, stops[:, channel]).round()
    table[_NO_DATA] = (*table[0, :3], 0)
    return table


_ERROR_TABLE = _color_table(ERROR_COLORS)


def _error_levels(grid: np.ndarray, scale_max: float) -> np.ndarray:
    """Error grid -> palette indices (uint8); NaN gives _NO_DATA."""
    top = _ERROR_LEVELS - 1
    level = np.rint(np.clip(grid * (top / scale_max), 0.0, top))  # NaN zostaje NaN
    return np.where(np.isnan(level), _NO_DATA, level).astype(np.uint8)


def colorize_error(grid: np.ndarray, scale_max: float = DEFAULT_ERROR_SCALE_MAX) -> np.ndarray:
    """Error grid (H, W) -> (H, W, 4) uint8 RGBA image on the ERROR_COLORS scale.

    The scale is fixed (independent of the query): error 0 is the first colour,
    scale_max and above the last, linear in between (255 colours). NaN gives
    a transparent pixel.
    """
    return _ERROR_TABLE[_error_levels(grid, scale_max)]


def render_error_map(grid: np.ndarray, scale_max: float = DEFAULT_ERROR_SCALE_MAX) -> str:
    """Error grid as a PNG data URI; once decoded it has the same pixels as colorize_error.

    A palette PNG instead of WebP as in the heatmap: the global map encodes about 3 times
    faster and comes out smaller. Compression level 4 chosen by measurement: higher levels
    slow down the global map, lower ones make the detailed maps bigger.
    """
    image = Image.fromarray(_error_levels(grid, scale_max))  # mode L, converted to a palette below
    image.putpalette(_ERROR_TABLE[:, :3].tobytes())
    return _data_uri(image, "image/png", format="PNG", transparency=_NO_DATA, compress_level=4)


@dataclass(frozen=True)
class DetailGrid:
    """Detailed error grid around a point.

    Projection as on the global map (equirectangular, north up):
    the columns split lon_min..lon_max evenly, the rows lat_max..lat_min.
    """

    errors: np.ndarray  # (height, width) float32; NaN = no data
    lat_min: float
    lat_max: float
    lon_min: float  # lon_min/lon_max go beyond [-180, 180] when the window crosses the 180th meridian
    lon_max: float
    point_errors: np.ndarray  # errors of the data points inside the window
    reach_deg: float  # a point fills pixels at most this many degrees away in each axis


def _typical_spacing_deg(x_deg: np.ndarray, y_deg: np.ndarray) -> float:
    """Typical spacing between points, in degrees.

    Median of the |dx| + |dy| distance to the third nearest neighbour. On a
    regular grid with cell s it is exactly s (also when many points
    lie on a coastline); for randomly scattered points it is about
    1.2 / sqrt(density). Computed on an even sample of the points.
    """
    count = x_deg.size
    if count < 2:
        return 360.0 / HEATMAP_WIDTH  # a single point: the cell of the global map grid
    x = x_deg.astype(np.float32)
    y = y_deg.astype(np.float32)
    wanted = min(max(_SPACING_PAIR_BUDGET // count, _SPACING_MIN_SAMPLE), _SPACING_MAX_SAMPLE)
    sample = np.linspace(0, count - 1, min(count, wanted)).astype(np.int64)
    distance = np.abs(x[sample, None] - x[None, :]) + np.abs(y[sample, None] - y[None, :])
    # After sorting, position 0 is the point itself (distance 0), position k is the k-th neighbour.
    neighbour = min(_SPACING_NEIGHBOUR, count - 1)
    return float(np.median(np.partition(distance, neighbour, axis=1)[:, neighbour]))


def _nearest_source(
    height: int, width: int, flat_sources: np.ndarray, step_x: int, step_y: int
) -> np.ndarray:
    """For every grid pixel, the number of the nearest source; -1 when there are no sources.

    Source `i` lies in pixel flat_sources[i] (row * width + column), each
    in a different one. The distance is step_x * |dx| + step_y * |dy|; ties go to the lower number.

    The pixel key is distance * 2^22 + source number, so the minimum key picks
    the smallest distance and its source at once. Such a distance separates into
    the axes: first the minimum along the rows, then along the columns, each in two
    np.minimum.accumulate passes (from the start and from the end of the axis). The cost
    does not depend on the number of sources.
    """
    key = np.full(height * width, _EMPTY, dtype=np.int64)
    key[flat_sources] = np.arange(flat_sources.size)
    key = key.reshape(height, width)
    for axis, step in ((1, step_x), (0, step_y)):
        # key[j] + cost*|i - j| = (key[j] - cost*j) + cost*i for j <= i, and likewise for j >= i.
        cost = np.arange(key.shape[axis], dtype=np.int64) * (step << _ID_BITS)
        cost = cost.reshape((-1, 1) if axis == 0 else (1, -1))
        forward = np.minimum.accumulate(key - cost, axis=axis) + cost
        backward = np.flip(np.minimum.accumulate(np.flip(key + cost, axis), axis=axis), axis) - cost
        key = np.minimum(forward, backward)
    return np.where(key < _EMPTY, key & ((1 << _ID_BITS) - 1), -1)


def detail_error_grid(
    data: EarthData,
    target: np.ndarray,
    weights_norm: np.ndarray,
    lat: float,
    lon: float,
    radius_km: float = DEFAULT_DETAIL_RADIUS_KM,
    size_px: int = DEFAULT_DETAIL_SIZE_PX,
) -> DetailGrid:
    """Detailed error grid for the area around the point (lat, lon).

    target: (K,) target profile, weights_norm: (K,) from scoring.normalize_weights.
    radius_km: the window reaches this many km from the point to the north, south, east and west.
    size_px: grid width; the height is the same unless the window was
        clipped at a pole.

    The global map has one pixel per ~39 km and keeps only the best point in it.
    Here every data point is separate, at its exact position:
    a pixel gets the error of the nearest point (distance |dlon| + |dlat| in degrees),
    as long as it is no farther than reach_deg in each axis; otherwise NaN.
    reach_deg is 0.75 of the typical local point spacing, so the detail of the
    map comes from the data density, not from interpolation.

    Raises ValueError for out-of-range parameters.
    """
    if not -90.0 <= lat <= 90.0:
        raise ValueError("lat: expected a number in [-90, 90]")
    if not math.isfinite(lon):
        raise ValueError("lon: expected a finite number")
    if not MIN_DETAIL_RADIUS_KM <= radius_km <= MAX_DETAIL_RADIUS_KM:
        raise ValueError(
            f"radius_km: expected a number in [{MIN_DETAIL_RADIUS_KM:g}, {MAX_DETAIL_RADIUS_KM:g}]"
        )
    if size_px != int(size_px) or not MIN_DETAIL_SIZE_PX <= size_px <= MAX_DETAIL_SIZE_PX:
        raise ValueError(
            f"size_px: expected an integer in [{MIN_DETAIL_SIZE_PX}, {MAX_DETAIL_SIZE_PX}]"
        )
    width = int(size_px)

    # The window is a square in km: the longitude range grows with latitude.
    half_lat = radius_km / _KM_PER_DEG
    half_lon = min(half_lat / max(math.cos(math.radians(lat)), 1e-9), 180.0)
    lat_min, lat_max = max(lat - half_lat, -90.0), min(lat + half_lat, 90.0)
    height = max(1, round(width * (lat_max - lat_min) / (2.0 * half_lat)))
    deg_x = 2.0 * half_lon / width
    deg_y = (lat_max - lat_min) / height

    index = np.flatnonzero(
        (data.lat >= lat_min - half_lat * _DETAIL_MARGIN) & (data.lat <= lat_max + half_lat * _DETAIL_MARGIN)
    )
    # Longitude difference wrapped to [-180, 180): the window may cross the 180th meridian.
    dlon = (data.lon[index] - lon + 180.0) % 360.0 - 180.0
    near = np.abs(dlon) <= half_lon * (1.0 + _DETAIL_MARGIN)
    index, dlon = index[near], dlon[near]
    monthly = score_block(np.asarray(data.features_norm[index]), target, weights_norm)
    best = np.where(np.isnan(monthly), -np.inf, monthly).max(axis=1)
    valid = np.isfinite(best)
    index, dlon, errors = index[valid], dlon[valid], 1.0 - best[valid]

    # Point positions relative to the window's top-left corner.
    x_deg = dlon + half_lon
    y_deg = lat_max - data.lat[index]
    column = np.floor(x_deg / deg_x).astype(np.int64)
    row = np.floor(y_deg / deg_y).astype(np.int64)
    inside = (column >= 0) & (column < width) & (row >= 0) & (row < height)

    # If a pixel has any point in reach, its nearest point lies at most
    # 2 * reach farther in each axis. The loaded margin must cover that, hence the limit.
    reach = min(_REACH_FACTOR * _typical_spacing_deg(x_deg, y_deg), _DETAIL_MARGIN * half_lat / 2.0)
    result = dict(
        lat_min=lat_min, lat_max=lat_max, lon_min=lon - half_lon, lon_max=lon + half_lon,
        point_errors=errors[inside], reach_deg=reach,
    )

    # Working grid with a border for the points beyond the window edge (2 * reach and one spare pixel).
    pad_x, pad_y = math.ceil(2.0 * reach / deg_x) + 1, math.ceil(2.0 * reach / deg_y) + 1
    work_w, work_h = width + 2 * pad_x, height + 2 * pad_y
    work_x, work_y = column + pad_x, row + pad_y
    in_work = (work_x >= 0) & (work_x < work_w) & (work_y >= 0) & (work_y < work_h)
    flat, source_errors = (work_y * work_w + work_x)[in_work], errors[in_work]
    if not flat.size:
        return DetailGrid(errors=np.full((height, width), np.nan, dtype=np.float32), **result)
    # Several points in one pixel: the one with the smallest error stays.
    order = np.lexsort((source_errors, flat))
    flat, source_errors = flat[order], source_errors[order]
    first = np.ones(flat.size, dtype=bool)
    first[1:] = flat[1:] != flat[:-1]
    flat, source_errors = flat[first], source_errors[first]

    unit = min(deg_x, deg_y) / _SUBPIXEL
    step_x = min(max(round(deg_x / unit), 1), _MAX_STEP)
    step_y = min(max(round(deg_y / unit), 1), _MAX_STEP)
    source = _nearest_source(work_h, work_w, flat, step_x, step_y)
    source = source[pad_y : pad_y + height, pad_x : pad_x + width]

    # The sources exist, so every pixel has a nearest one; it stays when it is within reach.
    source_row, source_column = np.divmod(flat, work_w)
    off_x = np.abs(np.arange(pad_x, pad_x + width) - source_column[source])
    off_y = np.abs(np.arange(pad_y, pad_y + height)[:, None] - source_row[source])
    covered = (off_x * deg_x <= reach) & (off_y * deg_y <= reach)
    grid = np.where(covered, source_errors[source], np.float32(np.nan))
    return DetailGrid(errors=grid, **result)
