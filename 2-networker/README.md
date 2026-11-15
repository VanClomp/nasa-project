# Networker (`2-networker`) and server infrastructure

The `2-networker` component is the API gateway and reverse proxy (Nginx + FastAPI with async `httpx`) for the whole
**Planetary Analog Finder** cluster.

## Architecture and traffic flow

1. **Public ports `80` / `443` (Nginx)**:
   - `/` -> web traffic goes to the `frontend` container (`PHP 8.3 + Apache`, serving the pages from `1-webpage/`
     and the images from `images/`).
   - `/api/v1/*` and `/health` -> the local FastAPI process (`127.0.0.1:8000` inside the `networker` container).
   - `/.well-known/acme-challenge/` -> domain verification by Certbot (Let's Encrypt).

2. **Request orchestration (FastAPI, `networker/api.py`)**:
   - `POST /api/v1/characterize` -> forwarded to `http://charakteryzator:8001/characterize` (including the optional
     `series` flag for 12-month p(t) data). If `3-charakteryzator` is unavailable or its map data is missing, the
     gateway answers from the precomputed site tables `3-charakteryzator/outputs/{mars,moon}_sites.json`
     (`networker/precomputed_sites.py`), marked `extra.model = "global"` because the values belong to the nearest
     known site, not the clicked point.
   - `POST /api/v1/search` -> forwarded (with the optional `min_distance_km`) to `http://szukacz:8002/search`; every
     candidate then gets a `name_hint` from the catalogue of analog regions (`networker/regions.py`), solving item 3
     of `todo_list.txt`.
   - `POST /api/v1/error-map` -> forwarded to `http://szukacz:8002/error-map`.
   - `GET /api/v1/health` -> queries `/health` of `charakteryzator` and `szukacz`.

## Quick start on a Google Cloud VM

```bash
chmod +x deploy_gcp.sh enable_https.sh
./deploy_gcp.sh
```

After pointing the domain's DNS `A` record at the server's external IP:

```bash
./enable_https.sh yourdomain.com you@example.com
```

## Data volumes

The containers read `./data` from the host (mounted as `/data`):
- `data/earth/` - real Earth feature matrices built by `5-precomputer/build_earth.py` (see `LICENCES.md` for sources)
- `data/mars/`, `data/moon/` - the map files the characterizer reads, prepared with
  `3-charakteryzator/scripts/pack_server_data.sh` (not in git; about 1.3 GB)
