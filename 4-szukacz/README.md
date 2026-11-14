# Szukacz (komponent 4)

Silnik wyszukiwania ziemskich analogów. Dostaje profil punktu na Księżycu lub
Marsie (K znormalizowanych cech) i K wag, a zwraca `top_k` (domyślnie 100)
lokalizacji na Ziemi, które najlepiej do niego pasują, razem z najlepszym
miesiącem i mapą dopasowania.

Zwracane lokalizacje są zróżnicowane: jeśli dwa punkty leżą bliżej siebie niż
`min_distance_km`, liczy się tylko lepszy z nich, a zwolnione miejsce zajmuje
kolejny punkt z rankingu. Wynik nadal ma `top_k` pozycji.

Szukacz na razie tylko zwraca te punkty. Dalsze badanie wyników (raycasting po
DEM, punkt 5.4 zadań w specyfikacji) nie jest zaimplementowane.

## Pliki

| Plik | Zawartość |
| :--- | :--- |
| `szukacz/data.py` | Wczytanie danych Ziemi z `/data/earth` (mmap) i metadanych punktów. |
| `szukacz/scoring.py` | Liczenie dopasowania i wybór zróżnicowanego Top-K. Sama matematyka, bez plików i JSON-a. |
| `szukacz/engine.py` | Funkcja `search()`: składa wynik w kształcie odpowiedzi `POST /search`, rysuje heatmapę. |
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
- Lista może mieć mniej niż `top_k` pozycji, gdy na Ziemi nie ma tylu punktów
  spełniających warunki (filtr jaskiń, duża `min_distance_km`).
- Brak danych (NaN w macierzach) wychodzi w JSON-ie jako `null`.

Błędne dane wejściowe (zła liczba cech, ujemna waga, NaN) dają status `422`
z opisem w polu `detail`.

**`GET /health`** zwraca `{"status": "ok", "n_points": ..., "n_features": ...}`.

### Python

Te same funkcje można wołać bez HTTP:

```python
from szukacz import load_earth_data, search

earth = load_earth_data("/data/earth")
result = search(earth, features_norm, weights, top_k=100, min_distance_km=100.0)
```

| Funkcja | Opis |
| :--- | :--- |
| `data.load_earth_data(data_dir) -> EarthData` | Mapuje macierze `.npy` do pamięci i wczytuje metadane. Sprawdza kształty i kolumny. |
| `engine.search(data, features_norm, weights, *, top_k, min_distance_km, require_caves, cave_max_km) -> dict` | Pełne wyszukiwanie, zwraca słownik odpowiedzi `POST /search`. |
| `engine.render_heatmap(data, point_scores) -> str` | Heatmapa jako data URI WebP. |
| `scoring.normalize_weights(weights)` | Wagi podzielone przez sumę. |
| `scoring.score_block(block, target, weights_norm)` | Dopasowanie dla dowolnego bloku cech `(..., K)`. |
| `scoring.score_all(features, target, weights_norm) -> (best_score, best_month)` | Dopasowanie wszystkich punktów, najlepszy miesiąc każdego (miesiące od 0). |
| `scoring.select_diverse_top_k(scores, unit_xyz, top_k, min_distance_km, eligible=None)` | Indeksy najlepszych punktów, parami dalej niż `min_distance_km`. |
| `scoring.latlon_to_unit_xyz(lat, lon)`, `scoring.great_circle_km(a, b)` | Pomocnicze: punkty na kuli i odległość między nimi. |

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
| `numpy` | `load(mmap_mode="r")`, `subtract`, `abs`, mnożenie macierzy `@`, `argmax`, `argpartition`, `argsort`, `fmax.reduceat`, `unique`. |
| `pillow` | `Image.fromarray`, `Image.save(format="WEBP", lossless=True)`. |
| `fastapi`, `pydantic` | `FastAPI`, `HTTPException`, `JSONResponse`, `BaseModel`, `Field`. |
| `uvicorn` | Serwer uruchamiający aplikację. |
| `pyarrow` | `parquet.read_table`, tylko gdy metadane są w `.parquet`. |
| biblioteka standardowa | `concurrent.futures.ThreadPoolExecutor`, `base64`, `io`, `math`, `time`. |

Specyfikacja wymienia też `numba` i `rasterio`. Nie są używane.

## Jak to liczy

**Dopasowanie** punktu `n` w miesiącu `m` (wzór ze specyfikacji):

    Score(n, m) = 1 - sum_k(w_k * |X[n, m, k] - y_k|) / sum_k(w_k)

Wynikiem punktu jest jego najlepszy miesiąc. Gdy wszystkie wagi są zerowe,
każdy punkt dostaje `1.0` (tak samo liczy frontend). Miesiąc z brakiem danych
(NaN w którejkolwiek cesze, także o wadze 0) przegrywa z każdym innym, a punkt
bez żadnego pełnego miesiąca nie trafia do wyników.

**Zróżnicowany Top-K.** Punkty są przeglądane od najlepszego. Punkt trafia do
wyniku, jeśli od każdego już wybranego dzieli go więcej niż `min_distance_km`
(odległość po powierzchni kuli o promieniu 6371 km); w przeciwnym razie jest
pomijany. Przeglądanie trwa, aż zbierze się `top_k` punktów albo skończą się
punkty.

**Filtr jaskiń.** Przy `require_caves: true` w rankingu biorą udział tylko
punkty z `nearest_cave_km <= 15`. Heatmapa nadal pokazuje wszystkie punkty.

**Heatmapa.** Każdy piksel siatki 1024x512 (`px_x`, `px_y` z metadanych)
dostaje najlepszy wynik spośród leżących w nim punktów. Kolor jest stały
(`#10B981`), zmienia się krycie. Skala jest względna dla zapytania: najsłabszy
punkt na mapie jest przezroczysty, najlepszy w pełni kryjący, a krycie rośnie
z kwadratem pozycji między nimi. Piksele bez punktów są przezroczyste.

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
| `SZUKACZ_THREADS` | liczba rdzeni, najwyżej 16 | Wątki liczące dopasowanie. |

## Testy

```bash
cd 4-szukacz
python -m unittest discover -s tests -v
```

Testy same tworzą małe dane w katalogu tymczasowym. Test endpointu HTTP jest
pomijany, gdy nie ma pakietów `fastapi` i `httpx`.

## Stan sprawdzenia i wydajność

Sprawdzone testami (numpy + pillow): wzór dopasowania, najlepszy miesiąc,
odsiewanie bliskich punktów (porównanie z prostą implementacją wzorcową),
filtr jaskiń, kształt odpowiedzi, heatmapa, obsługa braków danych i błędów
wejścia.

Nieuruchomione, bo na maszynie, na której to powstało, nie było tych pakietów
ani Dockera: warstwa HTTP (`api.py`), odczyt metadanych z `.parquet`,
budowanie obrazu z `Dockerfile`.

Czas jednego zapytania zmierzony na 400 000 syntetycznych punktów, 8 rdzeni:
około 80 ms, z czego liczenie dopasowania około 40 ms, heatmapa około 22 ms,
wybór Top-K około 9 ms. Przy dużej `min_distance_km` (500 km) rośnie do około
140 ms. Specyfikacja zakłada poniżej 15 ms; tego celu obecna wersja nie
spełnia.
