# Licences and data sources

Every dataset, publication, image and software library used by the Planetary Analog Finder.
All scientific data are public NASA, USGS, NOAA or international archive products that may be used freely with
citation; US Government works are in the public domain. Software licences are listed in section 5.
A plain, copy-ready list of all data links is at the end (section 6).

Contents:
1. Earth data (`5-precomputer/` → `data/earth/`, used by the search in `4-szukacz/`)
2. Mars data (`3-charakteryzator/`)
3. Moon data (`3-charakteryzator/`)
4. Images used by the website (`images/`)
5. Software and libraries
6. All data links (plain list)

---

## 1. Earth data

Earth surface data used to build the 12-month × 9-feature matrices of the Earth search (climatology 2019–2023,
0.2° grid, all land).

| Dataset | Used for | Provider / licence | DOI / source |
| :--- | :--- | :--- | :--- |
| MODIS Terra Land Surface Temperature, monthly CMG 0.05° (MOD11C3 v061) | `temp_mean`, `temp_diurnal_amp` (spatial pattern), land mask | NASA LP DAAC; NASA data, no restrictions | https://doi.org/10.5067/MODIS/MOD11C3.061 |
| MODIS Aqua Land Surface Temperature, monthly CMG 0.05° (MYD11C3 v061) | as above | NASA LP DAAC; NASA data, no restrictions | https://doi.org/10.5067/MODIS/MYD11C3.061 |
| GLDAS Noah Land Surface Model L4, monthly 0.25° (GLDAS_NOAH025_M v2.1) | `soil_moisture`; soil water and freezing for `thermal_inertia` | NASA GES DISC; NASA data, no restrictions | https://doi.org/10.5067/SXAVCZFAQLNO |
| MERRA-2 tavgU_2d_slv_Nx (M2TUNXSLV), monthly mean diurnal cycle, skin temperature | `temp_diurnal_amp` (24-hour range) | NASA GMAO / GES DISC; NASA data, no restrictions | https://doi.org/10.5067/AFOK0TPEVQEK |
| MERRA-2 tavgM_2d_aer_Nx (M2TMNXAER), total aerosol optical depth 550 nm | `dust_aerosol` | NASA GMAO / GES DISC; NASA data, no restrictions | https://doi.org/10.5067/FH9A0MLJPC7N |
| MERRA-2 const_2d_asm_Nx (M2C0NXASM), land and land-ice fractions | land / ice masks | NASA GMAO / GES DISC; NASA data, no restrictions | https://doi.org/10.5067/ME5QX6Q5IGGU |
| Regridded Harmonized World Soil Database v1.2 (HWSD_1247) | sand, clay, bulk density for `thermal_inertia` and `soil_moisture` | NASA ORNL DAAC; FAO / IIASA / ISRIC / ISSCAS / JRC | https://doi.org/10.3334/ORNLDAAC/1247 |
| NOAA ETOPO 2022 v1, 60 arc-second surface and bedrock elevation | `surface_roughness`, `slope_deg`, `radiation_proxy`, elevation, ice mask (surface − bedrock) | NOAA NCEI; US Government work, public domain | https://doi.org/10.25921/fd45-gt74 · https://www.ncei.noaa.gov/products/etopo-global-relief-model |

Archives: NASA LP DAAC https://lpdaac.usgs.gov · NASA GES DISC https://disc.gsfc.nasa.gov · NASA ORNL DAAC https://daac.ornl.gov
(accessed through NASA Earthdata).

Methods: soil thermal conductivity after Johansen (1975) in the form of Peters-Lidard, C. D., Blackburn, E., Liang, X.,
& Wood, E. F. (1998). The effect of soil thermal conductivity parameterization on surface energy fluxes and
temperatures. J. Atmos. Sci., 55, 1209–1224. https://doi.org/10.1175/1520-0469%281998%29055%3C1209%3ATEOSTC%3E2.0.CO%3B2 ;
atmospheric column mass from the ICAO standard atmosphere.

---

## 2. Mars data

### 2.1 Orbital maps (fixed properties of a place)

| Dataset | Used for | Archive | Source |
| :--- | :--- | :--- | :--- |
| MGS MOLA Mission Experiment Gridded Data Records (MEGDR, 32 px/deg) | elevation, `slope_deg`, `surface_roughness` | NASA PDS Geosciences Node | https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/ |
| MGS TES nightside thermal inertia map (MGS-M-TES-5-TIMAP-V1) | `thermal_inertia`; input of the temperature model | NASA PDS Geosciences Node | https://pds-geosciences.wustl.edu/mgs/mgs-m-tes-5-timap-v1/ |
| MGS TES bolometric albedo (MGS-M-TES-SPECIAL-V1) | albedo for the temperature model | NASA PDS Geosciences Node | https://pds-geosciences.wustl.edu/mgs/mgs-m-tes-special-v1/ |
| Mars Odyssey GRS elemental maps, water-equivalent hydrogen (ODY-M-GRS-5-ELEMENTS-V1) | `soil_moisture` | NASA PDS Geosciences Node | https://pds-geosciences.wustl.edu/ody/ody-m-grs-5-elements-v1/ |
| Mars Odyssey neutron spectrometer epithermal flux (Odyssey GRS special products) | hydrogen index | NASA PDS Geosciences Node | https://pds-geosciences.wustl.edu/ody/urn-nasa-pds-odyssey_grs_special/ |
| OMEGA / CRISM hydrated mineral detections (MEX-M-OMEGA-5-DDR-GLOBAL-MAPS-V1) | distance to hydrated minerals | NASA PDS Geosciences Node | https://pds-geosciences.wustl.edu/mex/mex-m-omega-5-ddr-global-maps-v1/ |
| Mars Global Cave Candidate Catalog (MGC3) v1, volcanic candidates of priority 0–2 | `nearest_skylight_km` | USGS Astrogeology / NASA PDS Imaging Node; US Government work, public domain | https://doi.org/10.17189/1519222 · https://astrogeology.usgs.gov/search/map/mars_global_cave_candidate_catalog_v1_cushing |

### 2.2 Atmosphere (global model)

| Dataset | Used for | Archive | Source |
| :--- | :--- | :--- | :--- |
| MGS TES atmospheric dust and water-ice opacity | `dust_aerosol`; dust in the energy-balance model | NASA PDS Atmospheres Node | https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/mgs_tes_atmos_dust-ice/ |
| NASA Ames Mars General Circulation Model output (MOGC_0001) | reference for the seasonal pressure and temperature cycle | NASA PDS Atmospheres Node | https://pds-atmospheres.nmsu.edu/PDS/data/mogc_0001/ |

### 2.3 Surface station records (local model and calibration of the global model)

| Mission / instrument | Data set | Source |
| :--- | :--- | :--- |
| Viking Lander 1 and 2 meteorology | VL_1001, VL_1002 | https://pds-atmospheres.nmsu.edu/PDS/data/vl_1001/ · https://pds-atmospheres.nmsu.edu/PDS/data/vl_1002/ |
| Mars Pathfinder ASI/MET surface records | MPAM_0001 | https://pds-atmospheres.nmsu.edu/PDS/data/mpam_0001/ |
| Phoenix MET (temperature, pressure), sky opacity, telltale wind | PHMT_0001, PHXAO_1001, PHXWND_0001 | https://pds-atmospheres.nmsu.edu/PDS/data/phmt_0001/ · https://pds-atmospheres.nmsu.edu/PDS/data/phxao_1001/ · https://pds-atmospheres.nmsu.edu/PDS/data/phxwnd_0001/ |
| Curiosity REMS environmental records | MSLREM_1001 | https://pds-atmospheres.nmsu.edu/PDS/data/mslrem_1001/ |
| InSight APSS (TWINS air temperature and wind, pressure) | InSight TWINS and calibrated bundles | https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/InSight/ |
| Perseverance MEDA environmental records | Mars 2020 MEDA bundle | https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/Mars2020/mars2020_meda/ |

### 2.4 Publications behind the Mars datasets

Cushing, G. E., Okubo, C. H., & Titus, T. N. (2015). Atypical pit craters on Mars: New insights from THEMIS, CTX, and
HiRISE observations. J. Geophys. Res. Planets, 120, 1023–1043. https://doi.org/10.1002/2014JE004735

Carter, J., Poulet, F., Bibring, J.-P., Mangold, N., & Murchie, S. (2013). Hydrous minerals on Mars as seen by the CRISM
and OMEGA imaging spectrometers: Updated global view. J. Geophys. Res. Planets, 118, 831–858.
https://doi.org/10.1029/2012JE004145

---

## 3. Moon data

| Dataset | Used for | Archive | Source |
| :--- | :--- | :--- | :--- |
| LRO LOLA Gridded Data Records (global 16 px/deg; polar 240 m and 40 m) | elevation, `slope_deg`, `surface_roughness` | NASA PDS Geosciences Node | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/ |
| LOLA average Sun and Earth visibility maps, poleward of 65° | sunlight and Earth-visibility fractions | NASA PGDA (Goddard) | https://pgda.gsfc.nasa.gov/products/69 · https://pgda.gsfc.nasa.gov/data/MoonIllumination/ |
| LRO Diviner polar resource products (annual mean / max temperature, ice stability depth) | polar `temp_mean`, ice | NASA PDS Geosciences Node | https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/ |
| LRO Diviner rock abundance (global, 32 px/deg) | lunar `thermal_inertia` (regolith / rock blend) | NASA PDS Geosciences Node | https://pds-geosciences.wustl.edu/lro/ |
| Lunar Prospector GRS and neutron spectrometer element abundances (LP-L-GRS-5-ELEM-ABUNDANCE-V1) | hydrogen, FeO, TiO2 | NASA PDS Geosciences Node | https://pds-geosciences.wustl.edu/lunar/lp-l-grs-5-elem-abundance-v1/ |
| LROC Lunar Pit Atlas (mare pits only, impact-melt pits excluded) | `nearest_skylight_km` | LROC / Arizona State University | https://www.lroc.asu.edu/atlases/pits |

Publications:

Hayne, P. O., Bandfield, J. L., Siegler, M. A., et al. (2017). Global regolith thermophysical properties of the Moon from
the Diviner Lunar Radiometer Experiment. J. Geophys. Res. Planets, 122, 2371–2400. https://doi.org/10.1002/2017JE005387
(parameters of the lunar regolith temperature model)

Bandfield, J. L., Ghent, R. R., Vasavada, A. R., Paige, D. A., Lawrence, S. J., & Robinson, M. S. (2011). Lunar surface
rock abundance and regolith fines temperatures derived from LRO Diviner Radiometer data. J. Geophys. Res., 116, E00H02.
https://doi.org/10.1029/2011JE003866

Mazarico, E., Neumann, G. A., Smith, D. E., Zuber, M. T., & Torrence, M. H. (2011). Illumination conditions of the lunar
polar regions using LOLA topography. Icarus, 211, 1066–1081. https://doi.org/10.1016/j.icarus.2010.10.030

---

## 4. Images used by the website

| Image | Source |
| :--- | :--- |
| `images/moon_photo.jpg` (Moon globe texture) | LROC Wide Angle Camera global mosaic (LROC Team, Arizona State University / NASA); references below |
| `images/earth_photo.jpg`, `images/mars_photo.jpg`, `images/sky_photo.jpg` (Earth and Mars globe textures, background sky) | added by the frontend team; to be credited by them |
| `images/member_*.jpg`, `images/team_photo.jpg` | the team's own photos |

LROC references:

Speyerer, E. J., Robinson, M. S., Denevi, B. W., & LROC Science Team (2011). Lunar Reconnaissance Orbiter Camera global
morphological map of the Moon. 42nd Lunar and Planetary Science Conference, Houston, TX.
https://www.lpi.usra.edu/meetings/lpsc2011/pdf/2387.pdf

Robinson, M. S., Brylow, S. M., Humm, D., Lawrence, S. J., Thomas, P. C., Denevi, B. W., Bowman-Cisneros, E., et al.
(2010). Lunar Reconnaissance Orbiter Camera (LROC) instrument overview. Space Science Reviews, 150(1), 81–124.
https://doi.org/10.1007/s11214-010-9634-2

Wagner, R. V., Speyerer, E. J., Robinson, M. S., & LROC Team (2015). New mosaicked data products from the LROC Team.
46th Lunar and Planetary Science Conference, Houston, TX. https://www.hou.usra.edu/meetings/lpsc2015/pdf/1473.pdf
(e-poster: http://www.lpi.usra.edu/meetings/lpsc2015/eposter/1473.pdf)

Sato, H., Robinson, M. S., Hapke, B., Denevi, B. W., & Boyd, A. K. (2014). Resolved Hapke parameter maps of the Moon.
J. Geophys. Res. Planets, 119, 1775–1805. https://doi.org/10.1002/2013JE004580

Tooley, C. R., Houghton, M. B., Saylor Jr., S. S., Peddie, C., Everett, D. F., Baker, C. L., & Safdie, K. N. (2010).
Lunar Reconnaissance Orbiter mission and spacecraft design. Space Science Reviews, 150, 23–62.
https://doi.org/10.1007/s11214-009-9624-4

Petro, N. E., Keller, J. W., Cohen, B. A., & McClanahan, T. P. (2019). Ten years of the Lunar Reconnaissance Orbiter:
Advancing lunar science and context for future lunar exploration. 50th Lunar and Planetary Science Conference,
Houston, TX. https://www.hou.usra.edu/meetings/lpsc2019/pdf/2780.pdf

Arizona State University (2019). About Lunar Reconnaissance Orbiter. https://www.lroc.asu.edu ·
PDS Cartography and Imaging Sciences Node (2018). Lunar Reconnaissance Orbiter. https://pds-imaging.jpl.nasa.gov/portal/lro_mission.html

---

## 5. Software and libraries

| Software | Licence | Used in | Source |
| :--- | :--- | :--- | :--- |
| Python | PSF-2.0 | all back-end services (`python:3.12-slim` image) | https://www.python.org |
| NumPy | BSD-3-Clause | 3, 4, 5 | https://numpy.org |
| pandas | BSD-3-Clause | 3, 5 | https://pandas.pydata.org |
| Numba | BSD-2-Clause | 3, 4 (fast heat solvers and scoring) | https://numba.pydata.org |
| SciPy | BSD-3-Clause | 5 | https://scipy.org |
| Pillow | MIT-CMU (HPND) | 3, 4 | https://python-pillow.org |
| PyArrow (Apache Arrow) | Apache-2.0 | 4, 5 | https://arrow.apache.org |
| FastAPI | MIT | 2, 3, 4 | https://fastapi.tiangolo.com |
| Pydantic | MIT | 2, 3, 4 | https://docs.pydantic.dev |
| Uvicorn | BSD-3-Clause | 2, 3, 4 | https://uvicorn.dev |
| HTTPX | BSD-3-Clause | 2 | https://www.python-httpx.org |
| earthaccess | MIT | 5 (NASA Earthdata downloads) | https://github.com/nsidc/earthaccess |
| xarray | Apache-2.0 | 5 | https://xarray.dev |
| netCDF4 | MIT | 5 | https://unidata.github.io/netcdf4-python/ |
| h5netcdf | BSD-3-Clause | 5 | https://h5netcdf.org |
| h5py | BSD-3-Clause | 5 | https://www.h5py.org |
| pyhdf | MIT | 5 | https://github.com/fhs/pyhdf |
| Nginx | BSD-2-Clause | 2 (reverse proxy) | https://nginx.org |
| PHP + Apache (`php:8.3-apache` image) | PHP-3.01 / Apache-2.0 | 1 (website) | https://hub.docker.com/_/php |
| Certbot (`certbot/certbot` image) | Apache-2.0 | HTTPS certificates | https://certbot.eff.org |
| three.js r128 | MIT | 1 (3D globes) | https://threejs.org |
| Chart.js 4.4.1 | MIT | 1 (charts) | https://www.chartjs.org |
| Inter, JetBrains Mono (Google Fonts) | SIL Open Font License 1.1 | 1 (typography) | https://fonts.google.com |

Components: 1 = website (`1-webpage/`), 2 = gateway (`2-networker/`), 3 = Moon/Mars characterizer
(`3-charakteryzator/`), 4 = Earth search (`4-szukacz/`), 5 = Earth data pipeline (`5-precomputer/`).

---

## 6. All data links (plain list)

Earth:

https://doi.org/10.5067/MODIS/MOD11C3.061
https://doi.org/10.5067/MODIS/MYD11C3.061
https://doi.org/10.5067/SXAVCZFAQLNO
https://doi.org/10.5067/AFOK0TPEVQEK
https://doi.org/10.5067/FH9A0MLJPC7N
https://doi.org/10.5067/ME5QX6Q5IGGU
https://doi.org/10.3334/ORNLDAAC/1247
https://doi.org/10.25921/fd45-gt74
https://www.ncei.noaa.gov/products/etopo-global-relief-model
https://lpdaac.usgs.gov
https://disc.gsfc.nasa.gov
https://daac.ornl.gov

Mars:

https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/
https://pds-geosciences.wustl.edu/mgs/mgs-m-tes-5-timap-v1/
https://pds-geosciences.wustl.edu/mgs/mgs-m-tes-special-v1/
https://pds-geosciences.wustl.edu/ody/ody-m-grs-5-elements-v1/
https://pds-geosciences.wustl.edu/ody/urn-nasa-pds-odyssey_grs_special/
https://pds-geosciences.wustl.edu/mex/mex-m-omega-5-ddr-global-maps-v1/
https://doi.org/10.17189/1519222
https://astrogeology.usgs.gov/search/map/mars_global_cave_candidate_catalog_v1_cushing
https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/mgs_tes_atmos_dust-ice/
https://pds-atmospheres.nmsu.edu/PDS/data/mogc_0001/
https://pds-atmospheres.nmsu.edu/PDS/data/vl_1001/
https://pds-atmospheres.nmsu.edu/PDS/data/vl_1002/
https://pds-atmospheres.nmsu.edu/PDS/data/mpam_0001/
https://pds-atmospheres.nmsu.edu/PDS/data/phmt_0001/
https://pds-atmospheres.nmsu.edu/PDS/data/phxao_1001/
https://pds-atmospheres.nmsu.edu/PDS/data/phxwnd_0001/
https://pds-atmospheres.nmsu.edu/PDS/data/mslrem_1001/
https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/InSight/
https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/Mars2020/mars2020_meda/
https://doi.org/10.1002/2014JE004735
https://doi.org/10.1029/2012JE004145

Moon:

https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/
https://pgda.gsfc.nasa.gov/products/69
https://pgda.gsfc.nasa.gov/data/MoonIllumination/
https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/
https://pds-geosciences.wustl.edu/lro/
https://pds-geosciences.wustl.edu/lunar/lp-l-grs-5-elem-abundance-v1/
https://www.lroc.asu.edu/atlases/pits
https://doi.org/10.1002/2017JE005387
https://doi.org/10.1029/2011JE003866
https://doi.org/10.1016/j.icarus.2010.10.030
https://www.lpi.usra.edu/meetings/lpsc2011/pdf/2387.pdf
https://doi.org/10.1007/s11214-010-9634-2
https://www.hou.usra.edu/meetings/lpsc2015/pdf/1473.pdf
https://doi.org/10.1002/2013JE004580
https://doi.org/10.1007/s11214-009-9624-4
https://www.hou.usra.edu/meetings/lpsc2019/pdf/2780.pdf
https://www.lroc.asu.edu
https://pds-imaging.jpl.nasa.gov/portal/lro_mission.html
