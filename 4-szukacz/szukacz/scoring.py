"""Match scoring and selection of a diverse Top-K.

A purely numerical module: it reads no files and knows nothing about the API response format.

    Score(n, m) = 1 - sum_k(w_k * |X[n, m, k] - y_k|) / sum_k(w_k)
"""

from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np

EARTH_RADIUS_KM = 6371.0088

# Size of the block of points computed at once: (2048, 12, 9) float32 is about 0.9 MB,
# so one thread's working data fits in the CPU cache.
# Value chosen by measurement (1024..16384) on 400k points.
_CHUNK_POINTS = 2048
# The diverse Top-K search starts from this many best points.
_MIN_POOL = 16384
_POOL_GROWTH = 8

_executor: ThreadPoolExecutor | None = None


def _pool() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        workers = int(os.environ.get("SZUKACZ_THREADS", "0")) or min(os.cpu_count() or 1, 16)
        _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="szukacz-score")
    return _executor


def normalize_weights(weights: np.ndarray) -> np.ndarray:
    """Returns the weights divided by their sum (float32).

    When the weights sum to 0 the denominator becomes 1, so every point
    gets a score of 1.0. The frontend computes it the same way when recalculating live.
    """
    w = np.asarray(weights, dtype=np.float64)
    total = float(w.sum())
    return (w / (total if total > 1e-12 else 1.0)).astype(np.float32)


def score_block(block: np.ndarray, target: np.ndarray, weights_norm: np.ndarray) -> np.ndarray:
    """Match for a block of features of shape (..., K); returns an array (...)."""
    diff = np.subtract(block, target, dtype=np.float32)
    np.abs(diff, out=diff)
    penalty = diff.reshape(-1, diff.shape[-1]) @ weights_norm
    np.subtract(1.0, penalty, out=penalty)
    return penalty.reshape(diff.shape[:-1])


def score_all(
    features: np.ndarray, target: np.ndarray, weights_norm: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Scores all points and months and keeps the best month.

    features: (N, M, K) float32, target: (K,), weights_norm: (K,) z normalize_weights.
    Returns (best_score (N,) float32, best_month (N,) int8, months counted from 0).
    A month with a NaN score (no data) loses to any other; a point without
    any valid month gets a score of -inf.
    """
    n_points = features.shape[0]
    if _score_kernel is not None and n_points:
        # Compiled single pass over the data (no temporary arrays), parallel over points.
        return _score_kernel(np.asarray(features, dtype=np.float32), np.asarray(target, dtype=np.float32),
                             np.asarray(weights_norm, dtype=np.float32))
    best_score = np.empty(n_points, dtype=np.float32)
    best_month = np.empty(n_points, dtype=np.int8)

    def work(start: int) -> None:
        stop = min(start + _CHUNK_POINTS, n_points)
        scores = score_block(features[start:stop], target, weights_norm)
        if np.isnan(scores).any():
            scores[np.isnan(scores)] = -np.inf
        best_month[start:stop] = scores.argmax(axis=1)
        best_score[start:stop] = scores.max(axis=1)

    starts = range(0, n_points, _CHUNK_POINTS)
    if n_points <= _CHUNK_POINTS:
        for start in starts:
            work(start)
    else:
        # list() forces execution and re-raises any exception from the thread.
        list(_pool().map(work, starts))
    return best_score, best_month


def _score_all_loop(features, target, weights_norm):
    """score_all for numba: per point and month 1 - sum_k(w_k * |x - y_k|) in float32, NaN months lose
    (-inf), ties go to the earlier month, as numpy's argmax does."""
    n, m, k = features.shape
    best_score = np.empty(n, dtype=np.float32)
    best_month = np.empty(n, dtype=np.int8)
    for i in numba.prange(n):
        best = np.float32(-np.inf)
        bm = 0
        for j in range(m):
            penalty = np.float32(0.0)
            for f in range(k):
                penalty += weights_norm[f] * abs(features[i, j, f] - target[f])
            s = np.float32(1.0) - penalty
            if s != s:                     # NaN: missing data
                s = np.float32(-np.inf)
            if s > best:
                best = s
                bm = j
        best_score[i] = best
        best_month[i] = bm
    return best_score, best_month


try:                                       # optional: without numba the numpy blocks above are used
    import numba

    _score_kernel = numba.njit(parallel=True, cache=True)(_score_all_loop)
except ImportError:
    _score_kernel = None


def latlon_to_unit_xyz(lat_deg: np.ndarray, lon_deg: np.ndarray) -> np.ndarray:
    """Geographic coordinates -> unit vectors (N, 3) float64."""
    lat = np.radians(np.asarray(lat_deg, dtype=np.float64))
    lon = np.radians(np.asarray(lon_deg, dtype=np.float64))
    cos_lat = np.cos(lat)
    return np.stack((cos_lat * np.cos(lon), cos_lat * np.sin(lon), np.sin(lat)), axis=1)


def great_circle_km(unit_a: np.ndarray, unit_b: np.ndarray) -> np.ndarray:
    """Distance along the Earth's surface between unit vectors (numpy broadcasting)."""
    return EARTH_RADIUS_KM * np.arccos(np.clip(np.sum(unit_a * unit_b, axis=-1), -1.0, 1.0))


def _top_descending(values: np.ndarray, count: int) -> np.ndarray:
    """Positions of the `count` largest values, descending; ties go to the lower index."""
    if count < values.size:
        positions = np.sort(np.argpartition(values, values.size - count)[values.size - count:])
    else:
        positions = np.arange(values.size)
    return positions[np.argsort(-values[positions], kind="stable")]


def _greedy_spread(unit_xyz: np.ndarray, top_k: int, cos_limit: float) -> np.ndarray:
    """Greedy selection from points sorted by descending score.

    Takes the best remaining point and strikes out all points no farther from it
    than the limit (angle cosine >= cos_limit). Returns the positions selected.
    """
    alive = np.ones(unit_xyz.shape[0], dtype=bool)
    chosen: list[int] = []
    pos = 0
    while len(chosen) < top_k and pos < alive.size:
        step = int(alive[pos:].argmax())
        if not alive[pos + step]:
            break
        pos += step
        chosen.append(pos)
        alive[pos:] &= unit_xyz[pos:] @ unit_xyz[pos] < cos_limit
        alive[pos] = False
        pos += 1
    return np.asarray(chosen, dtype=np.int64)


def select_diverse_top_k(
    scores: np.ndarray,
    unit_xyz: np.ndarray,
    top_k: int,
    min_distance_km: float,
    eligible: np.ndarray | None = None,
) -> np.ndarray:
    """Indices of the best points, pairwise more than min_distance_km apart.

    Points are scanned from the best. A point too close to an already chosen,
    better point is skipped and the next one in the ranking takes its place,
    so the result has top_k entries as long as that many separate places exist.

    scores: (N,) score of each point (higher is better); infinite values
        and NaN are skipped.
    unit_xyz: (N, 3) z latlon_to_unit_xyz.
    min_distance_km: 0 turns the filtering off (plain Top-K).
    eligible: optional (N,) mask of the points that may be returned.
    Returns indices (<= top_k) in order of descending score.
    """
    scores = np.asarray(scores)
    mask = np.isfinite(scores)
    if eligible is not None:
        mask &= eligible
    candidates = np.flatnonzero(mask)
    if top_k <= 0 or candidates.size == 0:
        return np.empty(0, dtype=np.int64)
    candidate_scores = scores[candidates]

    if min_distance_km <= 0:
        return candidates[_top_descending(candidate_scores, min(top_k, candidates.size))]

    cos_limit = math.cos(min(min_distance_km / EARTH_RADIUS_KM, math.pi))
    pool = min(candidates.size, max(top_k * 64, _MIN_POOL))
    while True:
        ranked = candidates[_top_descending(candidate_scores, pool)]
        chosen = ranked[_greedy_spread(unit_xyz[ranked], top_k, cos_limit)]
        # Not enough separate places among the `pool` best: search deeper.
        if chosen.size >= top_k or pool >= candidates.size:
            return chosen
        pool = min(candidates.size, pool * _POOL_GROWTH)
