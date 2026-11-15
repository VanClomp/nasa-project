"""Wyniki w kształcie odpowiedzi API: POST /search i POST /error-map.

Łączy dane (data.py) z liczeniem (scoring.py) i mapami (maps.py) i buduje
słowniki gotowe do zamiany na JSON. Nie zależy od FastAPI, więc da się go
wołać bezpośrednio.
"""

from __future__ import annotations

import math
import time

import numpy as np

from .data import EarthData
from .maps import (
    DEFAULT_DETAIL_RADIUS_KM,
    DEFAULT_DETAIL_SIZE_PX,
    DEFAULT_ERROR_SCALE_MAX,
    ERROR_COLORS,
    detail_error_grid,
    global_error_grid,
    pixel_best_scores,
    render_error_map,
    render_heatmap,
)
from .scoring import normalize_weights, score_all, score_block, select_diverse_top_k

DEFAULT_TOP_K = 100
DEFAULT_MIN_DISTANCE_KM = 100.0
# Próg filtra require_caves; ta sama wartość co w mocku w explorer.php.
DEFAULT_CAVE_MAX_KM = 15.0


def _rounded(values, digits: int):
    """Zaokrągla do typów Pythona; NaN i nieskończoności zamienia na None (JSON null)."""
    array = np.round(np.asarray(values, dtype=np.float64), digits)
    finite = np.isfinite(array)
    if finite.all():
        return array.tolist()
    as_objects = array.astype(object)
    as_objects[~finite] = None
    return as_objects.tolist()


def _check_vector(name: str, values, length: int) -> np.ndarray:
    try:
        vector = np.asarray(values, dtype=np.float32)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name}: oczekiwano listy liczb") from error
    if vector.shape != (length,):
        raise ValueError(f"{name}: oczekiwano {length} liczb, jest {vector.size}")
    if not np.isfinite(vector).all():
        raise ValueError(f"{name}: wartości muszą być skończone")
    return vector


def _check_weights(weights, length: int) -> np.ndarray:
    """Sprawdza wagi i zwraca je podzielone przez sumę."""
    raw_weights = _check_vector("weights", weights, length)
    if (raw_weights < 0).any():
        raise ValueError("weights: wagi nie mogą być ujemne")
    return normalize_weights(raw_weights)


def _check_scale_max(error_scale_max: float) -> float:
    if not (error_scale_max > 0 and math.isfinite(error_scale_max)):
        raise ValueError("error_scale_max: oczekiwano liczby > 0")
    return float(error_scale_max)


def _error_map_payload(grid: np.ndarray, bounds, point_errors: np.ndarray, scale_max: float) -> dict:
    """Mapa błędu w kształcie pola `error_map` (opis w README.md).

    grid: (H, W) błędów z NaN w miejscach bez danych; bounds: (lat_min, lat_max,
    lon_min, lon_max) krawędzi obrazu; point_errors: błędy punktów widocznych na mapie.
    """
    height, width = grid.shape
    if point_errors.size:
        low, mean, high = _rounded(
            [point_errors.min(), point_errors.mean(dtype=np.float64), point_errors.max()], 4
        )
    else:
        low = mean = high = None
    return {
        "image_base64": render_error_map(grid, scale_max),
        "width": width,
        "height": height,
        "bounds": dict(zip(("lat_min", "lat_max", "lon_min", "lon_max"), _rounded(bounds, 5))),
        "scale": {"min": 0.0, "max": scale_max, "colors": list(ERROR_COLORS)},
        "stats": {"n_points": int(point_errors.size), "min": low, "mean": mean, "max": high},
    }


def search(
    data: EarthData,
    features_norm,
    weights,
    *,
    top_k: int = DEFAULT_TOP_K,
    min_distance_km: float = DEFAULT_MIN_DISTANCE_KM,
    require_caves: bool = False,
    cave_max_km: float = DEFAULT_CAVE_MAX_KM,
    error_scale_max: float = DEFAULT_ERROR_SCALE_MAX,
) -> dict:
    """Szuka na Ziemi top_k lokalizacji najbliższych profilowi celu.

    features_norm: K znormalizowanych cech celu (z Charakteryzatora).
    weights: K nieujemnych wag cech.
    top_k: ile lokalizacji zwrócić.
    min_distance_km: zwracane lokalizacje są parami dalej niż ta odległość;
        z dwóch bliższych sobie zostaje lepsza. 0 wyłącza odsiewanie.
    require_caves: zwracaj tylko punkty z jaskinią nie dalej niż cave_max_km.
    error_scale_max: błąd, na którym kończy się skala kolorów mapy błędu.

    Zwraca słownik odpowiedzi POST /search (opis pól w README.md). Zgłasza
    ValueError przy błędnych danych wejściowych.
    """
    started = time.perf_counter()
    target = _check_vector("features_norm", features_norm, data.n_features)
    weights_norm = _check_weights(weights, data.n_features)
    if top_k < 1:
        raise ValueError("top_k: oczekiwano liczby >= 1")
    if not (min_distance_km >= 0):
        raise ValueError("min_distance_km: oczekiwano liczby >= 0")
    error_scale_max = _check_scale_max(error_scale_max)

    best_score, _ = score_all(data.features_norm, target, weights_norm)
    eligible = data.nearest_cave_km <= cave_max_km if require_caves else None
    chosen = select_diverse_top_k(best_score, data.unit_xyz, top_k, min_distance_km, eligible)

    # Sortowanie indeksów przed odczytem z mmap, potem powrót do kolejności rankingu.
    read_order = np.argsort(chosen)
    back = np.argsort(read_order)
    chosen_sorted = chosen[read_order]
    norm_12m = np.asarray(data.features_norm[chosen_sorted])[back]  # (C, 12, K)
    raw_12m = np.asarray(data.features_raw[chosen_sorted])[back]  # (C, 12, K)

    monthly = score_block(norm_12m, target, weights_norm)  # (C, 12)
    monthly_ranked = np.where(np.isnan(monthly), -np.inf, monthly)
    best_month = monthly_ranked.argmax(axis=1)
    rows = np.arange(chosen.size)

    if chosen.size:
        # Miesiąc o najwyższym średnim dopasowaniu wśród zwróconych lokalizacji.
        month_means = np.where(np.isfinite(monthly_ranked), monthly_ranked, np.nan)
        counts = np.isfinite(month_means).sum(axis=0)
        sums = np.nansum(month_means, axis=0)
        means = np.where(counts > 0, sums / np.maximum(counts, 1), -np.inf)
        best_global_month = int(means.argmax()) + 1
    else:
        best_global_month = None

    ids = data.ids[chosen].tolist()
    lats = _rounded(data.lat[chosen], 4)
    lons = _rounded(data.lon[chosen], 4)
    scores = _rounded(monthly[rows, best_month], 4)
    monthly_scores = _rounded(monthly, 4)
    norm_best = _rounded(norm_12m[rows, best_month], 4)
    raw_best = _rounded(raw_12m[rows, best_month], 3)
    climatograms = _rounded(raw_12m.transpose(0, 2, 1), 3)  # (C, K, 12)
    caves = _rounded(data.nearest_cave_km[chosen], 1)
    keys = data.feature_keys

    candidates = [
        {
            "rank": i + 1,
            "id": ids[i],
            "lat": lats[i],
            "lon": lons[i],
            "score": scores[i],
            "best_month": int(best_month[i]) + 1,
            "monthly_scores": monthly_scores[i],
            "features_norm": norm_best[i],
            "features_raw_best_month": dict(zip(keys, raw_best[i])),
            "climatogram_12m": dict(zip(keys, climatograms[i])),
            "nearest_cave_km": caves[i],
        }
        for i in range(chosen.size)
    ]
    # Mapy pokazują wszystkie punkty, także te odrzucone przez filtr jaskiń.
    pixel_scores = pixel_best_scores(data, best_score)
    heatmap = render_heatmap(data, best_score, pixel_scores)
    error_map = _error_map_payload(
        global_error_grid(data, best_score, pixel_scores),
        (-90.0, 90.0, -180.0, 180.0),
        1.0 - best_score[np.isfinite(best_score)],
        error_scale_max,
    )

    return {
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 2),
        "best_global_month": best_global_month,
        "heatmap_base64": heatmap,
        "error_map": error_map,
        "candidates": candidates,
    }


def error_map_detail(
    data: EarthData,
    features_norm,
    weights,
    lat: float,
    lon: float,
    *,
    radius_km: float = DEFAULT_DETAIL_RADIUS_KM,
    size_px: int = DEFAULT_DETAIL_SIZE_PX,
    error_scale_max: float = DEFAULT_ERROR_SCALE_MAX,
) -> dict:
    """Szczegółowa mapa błędu dla okolicy punktu (lat, lon) na Ziemi.

    features_norm, weights: jak w search(); mapa pokazuje ten sam błąd co
        error_map z search(), w tej samej skali kolorów.
    lat, lon: środek mapki w stopniach (x = lon, y = lat).
    radius_km: mapka sięga tyle km od punktu w każdą stronę.
    size_px: szerokość mapki w pikselach.

    Zwraca słownik odpowiedzi POST /error-map (opis pól w README.md). Zgłasza
    ValueError przy błędnych danych wejściowych.
    """
    started = time.perf_counter()
    target = _check_vector("features_norm", features_norm, data.n_features)
    weights_norm = _check_weights(weights, data.n_features)
    error_scale_max = _check_scale_max(error_scale_max)

    detail = detail_error_grid(data, target, weights_norm, lat, lon, radius_km, size_px)
    error_map = _error_map_payload(
        detail.errors,
        (detail.lat_min, detail.lat_max, detail.lon_min, detail.lon_max),
        detail.point_errors,
        error_scale_max,
    )
    return {
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 2),
        "center": {"lat": float(lat), "lon": float(lon)},
        "radius_km": float(radius_km),
        "km_per_px": round(2.0 * float(radius_km) / int(size_px), 4),
        "error_map": error_map,
    }
