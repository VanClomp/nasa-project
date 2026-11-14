# Project Context – Planetary Analog Finder (NASA Space Apps 2026)

## 1. Opis projektu i rola
**Planetary Analog Finder** to narzędzie analityczno-wizualizacyjne wyszukujące na Ziemi lokalizacje oraz okresy w roku (miesiące), które pod względem fizycznym, geologicznym i orbitalnym najlepiej odpowiadają wybranemu punktowi na **Księżycu** lub **Marsie**.

## 2. Kierunek Artystyczny i Design System (Minimalist Aerospace / Linear / SpaceX UI)

Odchodzimy od „growego”, przesadzonego stylu sci-fi/cyberpunk (brak gamingowych fontów typu *Orbitron*, brak sztucznych laserów, narożników z gier i jaskrawych tęczowych ramek). Stawiamy na **dojrzały, minimalistyczny, inżynieryjny design premium** inspirowany interfejsami **SpaceX Crew Dragon, Linear.app, Vercel oraz NASA JPL Eyes**.

### Zasady przewodnie:
1. **Minimalizm i przestrzeń (Negative Space):**
   * Czysta geometria, dużo oddechu wokół elementów, cienkie linie podziału (`1px solid rgba(255, 255, 255, 0.07)`), brak zbędnych ozdobników.
2. **Paleta kolorystyczna (Matte Obsidian & Precision Accents):**
   * **Tło bazowe:** Głęboki, matowy obsydian `#050507` oraz `#090A0F` (bez krzykliwych gradientów).
   * **Powierzchnie (Cards / Panels):** Subtelne, półprzezroczyste warstwy `rgba(17, 19, 24, 0.72)` z delikatnym rozmyciem `backdrop-filter: blur(20px)` oraz cienką obwódką `1px` rozświetlaną dopiero przy interakcji.
   * **Tekst:**
     * Główny: `#F4F4F6` (czysta, lekko złamana biel)
     * Drugorzędny: `#8E929F` (chłodny, techniczny szary)
     * Etykiety / metadane: `#525665`
   * **Stonowane, precyzyjne akcenty świetlne (tylko tam, gdzie niosą informację):**
     * **Księżyc (Lunar Ice / Silver):** `#E2E8F0` oraz chłodny subtelny błękit `#60A5FA`
     * **Mars (Ember / Terracotta):** `#F97316` oraz ciepły bursztyn `#FB923C`
     * **Wskaźnik dopasowania Ziemi (Signal Emerald):** `#10B981`
3. **Typografia (Inżynieryjna precyzja):**
   * **Nagłówki i UI:** *Inter* lub *Plus Jakarta Sans* (wagi `400`, `500`, `600`, ciasny kerning `letter-spacing: -0.03em`).
   * **Dane liczbowe, współrzędne i telemetria:** *JetBrains Mono* (`font-variant-numeric: tabular-nums`) – gwarantuje idealne wyrównanie kolumn z liczbami i brak skakania interfejsu podczas animacji.

---

## 3. Nowoczesne, subtelne animacje (High-Craft Motion)

Animacje mają budować wrażenie precyzyjnego instrumentu naukowego:

1. **Realistyczne oświetlenie 3D (Terminator & Fresnel Rim Glow):**
   * Globusy Księżyca i Marsa w Three.js są oświetlone kierunkowym światłem słonecznym z wyraźną granicą dnia i nocy (*terminator line*) oraz subtelną poświatą krawędziową (*Fresnel shader*).
   * Po najechaniu kursorem na kafelek kamera i źródło światła płynnie, z bezwładnością (*damped inertia*) reagują na ruch myszy, a globus delikatnie przyspiesza obrót.
2. **Subtelny efekt Spotlight na krawędziach (`1px Border Glow`):**
   * Zamiast świecenia całego kafelka – kursor myszy oświetla jedynie cienką (`1px`) krawędź karty oraz delikatny refleks w miejscu, w którym znajduje się wskaźnik (styl Linear / Vercel).
3. **Płynna fizyka przejść (`cubic-bezier(0.22, 1, 0.36, 1)`):**
   * Wszystkie przejścia (zmiana kart, rozwijanie parametrów, aktualizacja wykresów i pasków dopasowania) korzystają z miękkich krzywych wygaszania.
4. **Animacje danych (`Tabular Number Transitions`):**
   * Płynna interpolacja wartości liczbowych (np. `94.2%`) i szerokości pasków dopasowania w czasie rzeczywistym (60 FPS) podczas przesuwania suwaków wag.

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

## 5. Kontrakt API (9 cech `K_FEATURES`)

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

---

## 6. Organizacja CSS
* Wszystkie pliki `.php` korzystają z jednego, wspólnego arkusza stylów [style.css](file:///Users/antos/Documents/programowanie/nasa-project/nasa-project/style.css).
* Dla każdej nowej strony `.php` podpinaj `<link rel="stylesheet" href="style.css">` i dopisuj nowe klasy w tym pliku.

## 7. Licencje
Zapisz w pliku 'LICENCES.md' wszystkie źródła, gdy używamy czegoś z internetu