"""Liczenie dopasowania i wybór zróżnicowanego Top-K.

Moduł czysto numeryczny: nie czyta plików i nie zna formatu odpowiedzi API.

    Score(n, m) = 1 - sum_k(w_k * |X[n, m, k] - y_k|) / sum_k(w_k)
"""

from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np

EARTH_RADIUS_KM = 6371.0088

# Rozmiar bloku punktów liczonego naraz: (2048, 12, 9) float32 to ok. 0,9 MB,
# czyli dane robocze jednego wątku mieszczą się w pamięci podręcznej procesora.
# Wartość dobrana pomiarem (1024..16384) na 400 tys. punktów.
_CHUNK_POINTS = 2048
# Od tylu najlepszych punktów zaczyna się szukanie zróżnicowanego Top-K.
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
    """Zwraca wagi podzielone przez ich sumę (float32).

    Gdy suma wag wynosi 0, mianownik przyjmuje wartość 1, czyli każdy punkt
    dostaje wynik 1.0. Tak samo liczy frontend przy przeliczaniu na żywo.
    """
    w = np.asarray(weights, dtype=np.float64)
    total = float(w.sum())
    return (w / (total if total > 1e-12 else 1.0)).astype(np.float32)


def score_block(block: np.ndarray, target: np.ndarray, weights_norm: np.ndarray) -> np.ndarray:
    """Dopasowanie dla bloku cech o kształcie (..., K); zwraca tablicę (...)."""
    diff = np.subtract(block, target, dtype=np.float32)
    np.abs(diff, out=diff)
    penalty = diff.reshape(-1, diff.shape[-1]) @ weights_norm
    np.subtract(1.0, penalty, out=penalty)
    return penalty.reshape(diff.shape[:-1])


def score_all(
    features: np.ndarray, target: np.ndarray, weights_norm: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Liczy dopasowanie wszystkich punktów i miesięcy, zostawia najlepszy miesiąc.

    features: (N, M, K) float32, target: (K,), weights_norm: (K,) z normalize_weights.
    Zwraca (best_score (N,) float32, best_month (N,) int8, miesiące liczone od 0).
    Miesiąc z wynikiem NaN (brak danych) przegrywa z każdym innym; punkt bez
    żadnego poprawnego miesiąca dostaje wynik -inf.
    """
    n_points = features.shape[0]
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
        # list() wymusza wykonanie i przenosi ewentualny wyjątek z wątku.
        list(_pool().map(work, starts))
    return best_score, best_month


def latlon_to_unit_xyz(lat_deg: np.ndarray, lon_deg: np.ndarray) -> np.ndarray:
    """Współrzędne geograficzne -> wektory jednostkowe (N, 3) float64."""
    lat = np.radians(np.asarray(lat_deg, dtype=np.float64))
    lon = np.radians(np.asarray(lon_deg, dtype=np.float64))
    cos_lat = np.cos(lat)
    return np.stack((cos_lat * np.cos(lon), cos_lat * np.sin(lon), np.sin(lat)), axis=1)


def great_circle_km(unit_a: np.ndarray, unit_b: np.ndarray) -> np.ndarray:
    """Odległość po powierzchni Ziemi między wektorami jednostkowymi (rozgłaszanie numpy)."""
    return EARTH_RADIUS_KM * np.arccos(np.clip(np.sum(unit_a * unit_b, axis=-1), -1.0, 1.0))


def _top_descending(values: np.ndarray, count: int) -> np.ndarray:
    """Pozycje `count` największych wartości, malejąco; remisy wygrywa niższy indeks."""
    if count < values.size:
        positions = np.sort(np.argpartition(values, values.size - count)[values.size - count:])
    else:
        positions = np.arange(values.size)
    return positions[np.argsort(-values[positions], kind="stable")]


def _greedy_spread(unit_xyz: np.ndarray, top_k: int, cos_limit: float) -> np.ndarray:
    """Zachłanny wybór z punktów posortowanych malejąco po wyniku.

    Bierze najlepszy pozostały punkt i skreśla wszystkie leżące od niego nie
    dalej niż limit (cosinus kąta >= cos_limit). Zwraca pozycje wybranych.
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
    """Indeksy najlepszych punktów, parami oddalonych o więcej niż min_distance_km.

    Punkty są przeglądane od najlepszego. Punkt leżący za blisko już wybranego,
    lepszego punktu jest pomijany, a jego miejsce zajmuje kolejny z rankingu,
    więc wynik ma top_k pozycji, o ile tyle rozłącznych miejsc istnieje.

    scores: (N,) wynik punktu (im większy, tym lepszy); wartości nieskończone
        i NaN są pomijane.
    unit_xyz: (N, 3) z latlon_to_unit_xyz.
    min_distance_km: 0 wyłącza odsiewanie (zwykłe Top-K).
    eligible: opcjonalna maska (N,) punktów, które wolno zwrócić.
    Zwraca indeksy (<= top_k) w kolejności malejącego wyniku.
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
        # Za mało rozłącznych miejsc wśród `pool` najlepszych: szukamy głębiej.
        if chosen.size >= top_k or pool >= candidates.size:
            return chosen
        pool = min(candidates.size, pool * _POOL_GROWTH)
