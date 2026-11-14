# Networker (`2-networker`) i Infrastruktura Serwerowa

Komponent `2-networker` pełni rolę bramki API (API Gateway) oraz serwera Reverse Proxy (Nginx + FastAPI `httpx` async) dla całego klastra **Planetary Analog Finder**.

## Architektura i przepływ ruchu

1. **Porty publiczne `80` / `443` (Nginx)**:
   - `/` -> przekierowuje ruch webowy do kontenera `frontend` (`PHP 8.3 + Apache`, który serwuje `index.php`, `explorer.php` oraz `style.css` z głównego katalogu bez potrzeby reorganizacji plików).
   - `/api/v1/*` oraz `/health` -> przekierowuje do lokalnego procesu FastAPI (`127.0.0.1:8000` wewnątrz kontenera `networker`).
   - `/.well-known/acme-challenge/` -> obsługuje weryfikację domeny przez Certbota (Let's Encrypt).

2. **Orkiestracja zapytań (FastAPI `networker/api.py`)**:
   - `POST /api/v1/characterize` -> przekazuje zapytanie do `http://charakteryzator:8001/characterize`. Jeśli `3-charakteryzator` jest niedostępny, automatycznie używa wyraźnie oznaczonej heurystyki awaryjnej (`networker/mock_heuristics.py`).
   - `POST /api/v1/search` -> przekazuje zapytanie (wraz z opcjonalnym `min_distance_km`) do `http://szukacz:8002/search`, a następnie wzbogaca każdego kandydata o pole `name_hint` wyliczane z katalogu regionów analogowych (`networker/regions.py`), rozwiązując punkt 3 z `todo_list.txt`.
   - `GET /api/v1/health` -> odpytuje `/health` w `charakteryzator` i `szukacz` oraz sprawdza, czy w `/data/earth/` znajdują się dane mockowe czy docelowe.

## Szybki start na Google Cloud VM

```bash
chmod +x deploy_gcp.sh enable_gcp_https.sh 2>/dev/null || chmod +x deploy_gcp.sh enable_https.sh
./deploy_gcp.sh
```

Po zakupie domeny i skierowaniu rekordu DNS `A` na zewnętrzne IP serwera:

```bash
./enable_https.sh twojadomena.pl twoj@email.com
```

## Oznaczenie tymczasowych plików Mock / Heurystyka

Dopóki docelowe komponenty `3-charakteryzator` oraz `5-precomputer` są rozwijane na osobnych branchach, klaster korzysta z wyraźnie oznaczonych plików:
- `3-charakteryzator/MOCK_HEURYSTYKA_charakteryzator_api.py` (`Dockerfile.mock`)
- `5-precomputer/MOCK_HEURYSTYKA_generate_earth_data.py` (`Dockerfile.mock`)
- `/data/earth/UWAGA_DANE_MOCK_HEURYSTYKA.txt` (tworzony automatycznie przy generowaniu danych mockowych)
