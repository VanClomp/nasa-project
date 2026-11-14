"""Component 3 (Charakteryzator) contract: POST /characterize, exactly as in ARCHITECTURE_SPEC section 5.

characterize_spec(request_dict) -> response_dict. Pure function, no web framework; app.py (FastAPI) and
server_stdlib.py (no dependencies) both call it.

Response = the spec's fields at top level (target_body, coordinates, features_raw, features_norm, nearest_skylight_km)
plus an "extra" block that the spec does not require but the UI / search can use:
  extra.features_measured   yes/no per feature (true = measured at this place, false = global prediction)
  extra.weights             default importance per feature for this place (0-1)
  extra.season              Mars: Ls, Mars year, Mars month of the timestamp; Moon: local lunar hour, sub-solar / sub-Earth point
  extra.base_suitability    Moon only: 0-100 score for a permanent base and its seven components
  extra.site                known landing site within 10 km, if any
  extra.values / units      every parameter for that date (temperatures, pressure, wind, dust, sunlight, ...)
Missing values are null in features_raw and features_norm; the search should give them zero weight.
"""
import datetime as dt, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts'))
RANGES = json.load(open(os.path.join(HERE, 'norm_ranges.json')))
ORDER = RANGES['order']

class RequestError(ValueError):
    status = 400
class NotImplementedBody(RequestError):
    status = 501

def normalise(raw):
    out = []
    for k in ORDER:
        v = raw.get(k)
        if v is None: out.append(None); continue
        lo, hi = RANGES[k]['min'], RANGES[k]['max']
        out.append(round(min(max((float(v) - lo) / (hi - lo), 0.0), 1.0), 4))
    return out

def characterize_spec(req):
    if not isinstance(req, dict): raise RequestError('request body must be a JSON object')
    body = str(req.get('target_body', '')).lower()
    if body not in ('mars', 'moon'): raise RequestError("target_body must be 'mars' or 'moon'")
    try: lat, lon = float(req['lat']), float(req['lon'])
    except (KeyError, TypeError, ValueError): raise RequestError('lat and lon are required numbers')
    if not -90 <= lat <= 90: raise RequestError('lat must be within -90..90')
    ts = req.get('timestamp_iso') or dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    try: dt.datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except ValueError: raise RequestError('timestamp_iso must be ISO 8601, e.g. 2026-11-14T12:00:00Z')
    import characterize as ch
    if body == 'moon':
        r = ch._moon_point(dict(lat=lat, lon=lon, timestamp_iso=ts), float(req.get('site_radius_km', 10.0)))
        tp = r['target_profile']; raw = {k: tp['features_raw'].get(k) for k in ORDER}
        return dict(
            target_body=body, coordinates=dict(lat=lat, lon=lon), features_raw=raw, features_norm=normalise(raw),
            nearest_skylight_km=tp.get('nearest_skylight_km'),
            extra=dict(timestamp_iso=ts, features_measured=tp['features_measured'], weights=[r['weights'][k] for k in ORDER],
                       season=dict(local_lunar_hour=r['values']['local_lunar_hour'], **r['sky']), site=r['site'],
                       base_suitability=r['base_suitability'], base_weights=r['base_weights'],
                       values=r['values'], measured=r['measured'], units=r['units'], norm_ranges='service/norm_ranges.json'))
    r = ch._mars_point(dict(lat=lat, lon=lon, timestamp_iso=ts), float(req.get('site_radius_km', 10.0)))
    tp = r['target_profile']; raw = {k: tp['features_raw'].get(k) for k in ORDER}
    return dict(
        target_body=body, coordinates=dict(lat=lat, lon=lon), features_raw=raw, features_norm=normalise(raw),
        nearest_skylight_km=tp.get('nearest_skylight_km'),
        extra=dict(timestamp_iso=ts, features_measured=tp['features_measured'], weights=[r['weights'][k] for k in ORDER],
                   season=dict(ls=r['ls'], mars_year=r['mars_year'], mars_month=r['mars_month']), site=r['site'],
                   values=r['values'], measured=r['measured'], units=r['units'], storm_year=r['storm_year'],
                   norm_ranges='service/norm_ranges.json'))
