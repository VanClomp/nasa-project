"""=============================================================================
⚠️  UWAGA: TO JEST MOCK HEURYSTYCZNY KOMPONENTU 3-CHARAKTERYZATOR  ⚠️
=============================================================================
Plik: MOCK_HEURYSTYKA_charakteryzator_api.py

Ten serwis NIE CZYTA prawdziwych plików Cloud-Optimized GeoTIFF (.tif)
z wolumenu /data/moon ani /data/mars. Zamiast tego wylicza realistyczne,
deterministyczne wartości fizyczne na podstawie heurystyk planetarnych
(szerokość geograficzna, nachylenie osi obrotu, kratery biegunowe, ekspozycja
słoneczna), aby cały system działał end-to-end na serwerze przed wdrożeniem
docelowego kodu 3-charakteryzator.
=============================================================================
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("MOCK_HEURYSTYKA_charakteryzator")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MOCK-HEURYSTYKA-CHARAKTERYZATOR] %(message)s",
)

MOCK_WARNING_TEXT = "UWAGA_DANE_Z_MOCKA_HEURYSTYKI_3_CHARAKTERYZATOR"

# Znane punkty referencyjne (skatalogowane jamy lawowe / skylights na Księżycu i Marsie)
# (lat, lon) -> pozwala realistycznie wyliczyć odległość `nearest_skylight_km`
KNOWN_SKYLIGHTS: dict[str, tuple[tuple[float, float, float], ...]] = {
    "moon": (
        (-85.2, 31.4, 14.2),   # Shackleton / rejon bieguna południowego
        (14.2, -56.8, 0.8),    # Marius Hills Pit
        (8.3, 30.8, 1.2),      # Mare Tranquillitatis Pit
        (26.3, 3.6, 4.5),      # Rima Hadley (Apollo 15)
        (-89.5, 0.0, 18.0),    # Krater Shackleton
    ),
    "mars": (
        (18.4, 77.5, 19.5),    # Jezero Crater (okolice Syrtis Major)
        (-14.6, 175.5, 11.0),  # Gusev Crater
        (-4.5, 137.4, 24.0),   # Gale Crater
        (1.9, -7.5, 32.0),     # Meridiani Planum
        (-7.0, -112.5, 1.5),   # Arsia Mons Skylights (Seven Sisters)
        (0.8, -113.1, 2.2),    # Pavonis Mons Lava Tubes
    ),
}


class CharacterizeRequest(BaseModel):
    target_body: Literal["moon", "mars"] = "moon"
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    timestamp_iso: str = "2026-11-14T12:00:00Z"


app = FastAPI(
    title="[MOCK HEURYSTYKA] 3-Charakteryzator",
    description="Tymczasowy serwis heurystyczny zastępujący odczyt COG z /data/moon i /data/mars.",
)


@app.on_event("startup")
def _startup_banner() -> None:
    logger.warning("=" * 74)
    logger.warning(" URUCHOMIONO [MOCK HEURYSTYKA] DLA 3-CHARAKTERYZATOR (PORT 8001)")
    logger.warning(" Dane są wyliczane z heurystyk matematycznych, NIE z plików COG (.tif)!")
    logger.warning("=" * 74)


def _great_circle_km(lat1: float, lon1: float, lat2: float, lon2: float, radius_km: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * radius_km * math.asin(min(1.0, math.sqrt(a)))


def _parse_day_of_year(timestamp_iso: str) -> int:
    try:
        cleaned = timestamp_iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.timetuple().tm_yday
    except Exception:
        return 318  # 14 listopada


def _compute_heuristic_profile(body: str, lat: float, lon: float, timestamp_iso: str) -> dict[str, Any]:
    lat_abs = abs(lat)
    lat_rad = math.radians(lat_abs)
    lon_rad = math.radians(lon)
    doy = _parse_day_of_year(timestamp_iso)
    seasonal_phase = math.sin(2.0 * math.pi * (doy - 80) / 365.25)

    if body == "moon":
        # Księżyc: nachylenie osi 1.54°, promień 1737.4 km, brak atmosfery
        axial_tilt = 1.54 * seasonal_phase * (1.0 if lat >= 0 else -1.0)
        solar_max = round(max(0.0, min(90.0, 90.0 - lat_abs + axial_tilt)), 1)

        # Temperatura średnia: od ~-25°C na równiku do ~-195°C przy biegunach (PSR ~ -233°C)
        polar_drop = -145.0 * (math.sin(lat_rad) ** 1.35)
        crater_mod = 12.0 * math.cos(lon_rad) * math.cos(lat_rad)
        temp_mean = round(-42.0 + polar_drop + crater_mod, 1)

        # Dobowa amplituda: bardzo wysoka na równiku (~230°C), niska w cieniach biegunowych (~35°C)
        diurnal_amp = round(215.0 * math.cos(lat_rad) + 25.0, 1)

        # Bezwładność cieplna regolitu (typ. 40 - 95 TIU, wyższa w morzach bazaltowych)
        mare_factor = 1.0 if (-20.0 <= lat <= 40.0 and -70.0 <= lon <= 45.0) else 0.4
        thermal_inertia = round(45.0 + 38.0 * mare_factor + 18.0 * abs(math.sin(lon_rad * 2.0)), 1)

        # Chropowatość powierzchni (wyżyny południowe bardziej chropowate niż morza księżycowe)
        roughness = round(min(0.95, 0.22 + 0.35 * (1.0 - mare_factor) + 0.25 * abs(math.sin(math.radians(lat * 3.0)))), 2)

        # Lód wodny w regolicie (LEND/Diviner: skoncentrowany w kraterach biegunowych > 75°)
        if lat_abs >= 80.0:
            moisture = round(2.2 + 2.8 * abs(math.cos(lon_rad)), 2)
        elif lat_abs >= 70.0:
            moisture = round(0.6 + 1.1 * abs(math.sin(lon_rad)), 2)
        else:
            moisture = 0.05

        dust = 0.0
        radiation = 0.98
        slope = round(4.5 + 14.0 * abs(math.sin(math.radians(lat * 1.7 + lon))), 1)
        radius_km = 1737.4

    else:
        # Mars: nachylenie osi 25.19°, promień 3389.5 km, cienka atmosfera z pyłem
        axial_tilt = 25.19 * seasonal_phase * (1.0 if lat >= 0 else -1.0)
        solar_max = round(max(0.0, min(90.0, 90.0 - lat_abs + axial_tilt)), 1)

        temp_mean = round(-22.0 - 78.0 * (math.sin(lat_rad) ** 1.2) + 8.0 * math.sin(lon_rad) + 0.4 * axial_tilt, 1)
        diurnal_amp = round(68.0 * math.cos(lat_rad) + 18.0, 1)
        thermal_inertia = round(135.0 + 170.0 * abs(math.cos(lon_rad * 1.3)), 1)
        roughness = round(0.20 + 0.50 * abs(math.cos(math.radians(lat * 2.0 - lon * 0.5))), 2)

        if lat_abs >= 65.0:
            moisture = round(4.2 + 2.5 * abs(math.sin(lon_rad)), 2)
        else:
            moisture = round(0.8 + 1.6 * abs(math.sin(lat_rad)), 2)

        dust = round(0.18 + 0.45 * abs(math.cos(lat_rad)) + 0.12 * abs(math.sin(lon_rad)), 2)
        radiation = round(0.74 + 0.20 * abs(math.sin(lon_rad)), 2)
        slope = round(3.0 + 17.5 * abs(math.sin(math.radians(lon * 1.5 + lat))), 1)
        radius_km = 3389.5

    # Odległość do najbliższego skylightu / tunelu lawowego
    min_skylight = round(12.0 + 40.0 * abs(math.sin(math.radians(lat * 2.0 + lon))), 1)
    for s_lat, s_lon, base_dist in KNOWN_SKYLIGHTS.get(body, ()):
        d = _great_circle_km(lat, lon, s_lat, s_lon, radius_km)
        if d < 120.0:
            min_skylight = round(base_dist + d * 0.25, 1)
            break

    # Znormalizowany wektor 9 cech w skali [0.0, 1.0] zgodny ze specyfikacją i 4-szukacz
    features_norm = [
        round(max(0.0, min(1.0, (temp_mean + 190.0) / 230.0)), 4),
        round(max(0.0, min(1.0, diurnal_amp / 250.0)), 4),
        round(max(0.0, min(1.0, thermal_inertia / 400.0)), 4),
        round(max(0.0, min(1.0, roughness)), 4),
        round(max(0.0, min(1.0, moisture / 15.0)), 4),
        round(max(0.0, min(1.0, dust)), 4),
        round(max(0.0, min(1.0, solar_max / 90.0)), 4),
        round(max(0.0, min(1.0, radiation)), 4),
        round(max(0.0, min(1.0, slope / 35.0)), 4),
    ]

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
        "nearest_skylight_km": min_skylight,
        "_mock_warning": MOCK_WARNING_TEXT,
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "3-charakteryzator",
        "is_mock_heuristic": True,
        "warning": MOCK_WARNING_TEXT,
    }


@app.post("/characterize")
def characterize(body: CharacterizeRequest) -> JSONResponse:
    result = _compute_heuristic_profile(
        body=body.target_body,
        lat=body.lat,
        lon=body.lon,
        timestamp_iso=body.timestamp_iso,
    )
    return JSONResponse(content=result, headers={"X-Mock-Heuristic": "true"})
