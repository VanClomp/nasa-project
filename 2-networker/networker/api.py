"""Serwis HTTP Networkera (FastAPI + httpx async, port wewnętrzny 8000).

Odpowiada za:
1. Wystawienie publicznych endpointów `/api/v1/characterize` oraz `/api/v1/search`.
2. Orkiestrację zapytań do `3-charakteryzator` (domyślnie http://charakteryzator:8001)
   oraz `4-szukacz` (domyślnie http://szukacz:8002).
3. Wzbogacanie wyników z `4-szukacz` o pole `name_hint` (rozwiązuje pkt 3 z todo_list.txt)
   oraz przekazywanie parametru `min_distance_km` (pkt 1 z todo_list.txt).
4. Automatyczny, wyraźnie oznaczony fallback do heurystyki mocka, jeśli kontener
   `3-charakteryzator` jest wyłączony lub niedostępny.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .mock_heuristics import heuristic_characterize
from .regions import resolve_name_hint

logger = logging.getLogger("networker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DEFAULT_CHARAKTERYZATOR_URL = "http://charakteryzator:8001"
DEFAULT_SZUKACZ_URL = "http://szukacz:8002"
DEFAULT_TIMEOUT_SECONDS = 15.0


class CharacterizeRequest(BaseModel):
    target_body: Literal["moon", "mars"] = "moon"
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    timestamp_iso: str = "2026-11-14T12:00:00Z"


class SearchRequest(BaseModel):
    features_norm: list[float] = Field(..., min_length=9, max_length=9)
    weights: list[float] = Field(..., min_length=9, max_length=9)
    require_caves: bool = False
    top_k: int = Field(100, ge=1, le=1000)
    min_distance_km: float | None = Field(None, ge=0.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.charakteryzator_url = os.environ.get(
        "CHARAKTERYZATOR_URL", DEFAULT_CHARAKTERYZATOR_URL
    ).rstrip("/")
    app.state.szukacz_url = os.environ.get("SZUKACZ_URL", DEFAULT_SZUKACZ_URL).rstrip("/")
    app.state.allow_mock_fallback = (
        os.environ.get("NETWORKER_ALLOW_MOCK_FALLBACK", "1").strip() != "0"
    )
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
                "details": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None,
            }
        except Exception as exc:
            services[name] = {"reachable": False, "error": str(exc)}

    earth_mock_marker = Path("/data/earth/UWAGA_DANE_MOCK_HEURYSTYKA.txt")
    return {
        "status": "ok",
        "service": "2-networker",
        "earth_data_is_mock_heuristic": earth_mock_marker.exists(),
        "upstreams": services,
    }


@app.post("/api/v1/characterize")
async def characterize_endpoint(body: CharacterizeRequest, request: Request) -> JSONResponse:
    """Orkiestruje zapytanie do 3-charakteryzator (lub używa heurystyki mocka przy awarii)."""
    client: httpx.AsyncClient = request.app.state.http_client
    char_url = f"{request.app.state.charakteryzator_url}/characterize"
    payload = body.model_dump()

    try:
        resp = await client.post(char_url, json=payload)
        if resp.status_code == 200:
            return JSONResponse(content=resp.json(), status_code=200)
        if resp.status_code == 422:
            return JSONResponse(content=resp.json(), status_code=422)
        logger.warning(
            "Charakteryzator zwrócił status %s: %s", resp.status_code, resp.text[:200]
        )
    except httpx.HTTPError as exc:
        logger.warning("Brak połączenia z 3-charakteryzator (%s): %s", char_url, exc)

    if not request.app.state.allow_mock_fallback:
        raise HTTPException(
            status_code=503,
            detail="Serwis 3-charakteryzator jest niedostępny, a fallback mocka jest wyłączony.",
        )

    logger.warning(
        "[MOCK HEURYSTYKA] Używam awaryjnej heurystyki w 2-networker dla %s (%s, %s)",
        body.target_body,
        body.lat,
        body.lon,
    )
    mock_result = heuristic_characterize(
        target_body=body.target_body,
        lat=body.lat,
        lon=body.lon,
        timestamp_iso=body.timestamp_iso,
    )
    return JSONResponse(
        content=mock_result,
        headers={"X-Mock-Heuristic": "true"},
    )


@app.post("/api/v1/search")
async def search_endpoint(body: SearchRequest, request: Request) -> JSONResponse:
    """Przekazuje zapytanie do 4-szukacz i uzupełnia brakujące pole `name_hint`."""
    client: httpx.AsyncClient = request.app.state.http_client
    szuk_url = f"{request.app.state.szukacz_url}/search"

    payload: dict[str, Any] = {
        "features_norm": body.features_norm,
        "weights": body.weights,
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
