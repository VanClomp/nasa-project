"""Mapy wyników: heatmapa dopasowania i mapy błędu (cała Ziemia, okolica punktu).

Błąd punktu to ważona różnica między profilem celu a cechami punktu w jego
najlepszym miesiącu, czyli dopełnienie dopasowania:

    Error(n) = min_m sum_k(w_k * |X[n, m, k] - y_k|) / sum_k(w_k) = 1 - Score(n)

Funkcje zwracają siatki numpy i gotowe obrazy; nie znają formatu odpowiedzi API.
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

# Kolor heatmapy: Signal Emerald z CONTEXT.md (#10B981).
_HEATMAP_RGB = (16, 185, 129)
# Wykładnik > 1 przygasza przeciętne dopasowania i zostawia jasne tylko najlepsze.
_HEATMAP_GAMMA = 2.0

# Skala mapy błędu: jedna barwa (odcień Ember #F97316 z CONTEXT.md), 9 kolorów
# w równych odstępach jasności OKLCH (0.24 -> 0.94). Ciemny = mały błąd, jasny = duży.
ERROR_COLORS = (
    "#371300", "#582300", "#7B3401", "#A04502", "#C65803", "#EE6B03", "#FF9257", "#FFBE9E", "#FFE5D9",
)
# Błąd, na którym skala się kończy; większe błędy dostają ostatni kolor.
# Na danych mockowych błąd przy kilku cechach mieści się w 0.07..0.47.
DEFAULT_ERROR_SCALE_MAX = 0.5

DEFAULT_DETAIL_RADIUS_KM = 250.0
MIN_DETAIL_RADIUS_KM = 1.0
MAX_DETAIL_RADIUS_KM = 2000.0
DEFAULT_DETAIL_SIZE_PX = 512
MIN_DETAIL_SIZE_PX = 64
MAX_DETAIL_SIZE_PX = 1024

_KM_PER_DEG = math.pi * EARTH_RADIUS_KM / 180.0

# Mapka szczegółowa wczytuje też punkty spoza okna, do tej części jego połowy
# w każdą stronę; dzięki nim piksele przy krawędzi mają komplet sąsiadów.
_DETAIL_MARGIN = 0.5
# Punkt wypełnia piksele odległe od niego najwyżej o tę część typowego odstępu
# punktów (w każdej osi). 0.5 to dokładnie własne oczko regularnej siatki;
# zapas zamyka szczeliny przy nierównym rozkładzie punktów.
_REACH_FACTOR = 0.75
# Odstęp punktów liczony jest do tego sąsiada i na próbce o takim koszcie.
# Trzeci sąsiad: punkt na brzegu regularnej siatki ma ich w odległości oczka trzech.
_SPACING_NEIGHBOUR = 3
_SPACING_PAIR_BUDGET = 2_000_000
_SPACING_MIN_SAMPLE = 16
_SPACING_MAX_SAMPLE = 128

# Klucz piksela w _nearest_source: odległość * 2^22 + numer źródła.
# Siatka ma najwyżej (1.5 * 1024 + 4)^2 < 2^22 pikseli, więc numer się mieści.
_ID_BITS = 22
_EMPTY = 1 << 61
# Krok osi w jednostkach odległości: krótsza oś ma 256, dłuższa proporcjonalnie więcej
# (stosunek osi z dokładnością 0.2%). Z ograniczeniem kroku klucz mieści się w int64.
_SUBPIXEL = 256
_MAX_STEP = 1 << 23


def _data_uri(image: Image.Image, mime: str, **save_options) -> str:
    buffer = io.BytesIO()
    image.save(buffer, **save_options)
    return f"data:{mime};base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def pixel_best_scores(data: EarthData, point_scores: np.ndarray) -> np.ndarray:
    """Najlepszy wynik w każdym zajętym pikselu siatki 1024x512, w kolejności data.pixel_flat.

    Wyniki nieskończone i NaN są pomijane; piksel bez poprawnego wyniku dostaje NaN.
    Wspólny krok heatmapy i mapy błędu: wynik można im przekazać, żeby nie liczyć dwa razy.
    """
    if not data.pixel_starts.size:
        return np.empty(0, dtype=np.float32)
    ordered = np.where(np.isfinite(point_scores), point_scores, np.nan)[data.pixel_order]
    return np.fmax.reduceat(ordered, data.pixel_starts)


def render_heatmap(
    data: EarthData, point_scores: np.ndarray, pixel_scores: np.ndarray | None = None
) -> str:
    """Rzutuje wynik punktów na bitmapę 1024x512 i zwraca ją jako data URI WebP.

    Piksel dostaje najlepszy wynik spośród leżących w nim punktów. Obraz jest
    RGBA: stały kolor #10B981, a krycie rośnie z dopasowaniem. Skala jest
    względna dla danego zapytania: najsłabszy punkt jest przezroczysty,
    najlepszy w pełni kryjący. Piksele bez punktów (oceany, lasy) są przezroczyste.

    pixel_scores: opcjonalnie gotowy wynik pixel_best_scores(data, point_scores).
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
    # Bezstratnie i z exact=True, żeby kanał krycia i kolor pod nim nie były zmieniane.
    return _data_uri(image, "image/webp", format="WEBP", lossless=True, quality=0, method=0, exact=True)


def global_error_grid(
    data: EarthData, point_scores: np.ndarray, pixel_scores: np.ndarray | None = None
) -> np.ndarray:
    """Błąd na całej Ziemi: siatka (512, 1024) float32, NaN tam, gdzie nie ma danych.

    point_scores: (N,) dopasowanie punktów (best_score ze scoring.score_all).
    pixel_scores: opcjonalnie gotowy wynik pixel_best_scores(data, point_scores).
    Piksel dostaje najmniejszy błąd spośród leżących w nim punktów, czyli ten
    sam punkt, który wyznacza piksel heatmapy. Wiersz 0 to północ (lat 90),
    kolumna 0 to lon -180.
    """
    if pixel_scores is None:
        pixel_scores = pixel_best_scores(data, point_scores)
    grid = np.full(HEATMAP_HEIGHT * HEATMAP_WIDTH, np.nan, dtype=np.float32)
    grid[data.pixel_flat] = 1.0 - pixel_scores
    return grid.reshape(HEATMAP_HEIGHT, HEATMAP_WIDTH)


# Obraz mapy błędu ma paletę 256 pozycji: 255 kolorów skali i jedną na brak danych.
_ERROR_LEVELS = 255
_NO_DATA = 255


def _color_table(colors: tuple[str, ...]) -> np.ndarray:
    """Paleta (256, 4) RGBA: 255 kolorów rozpiętych liniowo między kolorami skali.

    Ostatnia pozycja to piksel bez danych: przezroczysty, w pierwszym kolorze skali.
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
    """Siatka błędu -> numery pozycji palety (uint8); NaN daje _NO_DATA."""
    top = _ERROR_LEVELS - 1
    level = np.rint(np.clip(grid * (top / scale_max), 0.0, top))  # NaN zostaje NaN
    return np.where(np.isnan(level), _NO_DATA, level).astype(np.uint8)


def colorize_error(grid: np.ndarray, scale_max: float = DEFAULT_ERROR_SCALE_MAX) -> np.ndarray:
    """Siatka błędu (H, W) -> obraz (H, W, 4) uint8 RGBA w skali ERROR_COLORS.

    Skala jest stała (nie zależy od zapytania): błąd 0 to pierwszy kolor,
    scale_max i więcej to ostatni, pomiędzy liniowo (255 kolorów). NaN daje
    piksel przezroczysty.
    """
    return _ERROR_TABLE[_error_levels(grid, scale_max)]


def render_error_map(grid: np.ndarray, scale_max: float = DEFAULT_ERROR_SCALE_MAX) -> str:
    """Siatka błędu jako data URI PNG; po zdekodowaniu daje te same piksele co colorize_error.

    PNG z paletą zamiast WebP jak w heatmapie: mapa globalna koduje się ok. 3 razy
    szybciej i wychodzi mniejsza. Poziom kompresji 4 dobrany pomiarem: wyższe
    wydłużają kodowanie mapy globalnej, niższe powiększają mapki szczegółowe.
    """
    image = Image.fromarray(_error_levels(grid, scale_max))  # tryb L, niżej zamieniany na paletę
    image.putpalette(_ERROR_TABLE[:, :3].tobytes())
    return _data_uri(image, "image/png", format="PNG", transparency=_NO_DATA, compress_level=4)


@dataclass(frozen=True)
class DetailGrid:
    """Szczegółowa siatka błędu wokół punktu.

    Odwzorowanie jak na mapie globalnej (równoodległościowe, północ u góry):
    kolumny dzielą równo zakres lon_min..lon_max, wiersze lat_max..lat_min.
    """

    errors: np.ndarray  # (height, width) float32; NaN = brak danych
    lat_min: float
    lat_max: float
    lon_min: float  # lon_min/lon_max wychodzą poza [-180, 180], gdy okno przecina południk 180
    lon_max: float
    point_errors: np.ndarray  # błędy punktów danych leżących w oknie
    reach_deg: float  # punkt wypełnia piksele odległe najwyżej o tyle stopni w każdej osi


def _typical_spacing_deg(x_deg: np.ndarray, y_deg: np.ndarray) -> float:
    """Typowy odstęp między punktami, w stopniach.

    Mediana odległości |dx| + |dy| do trzeciego najbliższego sąsiada. Na
    regularnej siatce o oczku s wynosi dokładnie s (także gdy sporo punktów
    leży na brzegu lądu), przy punktach rozrzuconych losowo około
    1.2 / sqrt(gęstość). Liczone na równomiernej próbce punktów.
    """
    count = x_deg.size
    if count < 2:
        return 360.0 / HEATMAP_WIDTH  # samotny punkt: oczko siatki mapy globalnej
    x = x_deg.astype(np.float32)
    y = y_deg.astype(np.float32)
    wanted = min(max(_SPACING_PAIR_BUDGET // count, _SPACING_MIN_SAMPLE), _SPACING_MAX_SAMPLE)
    sample = np.linspace(0, count - 1, min(count, wanted)).astype(np.int64)
    distance = np.abs(x[sample, None] - x[None, :]) + np.abs(y[sample, None] - y[None, :])
    # Pozycja 0 po uporządkowaniu to sam punkt (odległość 0), pozycja k to k-ty sąsiad.
    neighbour = min(_SPACING_NEIGHBOUR, count - 1)
    return float(np.median(np.partition(distance, neighbour, axis=1)[:, neighbour]))


def _nearest_source(
    height: int, width: int, flat_sources: np.ndarray, step_x: int, step_y: int
) -> np.ndarray:
    """Dla każdego piksela siatki numer najbliższego źródła; -1, gdy źródeł nie ma.

    Źródło `i` leży w pikselu flat_sources[i] (wiersz * width + kolumna), każde
    w innym. Odległość to step_x * |dx| + step_y * |dy|; remis wygrywa niższy numer.

    Klucz piksela to odległość * 2^22 + numer źródła, więc minimum klucza wybiera
    naraz najmniejszą odległość i jej źródło. Taka odległość rozkłada się na
    osie: najpierw minimum wzdłuż wierszy, potem wzdłuż kolumn, każde w dwóch
    przebiegach np.minimum.accumulate (od początku i od końca osi). Koszt nie
    zależy od liczby źródeł.
    """
    key = np.full(height * width, _EMPTY, dtype=np.int64)
    key[flat_sources] = np.arange(flat_sources.size)
    key = key.reshape(height, width)
    for axis, step in ((1, step_x), (0, step_y)):
        # key[j] + cost*|i - j| = (key[j] - cost*j) + cost*i dla j <= i, analogicznie dla j >= i.
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
    """Szczegółowa siatka błędu dla okolicy punktu (lat, lon).

    target: (K,) profil celu, weights_norm: (K,) z scoring.normalize_weights.
    radius_km: okno sięga tyle km od punktu na północ, południe, wschód i zachód.
    size_px: szerokość siatki; wysokość jest taka sama, chyba że okno zostało
        przycięte na biegunie.

    Mapa globalna ma jeden piksel na ok. 39 km i zostawia w nim tylko najlepszy
    punkt. Tutaj każdy punkt danych jest osobno, w swoim dokładnym położeniu:
    piksel dostaje błąd najbliższego punktu (odległość |dlon| + |dlat| w stopniach),
    o ile leży on nie dalej niż reach_deg w każdej osi; w przeciwnym razie NaN.
    reach_deg to 0.75 typowego odstępu punktów w okolicy, więc szczegółowość
    mapki wynika z gęstości danych, a nie z interpolacji.

    Zgłasza ValueError przy parametrach spoza zakresu.
    """
    if not -90.0 <= lat <= 90.0:
        raise ValueError("lat: oczekiwano liczby z zakresu [-90, 90]")
    if not math.isfinite(lon):
        raise ValueError("lon: oczekiwano skończonej liczby")
    if not MIN_DETAIL_RADIUS_KM <= radius_km <= MAX_DETAIL_RADIUS_KM:
        raise ValueError(
            f"radius_km: oczekiwano liczby z zakresu [{MIN_DETAIL_RADIUS_KM:g}, {MAX_DETAIL_RADIUS_KM:g}]"
        )
    if size_px != int(size_px) or not MIN_DETAIL_SIZE_PX <= size_px <= MAX_DETAIL_SIZE_PX:
        raise ValueError(
            f"size_px: oczekiwano liczby całkowitej z zakresu [{MIN_DETAIL_SIZE_PX}, {MAX_DETAIL_SIZE_PX}]"
        )
    width = int(size_px)

    # Okno jest kwadratem w km: zakres długości geograficznej rośnie z szerokością.
    half_lat = radius_km / _KM_PER_DEG
    half_lon = min(half_lat / max(math.cos(math.radians(lat)), 1e-9), 180.0)
    lat_min, lat_max = max(lat - half_lat, -90.0), min(lat + half_lat, 90.0)
    height = max(1, round(width * (lat_max - lat_min) / (2.0 * half_lat)))
    deg_x = 2.0 * half_lon / width
    deg_y = (lat_max - lat_min) / height

    index = np.flatnonzero(
        (data.lat >= lat_min - half_lat * _DETAIL_MARGIN) & (data.lat <= lat_max + half_lat * _DETAIL_MARGIN)
    )
    # Różnica długości zawinięta do [-180, 180): okno może przecinać południk 180.
    dlon = (data.lon[index] - lon + 180.0) % 360.0 - 180.0
    near = np.abs(dlon) <= half_lon * (1.0 + _DETAIL_MARGIN)
    index, dlon = index[near], dlon[near]
    monthly = score_block(np.asarray(data.features_norm[index]), target, weights_norm)
    best = np.where(np.isnan(monthly), -np.inf, monthly).max(axis=1)
    valid = np.isfinite(best)
    index, dlon, errors = index[valid], dlon[valid], 1.0 - best[valid]

    # Położenie punktów względem lewego górnego rogu okna.
    x_deg = dlon + half_lon
    y_deg = lat_max - data.lat[index]
    column = np.floor(x_deg / deg_x).astype(np.int64)
    row = np.floor(y_deg / deg_y).astype(np.int64)
    inside = (column >= 0) & (column < width) & (row >= 0) & (row < height)

    # Jeśli piksel ma jakiś punkt w zasięgu, to jego najbliższy punkt leży najwyżej
    # 2 * reach dalej w każdej osi. Wczytany margines musi to pokryć, stąd ograniczenie.
    reach = min(_REACH_FACTOR * _typical_spacing_deg(x_deg, y_deg), _DETAIL_MARGIN * half_lat / 2.0)
    result = dict(
        lat_min=lat_min, lat_max=lat_max, lon_min=lon - half_lon, lon_max=lon + half_lon,
        point_errors=errors[inside], reach_deg=reach,
    )

    # Siatka robocza z ramką na punkty za krawędzią okna (2 * reach i piksel zapasu).
    pad_x, pad_y = math.ceil(2.0 * reach / deg_x) + 1, math.ceil(2.0 * reach / deg_y) + 1
    work_w, work_h = width + 2 * pad_x, height + 2 * pad_y
    work_x, work_y = column + pad_x, row + pad_y
    in_work = (work_x >= 0) & (work_x < work_w) & (work_y >= 0) & (work_y < work_h)
    flat, source_errors = (work_y * work_w + work_x)[in_work], errors[in_work]
    if not flat.size:
        return DetailGrid(errors=np.full((height, width), np.nan, dtype=np.float32), **result)
    # Kilka punktów w jednym pikselu: zostaje ten o najmniejszym błędzie.
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

    # Źródła istnieją, więc każdy piksel ma najbliższe; zostaje, gdy mieści się w zasięgu.
    source_row, source_column = np.divmod(flat, work_w)
    off_x = np.abs(np.arange(pad_x, pad_x + width) - source_column[source])
    off_y = np.abs(np.arange(pad_y, pad_y + height)[:, None] - source_row[source])
    covered = (off_x * deg_x <= reach) & (off_y * deg_y <= reach)
    grid = np.where(covered, source_errors[source], np.float32(np.nan))
    return DetailGrid(errors=grid, **result)
