"""FastAPI service for Component 3 (port 8001), per ARCHITECTURE_SPEC.
Run:  uvicorn service.app:app --host 0.0.0.0 --port 8001      (from the component folder)
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from .contract import characterize_spec, RequestError

app = FastAPI(title='Charakteryzator', version='1.0')

class CharacterizeRequest(BaseModel):
    target_body: str = Field(..., examples=['mars'])
    lat: float = Field(..., ge=-90, le=90)
    lon: float
    timestamp_iso: Optional[str] = Field(None, examples=['2026-11-14T12:00:00Z'])

@app.get('/health')
def health():
    return {'status': 'ok', 'bodies': {'mars': 'ready', 'moon': 'in preparation'}}

@app.post('/characterize')
def characterize(req: CharacterizeRequest):
    try:
        return JSONResponse(characterize_spec(req.model_dump()))
    except RequestError as e:
        raise HTTPException(status_code=e.status, detail=str(e))
