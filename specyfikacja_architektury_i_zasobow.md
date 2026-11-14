# Specyfikacja Techniczna Projektu: Planetary Analog Finder (NASA Space Apps 2026)
**Wyzwanie:** *Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars*

---

## 1. Cel Systemu i Przepływ Danych (Data Flow)
System wyszukuje na Ziemi lokalizacje oraz okresy w roku (miesiące), które najlepiej odpowiadają warunkom fizycznym, geologicznym i oświetleniowym wybranego punktu na Księżycu lub Marsie. Architektura opiera się na dwuetapowym wyszukiwaniu: błyskawicznym precomputingu globalnym w pamięci RAM oraz dokładnym doczytywaniu lokalnym dla najlepszych kandydatów.

### Przepływ zapytania:
1. **Klient (Przeglądarka)** wysyła do **Networkera** zapytanie inicjujące: wybrany obiekt (`moon` | `mars`), współrzędne (`lat`, `lon`), czas docelowy oraz wektor wag parametrów `weights` (wartości z przedziału `[0.0, 1.0]`).
2. **Networker** odpytuje wewnętrznie **Charakteryzator** (`POST /characterize`).
3. **Charakteryzator** odczytuje z lokalnych map planetarnych (w formacie COG) oraz modeli astronomicznych fizyczne parametry tego punktu i zwraca obiekt JSON (`TargetProfile`).
4. **Networker**:
   - Natychmiast odsyła `TargetProfile` do **Klienta** (przez Server-Sent Events lub dwuetapowy REST), aby interfejs od razu wyświetlił parametry wybranego miejsca na Księżycu/Marsie.
   - Równolegle przekazuje `TargetProfile` wraz z wagami użytkownika do **Szukacza** (`POST /search`).
5. **Szukacz** wykonuje operację wektorową w pamięci RAM na precomputowanych macierzach Ziemi (`.npy`), wyznacza Top 100 lokalizacji lądowych, najlepszy miesiąc w roku oraz generuje uproszczone mapy dopasowania (heatmapy). Dla najlepszych punktów doczytuje szczegóły (np. widoczność Słońca i cienie rzucane przez rzeźbę terenu).
6. **Networker** odbiera wynik od **Szukacza** i przesyła go do **Klienta**.

---

## 2. Uzasadnienie Techniczne i Niskopoziomowe Decyzje Architektoniczne

### 2.1. Dlaczego macierz lądowa `.npy` (`mmap`) zamiast pełnych obrazów 4K?
- **Koszt map 4K:** Obraz 4K w odwzorowaniu równoodległościowym ($4096 \times 2048$) ma $8\,388\,608$ pikseli ($33{,}55\text{ MB}$ w `float32`). Przy 240 warstwach rocznych daje to ok. $8\text{ GB}$ danych do przemielenia przy każdym zapytaniu, z czego ok. 90% pikseli to oceany i gęste lasy ($\text{NDVI} > 0{,}25$), które nigdy nie będą analogiem Księżyca czy Marsa.
- **Rozwiązanie (Sparse Land Matrix):** Odrzucamy oceany i lasy na etapie precomputingu. Zostaje ok. $400\,000$ aktywnych komórek lądowych. Tensor w NumPy o wymiarach `(400000, 12, 9)` w `float32` zajmuje w pamięci RAM zaledwie ok. **$173\text{ MB}$**.
- **Mapowanie do pamięci (`mmap_mode='r'`):** Plik `.npy` to ciągły blok pamięci C-array. Otwarcie go przez `mmap` mapuje plik bezpośrednio do **Page Cache** jądra Linuxa. Kontener wstaje w $0\text{ ms}$, a procesor czyta dane liniowo z prędkością magistrali RAM ($\sim 40\text{ GB/s}$) przy użyciu instrukcji wektorowych **SIMD (AVX2/AVX-512)**. Czas wyliczenia zapytania dla całego świata i 12 miesięcy wynosi **poniżej $15\text{ ms}$**.

### 2.2. Dlaczego Cloud-Optimized GeoTIFF (COG) dla Księżyca i Marsa?
Plik COG posiada wewnętrzny indeks kafelków (`256x256`). Biblioteka `rasterio` (GDAL) wylicza z równania afinicznego dokładny offset bajtowy na dysku dla klikniętego punktu $(lat, lon)$ i wykonuje pojedynczy odczyt `pread()` (lub zapytanie sieciowe `HTTP Range: bytes=start-end`) o rozmiarze kilku kilobajtów. Czas odczytu wszystkich cech punktu z dysku NVMe wynosi **poniżej $2\text{ ms}$**.

### 2.3. Fizyka parametrów i uproszczenia algorytmiczne
- **Normalizacja kierunkowa:** Bezpośrednie odejmowanie temperatur Ziemi i Księżyca ($-233^\circ\text{C}$ w kraterach biegunowych vs. $-89^\circ\text{C}$ na Antarktydzie) zdominowałoby inne cechy. Wszystkie parametry w macierzy wyszukiwania są znormalizowane z ucięciem wartości odstających (`Clamping + Min-Max`) do bezwymiarowego przedziału $[0, 1]$.
- **Kąt Słońca i widoczność:** Sam kąt padania Słońca wynika bezpośrednio z geometrii orbitalnej (nachylenie osi Ziemi $\pm 23{,}44^\circ$, Marsa $\pm 25{,}19^\circ$, Księżyca $\pm 1{,}54^\circ$) i jest liczony analitycznie. Dane satelitarne służą wyłącznie do oceny **zachmurzenia** (MODIS) oraz **cienia od gór** (Raycasting po modelu wysokościowym DEM: 360 promieni wokół punktu szukających maksymalnego kąta wzniesienia horyzontu $\alpha(\phi) = \max_d \arctan(\frac{h(d) - h_0}{d})$).
- **Typ nawierzchni (sypka/twarda):** Reprezentowany fizycznie przez **bezwładność cieplną (Thermal Inertia)** wyliczaną z dobowej amplitudy temperatur $\Delta T = T_{\text{day}} - T_{\text{night}}$ (sypki pył nagrzewa się i stygnie szybko, lita skała wolno) oraz przez odbicie radarowe SAR (chropowatość powierzchni).
- **Promieniowanie kosmiczne:** Na powierzchni Ziemi zależy od grubości słupa atmosfery nad głową – wyliczane jako funkcja wysokości n.p.m. z modelu DEM oraz indeksu UV.
- **Jaskinie (Lava tubes):** Traktowane jako warstwa punktowa (odległość w km do najbliższego skatalogowanego tunelu lawowego / jaskini wulkanicznej), a nie ciągła heatmapa.

---

## 3. Infrastruktura i Struktura Repozytorium (Docker Compose + VPS)
Całość działa na pojedynczym serwerze VPS z Linuxem w środowisku Docker Compose. Ruch z domeny kierowany jest do kontenera `networker`. Wszystkie kontenery współdzielą wolumen `/data` (zamontowany jako `read-only` dla serwisów API).

```text
/
├── docker-compose.yml
├── ARCHITECTURE_SPEC.md
├── data/                      # Współdzielony wolumen z danymi (.npy, .tif, .parquet)
│   ├── moon/
│   ├── mars/
│   └── earth/
├── 1-frontend/                # Kod aplikacji webowej (Vite + Three.js)
├── 2-networker/               # Bramka API i serwer plików statycznych
├── 3-charakteryzator/         # Serwis ekstrakcji cech Księżyca i Marsa
├── 4-szukacz/                 # Silnik wyszukiwania wektorowego Ziemi
└── 5-precomputer/             # Skrypty ETL przygotowujące dane i mocki
```

---

## 4. Format Precomputowanych Danych (Wolumen `/data`)

### 4.1. Dane Ziemi (`/data/earth/`) – dla Szukacza
1. `earth_features_norm.npy`:
   - Typ: `float32`, układ pamięci C-contiguous (`mmap_mode='r'`).
   - Wymiary: `(N_POINTS, 12, K_FEATURES)`, gdzie `N_POINTS` (~400 000) to komórki lądowe, `12` to miesiące (`0..11`), a `K_FEATURES` (`9`) to znormalizowane cechy `[0.0, 1.0]`.
2. `earth_features_raw.npy`:
   - Typ: `float32`, wymiary `(N_POINTS, 12, K_FEATURES)`.
   - Rzeczywiste wartości fizyczne (°C, m, %) do rysowania klimatogramów i wyświetlania statystyk w UI.
3. `earth_metadata.parquet` (lub strukturalny `.npy`):
   - Kolumny dla każdego indeksu `i` (`0..N_POINTS-1`):
     - `id` (`int32`), `lat` (`float32`), `lon` (`float32`),
     - `px_x` (`int32`), `px_y` (`int32`) – współrzędne na siatce `1024x512` do szybkiego rzutowania heatmapy,
     - `elevation_m` (`float32`), `nearest_cave_km` (`float32`).

### 4.2. Słownik Cech (`K_FEATURES`) – indeksy osi `2`:
Każdy komponent systemu używa tej samej kolejności cech:
- `0`: `temp_mean` – Średnia temperatura powierzchni [$^\circ\text{C}$]
- `1`: `temp_diurnal_amp` – Dobowa amplituda temperatur $T_{\text{max}} - T_{\text{min}}$ [$^\circ\text{C}$]
- `2`: `thermal_inertia` – Bezwładność cieplna gruntu [$\text{J}\cdot\text{m}^{-2}\cdot\text{K}^{-1}\cdot\text{s}^{-1/2}$]
- `3`: `surface_roughness` – Chropowatość powierzchni z radaru SAR / wysokościomierza [m / indeks]
- `4`: `soil_moisture` – Wilgotność gruntu / zawartość lodu wodnego [%]
- `5`: `dust_aerosol` – Zapylenie atmosfery / grubość optyczna aerozoli (AOD) [bezwymiarowy]
- `6`: `solar_elevation_max` – Maksymalny dzienny kąt wzniesienia Słońca nad horyzontem [stopnie]
- `7`: `radiation_proxy` – Ekspozycja na promieniowanie (funkcja wysokości n.p.m. i UV) [indeks]
- `8`: `slope_deg` – Nachylenie terenu [stopnie]

### 4.3. Dane Księżyca i Marsa (`/data/moon/`, `/data/mars/`) – dla Charakteryzatora
Zestaw plików Cloud-Optimized GeoTIFF (`.tif`) z wewnętrznym kafelkowaniem (`TILED=YES`, `BLOCKXSIZE=256`, `BLOCKYSIZE=256`).

---

## 5. Podział Pracy na 5 Osób (Specyfikacja Komponentów i Kontrakty API)

### Komponent 1: Frontend (`1-frontend`)
- **Stack:** TypeScript, Vite, Three.js (WebGL), TailwindCSS, Chart.js / D3.
- **Zadania:**
  1. Wizualizacja 3D globusów (przełączanie Księżyc / Mars / Ziemia).
  2. Obsługa wyboru punktu na Księżycu/Marsie -> odpytanie API -> prezentacja odczytanych cech z `Charakteryzatora`.
  3. Panel suwaków wag `[0.0 - 1.0]` dla `K_FEATURES` oraz filtr jaskiń.
  4. Renderowanie na globusie Ziemi zwróconej heatmapy (jako `THREE.DataTexture` nakładana i kolorowana w GLSL Fragment Shaderze) oraz pinezek dla Top 100 miejsc.
  5. Widok szczegółów kandydata: zdjęcia satelitarne (WMS Sentinel-2 / NASA GIBS), klimatogram 12-miesięczny, wizualizacja kąta Słońca (syntetyczne niebo / shader atmosferyczny) i profilu horyzontu.

### Komponent 2: Networker (`2-networker`)
- **Stack:** Nginx + Python (FastAPI + `httpx` async) lub Go (Fiber).
- **Porty:** Zewnętrzny `80`/`443` -> wewnętrzny `8000`.
- **Zadania:**
  1. Serwowanie statycznego buildu z `1-frontend`.
  2. Orkiestracja zapytań między klientem, `charakteryzatorem` (`http://charakteryzator:8001`) a `szukaczem` (`http://szukacz:8002`).
- **Endpointy publiczne:**
  - `POST /api/v1/characterize` -> zwraca `TargetProfile`.
  - `POST /api/v1/search` -> przyjmuje `TargetProfile` + `weights`, zwraca wynik z `Szukacza`.

### Komponent 3: Charakteryzator (`3-charakteryzator`)
- **Stack:** Python 3.12, FastAPI, `rasterio`, `numpy`, `ephem` / `astropy`.
- **Port wewnętrzny:** `8001`.
- **Zadania:**
  1. Odczyt wartości pikseli z plików COG w `/data/moon/` lub `/data/mars/` dla podanego `(lat, lon)`.
  2. Wyliczenie kąta padania Słońca dla zadanego czasu.
  3. Zwrócenie wartości fizycznych (`features_raw`) oraz znormalizowanych względem skali ziemskiej (`features_norm`).
- **Kontrakt API (`POST /characterize`):**
```json
// Request:
{
  "target_body": "moon",
  "lat": -85.2,
  "lon": 31.4,
  "timestamp_iso": "2026-11-14T12:00:00Z"
}

// Response:
{
  "target_body": "moon",
  "coordinates": {"lat": -85.2, "lon": 31.4},
  "features_raw": {
    "temp_mean": -180.5,
    "temp_diurnal_amp": 45.0,
    "thermal_inertia": 55.0,
    "surface_roughness": 0.35,
    "soil_moisture": 2.1,
    "dust_aerosol": 0.0,
    "solar_elevation_max": 4.8,
    "radiation_proxy": 1.0,
    "slope_deg": 7.2
  },
  "features_norm": [0.0, 0.85, 0.12, 0.40, 0.02, 0.0, 0.05, 1.0, 0.16],
  "nearest_skylight_km": 14.2
}
```

### Komponent 4: Szukacz (`4-szukacz`)
- **Stack:** Python 3.12, FastAPI, `numpy`, `numba`, `pillow` / `rasterio`.
- **Port wewnętrzny:** `8002`.
- **Zadania:**
  1. Zmapowanie przy starcie macierzy `.npy` z `/data/earth/` do RAM-u.
  2. Wektorowe wyliczenie dopasowania dla wszystkich punktów $n$ i miesięcy $m$:
     $$\text{Score}(n, m) = 1 - \frac{\sum_{k} w_k \cdot |X_{n, m, k} - y_k|}{\sum_{k} w_k}$$
  3. Wybór najlepszego miesiąca dla każdego punktu, wyłonienie Top 100 kandydatów oraz rzutowanie wyników na bitmapę `1024x512` (`uint8` WebP/PNG w Base64).
  4. Dla Top 5–10 kandydatów: szybki raycasting na lokalnym wycinku DEM w celu zwrócenia profilu zasłonięcia Słońca przez góry.
- **Kontrakt API (`POST /search`):**
```json
// Request:
{
  "features_norm": [0.0, 0.85, 0.12, 0.40, 0.02, 0.0, 0.05, 1.0, 0.16],
  "weights": [1.0, 0.5, 0.8, 0.4, 0.9, 0.2, 1.0, 0.3, 0.5],
  "require_caves": false,
  "top_k": 100
}

// Response:
{
  "execution_time_ms": 14.2,
  "best_global_month": 7,
  "heatmap_base64": "data:image/webp;base64,UklGR...",
  "candidates": [
    {
      "rank": 1,
      "id": 104921,
      "lat": -77.55,
      "lon": 161.80,
      "name_hint": "McMurdo Dry Valleys, Antarctica",
      "score": 0.942,
      "best_month": 7,
      "monthly_scores": [0.61, 0.65, 0.78, 0.85, 0.91, 0.93, 0.94, 0.92, 0.84, 0.72, 0.64, 0.60],
      "features_raw_best_month": {
        "temp_mean": -58.2,
        "temp_diurnal_amp": 12.0,
        "thermal_inertia": 85.0,
        "surface_roughness": 0.31,
        "soil_moisture": 1.5,
        "dust_aerosol": 0.02,
        "solar_elevation_max": 0.0,
        "radiation_proxy": 0.78,
        "slope_deg": 6.5
      },
      "climatogram_12m": {
        "temp_mean": [-15.2, -22.1, -35.0, -45.2, -52.0, -55.1, -58.2, -56.0, -48.1, -36.0, -24.0, -16.1],
        "soil_moisture": [3.1, 2.8, 2.1, 1.8, 1.6, 1.5, 1.5, 1.5, 1.7, 2.0, 2.5, 3.0]
      },
      "nearest_cave_km": 42.0
    }
  ]
}
```

### Komponent 5: Precomputer (`5-precomputer`)
- **Stack:** Python 3.12, `earthaccess`, `xarray`, `rasterio`, `scipy`, `pyarrow`.
- **Zadania:**
  1. **PRIORYTET 0 (Pierwsze 15 minut hackathonu):** Napisanie i uruchomienie skryptu `generate_mock_data.py`, który generuje syntetyczne pliki `.npy`, `.parquet` oraz `.tif` o docelowych wymiarach i strukturze. Pozwala to pozostałym 4 osobom na natychmiastowe testowanie swoich kontenerów.
  2. Pobranie prawdziwych danych satelitarnych z API agencji kosmicznych, nałożenie maski lądowej ($\text{NDVI} < 0{,}25$), normalizacja i nadpisanie plików mockowych docelowymi macierzami.

---

## 6. Katalog Zasobów Kosmicznych (Co z nich wyciągamy i jak się łączymy)

### 6.1. Zasoby NASA – Ziemia
1. **NASA Earthdata Search (`earthaccess` / CMR API / Harmony API):**
   - *Fizyka:* Pomiary promieniowania odbitego i emitowanego (podczerwień, mikrofale, laser).
   - *Co pobieramy:* Miesięczne produkty MODIS Land Surface Temperature (temperatura dzień/noc do wyliczenia bezwładności cieplnej), SMAP Soil Moisture (wilgotność gleby), MODIS Aerosol Optical Depth (zapylenie atmosfery), MODIS NDVI (maska roślinności). Formaty: HDF5, NetCDF, Cloud-Optimized GeoTIFF (strumieniowane z chmury AWS S3).
2. **NASA Worldview (GIBS API – WMTS/WMS):**
   - *Fizyka:* Gotowe, pokolorowane kafelki mapowe renderowane z surowych danych satelitarnych.
   - *Co pobieramy:* Kafelki obrazowe ładowane bezpośrednio na frontendzie do wizualizacji wybranych lokalizacji oraz szybkiego podglądu pokryw lodowych i burz piaskowych.

### 6.2. Zasoby NASA – Księżyc i Mars
3. **NASA Planetary Data System – PDS (PDS API / NASA Trek WMTS):**
   - *Fizyka:* Archiwum telemetrii i odczytów z instrumentów orbiterów i łazików (standard PDS4).
   - *Co pobieramy:* Globalne mapy wysokościowe Marsa (MOLA DEM), bezwładności cieplnej (TES/THEMIS) oraz zdjęcia o wysokiej rozdzielczości (HiRISE) konwertowane do formatu COG dla `Charakteryzatora`.
4. **NASA Lunar Reconnaissance Orbiter – LRO:**
   - *Fizyka:* Zestaw sensorów na niskiej orbicie biegunowej Księżyca:
     - **LROC:** Kamery optyczne (rozdzielczość do $0{,}5\text{ m/px}$, mapy nasłonecznienia biegunów).
     - **LOLA:** Wysokościomierz laserowy mierzący czas powrotu impulsu – dostarcza dokładny model terenu DEM, nachylenia stoków i chropowatość.
     - **LEND:** Detektor neutronów – mierzy spadek liczby szybkich neutronów wybijanych przez promieniowanie kosmiczne, co wskazuje na obecność jąder wodoru (lodu wodnego) w górnym metrze regolitu.
     - **Mini-RF:** Radar SAR w paśmie S/X analizujący polaryzację fali po odbiciu (odróżnia skały od podpowierzchniowego lodu).
5. **NASA LRO Diviner Lunar Data:**
   - *Fizyka:* 9-kanałowy radiometr podczerwieni mierzący emisję cieplną gruntu.
   - *Co pobieramy:* Globalne mapy temperatur minimalnych/maksymalnych Księżyca (w tym ekstremalnie zimnych kraterów biegunowych o temp. $\sim 40\text{ K}$) oraz bezwładności cieplnej regolitu (`Polar Resource Products`).

### 6.3. Zasoby CSA (Kanadyjska Agencja Kosmiczna)
6. **RADARSAT Constellation Mission (RCM) & RADARSAT-1 (STAC API / AWS):**
   - *Fizyka:* Aktywny radar z syntetyczną aperturą (SAR) w paśmie C ($5{,}405\text{ GHz}$). Wysyła własną wiązkę mikrofal przenikającą przez chmury i noc; siła i polaryzacja odbicia zależą od chropowatości geometrycznej i wilgotności gruntu.
   - *Co pobieramy:* Obrazy radarowe (GeoTIFF) do wyznaczenia parametru `surface_roughness` oraz struktury lodu w regionach polarnych Ziemi.
7. **SAR Python Tutorial:**
   - *Zastosowanie:* Gotowy kod w Pythonie pokazujący pobieranie wycinków RADARSAT przez `HTTP Range Requests`, kalibrację radiometryczną i filtrację szumu plamkowego (*speckle*).

### 6.4. Zasoby ESA (Europejska Agencja Kosmiczna)
8. **Copernicus Data Space Ecosystem – CDSE (Sentinel Hub API / openEO / STAC):**
   - *Fizyka:* Konstelacja Sentinel-1 (radar SAR w paśmie C) oraz Sentinel-2 (kamera wielospektralna w 13 pasmach optycznych i bliskiej podczerwieni).
   - *Co pobieramy:* Globalny model wysokościowy **Copernicus DEM** (do wyliczania nachylenia stoków, ekspozycji na promieniowanie i cieni horyzontu), mapę pokrycia terenu **WorldCover** (do wykluczenia wody, miast i lasów) oraz bezchmurne zdjęcia optyczne Sentinel-2 dla Top 100 kandydatów.
9. **ESA Open Science Catalog (EarthCODE):**
   - *Co pobieramy:* Gotowe, zagregowane zestawy danych geofizycznych (kriosfera, wilgotność gleby) oraz notatniki z kodem przetwarzającym.

### 6.5. Zasoby JAXA (Japońska Agencja Kosmiczna)
10. **JAXA G-Portal (OpenSearch API / HDF5 / GeoTIFF):**
    - *Fizyka:* Radiometry mikrofalowe (AMSR2 na GCOM-W), sensory optyczne (SGLI na GCOM-C) oraz radar SAR w **paśmie L** (ALOS/ALOS-2 – fala o długości $\sim 23\text{ cm}$ przenika głębiej w suchy piasek i lód niż pasmo C, odbijając się od twardego podłoża skalnego).
    - *Co pobieramy:* Gotowe statystyki miesięczne poziomu 3 (temperatura gruntu LST, ekwiwalent wody w śniegu, chropowatość podłoża w paśmie L).
```

Cała dokumentacja znajduje się teraz w jednym pliku gotowym do pobrania lub skopiowania do głównego katalogu Waszego repozytorium. Daj znać, jeśli chcecie doprecyzować któryś z kontraktów JSON albo od razu wygenerować wspomniany skrypt `generate_mock_data.py` wraz z plikiem `docker-compose.yml`, żebyście mieli gotowy szkielet na start!