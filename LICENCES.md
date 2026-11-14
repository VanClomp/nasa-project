# Licencje i źródła zewnętrzne

## Szukacz (`4-szukacz/`)

Biblioteki Pythona instalowane z PyPI (`4-szukacz/requirements.txt`):

| Biblioteka | Licencja | Źródło |
| :--- | :--- | :--- |
| NumPy | BSD-3-Clause | https://numpy.org |
| Pillow | MIT-CMU (HPND) | https://python-pillow.org |
| FastAPI | MIT | https://fastapi.tiangolo.com |
| Pydantic (zależność FastAPI) | MIT | https://docs.pydantic.dev |
| Uvicorn | BSD-3-Clause | https://www.uvicorn.org |
| PyArrow (Apache Arrow) | Apache-2.0 | https://arrow.apache.org |

Obraz bazowy kontenera: `python:3.12-slim` (Docker Official Image; Python na licencji PSF-2.0).


## Networker (`2-networker/`) oraz Infrastruktura

Biblioteki i oprogramowanie używane w `2-networker/`, `docker-compose.yml` i skryptach wdrożeniowych:

| Oprogramowanie / Biblioteka | Licencja | Źródło |
| :--- | :--- | :--- |
| Nginx | BSD-2-Clause | https://nginx.org |
| HTTPX | BSD-3-Clause | https://www.python-httpx.org |
| FastAPI | MIT | https://fastapi.tiangolo.com |
| Pydantic | MIT | https://docs.pydantic.dev |
| Uvicorn | BSD-3-Clause | https://www.uvicorn.org |
| PHP + Apache (`php:8.3-apache`) | PHP-3.01 / Apache-2.0 | https://hub.docker.com/_/php |
| Certbot (`certbot/certbot`) | Apache-2.0 | https://certbot.eff.org |
