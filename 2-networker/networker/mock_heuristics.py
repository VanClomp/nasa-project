"""=============================================================================
[UWAGA: MOCK HEURYSTYKA - TYLKO AWARYJNY FALLBACK NETWORKERA]
=============================================================================
Ten plik zawiera przybliżone heurystyki fizyczne używane WYŁĄCZNIE wtedy, gdy
docelowy kontener `3-charakteryzator` (port 8001) lub `4-szukacz` (port 8002)
jest niedostępny (np. w trakcie prac na osobnym branchu).

NIE MYLIĆ Z DOCELOWYM KODEM CHARAKTERYZATORA ANI PRECOMPUTERA!
Każda odpowiedź wygenerowana przez ten moduł zawiera pole:
    "_mock_warning": "DANE_Z_MOCKA_HEURYSTYKI_NIE_PRAWDZIWE"
=============================================================================
"""

from __future__ import annotations

import math
from typing import Any

MOCK_BANNER = "DANE_Z_MOCKA_HEURYSTYKI_NIE_PRAWDZIWE"


def heuristic_characterize(
    target_body: str,
    lat: float,
    lon: float,
    timestamp_iso: str | None = None,
) -> dict[str, Any]:
    """Awaryjna heurystyka Charakteryzatora dla punktu (lat, lon) na Księżycu lub Marsie."""
    body = target_body.lower().strip()
    lat_rad = math.radians(abs(lat))
    lon_rad = math.radians(lon)

    if body == "moon":
        # Księżyc: nachylenie osi 1.54°, brak atmosfery (dust=0), zimne bieguny (~40K = -233°C)
        temp_mean = round(-50.0 - 140.0 * math.sin(lat_rad) + 15.0 * math.cos(lon_rad), 1)
        diurnal_amp = round(210.0 * math.cos(lat_rad) + 25.0, 1)
        thermal_inertia = round(45.0 + 35.0 * abs(math.sin(lon_rad * 2.0)), 1)
        roughness = round(0.25 + 0.45 * abs(math.sin(math.radians(lat * 3.0))), 2)
        moisture = round(1.8 + 1.5 * abs(math.cos(lon_rad)), 2) if abs(lat) > 75.0 else 0.1
        dust = 0.0
        solar_max = round(max(1.5, 90.0 - abs(lat) + 1.54), 1)
        radiation = 0.98
        slope = round(4.0 + 14.0 * abs(math.sin(math.radians(lat + lon))), 1)
    else:
        # Mars: nachylenie osi 25.19°, cienka atmosfera CO2 z pyłem (AOD), czapy polarne
        temp_mean = round(-25.0 - 75.0 * math.sin(lat_rad) + 10.0 * math.sin(lon_rad), 1)
        diurnal_amp = round(65.0 * math.cos(lat_rad) + 18.0, 1)
        thermal_inertia = round(140.0 + 160.0 * abs(math.cos(lon_rad)), 1)
        roughness = round(0.20 + 0.50 * abs(math.cos(math.radians(lat * 2.0))), 2)
        moisture = 4.5 if abs(lat) > 65.0 else round(0.8 + 1.4 * abs(math.sin(lat_rad)), 2)
        dust = round(0.18 + 0.45 * abs(math.cos(lat_rad)), 2)
        solar_max = round(max(5.0, 90.0 - abs(lat) + 12.0), 1)
        radiation = round(0.72 + 0.22 * abs(math.sin(lon_rad)), 2)
        slope = round(3.0 + 18.0 * abs(math.sin(math.radians(lon * 1.5))), 1)

    features_norm = [
        round(max(0.0, min(1.0, (temp_mean + 190.0) / 230.0)), 3),
        round(max(0.0, min(1.0, diurnal_amp / 250.0)), 3),
        round(max(0.0, min(1.0, thermal_inertia / 400.0)), 3),
        round(max(0.0, min(1.0, roughness)), 3),
        round(max(0.0, min(1.0, moisture / 15.0)), 3),
        round(max(0.0, min(1.0, dust)), 3),
        round(max(0.0, min(1.0, solar_max / 90.0)), 3),
        round(max(0.0, min(1.0, radiation)), 3),
        round(max(0.0, min(1.0, slope / 35.0)), 3),
    ]

    nearest_skylight_km = round(6.5 + 35.0 * abs(math.sin(math.radians(lat * lon))), 1)

    return {
        "target_body": body,
        "coordinates": {"lat": round(lat, 2), "lon": round(lon, 2)},
        "features_raw": {
            "temp_mean": temp_mean,
            "temp_diurnal_amp": diurnal_amp,
            "thermal_inertia": thermal_inertia,
            "surface_roughness": roughness,
            "soil_moisture": moisture,
            "dust_aerosol": dust,
            "solar_elevation_max": solar_max,
            "radiation_proxy": radiation,
            "slope_deg": slope,
        },
        "features_norm": features_norm,
        "nearest_skylight_km": nearest_skylight_km,
        "_mock_warning": MOCK_BANNER,
    }
