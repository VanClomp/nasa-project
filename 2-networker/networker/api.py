"""Serwis HTTP Networkera (FastAPI + httpx async, port wewnętrzny 8000).

Odpowiada za:
1. Wystawienie publicznych endpointów `/api/v1/characterize`, `/api/v1/search`
   oraz `/api/v1/error-map`.
2. Orkiestrację zapytań do `3-charakteryzator` (domyślnie http://charakteryzator:8001)
   oraz `4-szukacz` (domyślnie http://szukacz:8002).
3. Jeśli na maszynie nie pobrano jeszcze surowych map binarnych PDS (.img) do
   `/data/mars` i `/data/moon`, korzysta z precomputowanych tablic wynikowych
   `3-charakteryzator/outputs/{mars,moon}_sites.json`.
4. Wzbogacanie wyników z `4-szukacz` o pole `name_hint` (pkt 3 z todo_list.txt).
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .precomputed_sites import characterize_from_precomputed_outputs
from .regions import resolve_name_hint

logger = logging.getLogger("networker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DEFAULT_CHARAKTERYZATOR_URL = "http://charakteryzator:8001"
DEFAULT_SZUKACZ_URL = "http://szukacz:8002"
DEFAULT_TIMEOUT_SECONDS = 30.0


class CharacterizeRequest(BaseModel):
    target_body: str = "moon"
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(...)
    timestamp_iso: str | None = "2026-11-14T12:00:00Z"


class SearchRequest(BaseModel):
    features_norm: list[float | None] = Field(..., min_length=9, max_length=9)
    weights: list[float] = Field(..., min_length=9, max_length=9)
    require_caves: bool = False
    top_k: int = Field(100, ge=1, le=1000)
    min_distance_km: float | None = Field(None, ge=0.0)


class ErrorMapRequest(BaseModel):
    features_norm: list[float | None] = Field(..., min_length=9, max_length=9)
    weights: list[float] = Field(..., min_length=9, max_length=9)
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    radius_km: float = Field(250.0, ge=1.0, le=2000.0)
    size_px: int = Field(512, ge=64, le=1024)


def _sanitize_null_features(
    features_norm: list[float | None], weights: list[float]
) -> tuple[list[float], list[float]]:
    """Zgodnie z kontraktem 3-charakteryzator (service/contract.py):
    'Missing values are null in features_raw and features_norm; the search should give them zero weight.'
    """
    clean_features: list[float] = []
    clean_weights: list[float] = []
    for f_val, w_val in zip(features_norm, weights):
        if f_val is None:
            clean_features.append(0.0)
            clean_weights.append(0.0)
        else:
            clean_features.append(float(f_val))
            clean_weights.append(float(w_val))
    return clean_features, clean_weights


def _sanitize_characterize_response(data: dict[str, Any]) -> dict[str, Any]:
    """Zastępuje wartości null w features_raw, features_norm i nearest_skylight_km wartością 0.0,
    aby explorer.php i results.php nie wyświetlały 'null' w interfejsie użytkownika.
    """
    raw = data.get("features_raw")
    if isinstance(raw, dict):
        for k, v in list(raw.items()):
            if v is None:
                raw[k] = 0.0
    norm = data.get("features_norm")
    if isinstance(norm, list):
        data["features_norm"] = [0.0 if v is None else float(v) for v in norm]
    if data.get("nearest_skylight_km") is None:
        data["nearest_skylight_km"] = 0.0
    return data


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.charakteryzator_url = os.environ.get(
        "CHARAKTERYZATOR_URL", DEFAULT_CHARAKTERYZATOR_URL
    ).rstrip("/")
    app.state.szukacz_url = os.environ.get("SZUKACZ_URL", DEFAULT_SZUKACZ_URL).rstrip("/")
    timeout = float(os.environ.get("NETWORKER_HTTP_TIMEOUT", DEFAULT_TIMEOUT_SECONDS))
    async with httpx.AsyncClient(timeout=timeout) as client:
        app.state.http_client = client
        yield


app = FastAPI(
    title="Planetary Analog Finder - Networker API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
@app.get("/api/v1/health")
async def health(request: Request) -> dict[str, Any]:
    """Sprawdza stan Networkera oraz mikroserwisów Charakteryzator i Szukacz."""
    client: httpx.AsyncClient = request.app.state.http_client
    char_url = request.app.state.charakteryzator_url
    szuk_url = request.app.state.szukacz_url

    services: dict[str, Any] = {}
    for name, url in (("charakteryzator", char_url), ("szukacz", szuk_url)):
        try:
            resp = await client.get(f"{url}/health", timeout=3.0)
            services[name] = {
                "reachable": resp.status_code == 200,
                "status_code": resp.status_code,
                "details": resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else None,
            }
        except Exception as exc:
            services[name] = {"reachable": False, "error": str(exc)}

    return {
        "status": "ok",
        "service": "2-networker",
        "upstreams": services,
    }


@app.post("/api/v1/characterize")
async def characterize_endpoint(body: CharacterizeRequest, request: Request) -> JSONResponse:
    """Przekazuje zapytanie do 3-charakteryzator (lub czyta z 3-charakteryzator/outputs/*_sites.json,
    gdy mapy binarne .img w /data/mars i /data/moon nie są pobrane na dysk).
    """
    client: httpx.AsyncClient = request.app.state.http_client
    char_url = f"{request.app.state.charakteryzator_url}/characterize"
    payload = body.model_dump()

    try:
        resp = await client.post(char_url, json=payload)
        if resp.status_code == 200:
            return JSONResponse(
                content=_sanitize_characterize_response(resp.json()),
                status_code=200,
            )
        if resp.status_code in (400, 422):
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.HTTPError as exc:
        logger.warning("Brak odpowiedzi z 3-charakteryzator (%s): %s", char_url, exc)

    try:
        fallback_data = characterize_from_precomputed_outputs(
            target_body=body.target_body,
            lat=body.lat,
            lon=body.lon,
            timestamp_iso=body.timestamp_iso,
        )
        return JSONResponse(content=fallback_data, status_code=200)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Błąd odczytu precomputowanych tablic 3-charakteryzator: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/v1/search")
async def search_endpoint(body: SearchRequest, request: Request) -> JSONResponse:
    """Przekazuje zapytanie do 4-szukacz i uzupełnia brakujące pole `name_hint`."""
    client: httpx.AsyncClient = request.app.state.http_client
    szuk_url = f"{request.app.state.szukacz_url}/search"

    clean_features, clean_weights = _sanitize_null_features(body.features_norm, body.weights)
    payload: dict[str, Any] = {
        "features_norm": clean_features,
        "weights": clean_weights,
        "require_caves": body.require_caves,
        "top_k": body.top_k,
    }
    if body.min_distance_km is not None:
        payload["min_distance_km"] = body.min_distance_km

    try:
        resp = await client.post(szuk_url, json=payload)
    except httpx.HTTPError as exc:
        logger.error("Błąd połączenia z 4-szukacz (%s): %s", szuk_url, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Serwis 4-szukacz jest niedostępny: {exc}",
        ) from exc

    if resp.status_code != 200:
        try:
            err_body = resp.json()
        except Exception:
            err_body = {"detail": resp.text}
        return JSONResponse(content=err_body, status_code=resp.status_code)

    data = resp.json()

    # Uzupełnienie `name_hint` (punkt 3 z todo_list.txt), jeśli Szukacz go nie zwrócił
    candidates = data.get("candidates")
    if isinstance(candidates, list):
        for cand in candidates:
            if not cand.get("name_hint"):
                c_lat = float(cand.get("lat", 0.0))
                c_lon = float(cand.get("lon", 0.0))
                cand["name_hint"] = resolve_name_hint(c_lat, c_lon)

    return JSONResponse(content=data, status_code=200)


@app.post("/api/v1/error-map")
async def error_map_endpoint(body: ErrorMapRequest, request: Request) -> JSONResponse:
    """Przekazuje zapytanie o szczegółową mapę błędu do 4-szukacz (pkt 18 z todo_list.txt)."""
    client: httpx.AsyncClient = request.app.state.http_client
    szuk_url = f"{request.app.state.szukacz_url}/error-map"

    clean_features, clean_weights = _sanitize_null_features(body.features_norm, body.weights)
    payload: dict[str, Any] = {
        "features_norm": clean_features,
        "weights": clean_weights,
        "lat": body.lat,
        "lon": body.lon,
        "radius_km": body.radius_km,
        "size_px": body.size_px,
    }

    try:
        resp = await client.post(szuk_url, json=payload)
    except httpx.HTTPError as exc:
        logger.error("Błąd połączenia z 4-szukacz (%s): %s", szuk_url, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Serwis 4-szukacz jest niedostępny: {exc}",
        ) from exc

    try:
        resp_data = resp.json()
    except Exception:
        resp_data = {"detail": resp.text}
    return JSONResponse(content=resp_data, status_code=resp.status_code)
