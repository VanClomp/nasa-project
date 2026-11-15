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




## Precomputer (`5-precomputer/`): real Earth data in `data/earth/`

Earth surface data used to build the 12-month x 9-feature matrices (climatology 2019-2023, 0.2 deg grid):

| Dataset | Used for | Provider / licence | Source |
| :--- | :--- | :--- | :--- |
| MODIS Terra/Aqua Land Surface Temperature monthly CMG 0.05 deg (MOD11C3 / MYD11C3 v061) | `temp_mean`, `temp_diurnal_amp` (spatial pattern), land mask | NASA LP DAAC; NASA data, no restrictions (cite DOIs 10.5067/MODIS/MOD11C3.061, 10.5067/MODIS/MYD11C3.061) | https://lpdaac.usgs.gov |
| GLDAS Noah Land Surface Model L4 monthly 0.25 deg (GLDAS_NOAH025_M v2.1) | `soil_moisture`, soil water and freezing for `thermal_inertia` | NASA GES DISC; NASA data, no restrictions (DOI 10.5067/SXAVCZFAQLNO) | https://disc.gsfc.nasa.gov |
| MERRA-2 tavgU_2d_slv_Nx (M2TUNXSLV), monthly mean diurnal cycle, skin temperature TS | `temp_diurnal_amp` (24-hour range) | NASA GMAO / GES DISC; NASA data, no restrictions (DOI 10.5067/AFOK0TPEVQEK) | https://disc.gsfc.nasa.gov |
| MERRA-2 tavgM_2d_aer_Nx (M2TMNXAER), total aerosol optical depth 550 nm | `dust_aerosol` | NASA GMAO / GES DISC (DOI 10.5067/FH9A0MLJPC7N) | https://disc.gsfc.nasa.gov |
| MERRA-2 const_2d_asm_Nx (M2C0NXASM) | land and land-ice fractions | NASA GMAO / GES DISC (DOI 10.5067/ME5QX6Q5IGGU) | https://disc.gsfc.nasa.gov |
| Regridded Harmonized World Soil Database v1.2 (HWSD_1247) | sand, clay, bulk density for `thermal_inertia` and `soil_moisture` | NASA ORNL DAAC; FAO/IIASA/ISRIC/ISSCAS/JRC (DOI 10.3334/ORNLDAAC/1247) | https://daac.ornl.gov |
| NOAA ETOPO 2022 v1, 60 arc-second surface elevation | `surface_roughness`, `slope_deg`, `radiation_proxy`, `elevation_m` | NOAA NCEI; US Government work, public domain (DOI 10.25921/fd45-gt74) | https://www.ncei.noaa.gov/products/etopo-global-relief-model |

Methods: soil thermal conductivity after Johansen (1975) in the form of Peters-Lidard, C. D., et al. (1998), J. Atmos. Sci. 55, 1209-1224; column mass from the ICAO standard atmosphere.

Python libraries: earthaccess (MIT), xarray (Apache-2.0), netCDF4 (MIT), h5netcdf (BSD-3-Clause), h5py (BSD-3-Clause), pyhdf (MIT), SciPy (BSD-3-Clause), NumPy (BSD-3-Clause), PyArrow (Apache-2.0), pandas (BSD-3-Clause).


## Charakteryzator (`3-charakteryzator/`): Mars cave candidates

| Dataset | Used for | Provider / licence | Source |
| :--- | :--- | :--- | :--- |
| Mars Global Cave Candidate Catalog (MGC3) v1, Cushing & Okubo (2016/2017), volcanic candidates of priority 0-2 | `nearest_skylight_km` on Mars | USGS Astrogeology / NASA PDS Imaging Node; US Government work, public domain (DOI 10.17189/1519222) | https://astrogeology.usgs.gov/search/map/mars_global_cave_candidate_catalog_v1_cushing |

Cushing, G. E., Okubo, C. H., & Titus, T. N. (2015). Atypical pit craters on Mars: New insights from THEMIS, CTX, and HiRISE observations. J. Geophys. Res. Planets, 120, 1023-1043. https://doi.org/10.1002/2014JE004735
