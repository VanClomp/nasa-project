"""Serwis HTTP Szukacza (FastAPI, port wewnętrzny 8002).

Uruchomienie z katalogu 4-szukacz:
    uvicorn szukacz.api:app --host 0.0.0.0 --port 8002

Zmienne środowiskowe:
    SZUKACZ_DATA_DIR         katalog z danymi Ziemi (domyślnie /data/earth)
    SZUKACZ_MIN_DISTANCE_KM  odległość używana, gdy zapytanie nie poda min_distance_km (100)
    SZUKACZ_CAVE_MAX_KM      próg filtra require_caves w km (15)
    SZUKACZ_THREADS          liczba wątków liczących (domyślnie liczba rdzeni, najwyżej 16)
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .data import load_earth_data
from .engine import DEFAULT_CAVE_MAX_KM, DEFAULT_MIN_DISTANCE_KM, DEFAULT_TOP_K, search

MAX_TOP_K = 1000


class SearchRequest(BaseModel):
    features_norm: list[float]
    weights: list[float]
    require_caves: bool = False
    top_k: int = Field(DEFAULT_TOP_K, ge=1, le=MAX_TOP_K)
    # Brak pola oznacza wartość z SZUKACZ_MIN_DISTANCE_KM; 0 wyłącza odsiewanie.
    min_distance_km: float | None = Field(None, ge=0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.earth = load_earth_data(os.environ.get("SZUKACZ_DATA_DIR", "/data/earth"))
    app.state.min_distance_km = float(
        os.environ.get("SZUKACZ_MIN_DISTANCE_KM", DEFAULT_MIN_DISTANCE_KM)
    )
    app.state.cave_max_km = float(os.environ.get("SZUKACZ_CAVE_MAX_KM", DEFAULT_CAVE_MAX_KM))
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
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    # JSONResponse wprost: wynik to już typy JSON, pomijamy drugą walidację FastAPI.
    return JSONResponse(result)
