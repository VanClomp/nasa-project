"""Szybkie przypisywanie nazw regionów (name_hint) po współrzędnych (lat, lon).

Rozwiązuje punkt 3 z todo_list.txt: Szukacz (4-szukacz) zwraca jedynie surowe
współrzędne (lat, lon) bez pola `name_hint`, którego oczekuje explorer.php.
"""

from __future__ import annotations

import math

# Katalog znanych ziemskich analogów planetarnych oraz charakterystycznych krain
# geograficznych: (lat, lon, promień_km, nazwa)
KNOWN_ANALOG_REGIONS: tuple[tuple[float, float, float, str], ...] = (
    (-77.55, 161.80, 350.0, "McMurdo Dry Valleys, Antarktyda"),
    (-82.86, 135.00, 1200.0, "Płaskowyż Polarny, Antarktyda Wschodnia"),
    (-75.10, 123.35, 900.0, "Dome C (Concordia), Antarktyda"),
    (-24.08, -69.92, 450.0, "Pustynia Atacama (Yungay), Chile"),
    (-23.00, -67.75, 350.0, "Altiplano / Laguna Colorada, Andy"),
    (19.47, -155.59, 220.0, "Wulkan Mauna Loa (HI-SEAS), Hawaje"),
    (75.38, -89.68, 450.0, "Krater Haughton (Devon Island), Kanada"),
    (79.40, -90.80, 500.0, "Wyspa Axela Heiberga, Arktyka Kanadyjska"),
    (78.22, 15.63, 450.0, "Svalbard (Spitsbergen), Norwegia"),
    (64.80, -16.75, 300.0, "Wyżyna Islandzka (Askja / Holuhraun), Islandia"),
    (38.40, -110.79, 350.0, "Mars Desert Research Station (MDRS), Utah, USA"),
    (36.06, -112.14, 300.0, "Wyżyna Kolorado / Meteor Crater, Arizona, USA"),
    (43.46, -113.56, 300.0, "Craters of the Moon (Lava Beds), Idaho, USA"),
    (37.72, -6.55, 250.0, "Rio Tinto, Andaluzja, Hiszpania"),
    (29.57, 35.42, 350.0, "Pustynia Wadi Rum, Jordania"),
    (30.58, 34.80, 250.0, "Krater Ramon (Negew), Izrael"),
    (30.20, 58.80, 550.0, "Pustynia Lut (Dasht-e Lut), Iran"),
    (14.25, 40.30, 400.0, "Kotlina Danakilska (Afar), Etiopia"),
    (24.00, 10.00, 1400.0, "Góry Ahaggar / Tassili, Centralna Sahara"),
    (22.00, 25.00, 1200.0, "Pustynia Libijska (Gilf Kebir), Sahara"),
    (-24.50, 15.50, 600.0, "Pustynia Namib, Namibia"),
    (42.50, 103.50, 900.0, "Pustynia Gobi, Mongolia / Chiny"),
    (38.90, 82.20, 700.0, "Pustynia Takla Makan (Kotlina Tarymska)"),
    (33.00, 88.00, 950.0, "Wyżyna Tybetańska (Changtang)"),
    (-25.00, 133.00, 1200.0, "Pustynia Simpsona / Red Centre, Australia"),
    (28.27, -16.64, 200.0, "Kaldera Las Cañadas (Teide), Teneryfa"),
    (29.00, -13.63, 200.0, "Pola lawowe Timanfaya, Lanzarote"),
    (37.75, 15.00, 180.0, "Masyw wulkanu Etna, Sycylia"),
    (56.06, 160.64, 450.0, "Masyw wulkaniczny Tołbaczik, Kamczatka"),
)

EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def resolve_name_hint(lat: float, lon: float) -> str:
    """Zwraca czytelny opis regionu dla podanych współrzędnych (lat, lon)."""
    best_name: str | None = None
    best_dist = float("inf")

    for r_lat, r_lon, radius_km, name in KNOWN_ANALOG_REGIONS:
        dist = _haversine_km(lat, lon, r_lat, r_lon)
        if dist <= radius_km and dist < best_dist:
            best_dist = dist
            best_name = name

    if best_name is not None:
        return best_name

    # Ogólne pasy geograficzne, gdy punkt leży poza skatalogowanymi analogami
    if lat <= -66.5:
        return f"Strefa Antarktyczna ({abs(lat):.1f}°S, {abs(lon):.1f}°{'E' if lon >= 0 else 'W'})"
    if lat >= 66.5:
        return f"Strefa Arktyczna ({lat:.1f}°N, {abs(lon):.1f}°{'E' if lon >= 0 else 'W'})"
    if -35.0 <= lat <= 35.0 and -20.0 <= lon <= 55.0:
        return f"Pas Suchego Klimatu Afro-Arabskiego ({lat:.1f}°, {lon:.1f}°)"
    if 25.0 <= lat <= 50.0 and 60.0 <= lon <= 115.0:
        return f"Wyżyny Centralnej Azji ({lat:.1f}°N, {lon:.1f}°E)"
    if -55.0 <= lat <= -10.0 and -76.0 <= lon <= -64.0:
        return f"Kordyliera Andów ({abs(lat):.1f}°S, {abs(lon):.1f}°W)"
    if 20.0 <= lat <= 50.0 and -125.0 <= lon <= -100.0:
        return f"Kordyliery Ameryki Północnej ({lat:.1f}°N, {abs(lon):.1f}°W)"
    if -38.0 <= lat <= -15.0 and 113.0 <= lon <= 152.0:
        return f"Interior Australijski ({abs(lat):.1f}°S, {lon:.1f}°E)"

    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"Lokalizacja lądowa ({abs(lat):.1f}°{ns}, {abs(lon):.1f}°{ew})"
