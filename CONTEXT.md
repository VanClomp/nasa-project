# Project Context – Planetary Analog Finder (Hackathon NASA)

## 1. Opis projektu
Aplikacja webowa tworzona w ramach hackathonu, której celem jest porównywanie lokalizacji na **Księżycu** oraz **Marsie** i dobieranie najbardziej zbliżonych do nich miejsc (analogów planetarnych) na **Ziemi**. Dopasowanie odbywa się na podstawie różnych czynników środowiskowych, geologicznych i topograficznych (np. temperatura, ukształtowanie terenu, skład gleby/regolitu, nasłonecznienie, promieniowanie, grawitacja/ciśnienie).

---

## 2. Rola i zakres (Frontend)
Ten dokument definiuje wytyczne wizualne, architekturę UI/UX oraz standardy animacji dla warstwy frontendowej projektu.

---

## 3. Styl wizualny i Design System (Dark Sci-Fi / Neon Space UI)

### Paleta kolorystyczna
* **Tło bazowe (Deep Space Dark):**
  * Główne tło: `#07090E` / `#0B0F19` (głęboka czerń z subtelnym odcieniem kosmicznego granatu)
  * Powierzchnie kart / paneli (Glassmorphism): `rgba(17, 24, 39, 0.65)` z rozmyciem tła (`backdrop-filter: blur(16px)`)
* **Akcenty neonowe (Neon Accents):**
  * **Główny neon (Cyan / Telemetry):** `#00F0FF` – główny kolor interakcji, aktywne stany, wykresy, kursory, linie skanowania
  * **Akcent Marsa (Neon Crimson / Rust Orange):** `#FF4D2A` / `#FF2A6D` – wizualizacje i stany powiązane z Marsem
  * **Akcent Księżyca (Electric Violet / Ice Blue):** `#8B5CF6` / `#38BDF8` – wizualizacje i stany powiązane z Księżycem
  * **Akcent Ziemi (Bio Emerald):** `#00FF9D` – wskaźniki wysokiego dopasowania (Match Score) i lokalizacje ziemskie
* **Tekst i typografia:**
  * Tekst główny: `#F8FAFC`
  * Tekst pomocniczy / etykiety telemetryczne: `#94A3B8`
  * Obramowania (Subtle Glow Borders): `1px solid rgba(0, 240, 255, 0.18)` (z podświetleniem `box-shadow` przy `hover`)

### Typografia
* **Nagłówki (Display / Sci-Fi):** *Orbitron*, *Space Grotesk* lub *Rajdhani* – geometryczne, technologiczne kroje pisma.
* **Tekst główny (UI):** *Inter* lub *Plus Jakarta Sans* – wysoka czytelność danych.
* **Dane liczbowe / współrzędne / telemetria:** *JetBrains Mono* lub *Fira Code* (fonty monospace dla współrzędnych geograficznych, parametrów i procentów dopasowania).

### Elementy interfejsu (HUD & Glassmorphism)
* Półprzezroczyste panele w stylu HUD (Heads-Up Display) z delikatnymi narożnikami technicznymi (ścięte rogi lub znaczniki `+` w narożnikach kart).
* Subtelna siatka telemetryczna (grid) lub gwiazdozbiory/cząsteczki w tle.
* Wyraźne mikro-poświaty (`text-shadow` i `box-shadow`) dla kluczowych wskaźników (np. procent zgodności lokalizacji: `94% MATCH`).

---

## 4. Nowoczesne animacje i mikro-interakcje (Kluczowy priorytet)

Strona ma sprawiać wrażenie żywego, responsywnego terminala misji kosmicznej:

1. **Animacje wejścia i przejść (Page & Scroll Animations):**
   * Płynne kaskadowe pojawianie się kart i sekcji (`staggered fade-in + slide-up`).
   * Płynne przejścia między trybami **Księżyc ↔ Mars** (dynamiczna zmiana palety akcentów i oświetlenia tła w CSS/JS).
2. **Interaktywne tło i wizualizacje 3D / Canvas:**
   * Animowane tło cząsteczkowe (gwiazdy, pył kosmiczny reagujący na ruch kursora – efekt paralaksy).
   * Obracające się modele 3D / globusy (np. Three.js / WebGL lub zaawansowane CSS/SVG) z zaznaczonymi punktami lądowania i liniami łączącymi z analogiem na Ziemi.
3. **Efekt skanowania i porównywania (Scanning & Matching Effects):**
   * Animowana wiązka skanera przechodząca przez wybraną lokalizację na Księżycu/Marsie podczas wyszukiwania odpowiednika na Ziemi.
   * Liczniki typu *number ticker / scramble text* (efekt dekodowania tekstu i odliczania od `0%` do docelowego wyniku dopasowania).
   * Animowane wykresy radarowe (Spider/Radar Charts) i paski postępu porównujące parametry (temperatura, grawitacja, topografia, podobieństwo geologiczne).
4. **Mikro-interakcje na kartach i przyciskach (Hover & Active States):**
   * Efekt *magnetic buttons* lub rozchodzącej się neonowej poświaty pod kursorem (`spotlight hover effect` śledzący pozycję myszy na kartach).
   * Płynne powiększanie miniatur terenu z nakładką danych wysokościowych / mapy cieplnej.

---

## 5. Kluczowe widoki / sekcje frontendowe
1. **Hero Section (Mission Control):**
   * Duży, efektowny nagłówek z animacją tekstu, podglądem 3D/wizualizacją ciał niebieskich i szybkim przyciskiem `Rozpocznij eksplorację`.
2. **Selektor Ciała Niebieskiego i Lokalizacji (Moon / Mars Explorer):**
   * Przełącznik Księżyc / Mars zmieniający klimat kolorystyczny interfejsu.
   * Lista lub interaktywna mapa kraterów/regionów (np. *Jezero Crater*, *Olympus Mons*, *Mare Tranquillitatis*, *Shackleton Crater*).
3. **Panel Czynników i Wag (Comparison Engine UI):**
   * Suwaki / przełączniki pozwalające określić, które czynniki są najważniejsze (geologia, temperatura, promieniowanie, nachylenie terenu).
4. **Widok Porównania (Side-by-Side Split View):**
   * Bezpośrednie zestawienie wybranej lokalizacji pozaziemskiej z najlepszym odpowiednikiem na Ziemi (np. *Pustynia Atacama*, *Dolina Sucha McMurdo*, *Wulkan Mauna Loa*, *Islandia*).
   * Wykresy porównawcze, wskaźnik `% Match`, mapa i karty parametrów.

---

## 6. Wskazówki implementacyjne dla AI / Developerów
* Każdy nowy komponent UI powinien wspierać ciemny motyw (`dark mode first`), posiadać płynne `transition` (`cubic-bezier(0.16, 1, 0.3, 1)`) oraz efekt neonowego podświetlenia przy interakcji.
* Unikamy płaskich, statycznych białych/szarych bloków – wszystkie kontenery powinny wykorzystywać głębię (cienie, gradientowe obramowania, blur).
* Animacje powinny być wydajne (oparte o `transform`, `opacity`, `requestAnimationFrame`, GSAP / Framer Motion / Anime.js lub czysty CSS Keyframes).
