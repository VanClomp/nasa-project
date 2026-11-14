"""=============================================================================
⚠️  UWAGA: GENERATOR DANYCH HEURYSTYCZNYCH (MOCK) DLA 5-PRECOMPUTER  ⚠️
=============================================================================
Plik: MOCK_HEURYSTYKA_generate_earth_data.py

Generuje syntetyczne, oparte na heurystykach geofizycznych i klimatycznych
pliki w katalogu `/data/earth` (domyślnie `./data/earth`):
  - earth_features_norm.npy      (N_POINTS, 12, 9) float32 w [0, 1]
  - earth_features_raw.npy       (N_POINTS, 12, 9) float32 (jednostki fizyczne)
  - earth_metadata.npy           tablica strukturalna z kolumnami wymaganymi przez 4-szukacz
  - earth_metadata.parquet       (jeśli zainstalowane jest pyarrow)
  - UWAGA_DANE_MOCK_HEURYSTYKA.txt  (znacznik informujący, że dane pochodzą z mocka)

NIE MYLIĆ Z DOCELOWYM PIPELINE'EM POBIERAJĄCYM DANE Z NASA EARTHDATA / ESA!
=============================================================================
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

N_MONTHS = 12
N_FEATURES = 9
HEATMAP_WIDTH = 1024
HEATMAP_HEIGHT = 512

# Przybliżone prostokąty lądowe (lat_min, lat_max, lon_min, lon_max, waga_gęstości, śr_wys_m, suchość)
# Pozwalają wygenerować punkty tylko na kontynentach (oceany pozostają przezroczyste na heatmapie)
LAND_REGIONS: tuple[tuple[float, float, float, float, float, float, float], ...] = (
    # Antarktyda (kluczowa dla analogów bieguna południowego Księżyca i Marsa)
    (-86.0, -68.0, -180.0, 180.0, 0.22, 2200.0, 0.95),
    # Ameryka Północna (Zachód / Pustynie / Kordyliery + Arktyka Kanadyjska)
    (22.0, 52.0, -124.0, -98.0, 0.12, 1400.0, 0.78),
    (52.0, 81.0, -135.0, -62.0, 0.10, 600.0, 0.70),
    # Grenlandia i Islandia i Svalbard
    (60.0, 82.0, -55.0, -18.0, 0.06, 1800.0, 0.88),
    (63.3, 66.5, -24.0, -13.5, 0.02, 700.0, 0.65),
    (76.5, 80.5, 10.5, 28.0, 0.02, 500.0, 0.80),
    # Ameryka Południowa (Andy, Atacama, Patagonia)
    (-54.0, -14.0, -75.0, -63.0, 0.10, 2900.0, 0.88),
    # Afryka Północna (Sahara, Afar) i Południowa (Namib, Kalahari)
    (12.0, 34.0, -16.0, 43.0, 0.14, 650.0, 0.94),
    (-32.0, -16.0, 12.0, 28.0, 0.05, 1100.0, 0.85),
    # Bliski Wschód i Azja Centralna / Wyżyna Tybetańska / Gobi
    (15.0, 38.0, 34.0, 62.0, 0.07, 900.0, 0.92),
    (28.0, 50.0, 62.0, 112.0, 0.10, 2600.0, 0.86),
    # Australia (Interior)
    (-34.0, -18.0, 114.0, 146.0, 0.06, 450.0, 0.88),
    # Kamczatka / Syberia Wschodnia
    (51.0, 70.0, 135.0, 165.0, 0.04, 950.0, 0.68),
)

# Punkty wulkaniczne / pola lawowe na Ziemi (do realistycznego wyliczania nearest_cave_km)
LAVA_TUBE_HOTSPOTS: tuple[tuple[float, float], ...] = (
    (19.47, -155.59),   # Hawaje (Mauna Loa / Kilauea)
    (64.80, -16.75),    # Islandia (Askja / Surtshellir)
    (43.46, -113.56),   # Craters of the Moon, Idaho
    (41.71, -121.51),   # Lava Beds National Monument, Kalifornia
    (28.27, -16.64),    # Cueva del Viento, Teneryfa
    (29.00, -13.63),    # Cueva de los Verdes, Lanzarote
    (37.75, 15.00),     # Etna, Sycylia
    (56.06, 160.64),    # Tołbaczik, Kamczatka
    (14.25, 40.30),     # Kotlina Danakilska / Erta Ale
    (25.00, 39.90),     # Harrat Khaybar (pola lawowe Arabii Saudyjskiej)
    (-77.53, 167.15),   # Mount Erebus (jaskinie lodowo-wulkaniczne, Antarktyda)
    (-23.30, -67.70),   # Wulkany Andów Środkowych (Licancabur / Lascar)
)

# Katalog kotwiczących analogów referencyjnych (gwarantuje realistyczne wyniki Top-K)
ANCHOR_ANALOGS: tuple[tuple[float, float, float, float, float], ...] = (
    # (lat, lon, elevation_m, aridity 0..1, nearest_cave_km)
    (-77.55, 161.80, 1200.0, 0.99, 14.5),   # McMurdo Dry Valleys, Antarktyda
    (-82.86, 135.00, 3100.0, 0.99, 85.0),   # Płaskowyż Polarny, Antarktyda
    (-75.10, 123.35, 3233.0, 0.99, 120.0),  # Dome C (Concordia), Antarktyda
    (-24.08, -69.92, 2400.0, 0.99, 28.0),   # Pustynia Atacama (Yungay), Chile
    (-23.00, -67.75, 4300.0, 0.96, 8.5),    # Altiplano, Andy
    (19.47, -155.59, 2500.0, 0.82, 1.2),    # Wulkan Mauna Loa (HI-SEAS), Hawaje
    (75.38, -89.68, 450.0, 0.90, 22.0),     # Krater Haughton (Devon Island), Kanada
    (79.40, -90.80, 600.0, 0.91, 35.0),     # Wyspa Axela Heiberga, Kanada
    (78.22, 15.63, 400.0, 0.86, 19.0),      # Svalbard, Norwegia
    (64.80, -16.75, 1100.0, 0.78, 2.4),     # Wyżyna Islandzka (Askja), Islandia
    (38.40, -110.79, 1380.0, 0.92, 18.0),   # MDRS, Utah, USA
    (36.06, -112.14, 1740.0, 0.91, 14.0),   # Wyżyna Kolorado / Meteor Crater, USA
    (43.46, -113.56, 1800.0, 0.89, 0.9),    # Craters of the Moon, Idaho, USA
    (37.72, -6.55, 420.0, 0.80, 16.0),      # Rio Tinto, Hiszpania
    (29.57, 35.42, 950.0, 0.96, 24.0),      # Pustynia Wadi Rum, Jordania
    (30.58, 34.80, 650.0, 0.95, 19.5),      # Krater Ramon (Negew), Izrael
    (30.20, 58.80, 500.0, 0.99, 42.0),      # Pustynia Lut, Iran
    (14.25, 40.30, -100.0, 0.98, 4.2),      # Kotlina Danakilska, Etiopia
    (24.00, 10.00, 1800.0, 0.97, 11.0),     # Góry Ahaggar, Sahara
    (22.00, 25.00, 900.0, 0.99, 55.0),      # Gilf Kebir, Sahara
    (-24.50, 15.50, 600.0, 0.96, 65.0),     # Pustynia Namib, Namibia
    (42.50, 103.50, 1300.0, 0.93, 48.0),    # Pustynia Gobi, Mongolia
    (38.90, 82.20, 1100.0, 0.96, 75.0),     # Pustynia Takla Makan
    (33.00, 88.00, 4700.0, 0.92, 34.0),     # Wyżyna Tybetańska (Changtang)
    (-25.00, 133.00, 480.0, 0.94, 60.0),    # Pustynia Simpsona, Australia
    (28.27, -16.64, 2350.0, 0.88, 1.5),     # Kaldera Las Cañadas (Teide), Teneryfa
    (29.00, -13.63, 350.0, 0.91, 1.1),      # Timanfaya, Lanzarote
    (37.75, 15.00, 2600.0, 0.80, 1.8),      # Wulkan Etna, Sycylia
    (56.06, 160.64, 1600.0, 0.79, 2.5),     # Wulkan Tołbaczik, Kamczatka
)


def _compute_nearest_cave_km(lat: np.ndarray, lon: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Wylicza odległość do najbliższego regionu wulkanicznego / jaskini lawowej."""
    lat_r = np.radians(lat)[:, None]
    lon_r = np.radians(lon)[:, None]

    hot_lats = np.radians([h[0] for h in LAVA_TUBE_HOTSPOTS])[None, :]
    hot_lons = np.radians([h[1] for h in LAVA_TUBE_HOTSPOTS])[None, :]

    dlat = hot_lats - lat_r
    dlon = hot_lons - lon_r
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat_r) * np.cos(hot_lats) * np.sin(dlon / 2.0) ** 2
    dist_km = 2.0 * 6371.0 * np.arcsin(np.minimum(1.0, np.sqrt(a)))
    min_dist = dist_km.min(axis=1)

    # Skalujemy tak, aby w okolicach wulkanicznych (<600 km od hotspotu) były lokalne jaskinie (1..25 km)
    cave_km = np.where(
        min_dist < 400.0,
        1.0 + (min_dist / 400.0) * 14.0,
        15.0 + np.minimum(250.0, (min_dist - 400.0) * 0.08) + rng.uniform(0.0, 20.0, size=lat.shape[0]),
    )
    return cave_km.astype(np.float32)


def generate_mock_earth_dataset(output_dir: str | Path, n_points: int = 60_000, seed: int = 2026) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 76)
    print(" ⚠️  [MOCK HEURYSTYKA] GENEROWANIE SYNTETYCZNYCH DANYCH ZIEMI (/data/earth)")
    print(f"    Katalog docelowy: {out.resolve()}")
    print(f"    Liczba punktów lądowych: {n_points}")
    print("=" * 76)

    rng = np.random.default_rng(seed)
    n_anchors = len(ANCHOR_ANALOGS)
    n_random = max(0, n_points - n_anchors)

    # Losowanie punktów w regionach lądowych proporcjonalnie do wag
    weights = np.array([r[4] for r in LAND_REGIONS], dtype=np.float64)
    weights /= weights.sum()
    counts = np.random.multinomial(n_random, weights)

    lats_list = [np.array([a[0] for a in ANCHOR_ANALOGS], dtype=np.float32)]
    lons_list = [np.array([a[1] for a in ANCHOR_ANALOGS], dtype=np.float32)]
    elev_list = [np.array([a[2] for a in ANCHOR_ANALOGS], dtype=np.float32)]
    arid_list = [np.array([a[3] for a in ANCHOR_ANALOGS], dtype=np.float32)]

    for idx, count in enumerate(counts):
        if count == 0:
            continue
        lat_min, lat_max, lon_min, lon_max, _, mean_elev, mean_arid = LAND_REGIONS[idx]
        r_lat = rng.uniform(lat_min, lat_max, size=count).astype(np.float32)
        r_lon = rng.uniform(lon_min, lon_max, size=count).astype(np.float32)
        r_elev = np.clip(
            rng.normal(mean_elev, 650.0, size=count), -150.0, 5800.0
        ).astype(np.float32)
        r_arid = np.clip(
            rng.normal(mean_arid, 0.08, size=count), 0.15, 0.99
        ).astype(np.float32)
        lats_list.append(r_lat)
        lons_list.append(r_lon)
        elev_list.append(r_elev)
        arid_list.append(r_arid)

    lat = np.concatenate(lats_list)
    lon = np.concatenate(lons_list)
    elevation_m = np.concatenate(elev_list)
    aridity = np.concatenate(arid_list)

    nearest_cave_km = _compute_nearest_cave_km(lat, lon, rng)
    for i, a in enumerate(ANCHOR_ANALOGS):
        nearest_cave_km[i] = a[4]

    # Przeliczenie (lat, lon) na siatkę 1024x512 odwzorowania równoodległościowego
    px_x = np.clip(((lon + 180.0) / 360.0 * HEATMAP_WIDTH).astype(np.int32), 0, HEATMAP_WIDTH - 1)
    px_y = np.clip(((90.0 - lat) / 180.0 * HEATMAP_HEIGHT).astype(np.int32), 0, HEATMAP_HEIGHT - 1)
    ids = np.arange(100_000, 100_000 + n_points, dtype=np.int32)

    # Wektorowe wyliczenie 12 miesięcy (oś 1: m=0..11) i 9 cech (oś 2: k=0..8)
    months = np.arange(N_MONTHS, dtype=np.float32)[None, :]  # (1, 12)
    # Deklinacja słoneczna w miesiącu m (lipiec = m=6 maksimum na półkuli N)
    solar_decl = -23.44 * np.cos(2.0 * np.pi * (months + 0.5) / 12.0)  # (1, 12)

    lat_2d = lat[:, None]          # (N, 1)
    lon_2d = lon[:, None]          # (N, 1)
    elev_2d = elevation_m[:, None] # (N, 1)
    arid_2d = aridity[:, None]     # (N, 1)

    # 6: solar_elevation_max [stopnie, 0..90]
    solar_elev_max = np.clip(90.0 - np.abs(lat_2d - solar_decl), 0.0, 90.0)

    # 0: temp_mean [°C] (zależna od szerokości geogr., pory roku i wysokości n.p.m.)
    base_temp = 28.0 - 0.82 * np.abs(lat_2d) - 0.0065 * np.maximum(0.0, elev_2d)
    # Dodatkowe wychłodzenie wnętrza Antarktydy
    antarctic_chill = np.where(lat_2d < -68.0, -24.0 * ((np.abs(lat_2d) - 68.0) / 22.0), 0.0)
    seasonal_swing = (0.15 + 0.32 * (np.abs(lat_2d) / 90.0)) * (solar_decl * np.sign(lat_2d + 1e-4))
    temp_mean = base_temp + antarctic_chill + seasonal_swing

    # 1: temp_diurnal_amp [°C] (wysoka na suchych wyżynach i przy wysokim Słońcu)
    diurnal_amp = np.clip(
        8.0 + 22.0 * arid_2d + 0.14 * solar_elev_max + 0.002 * np.maximum(0.0, elev_2d),
        3.0,
        48.0,
    )

    # 2: thermal_inertia [TIU, ~40..400]
    rock_factor = np.abs(np.sin(np.radians(lat_2d * 2.3 + lon_2d * 1.7)))
    thermal_inertia = np.clip(60.0 + 260.0 * rock_factor + 0.015 * np.maximum(0.0, elev_2d), 40.0, 395.0)

    # 3: surface_roughness [0.05..0.95]
    roughness_base = np.clip(
        0.15 + 0.45 * np.abs(np.sin(np.radians(lat * 3.1 - lon * 2.2))) + 0.00006 * np.maximum(0.0, elevation_m),
        0.05,
        0.95,
    )[:, None]
    surface_roughness = np.broadcast_to(roughness_base, (n_points, N_MONTHS)).copy()

    # 4: soil_moisture [%, 0.1..15.0]
    moisture_season = 1.0 - 0.25 * np.sin(2.0 * np.pi * (months - 3.0) / 12.0)
    soil_moisture = np.clip((1.0 - arid_2d) * 14.0 * moisture_season + 0.3, 0.1, 15.0)

    # 5: dust_aerosol [AOD, 0.0..1.0] (wyższy na pustyniach zwrotnikowych wiosną/latem)
    desert_belt = np.exp(-((np.abs(lat_2d) - 24.0) / 16.0) ** 2)
    dust_aerosol = np.clip(
        arid_2d * desert_belt * (0.28 + 0.18 * np.sin(2.0 * np.pi * (months - 2.0) / 12.0)),
        0.01,
        0.95,
    )

    # 7: radiation_proxy [0.1..1.0] (funkcja wysokości n.p.m., suchości atmosfery i UV)
    radiation_proxy = np.clip(
        0.45 + 0.35 * (np.maximum(0.0, elev_2d) / 5000.0) + 0.15 * arid_2d + 0.08 * (solar_elev_max / 90.0),
        0.10,
        0.99,
    )

    # 8: slope_deg [stopnie, 0.5..35.0]
    slope_base = np.clip(
        1.5 + 0.0032 * np.maximum(0.0, elevation_m) + 12.0 * np.abs(np.cos(np.radians(lat * 4.0 + lon * 2.5))),
        0.5,
        34.0,
    )[:, None]
    slope_deg = np.broadcast_to(slope_base, (n_points, N_MONTHS)).copy()

    # Złożenie tensora features_raw (N_POINTS, 12, 9) w float32
    features_raw = np.stack(
        [
            temp_mean,
            diurnal_amp,
            thermal_inertia,
            surface_roughness,
            soil_moisture,
            dust_aerosol,
            solar_elev_max,
            radiation_proxy,
            slope_deg,
        ],
        axis=2,
    ).astype(np.float32)

    # Normalizacja kierunkowa do [0.0, 1.0] spójna z Charakteryzatorem i Frontendem
    features_norm = np.empty_like(features_raw, dtype=np.float32)
    features_norm[:, :, 0] = np.clip((features_raw[:, :, 0] + 90.0) / 140.0, 0.0, 1.0)
    features_norm[:, :, 1] = np.clip(features_raw[:, :, 1] / 60.0, 0.0, 1.0)
    features_norm[:, :, 2] = np.clip(features_raw[:, :, 2] / 400.0, 0.0, 1.0)
    features_norm[:, :, 3] = np.clip(features_raw[:, :, 3], 0.0, 1.0)
    features_norm[:, :, 4] = np.clip(features_raw[:, :, 4] / 15.0, 0.0, 1.0)
    features_norm[:, :, 5] = np.clip(features_raw[:, :, 5], 0.0, 1.0)
    features_norm[:, :, 6] = np.clip(features_raw[:, :, 6] / 90.0, 0.0, 1.0)
    features_norm[:, :, 7] = np.clip(features_raw[:, :, 7], 0.0, 1.0)
    features_norm[:, :, 8] = np.clip(features_raw[:, :, 8] / 35.0, 0.0, 1.0)

    # Dopisanie dokładnych profili dla pierwszych 4 flagowych analogów z explorer.php
    # (McMurdo, Atacama, Mauna Loa, Devon Island), aby testy integracyjne były w 100% powtarzalne
    features_norm[0, :, :] = np.array([0.08, 0.55, 0.22, 0.34, 0.03, 0.02, 0.04, 0.85, 0.19], dtype=np.float32)
    features_norm[3, :, :] = np.array([0.48, 0.72, 0.52, 0.29, 0.01, 0.28, 0.49, 0.92, 0.14], dtype=np.float32)
    features_norm[5, :, :] = np.array([0.44, 0.64, 0.76, 0.62, 0.08, 0.06, 0.58, 0.89, 0.38], dtype=np.float32)
    features_norm[6, :, :] = np.array([0.16, 0.46, 0.34, 0.48, 0.12, 0.03, 0.08, 0.79, 0.26], dtype=np.float32)

    features_norm = np.ascontiguousarray(features_norm, dtype=np.float32)
    features_raw = np.ascontiguousarray(features_raw, dtype=np.float32)

    np.save(out / "earth_features_norm.npy", features_norm)
    np.save(out / "earth_features_raw.npy", features_raw)

    meta_dtype = np.dtype(
        [
            ("id", "<i4"),
            ("lat", "<f4"),
            ("lon", "<f4"),
            ("px_x", "<i4"),
            ("px_y", "<i4"),
            ("elevation_m", "<f4"),
            ("nearest_cave_km", "<f4"),
        ]
    )
    meta_records = np.empty(n_points, dtype=meta_dtype)
    meta_records["id"] = ids
    meta_records["lat"] = lat
    meta_records["lon"] = lon
    meta_records["px_x"] = px_x
    meta_records["px_y"] = px_y
    meta_records["elevation_m"] = elevation_m
    meta_records["nearest_cave_km"] = nearest_cave_km
    np.save(out / "earth_metadata.npy", meta_records)

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.table(
            {
                "id": ids,
                "lat": lat,
                "lon": lon,
                "px_x": px_x,
                "px_y": px_y,
                "elevation_m": elevation_m,
                "nearest_cave_km": nearest_cave_km,
            }
        )
        pq.write_table(table, out / "earth_metadata.parquet")
        print(" -> Zapisano earth_metadata.parquet oraz earth_metadata.npy")
    except ImportError:
        print(" -> Zapisano earth_metadata.npy (brak pyarrow, pominięto .parquet - 4-szukacz obsługuje .npy)")

    marker_file = out / "UWAGA_DANE_MOCK_HEURYSTYKA.txt"
    marker_file.write_text(
        "UWAGA! Pliki .npy/.parquet w tym katalogu zostały wygenerowane przez skrypt:\n"
        "5-precomputer/MOCK_HEURYSTYKA_generate_earth_data.py\n"
        "Są to dane oparte na heurystykach klimatyczno-geograficznych do testów integracyjnych.\n"
        "Po wygenerowaniu prawdziwych danych satelitarnych usuń ten plik.\n",
        encoding="utf-8",
    )
    print(f" -> Zapisano znacznik mocka: {marker_file.name}")
    print(" Gotowe!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generator danych heurystycznych (MOCK) dla /data/earth")
    parser.add_argument("--output-dir", default="./data/earth", help="Katalog wyjściowy (domyślnie ./data/earth)")
    parser.add_argument("--n-points", type=int, default=60000, help="Liczba punktów lądowych (domyślnie 60000)")
    args = parser.parse_args()
    generate_mock_earth_dataset(args.output_dir, n_points=args.n_points)
