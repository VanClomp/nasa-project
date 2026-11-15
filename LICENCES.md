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

References:

Original Mosaic: Speyerer, E. J., Robinson, M. S., Denevi, B. W., & LROC Science Team (2011). Lunar Reconnaissance Orbiter Camera global morphological map of the Moon. Paper presented at the 42nd Lunar Planetary Science Conference, Lunar and Planetary Science Institute, Houston, TX. https://www.lpi.usra.edu/meetings/lpsc2011/pdf/2387.pdf

Mission: Robinson, M. S., Brylow, S. M., Humm, D., Lawrence, S. J., Thomas, P. C., Denevi, B. W., Bowman-Cisneros, E., et al. (2010). Lunar Reconnaissance Orbiter Camera (LROC) instrument overview. Space Science Review, 150(1), 81â124. https://doi.org/10.1007/s11214-010-9634-2

Mosaic Production: Wagner, R. V., Speyerer, E. J., Robinson, M. S., & LROC Team (2015). New Mosaicked Data Products from the LROC Team. Paper presented at the 46th Lunar and Planetary Science Conference, Lunar and Planetary Institute, Houston, TX. https://www.hou.usra.edu/meetings/lpsc2015/pdf/1473.pdf
Eposter: http://www.lpi.usra.edu/meetings/lpsc2015/eposter/1473.pdf

Photometry: Sato, H., Robinson, M. S., Hapke, B., Denevi, B. W., & Boyd, A. K. (2104). Resolved Hapke parameter maps of the Moon. Journal of Geophysical Research: Planets, 119, 1775-1805. https://doi.org/10.1002/2013JE004580

Arizona State University (ASU) (2019). About Lunar Reconnaissance Orbiter. https://www.lroc.sese.asu.edu

Petro, N. E., Keller, J. W., Cohen, B. A., & McClanahan, T. P. (2019). Ten years of the Lunar Reconnaissance Orbiter: Advancing lunar science and context for future lunar exploration. Paper presented at the 50th Lunar and Planetary Science Conference, Lunar and Planetary Institute, Houston, TX. https://www.hou.usra.edu/meetings/lpsc2019/pdf/2780.pdf

Planetary Data Systems (PDS) Cartography and Imaging Sciences (IMG) (2018). Lunar Reconnaissance Orbiter. https://pds-imaging.jpl.nasa.gov/portal/lro_mission.html

Tooley, C. R., Houghton, M. B., Saylor Jr., S. S., Peddie, C., Everett, D. F., Baker, C. L., & Safdie, K. N. (2010). Lunar Reconnaissance Orbiter mission and spacecraft design. Space Science Review, 150, 23â62. https://doi.org/10.1007/s11214-009-9624-4


