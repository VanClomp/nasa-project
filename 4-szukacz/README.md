# Szukacz (komponent 4)

Silnik wyszukiwania ziemskich analogów. Dostaje profil punktu na Księżycu lub
Marsie (K znormalizowanych cech) i K wag, a zwraca `top_k` (domyślnie 100)
lokalizacji na Ziemi, które najlepiej do niego pasują, razem z najlepszym
miesiącem i mapą dopasowania.

Zwracane lokalizacje są zróżnicowane: jeśli dwa punkty leżą bliżej siebie niż
`min_distance_km`, liczy się tylko lepszy z nich, a zwolnione miejsce zajmuje
kolejny punkt z rankingu. Wynik nadal ma `top_k` pozycji.

Do wyniku dołączona jest **mapa błędu** całej Ziemi: dla każdego miejsca
ważona różnica między profilem celu a tym, co w tym miejscu jest. Osobny
endpoint zwraca tę samą mapę w dużym powiększeniu dla okolicy wybranego
punktu.

Szukacz na razie tylko zwraca te punkty i mapy. Dalsze badanie wyników
(raycasting po DEM, punkt 5.4 zadań w specyfikacji) nie jest zaimplementowane.

## Pliki

| Plik | Zawartość |
| :--- | :--- |
| `szukacz/data.py` | Wczytanie danych Ziemi z `/data/earth` (mmap) i metadanych punktów. |
| `szukacz/scoring.py` | Liczenie dopasowania i wybór zróżnicowanego Top-K. Sama matematyka, bez plików i JSON-a. |
| `szukacz/maps.py` | Mapy: heatmapa dopasowania, mapa błędu całej Ziemi, szczegółowa mapka błędu wokół punktu. Siatki numpy i obrazy, bez JSON-a. |
| `szukacz/engine.py` | Funkcje `search()` i `error_map_detail()`: składają wyniki w kształcie odpowiedzi `POST /search` i `POST /error-map`. |
| `szukacz/api.py` | Serwis HTTP (FastAPI), port 8002. |
| `tests/test_szukacz.py` | Testy na danych syntetycznych. |

## Co oferuję

### HTTP

**`POST /search`**

Zapytanie:

| Pole | Typ | Opis |
| :--- | :--- | :--- |
| `features_norm` | K liczb | Znormalizowany profil celu z Charakteryzatora. |
| `weights` | K liczb `>= 0` | Wagi cech. Liczy się tylko ich proporcja. |
| `require_caves` | bool, domyślnie `false` | Zwracaj tylko punkty z jaskinią nie dalej niż 15 km. |
| `top_k` | int 1..1000, domyślnie 100 | Ile lokalizacji zwrócić. |
| `min_distance_km` | liczba `>= 0`, opcjonalne | Minimalna odległość między zwracanymi lokalizacjami. Brak pola oznacza 100 km, `0` wyłącza odsiewanie. **Pole spoza specyfikacji.** |

K to liczba cech w macierzy danych (9 według specyfikacji).

Odpowiedź:

| Pole | Opis |
| :--- | :--- |
| `execution_time_ms` | Czas liczenia po stronie Szukacza. |
| `best_global_month` | Miesiąc `1..12` o najwyższym średnim dopasowaniu wśród zwróconych lokalizacji; `null`, gdy lista jest pusta. |
| `heatmap_base64` | `data:image/webp;base64,...`, obraz RGBA 1024x512 (opis niżej). |
| `error_map` | Mapa błędu całej Ziemi, obiekt opisany w części „Format mapy błędu". **Pole spoza specyfikacji.** |
| `candidates` | Lista lokalizacji od najlepszej. |

Pola kandydata:

| Pole | Opis |
| :--- | :--- |
| `rank` | Pozycja od 1. |
| `id`, `lat`, `lon` | Z metadanych Ziemi. |
| `score` | Dopasowanie w najlepszym miesiącu. |
| `best_month` | Najlepszy miesiąc, `1..12`. |
| `monthly_scores` | 12 wyników, indeks 0 to styczeń. |
| `features_norm` | K znormalizowanych cech punktu w najlepszym miesiącu. **Pole spoza specyfikacji**, potrzebne frontendowi do przeliczania na żywo. |
| `features_raw_best_month` | Słownik `nazwa cechy -> wartość fizyczna` w najlepszym miesiącu. |
| `climatogram_12m` | Słownik `nazwa cechy -> 12 wartości fizycznych`, dla wszystkich cech (specyfikacja pokazuje dwie). |
| `nearest_cave_km` | Z metadanych Ziemi. |

Różnice względem przykładu ze specyfikacji:

- Nie ma pola `name_hint`. Szukacz nie zna nazw regionów.
- Jest dodatkowe pole `error_map` i dodatkowy endpoint `POST /error-map`.
- Lista może mieć mniej niż `top_k` pozycji, gdy na Ziemi nie ma tylu punktów
  spełniających warunki (filtr jaskiń, duża `min_distance_km`).
- Brak danych (NaN w macierzach) wychodzi w JSON-ie jako `null`.

Błędne dane wejściowe (zła liczba cech, ujemna waga, NaN) dają status `422`
z opisem w polu `detail`.

**`POST /error-map`** (endpoint spoza specyfikacji)

Szczegółowa mapka błędu dla okolicy wybranego punktu na Ziemi. Pokazuje ten
sam błąd co `error_map` z `/search`, w tej samej skali kolorów, ale w dużo
większym powiększeniu: przy wartościach domyślnych ok. 1 km na piksel, a mapa
całej Ziemi ma ok. 39 km na piksel (na równiku).

Zapytanie:

| Pole | Typ | Opis |
| :--- | :--- | :--- |
| `features_norm`, `weights` | jak w `/search` | Te same wartości, z którymi wołano `/search`. |
| `lat` | liczba -90..90 | Szerokość geograficzna środka mapki (współrzędna y). |
| `lon` | liczba -180..180 | Długość geograficzna środka mapki (współrzędna x). |
| `radius_km` | liczba 1..2000, domyślnie 250 | Mapka sięga tyle km od punktu na północ, południe, wschód i zachód. |
| `size_px` | int 64..1024, domyślnie 512 | Szerokość mapki w pikselach. |

Punkt podaje się we współrzędnych geograficznych. Piksel `(px_x, px_y)` mapy
całej Ziemi przelicza się na nie tak:
`lon = (px_x + 0.5) / 1024 * 360 - 180`, `lat = 90 - (px_y + 0.5) / 512 * 180`.

Odpowiedź:

| Pole | Opis |
| :--- | :--- |
| `execution_time_ms` | Czas liczenia po stronie Szukacza. |
| `center` | `{"lat": ..., "lon": ...}` z zapytania. |
| `radius_km` | Promień z zapytania (albo domyślny). |
| `km_per_px` | Skala mapki, `2 * radius_km / size_px`. |
| `error_map` | Mapka, obiekt opisany w części „Format mapy błędu". |

Przykład:

```json
// Request:
{
  "features_norm": [0.0, 0.85, 0.12, 0.40, 0.02, 0.0, 0.05, 1.0, 0.16],
  "weights": [1.0, 0.5, 0.8, 0.4, 0.9, 0.2, 1.0, 0.3, 0.5],
  "lat": -77.55,
  "lon": 161.80
}

// Response:
{
  "execution_time_ms": 27.4,
  "center": {"lat": -77.55, "lon": 161.8},
  "radius_km": 250.0,
  "km_per_px": 0.9766,
  "error_map": {
    "image_base64": "data:image/png;base64,iVBORw0KGgo...",
    "width": 512,
    "height": 512,
    "bounds": {"lat_min": -79.7983, "lat_max": -75.3017, "lon_min": 151.37129, "lon_max": 172.22871},
    "scale": {
      "min": 0.0,
      "max": 0.5,
      "colors": ["#371300", "#582300", "#7B3401", "#A04502", "#C65803", "#EE6B03", "#FF9257", "#FFBE9E", "#FFE5D9"]
    },
    "stats": {"n_points": 152, "min": 0.0745, "mean": 0.2206, "max": 0.2546}
  }
}
```

Błędne dane wejściowe dają status `422`, tak jak w `/search`.

**Format mapy błędu** (pole `error_map` w obu odpowiedziach)

Błąd to liczba od 0 do 1: `0` oznacza miejsce o profilu identycznym z celem,
im więcej, tym gorzej. Dla każdego punktu `błąd = 1 - score`.

| Pole | Opis |
| :--- | :--- |
| `image_base64` | `data:image/png;base64,...`, obraz z przezroczystością. Kolor piksela oznacza błąd w tym miejscu, piksel przezroczysty oznacza brak danych. Uwaga: to PNG, a nie WebP jak heatmapa. |
| `width`, `height` | Rozmiar obrazu w pikselach. Mapa całej Ziemi ma 1024x512. Mapka szczegółowa ma `size_px` x `size_px`; jest niższa tylko wtedy, gdy okno sięga bieguna. |
| `bounds` | `lat_min`, `lat_max`, `lon_min`, `lon_max`: krawędzie obrazu w stopniach. Odwzorowanie jak w heatmapie (równoodległościowe, północ u góry): kolumny dzielą równo zakres długości, wiersze zakres szerokości. W mapce szczegółowej `lon_min` i `lon_max` wychodzą poza `[-180, 180]`, gdy okno przecina południk 180 (np. `170..190`). |
| `scale` | `min` (zawsze 0), `max` i `colors`: 9 kolorów rozłożonych równo od `min` do `max`, od ciemnego (mały błąd) do jasnego (duży). Błąd `max` i większy ma ostatni kolor. Skala jest stała: ten sam kolor oznacza ten sam błąd w każdym zapytaniu i na obu mapach. |
| `stats` | `n_points`: ile punktów danych leży na mapie; `min`, `mean`, `max`: ich błąd (`null`, gdy punktów nie ma). |

**`GET /health`** zwraca `{"status": "ok", "n_points": ..., "n_features": ...}`.

### Python

Te same funkcje można wołać bez HTTP:

```python
from szukacz import error_map_detail, load_earth_data, search

earth = load_earth_data("/data/earth")
result = search(earth, features_norm, weights, top_k=100, min_distance_km=100.0)
result["error_map"]  # mapa błędu całej Ziemi

best = result["candidates"][0]
detail = error_map_detail(earth, features_norm, weights, best["lat"], best["lon"], radius_km=250.0)
detail["error_map"]  # mapka błędu wokół najlepszej lokalizacji
```

| Funkcja | Opis |
| :--- | :--- |
| `data.load_earth_data(data_dir) -> EarthData` | Mapuje macierze `.npy` do pamięci i wczytuje metadane. Sprawdza kształty i kolumny. |
| `engine.search(data, features_norm, weights, *, top_k, min_distance_km, require_caves, cave_max_km, error_scale_max) -> dict` | Pełne wyszukiwanie, zwraca słownik odpowiedzi `POST /search`. |
| `engine.error_map_detail(data, features_norm, weights, lat, lon, *, radius_km, size_px, error_scale_max) -> dict` | Szczegółowa mapka błędu wokół punktu, zwraca słownik odpowiedzi `POST /error-map`. |
| `maps.global_error_grid(data, point_scores) -> ndarray (512, 1024)` | Błąd na całej Ziemi jako liczby; `NaN` tam, gdzie nie ma danych. |
| `maps.detail_error_grid(data, target, weights_norm, lat, lon, radius_km, size_px) -> DetailGrid` | Szczegółowa siatka błędu jako liczby (`errors`), z granicami okna i błędami punktów, które w nim leżą. |
| `maps.colorize_error(grid, scale_max)`, `maps.render_error_map(grid, scale_max)` | Siatka błędu jako obraz RGBA albo data URI PNG. |
| `maps.render_heatmap(data, point_scores) -> str` | Heatmapa jako data URI WebP. |
| `maps.pixel_best_scores(data, point_scores)` | Najlepszy wynik w każdym pikselu siatki 1024x512; wspólny krok heatmapy i mapy błędu. |
| `scoring.normalize_weights(weights)` | Wagi podzielone przez sumę. |
| `scoring.score_block(block, target, weights_norm)` | Dopasowanie dla dowolnego bloku cech `(..., K)`. |
| `scoring.score_all(features, target, weights_norm) -> (best_score, best_month)` | Dopasowanie wszystkich punktów, najlepszy miesiąc każdego (miesiące od 0). |
| `scoring.select_diverse_top_k(scores, unit_xyz, top_k, min_distance_km, eligible=None)` | Indeksy najlepszych punktów, parami dalej niż `min_distance_km`. |
| `scoring.latlon_to_unit_xyz(lat, lon)`, `scoring.great_circle_km(a, b)` | Pomocnicze: punkty na kuli i odległość między nimi. |

`render_heatmap` było wcześniej w `engine.py`; stamtąd nadal da się je
zaimportować.

## Z czego korzystam

**Inne moduły projektu.** Szukacz nie woła żadnych funkcji ani endpointów
innych komponentów. Jedyne, czego potrzebuje, to pliki od Precomputera
w katalogu `SZUKACZ_DATA_DIR` (domyślnie `/data/earth`):

| Plik | Wymagania |
| :--- | :--- |
| `earth_features_norm.npy` | `(N_POINTS, 12, K)`, float32, wartości w `[0, 1]`. |
| `earth_features_raw.npy` | Ten sam kształt, wartości fizyczne. |
| `earth_metadata.parquet` albo `earth_metadata.npy` | Kolumny `id`, `lat`, `lon`, `px_x` (0..1023), `px_y` (0..511), `nearest_cave_km`; po jednym wierszu na punkt, w tej samej kolejności co macierze. Gdy istnieją oba pliki, czytany jest `.parquet`. |

**Biblioteki zewnętrzne** (licencje w `LICENCES.md` w katalogu głównym):

| Biblioteka | Używane funkcje |
| :--- | :--- |
| `numpy` | `load(mmap_mode="r")`, `subtract`, `abs`, mnożenie macierzy `@`, `argmax`, `argpartition`, `argsort`, `fmax.reduceat`, `unique`; w mapach błędu także `minimum.accumulate`, `partition`, `lexsort`, `interp`, `flatnonzero`. |
| `pillow` | `Image.fromarray`, `Image.save(format="WEBP", lossless=True)` dla heatmapy; `Image.putpalette`, `Image.save(format="PNG")` dla map błędu. |
| `fastapi`, `pydantic` | `FastAPI`, `HTTPException`, `JSONResponse`, `BaseModel`, `Field`. |
| `uvicorn` | Serwer uruchamiający aplikację. |
| `pyarrow` | `parquet.read_table`, tylko gdy metadane są w `.parquet`. |
| biblioteka standardowa | `concurrent.futures.ThreadPoolExecutor`, `base64`, `io`, `math`, `time`. |

Mapy błędu nie wymagają żadnej nowej biblioteki. Specyfikacja wymienia też
`numba` i `rasterio`. Nie są używane.

## Jak to liczy

**Dopasowanie** punktu `n` w miesiącu `m` (wzór ze specyfikacji):

    Score(n, m) = 1 - sum_k(w_k * |X[n, m, k] - y_k|) / sum_k(w_k)

Wynikiem punktu jest jego najlepszy miesiąc. Gdy wszystkie wagi są zerowe,
każdy punkt dostaje `1.0` (tak samo liczy frontend). Miesiąc z brakiem danych
(NaN w którejkolwiek cesze, także o wadze 0) przegrywa z każdym innym, a punkt
bez żadnego pełnego miesiąca nie trafia do wyników.

**Błąd** punktu to ważona różnica między profilem celu a cechami punktu
w jego najlepszym miesiącu, czyli drugi składnik wzoru na dopasowanie:

    Error(n) = min_m sum_k(w_k * |X[n, m, k] - y_k|) / sum_k(w_k) = 1 - Score(n)

Punkt bez żadnego pełnego miesiąca nie ma błędu i nie trafia na mapy.

**Zróżnicowany Top-K.** Punkty są przeglądane od najlepszego. Punkt trafia do
wyniku, jeśli od każdego już wybranego dzieli go więcej niż `min_distance_km`
(odległość po powierzchni kuli o promieniu 6371 km); w przeciwnym razie jest
pomijany. Przeglądanie trwa, aż zbierze się `top_k` punktów albo skończą się
punkty.

**Filtr jaskiń.** Przy `require_caves: true` w rankingu biorą udział tylko
punkty z `nearest_cave_km <= 15`. Heatmapa i mapy błędu nadal pokazują
wszystkie punkty.

**Heatmapa.** Każdy piksel siatki 1024x512 (`px_x`, `px_y` z metadanych)
dostaje najlepszy wynik spośród leżących w nim punktów. Kolor jest stały
(`#10B981`), zmienia się krycie. Skala jest względna dla zapytania: najsłabszy
punkt na mapie jest przezroczysty, najlepszy w pełni kryjący, a krycie rośnie
z kwadratem pozycji między nimi. Piksele bez punktów są przezroczyste.

**Mapa błędu całej Ziemi.** Ta sama siatka 1024x512 co w heatmapie. Piksel
dostaje najmniejszy błąd spośród leżących w nim punktów, czyli błąd tego
samego punktu, który wyznacza piksel heatmapy. Od heatmapy różni ją skala:

- Skala jest bezwzględna. Kolor zależy tylko od wartości błędu, a nie od
  tego, jak wypadły inne punkty w tym zapytaniu, więc mapy z różnych zapytań
  (inne wagi, inny cel) da się porównywać.
- Krycie jest stałe, zmienia się kolor: jedna barwa (odcień Ember `#F97316`
  z CONTEXT.md) w 255 odcieniach, od ciemnego przy błędzie 0 do jasnego przy
  błędzie `scale.max`. Każde miejsce z danymi jest widoczne, także najlepsze.
- Koniec skali to `0.5` (zmienna `SZUKACZ_ERROR_SCALE_MAX`). Na danych
  mockowych błąd przy kilku cechach z wagami mieści się w `0.07..0.47`; przy
  jednej cesze dochodzi do `0.74` i wtedy najgorsze miejsca mają ostatni kolor.

**Mapka szczegółowa.** Okno jest kwadratem w kilometrach: `radius_km` od
punktu w każdą stronę, więc zakres długości geograficznej rośnie z szerokością
(`radius_km / 111.195 / cos(lat)` stopni). Mapa całej Ziemi zostawia w pikselu
tylko najlepszy punkt; tutaj każdy punkt danych jest osobno i w swoim
dokładnym położeniu:

- Piksel dostaje błąd najbliższego punktu danych (odległość `|dlon| + |dlat|`
  w stopniach).
- Jeśli ten punkt leży dalej niż 0.75 typowego odstępu między punktami
  (w którejkolwiek osi), piksel zostaje przezroczysty: tam nie ma danych
  (ocean, las).
- Typowy odstęp to mediana odległości do trzeciego najbliższego sąsiada
  wśród punktów okna (liczona na próbce).
- Gdy kilka punktów trafia w jeden piksel, zostaje najmniejszy błąd, tak jak
  na mapie całej Ziemi.

Na regularnej siatce lat/lon każdy punkt wypełnia dokładnie swoje oczko
(z zapasem ćwierć oczka na brzegu lądu), a dziury wielkości oczka i większe
zostają widoczne.

Ograniczenia mapki szczegółowej:

- Nie interpoluje i nie dodaje szczegółów, których nie ma w danych. O tym, ile
  widać, decyduje gęstość punktów od Precomputera. Mock z 60 000 punktów ma
  ich ok. 1.4 na piksel mapy całej Ziemi, więc mapka pokazuje niewiele więcej
  niż ona; przy 400 000 punktów jest ich ok. 3.7 na piksel.
- Zakłada punkty rozłożone równomiernie w stopniach. Przy punktach losowych
  (mock) ok. 10% pikseli lądu zostaje pustych, bo wypadają w przerwach między
  punktami.
- Samotny punkt wypełnia najwyżej 1/8 szerokości mapki w każdą stronę.
- Okno sięgające bieguna jest przycinane (`height < size_px`) i obejmuje pełny
  zakres długości; lewa i prawa krawędź obrazu to wtedy ten sam południk,
  a wypełnianie nie przechodzi przez tę krawędź.

## Uruchomienie

```bash
cd 4-szukacz
pip install -r requirements.txt
SZUKACZ_DATA_DIR=/data/earth uvicorn szukacz.api:app --host 0.0.0.0 --port 8002
```

Albo przez `Dockerfile` z tego katalogu (dane montowane jako `/data`).

| Zmienna | Domyślnie | Znaczenie |
| :--- | :--- | :--- |
| `SZUKACZ_DATA_DIR` | `/data/earth` | Katalog z danymi Ziemi. |
| `SZUKACZ_MIN_DISTANCE_KM` | `100` | Odległość używana, gdy zapytanie nie poda `min_distance_km`. |
| `SZUKACZ_CAVE_MAX_KM` | `15` | Próg filtra `require_caves`. |
| `SZUKACZ_ERROR_SCALE_MAX` | `0.5` | Błąd, na którym kończy się skala kolorów map błędu (obu). |
| `SZUKACZ_THREADS` | liczba rdzeni, najwyżej 16 | Wątki liczące dopasowanie. |

## Testy

```bash
cd 4-szukacz
python -m unittest discover -s tests -v
```

Testy same tworzą małe dane w katalogu tymczasowym. Dwa testy endpointów HTTP
są pomijane, gdy nie ma pakietów `fastapi` i `httpx`.

## Stan sprawdzenia i wydajność

Sprawdzone testami (numpy + pillow): wzór dopasowania, najlepszy miesiąc,
odsiewanie bliskich punktów (porównanie z prostą implementacją wzorcową),
filtr jaskiń, kształt odpowiedzi, heatmapa, obsługa braków danych i błędów
wejścia. Dla map błędu: mapa całej Ziemi porównana ze wzorem piksel po
pikselu, mapka szczegółowa porównana z prostą implementacją wzorcową, która
dla każdego piksela sprawdza wszystkie punkty (punkty losowe, regularna siatka
z dziurą, okno przez południk 180, okno przy biegunie, okolica bez danych).

Uruchomione 2026-11-14 w osobnym środowisku (Python 3.13, fastapi 0.163,
httpx 0.28, numpy 2.5, pillow 13, pyarrow 26):

- Testy endpointów `/search` i `/error-map` przechodzą.
- Serwer `uvicorn` wystartował i odpowiedział na `/health`, `/search`
  i `/error-map`. Dane: 60 000 punktów z generatora mocka Precomputera,
  metadane w `.parquet`. Generator w obecnej postaci kończy się błędem
  (`todo_list.txt`, punkt 12); do tej próby został uruchomiony z poprawką
  w pamięci, bez zmiany pliku.
- Odczyt metadanych z `.parquet` działa, ale nie ma testu automatycznego.

Nieuruchomione: budowanie obrazu z `Dockerfile` (brak Dockera na maszynie).

Czasy zmierzone na 400 000 punktów z generatora mocka, 8 rdzeni. Maszyna była
w tym czasie obciążona innymi procesami, więc liczy się głównie porównanie:

| Co | Czas (mediana) | Rozmiar odpowiedzi |
| :--- | :--- | :--- |
| `POST /search` przed dodaniem mapy błędu | ok. 92 ms | 335 kB |
| `POST /search` z mapą błędu | ok. 105 ms | 465 kB |
| `POST /search`, `min_distance_km` = 500 | ok. 160 ms | |
| `POST /error-map`, wartości domyślne (250 km, 512 px) | ok. 27 ms | 33-43 kB |
| `POST /error-map`, 250 km, 256 px | ok. 10 ms | |
| `POST /error-map`, 2000 km, 512 px | ok. 85 ms | 115 kB |
| `POST /error-map`, 2000 km, 1024 px | ok. 160 ms | |

W czasie `/search` liczenie dopasowania to 40-50 ms, heatmapa ok. 23 ms,
mapa błędu ok. 11 ms. Specyfikacja zakłada poniżej 15 ms na zapytanie; tego
celu obecna wersja nie spełnia.
