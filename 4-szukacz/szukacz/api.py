"""Szukacz HTTP service (FastAPI, internal port 8002).

Run from the 4-szukacz folder:
    uvicorn szukacz.api:app --host 0.0.0.0 --port 8002

Environment variables:
    SZUKACZ_DATA_DIR         folder with the Earth data (default /data/earth)
    SZUKACZ_MIN_DISTANCE_KM  distance used when the request gives no min_distance_km (100)
    SZUKACZ_CAVE_MAX_KM      require_caves filter threshold in km (15)
    SZUKACZ_ERROR_SCALE_MAX  error at which the error-map colour scale ends (0.5)
    SZUKACZ_THREADS          number of worker threads (default: number of cores, at most 16)
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .data import load_earth_data
from .scoring import score_all
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
    # A missing field means the SZUKACZ_MIN_DISTANCE_KM value; 0 turns the filtering off.
    min_distance_km: float | None = Field(None, ge=0)
    # False skips the heatmap and error-map images (both returned as null): faster and ~375 kB smaller.
    include_maps: bool = True


class ErrorMapRequest(BaseModel):
    features_norm: list[float]
    weights: list[float]
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(DEFAULT_DETAIL_RADIUS_KM, ge=MIN_DETAIL_RADIUS_KM, le=MAX_DETAIL_RADIUS_KM)
    size_px: int = Field(DEFAULT_DETAIL_SIZE_PX, ge=MIN_DETAIL_SIZE_PX, le=MAX_DETAIL_SIZE_PX)


def _default_data_dir() -> str:
    """SZUKACZ_DATA_DIR if set; otherwise /data/earth_real (the real Earth data, git-ignored so that git operations
    on the server cannot replace it) when it exists, else /data/earth (the small mock tracked in git)."""
    if os.environ.get("SZUKACZ_DATA_DIR"):
        return os.environ["SZUKACZ_DATA_DIR"]
    real = Path("/data/earth_real")
    return str(real) if (real / "earth_features_norm.npy").exists() else "/data/earth"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.earth = load_earth_data(_default_data_dir())
    # Warm-up: compiles the scoring kernel and reads the matrix into the page cache before the first request.
    earth = app.state.earth
    score_all(earth.features_norm, np.zeros(earth.n_features, np.float32), np.ones(earth.n_features, np.float32))
    app.state.min_distance_km = float(
        os.environ.get("SZUKACZ_MIN_DISTANCE_KM", DEFAULT_MIN_DISTANCE_KM)
    )
    app.state.cave_max_km = float(os.environ.get("SZUKACZ_CAVE_MAX_KM", DEFAULT_CAVE_MAX_KM))
    app.state.error_scale_max = float(
        os.environ.get("SZUKACZ_ERROR_SCALE_MAX", DEFAULT_ERROR_SCALE_MAX)
    )
    if not app.state.error_scale_max > 0:
        raise ValueError("SZUKACZ_ERROR_SCALE_MAX: expected a number > 0")
    yield


app = FastAPI(title="Szukacz", lifespan=lifespan)


@app.get("/health")
def health(request: Request) -> dict:
    earth = request.app.state.earth
    return {"status": "ok", "n_points": earth.n_points, "n_features": earth.n_features}


# A plain (non-async) function: FastAPI runs it in a thread pool, so the long
# computation does not block the event loop.
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
            include_maps=body.include_maps,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    # JSONResponse directly: the result is already JSON types, skipping FastAPI's second validation.
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
