# ⚠️ UWAGA: TO JEST TYMCZASOWY GENERATOR DANYCH HEURYSTYCZNYCH (`5-precomputer`) ⚠️

Plik **`MOCK_HEURYSTYKA_generate_earth_data.py`** służy **wyłącznie** do wygenerowania startowych plików `.npy` w katalogu `/data/earth/`, aby kontener `4-szukacz` mógł wystartować i działać na żywo zanim właściwy `5-precomputer` pobierze i przetworzy prawdziwe dane satelitarne NASA/ESA/JAXA.

## Jak odróżnić wygenerowane dane mockowe od prawdziwych?
1. Skrypt nosi jawną nazwę `MOCK_HEURYSTYKA_generate_earth_data.py`.
2. Podczas generowania danych w katalogu `/data/earth/` tworzony jest plik ostrzegawczy:
   **`/data/earth/UWAGA_DANE_MOCK_HEURYSTYKA.txt`**
3. Endpoint `/api/v1/health` w `2-networker` sprawdza obecność tego pliku i zwraca flagę:
   `"earth_data_is_mock_heuristic": true`.

## Co zrobić, gdy prawdziwy `5-precomputer` wygeneruje docelowe macierze?
Nadpisz pliki `earth_features_norm.npy`, `earth_features_raw.npy` oraz `earth_metadata.parquet` / `earth_metadata.npy` w `/data/earth/` i usuń plik `UWAGA_DANE_MOCK_HEURYSTYKA.txt`.
