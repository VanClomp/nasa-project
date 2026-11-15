"""Reads the precomputed 3-charakteryzator tables (outputs/mars_sites.json and moon_sites.json).

When the raw binary PDS maps (.img, ~3.1 GB) have not been downloaded to `/data/mars` or
`/data/moon`, the `3-charakteryzator` container raises FileNotFoundError.
In that case `2-networker` uses the profiles that `3-charakteryzator` precomputed
in `3-charakteryzator/outputs/mars_sites.json` and
`3-charakteryzator/outputs/moon_sites.json`, with the normalisation ranges from
`3-charakteryzator/service/norm_ranges.json`.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_OUTPUTS_DIR = Path(
    os.environ.get("CHARAKTERYZATOR_OUTPUTS_DIR", "/charakteryzator/outputs")
)
DEFAULT_NORM_RANGES_PATH = Path(
    os.environ.get("CHARAKTERYZATOR_NORM_RANGES", "/charakteryzator/service/norm_ranges.json")
)


def _great_circle_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(((lon2 - lon1 + 180.0) % 360.0) - 180.0)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return math.degrees(2.0 * math.asin(min(1.0, math.sqrt(a))))


@lru_cache(maxsize=1)
def _load_norm_ranges() -> dict[str, Any]:
    for candidate in (
        DEFAULT_NORM_RANGES_PATH,
        Path(__file__).resolve().parents[2] / "3-charakteryzator" / "service" / "norm_ranges.json",
    ):
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    raise FileNotFoundError("norm_ranges.json from 3-charakteryzator not found")


@lru_cache(maxsize=2)
def _load_sites_file(body: str) -> list[dict[str, Any]]:
    filename = "mars_sites.json" if body == "mars" else "moon_sites.json"
    for candidate in (
        DEFAULT_OUTPUTS_DIR / filename,
        Path(__file__).resolve().parents[2] / "3-charakteryzator" / "outputs" / filename,
    ):
        if candidate.exists():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            return data.get("results", [])
    raise FileNotFoundError(f"{filename} not found in the 3-charakteryzator outputs")


def _normalise_from_ranges(raw: dict[str, Any], ranges: dict[str, Any]) -> list[float]:
    order: list[str] = ranges["order"]
    out: list[float] = []
    for key in order:
        val = raw.get(key)
        if val is None:
            out.append(0.0)
            continue
        lo = float(ranges[key]["min"])
        hi = float(ranges[key]["max"])
        norm_val = (float(val) - lo) / (hi - lo) if hi > lo else 0.0
        out.append(round(min(max(norm_val, 0.0), 1.0), 4))
    return out


def _month_from_iso(timestamp_iso: str | None) -> int:
    if not timestamp_iso:
        return 11
    try:
        dt = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
        return max(1, min(12, dt.month))
    except Exception:
        return 11


def characterize_from_precomputed_outputs(
    target_body: str,
    lat: float,
    lon: float,
    timestamp_iso: str | None = None,
) -> dict[str, Any]:
    """Returns a profile from the precomputed 3-charakteryzator data (outputs/*_sites.json)."""
    body = target_body.lower().strip()
    if body not in ("mars", "moon"):
        raise ValueError("target_body must be 'mars' or 'moon'")

    sites = _load_sites_file(body)
    ranges = _load_norm_ranges()
    order: list[str] = ranges["order"]
    month_idx = _month_from_iso(timestamp_iso)

    # Find the nearest site in the precomputed 3-charakteryzator results
    best_site = min(
        sites,
        key=lambda s: _great_circle_deg(
            lat,
            lon,
            float(s["coordinates"]["lat"]),
            float(s["coordinates"].get("lon", s["coordinates"].get("lon_east", 0.0))),
        ),
    )

    months_list = best_site.get("months", [])
    month_entry = next(
        (m for m in months_list if int(m.get("month", 1)) == month_idx),
        months_list[0],
    )
    tp = month_entry["target_profile"]
    raw_in = tp["features_raw"]

    # Missing values stay null (UI: "no data"); extra.null_features lists them so the search gives them weight 0.
    null_features = [k for k in order if raw_in.get(k) is None]
    raw_clean: dict[str, float | None] = {k: None if raw_in.get(k) is None else float(raw_in[k]) for k in order}

    skylight = tp.get("nearest_skylight_km")
    return {
        "target_body": body,
        "coordinates": {"lat": round(lat, 2), "lon": round(lon, 2)},
        "features_raw": raw_clean,
        "features_norm": _normalise_from_ranges(raw_in, ranges),
        "nearest_skylight_km": None if skylight is None else float(skylight),
        "extra": {
            # Fallback = values of the NEAREST known site, not the clicked point: always "global"
            # (uncertain), even if that site has station data. Matches extra.model from 3-charakteryzator.
            "model": "global",
            "model_basis": "characterizer unavailable: values of the nearest precomputed site, not this point",
            "matched_site": best_site.get("site"),
            "month": month_idx,
            "features_measured": [False] * len(order),
            "features_source": ["none" if k in null_features else "global" for k in order],
            "features_detail": ["nearest precomputed site, not this point"] * len(order),
            "null_features": null_features,
        },
    }
