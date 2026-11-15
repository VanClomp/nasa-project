"""Fast region naming (name_hint) from coordinates (lat, lon).

Solves item 3 of todo_list.txt: the Szukacz (4-szukacz) returns only raw coordinates (lat, lon) without the
`name_hint` field that explorer.php expects.
"""

from __future__ import annotations

import math

# Catalogue of known terrestrial planetary analogs and characteristic geographic regions:
# (lat, lon, radius_km, name)
KNOWN_ANALOG_REGIONS: tuple[tuple[float, float, float, str], ...] = (
    (-77.55, 161.80, 350.0, "McMurdo Dry Valleys, Antarctica"),
    (-82.86, 135.00, 1200.0, "Polar Plateau, East Antarctica"),
    (-75.10, 123.35, 900.0, "Dome C (Concordia), Antarctica"),
    (-24.08, -69.92, 450.0, "Atacama Desert (Yungay), Chile"),
    (-23.00, -67.75, 350.0, "Altiplano / Laguna Colorada, Andes"),
    (19.47, -155.59, 220.0, "Mauna Loa volcano (HI-SEAS), Hawaii"),
    (75.38, -89.68, 450.0, "Haughton Crater (Devon Island), Canada"),
    (79.40, -90.80, 500.0, "Axel Heiberg Island, Canadian Arctic"),
    (78.22, 15.63, 450.0, "Svalbard (Spitsbergen), Norway"),
    (64.80, -16.75, 300.0, "Icelandic Highlands (Askja / Holuhraun), Iceland"),
    (38.40, -110.79, 350.0, "Mars Desert Research Station (MDRS), Utah, USA"),
    (36.06, -112.14, 300.0, "Colorado Plateau / Meteor Crater, Arizona, USA"),
    (43.46, -113.56, 300.0, "Craters of the Moon (Lava Beds), Idaho, USA"),
    (37.72, -6.55, 250.0, "Rio Tinto, Andalusia, Spain"),
    (29.57, 35.42, 350.0, "Wadi Rum Desert, Jordan"),
    (30.58, 34.80, 250.0, "Ramon Crater (Negev), Israel"),
    (30.20, 58.80, 550.0, "Lut Desert (Dasht-e Lut), Iran"),
    (14.25, 40.30, 400.0, "Danakil Depression (Afar), Ethiopia"),
    (24.00, 10.00, 1400.0, "Ahaggar Mountains / Tassili, central Sahara"),
    (22.00, 25.00, 1200.0, "Libyan Desert (Gilf Kebir), Sahara"),
    (-24.50, 15.50, 600.0, "Namib Desert, Namibia"),
    (42.50, 103.50, 900.0, "Gobi Desert, Mongolia / China"),
    (38.90, 82.20, 700.0, "Taklamakan Desert (Tarim Basin)"),
    (33.00, 88.00, 950.0, "Tibetan Plateau (Changtang)"),
    (-25.00, 133.00, 1200.0, "Simpson Desert / Red Centre, Australia"),
    (28.27, -16.64, 200.0, "Las Cañadas caldera (Teide), Tenerife"),
    (29.00, -13.63, 200.0, "Timanfaya lava fields, Lanzarote"),
    (37.75, 15.00, 180.0, "Mount Etna volcanic massif, Sicily"),
    (56.06, 160.64, 450.0, "Tolbachik volcanic massif, Kamchatka"),
)

EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def resolve_name_hint(lat: float, lon: float) -> str:
    """Return a readable description of the region at the given coordinates (lat, lon)."""
    best_name: str | None = None
    best_dist = float("inf")

    for r_lat, r_lon, radius_km, name in KNOWN_ANALOG_REGIONS:
        dist = _haversine_km(lat, lon, r_lat, r_lon)
        if dist <= radius_km and dist < best_dist:
            best_dist = dist
            best_name = name

    if best_name is not None:
        return best_name

    # General geographic belts when the point lies outside the catalogued analogs
    if lat <= -66.5:
        return f"Antarctic zone ({abs(lat):.1f}°S, {abs(lon):.1f}°{'E' if lon >= 0 else 'W'})"
    if lat >= 66.5:
        return f"Arctic zone ({lat:.1f}°N, {abs(lon):.1f}°{'E' if lon >= 0 else 'W'})"
    if -35.0 <= lat <= 35.0 and -20.0 <= lon <= 55.0:
        return f"Afro-Arabian arid belt ({lat:.1f}°, {lon:.1f}°)"
    if 25.0 <= lat <= 50.0 and 60.0 <= lon <= 115.0:
        return f"Central Asian highlands ({lat:.1f}°N, {lon:.1f}°E)"
    if -55.0 <= lat <= -10.0 and -76.0 <= lon <= -64.0:
        return f"Andean Cordillera ({abs(lat):.1f}°S, {abs(lon):.1f}°W)"
    if 20.0 <= lat <= 50.0 and -125.0 <= lon <= -100.0:
        return f"North American Cordillera ({lat:.1f}°N, {abs(lon):.1f}°W)"
    if -38.0 <= lat <= -15.0 and 113.0 <= lon <= 152.0:
        return f"Australian interior ({abs(lat):.1f}°S, {lon:.1f}°E)"

    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"Land location ({abs(lat):.1f}°{ns}, {abs(lon):.1f}°{ew})"
