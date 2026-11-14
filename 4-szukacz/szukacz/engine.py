"""Pełne wyszukiwanie: wynik w kształcie odpowiedzi POST /search.

Łączy dane (data.py) z liczeniem (scoring.py) i buduje słownik gotowy do
zamiany na JSON. Nie zależy od FastAPI, więc da się go wołać bezpośrednio.
"""

from __future__ import annotations

import base64
import io
import time

import numpy as np
from PIL import Image

from .data import HEATMAP_HEIGHT, HEATMAP_WIDTH, EarthData
from .scoring import normalize_weights, score_all, score_block, select_diverse_top_k

DEFAULT_TOP_K = 100
DEFAULT_MIN_DISTANCE_KM = 100.0
# Próg filtra require_caves; ta sama wartość co w mocku w explorer.php.
DEFAULT_CAVE_MAX_KM = 15.0

# Kolor heatmapy: Signal Emerald z CONTEXT.md (#10B981).
_HEATMAP_RGB = (16, 185, 129)
# Wykładnik > 1 przygasza przeciętne dopasowania i zostawia jasne tylko najlepsze.
_HEATMAP_GAMMA = 2.0


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


def render_heatmap(data: EarthData, point_scores: np.ndarray) -> str:
    """Rzutuje wynik punktów na bitmapę 1024x512 i zwraca ją jako data URI WebP.

    Piksel dostaje najlepszy wynik spośród leżących w nim punktów. Obraz jest
    RGBA: stały kolor #10B981, a krycie rośnie z dopasowaniem. Skala jest
    względna dla danego zapytania: najsłabszy punkt jest przezroczysty,
    najlepszy w pełni kryjący. Piksele bez punktów (oceany, lasy) są przezroczyste.
    """
    rgba = np.zeros((HEATMAP_HEIGHT * HEATMAP_WIDTH, 4), dtype=np.uint8)
    rgba[:, :3] = _HEATMAP_RGB
    if data.pixel_starts.size:
        ordered = np.where(np.isfinite(point_scores), point_scores, np.nan)[data.pixel_order]
        pixel_scores = np.fmax.reduceat(ordered, data.pixel_starts)
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
    buffer = io.BytesIO()
    # Bezstratnie i z exact=True, żeby kanał krycia i kolor pod nim nie były zmieniane.
    image.save(buffer, format="WEBP", lossless=True, quality=0, method=0, exact=True)
    return "data:image/webp;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def search(
    data: EarthData,
    features_norm,
    weights,
    *,
    top_k: int = DEFAULT_TOP_K,
    min_distance_km: float = DEFAULT_MIN_DISTANCE_KM,
    require_caves: bool = False,
    cave_max_km: float = DEFAULT_CAVE_MAX_KM,
) -> dict:
    """Szuka na Ziemi top_k lokalizacji najbliższych profilowi celu.

    features_norm: K znormalizowanych cech celu (z Charakteryzatora).
    weights: K nieujemnych wag cech.
    top_k: ile lokalizacji zwrócić.
    min_distance_km: zwracane lokalizacje są parami dalej niż ta odległość;
        z dwóch bliższych sobie zostaje lepsza. 0 wyłącza odsiewanie.
    require_caves: zwracaj tylko punkty z jaskinią nie dalej niż cave_max_km.

    Zwraca słownik odpowiedzi POST /search (opis pól w README.md). Zgłasza
    ValueError przy błędnych danych wejściowych.
    """
    started = time.perf_counter()
    target = _check_vector("features_norm", features_norm, data.n_features)
    raw_weights = _check_vector("weights", weights, data.n_features)
    if (raw_weights < 0).any():
        raise ValueError("weights: wagi nie mogą być ujemne")
    if top_k < 1:
        raise ValueError("top_k: oczekiwano liczby >= 1")
    if not (min_distance_km >= 0):
        raise ValueError("min_distance_km: oczekiwano liczby >= 0")
    weights_norm = normalize_weights(raw_weights)

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
    heatmap = render_heatmap(data, best_score)

    return {
        "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 2),
        "best_global_month": best_global_month,
        "heatmap_base64": heatmap,
        "candidates": candidates,
    }
