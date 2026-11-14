"""Serwis HTTP Szukacza (FastAPI, port wewnętrzny 8002).

Uruchomienie z katalogu 4-szukacz:
    uvicorn szukacz.api:app --host 0.0.0.0 --port 8002

Zmienne środowiskowe:
    SZUKACZ_DATA_DIR         katalog z danymi Ziemi (domyślnie /data/earth)
    SZUKACZ_MIN_DISTANCE_KM  odległość używana, gdy zapytanie nie poda min_distance_km (100)
    SZUKACZ_CAVE_MAX_KM      próg filtra require_caves w km (15)
    SZUKACZ_ERROR_SCALE_MAX  błąd, na którym kończy się skala kolorów map błędu (0.5)
    SZUKACZ_THREADS          liczba wątków liczących (domyślnie liczba rdzeni, najwyżej 16)
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .data import load_earth_data
from .engine import (
    DEFAULT_CAVE_MAX_KM,
    DEFAULT_MIN_DISTANCE_KM,
    DEFAULT_TOP_K,
    error_map_detail,
    search,
)
from .maps import (
    DEFAULT_DETAIL_RADIUS_KM,
    DEFAULT_DETAIL_SIZE_PX,
    DEFAULT_ERROR_SCALE_MAX,
    MAX_DETAIL_RADIUS_KM,
    MAX_DETAIL_SIZE_PX,
    MIN_DETAIL_RADIUS_KM,
    MIN_DETAIL_SIZE_PX,
)

MAX_TOP_K = 1000


class SearchRequest(BaseModel):
    features_norm: list[float]
    weights: list[float]
    require_caves: bool = False
    top_k: int = Field(DEFAULT_TOP_K, ge=1, le=MAX_TOP_K)
    # Brak pola oznacza wartość z SZUKACZ_MIN_DISTANCE_KM; 0 wyłącza odsiewanie.
    min_distance_km: float | None = Field(None, ge=0)


class ErrorMapRequest(BaseModel):
    features_norm: list[float]
    weights: list[float]
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(DEFAULT_DETAIL_RADIUS_KM, ge=MIN_DETAIL_RADIUS_KM, le=MAX_DETAIL_RADIUS_KM)
    size_px: int = Field(DEFAULT_DETAIL_SIZE_PX, ge=MIN_DETAIL_SIZE_PX, le=MAX_DETAIL_SIZE_PX)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.earth = load_earth_data(os.environ.get("SZUKACZ_DATA_DIR", "/data/earth"))
    app.state.min_distance_km = float(
        os.environ.get("SZUKACZ_MIN_DISTANCE_KM", DEFAULT_MIN_DISTANCE_KM)
    )
    app.state.cave_max_km = float(os.environ.get("SZUKACZ_CAVE_MAX_KM", DEFAULT_CAVE_MAX_KM))
    app.state.error_scale_max = float(
        os.environ.get("SZUKACZ_ERROR_SCALE_MAX", DEFAULT_ERROR_SCALE_MAX)
    )
    if not app.state.error_scale_max > 0:
        raise ValueError("SZUKACZ_ERROR_SCALE_MAX: oczekiwano liczby > 0")
    yield


app = FastAPI(title="Szukacz", lifespan=lifespan)


@app.get("/health")
def health(request: Request) -> dict:
    earth = request.app.state.earth
    return {"status": "ok", "n_points": earth.n_points, "n_features": earth.n_features}


# Zwykła funkcja (nie async): FastAPI wykonuje ją w puli wątków, więc długie
# liczenie nie blokuje pętli zdarzeń.
@app.post("/search")
def search_endpoint(body: SearchRequest, request: Request) -> JSONResponse:
    state = request.app.state
    min_distance_km = state.min_distance_km if body.min_distance_km is None else body.min_distance_km
    try:
        result = search(
            state.earth,
            body.features_norm,
            body.weights,
            top_k=body.top_k,
            min_distance_km=min_distance_km,
            require_caves=body.require_caves,
            cave_max_km=state.cave_max_km,
            error_scale_max=state.error_scale_max,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    # JSONResponse wprost: wynik to już typy JSON, pomijamy drugą walidację FastAPI.
    return JSONResponse(result)


@app.post("/error-map")
def error_map_endpoint(body: ErrorMapRequest, request: Request) -> JSONResponse:
    state = request.app.state
    try:
        result = error_map_detail(
            state.earth,
            body.features_norm,
            body.weights,
            body.lat,
            body.lon,
            radius_km=body.radius_km,
            size_px=body.size_px,
            error_scale_max=state.error_scale_max,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return JSONResponse(result)
