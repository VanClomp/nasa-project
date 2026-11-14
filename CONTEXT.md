# Project Context – Planetary Analog Finder (NASA Space Apps 2026)

## 1. Opis projektu i Twoja rola
Projekt **Planetary Analog Finder** wyszukuje na Ziemi lokalizacje oraz miesiące w roku, które najlepiej odpowiadają warunkom fizycznym, geologicznym i oświetleniowym wybranego punktu na **Księżycu** lub **Marsie**.

Odpowiadasz za **Komponent 1 (`1-frontend`)**. Architektura całego systemu jest oparta o kontenery Dockerowe i kontrakty JSON (`POST /api/v1/characterize` oraz `POST /api/v1/search`), dzięki czemu Twój komponent jest w 100% kompatybilny z resztą zespołu (`2-networker`, `3-charakteryzator`, `4-szukacz`, `5-precomputer`), będąc jednocześnie napisanym w technologiach dopasowanych pod Ciebie: **PHP 8 + HTML5/CSS3 + JavaScript (Three.js) + C++**.

---

## 2. Twój Stack Technologiczny (`1-frontend`)

* **PHP 8.x + HTML5:**
  * Generowanie struktury strony ([index.php](file:///Users/antos/Documents/programowanie/nasa-project/nasa-project/index.php)) oraz modularnych komponentów UI (np. pętla generująca 9 suwaków dla `K_FEATURES`, gotowe presety misji NASA, karty kandydatów).
  * Opcjonalny lokalny endpoint proxy/mock w PHP (`api_proxy.php`), który pozwala Ci testować cały frontend nawet zanim reszta zespołu postawi swoje kontenery Dockerowe!
* **Modern CSS3 + Vanilla JS (ES6+) + Three.js / Chart.js (przez CDN):**
  * Zero skomplikowanych bundlerów (brak konieczności używania Node.js/Vite) – czysty, szybki kod uruchamiany od razu z serwera PHP.
  * Wizualizacja 3D globusów (Księżyc / Mars / Ziemia), nakładanie heatmapy (`heatmap_base64`) i pinezek Top 100 miejsc.
* **C++ (Super-boost wydajnościowy i efekt „WOW” dla jury hackathonu):**
  * **Opcja A – C++ skompilowany do WebAssembly (Wasm przez Emscripten):**
    * Przeliczanie wag w czasie rzeczywistym (60 FPS podczas przeciągania suwaków `[0.0 - 1.0]`) na pobranej liście kandydatów bez czekania na zapytanie sieciowe.
    * Obliczanie geometrii Słońca, cieni horyzontu lub generowanie siatki 3D terenu (DEM) bezpośrednio w przeglądarce.
  * **Opcja B – Natywny program w C++ wywoływany z PHP (`proc_open` / `exec` lub FastCGI):**
    * Błyskawiczne przetwarzanie danych lokalnych, symulacje fizyczne/orbitalne lub generowanie profili terenu po stronie kontenera `1-frontend`.

---

## 3. Styl wizualny i Design System (Dark Sci-Fi / Neon Space HUD)

### Paleta kolorystyczna
* **Tło bazowe (Deep Space Dark):**
  * Główne tło: `#07090E` / `#0B0F19` (głęboka czerń z kosmicznym granatem)
  * Panele HUD (Glassmorphism): `rgba(15, 23, 42, 0.68)` + `backdrop-filter: blur(16px)`
* **Akcenty neonowe (Neon Accents):**
  * **Główny neon (Telemetry Cyan):** `#00F0FF` – obramowania HUD, aktywne kontrolki, wiązka skanera, wykresy
  * **Tryb Księżyca (Lunar Violet / Ice Blue):** `#38BDF8` / `#8B5CF6`
  * **Tryb Marsa (Martian Neon Orange / Crimson):** `#FF4D2A` / `#FF2A6D`
  * **Dopasowanie na Ziemi (Bio Emerald):** `#00FF9D` – wysoki `% Match`, pinezki najlepszych analogów na Ziemi
* **Typografia:**
  * Nagłówki: *Orbitron* lub *Space Grotesk* (klimat NASA / Sci-Fi HUD)
  * Interfejs: *Inter* / *Plus Jakarta Sans*
  * Dane telemetryczne, współrzędne `(lat, lon)`, wyniki `Score`: *JetBrains Mono*

---

## 4. Nowoczesne animacje i mikro-interakcje (Kluczowy priorytet)

1. **Dynamiczna transformacja motywu (`Moon` ↔ `Mars` ↔ `Earth`):**
   * Płynna zmiana zmiennych CSS (`--accent-glow`, `--accent-primary`) oraz oświetlenia sceny 3D przy przełączaniu globusów.
2. **Efekt skanowania po kliknięciu współrzędnych (`lat`, `lon`):**
   * Animowany pierścień / fala radarowa rozchodząca się od klikniętego punktu na Księżycu lub Marsie w trakcie odpytywania `/api/v1/characterize`.
3. **Liczniki telemetryczne (Scramble Text & Number Ticker):**
   * Podczas wczytywania parametrów `features_raw` i `score` (np. `94.2% MATCH`), cyfry płynnie odliczają wartość lub „dekodują się” w stylu terminala kosmicznego.
4. **Kaskadowe wejścia i Spotlight Hover:**
   * Karty z Top kandydatami pojawiają się kaskadowo (`staggered animation`), a po najechaniu myszką podąża za kursorem neonowa poświata (`radial-gradient` śledzący `clientX/clientY`).
5. **Interaktywne suwaki wag (`K_FEATURES`) z natychmiastowym feedbackiem:**
   * Przesunięcie suwaka płynnie animuje wykres radarowy i pasek dopasowania.

---

## 5. Kontrakt Danych z Resztą Zespołu (9 cech `K_FEATURES`)

Kolejność cech w tablicach `features_norm` i `weights` (indeksy `0..8`) jest stała w całym systemie:

| Indeks | Klucz | Opis | Jednostka |
| :--- | :--- | :--- | :--- |
| `0` | `temp_mean` | Średnia temperatura powierzchni | `°C` |
| `1` | `temp_diurnal_amp` | Dobowa amplituda temperatur ($T_{\max} - T_{\min}$) | `°C` |
| `2` | `thermal_inertia` | Bezwładność cieplna gruntu (sypki pył vs lita skała) | $\text{J}\cdot\text{m}^{-2}\cdot\text{K}^{-1}\cdot\text{s}^{-1/2}$ |
| `3` | `surface_roughness` | Chropowatość powierzchni (SAR / wysokościomierz) | `m / indeks` |
| `4` | `soil_moisture` | Wilgotność gruntu / zawartość lodu wodnego | `%` |
| `5` | `dust_aerosol` | Zapylenie atmosfery (AOD) | `bezwymiarowy` |
| `6` | `solar_elevation_max` | Maksymalny dzienny kąt wzniesienia Słońca | `°` (stopnie) |
| `7` | `radiation_proxy` | Ekspozycja na promieniowanie (wysokość n.p.m. + UV) | `indeks` |
| `8` | `slope_deg` | Nachylenie terenu | `°` (stopnie) |

### Endpointy, z którymi rozmawia Twój Frontend:
1. **`POST /api/v1/characterize`**
   * Wysyłasz: `{"target_body": "moon" | "mars", "lat": -85.2, "lon": 31.4, "timestamp_iso": "2026-11-14T12:00:00Z"}`
   * Otrzymujesz: `features_raw` (do wyświetlenia w HUD), `features_norm` (tablica 9 floatów `[0..1]`), `nearest_skylight_km`.
2. **`POST /api/v1/search`**
   * Wysyłasz: `{"features_norm": [...], "weights": [...], "require_caves": false, "top_k": 100}`
   * Otrzymujesz: `execution_time_ms`, `best_global_month`, `heatmap_base64` (obraz `1024x512` nakładany na globus Ziemi) oraz listę `candidates` (Top lokalizacje na Ziemi z ich `climatogram_12m`, `monthly_scores` i `features_raw_best_month`).
