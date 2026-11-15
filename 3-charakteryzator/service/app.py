"""FastAPI service for Component 3 (port 8001), per ARCHITECTURE_SPEC.
Run:  uvicorn service.app:app --host 0.0.0.0 --port 8001      (from the component folder)
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from .contract import characterize_spec, RequestError

@asynccontextmanager
async def lifespan(app):
    # Warm-up: compiles the numba heat solvers (Mars ground, Moon regolith) before the first request.
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
        import mars_climate, moon_thermal
        mars_climate.ground_temps(0.0, [90.0], 0.2, 250.0, [700.0], [0.5], n_sols=1, steps=48)
        moon_thermal.surface_temps([0.0], days=1, steps=600)
        # ...and loads the map caches (both lunar polar products, Mars maps) so the first click is fast too.
        for body, lat, lon in (('moon', -85.9, -3.4), ('moon', 85.0, 0.0), ('moon', 0.7, 23.5), ('mars', 18.4, 77.5)):
            characterize_spec(dict(target_body=body, lat=lat, lon=lon, timestamp_iso='2027-01-01T12:00:00Z'))
    except Exception as e:                                # never block start-up on the warm-up
        print('warm-up skipped:', e)
    yield

app = FastAPI(title='Charakteryzator', version='1.0', lifespan=lifespan)

class CharacterizeRequest(BaseModel):
    target_body: str = Field(..., examples=['mars'])
    lat: float = Field(..., ge=-90, le=90)
    lon: float
    timestamp_iso: Optional[str] = Field(None, examples=['2026-11-14T12:00:00Z'])
    series: bool = False          # also return extra.series: 12-month p(t) for the time-varying features

@app.get('/health')
def health():
    return {'status': 'ok', 'bodies': {'mars': 'ready', 'moon': 'ready'}}

@app.post('/characterize')
def characterize(req: CharacterizeRequest):
    try:
        return JSONResponse(characterize_spec(req.model_dump()))
    except RequestError as e:
        raise HTTPException(status_code=e.status, detail=str(e))
