# ⚠️ UWAGA: TO JEST TYMCZASOWY MOCK HEURYSTYCZNY (`3-charakteryzator`) ⚠️

Pliki w tym katalogu z prefiksem **`MOCK_HEURYSTYKA_`** oraz **`Dockerfile.mock`** to **tymczasowe zaślepki heurystyczne** przygotowane wyłącznie po to, aby:
1. Postawić pełny klaster Docker Compose na serwerze Google Cloud już teraz.
2. Przetestować komunikację `1-frontend` ↔ `2-networker` ↔ `3-charakteryzator` ↔ `4-szukacz`.

## Jak odróżnić ten mock od prawdziwego komponentu?
- Plik kodu nazywa się wprost `MOCK_HEURYSTYKA_charakteryzator_api.py`.
- Nie czyta on prawdziwych plików GeoTIFF (`.tif`) z `/data/moon/` ani `/data/mars/`, lecz wylicza cechy z analitycznych heurystyk szerokości/długości geograficznej i geometrii Słońca.
- Każda odpowiedź HTTP zawiera dodatkowe pole:
  `"_mock_warning": "UWAGA_DANE_Z_MOCKA_HEURYSTYKI_3_CHARAKTERYZATOR"`
  oraz nagłówek HTTP `X-Mock-Heuristic: true`.

## Co zrobić, gdy prawdziwy `3-charakteryzator` będzie gotowy?
1. Zastąp ten katalog docelowym kodem `3-charakteryzator` i jego docelowym `Dockerfile`.
2. W pliku `docker-compose.yml` zmień `dockerfile: Dockerfile.mock` na `dockerfile: Dockerfile`.
