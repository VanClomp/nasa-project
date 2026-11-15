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
  extra.model               Mars: "local" = this date's surface weather comes from that site's station records
                            (Viking 1/2, Pathfinder, Phoenix, Curiosity, InSight, Perseverance); "global" = the global
                            predictor (latitude + elevation + orbital maps), less certain.
                            Moon: "orbital" = no surface stations, but most values are measured from orbit at this
                            pixel (LOLA, Diviner, Lunar Prospector); temperatures for a date come from the regolith
                            model. extra.model_basis says why in one sentence.
  extra.features_measured   per feature: true = measured at this place (station record, orbital map pixel, exact
                            geometry); false = predicted by the global model
  extra.features_time_varying per feature: true = the value depends on the date (season, Sun position, dust season);
                            false = fixed property of the place. See PARAMETERS.md.
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

# Parameters that only surface station records can measure; the global model always predicts them (measured=false).
STATION_PARAMS = ('air_temp_min', 'air_temp_max', 'air_temp_mean', 'ground_temp_min', 'ground_temp_max',
                  'ground_temp_mean', 'pressure', 'wind_mean')

def model_source(body, site, measured):
    """('local' | 'global', one-sentence reason). Local only when station data actually backs this date, so a known
    site without a weather station (Spirit, Opportunity, Zhurong, Oxia, Arcadia) or a station month with no records
    (e.g. Phoenix outside its 5 months) is still 'global'."""
    if body == 'moon':
        return 'orbital', ('Moon: no surface weather stations; terrain, sunlight, rocks and hydrogen measured from orbit '
                           'at this pixel (LOLA, Diviner, Lunar Prospector); temperatures for the date from the regolith model')
    if isinstance(site, str):                       # Mars dated answers carry only the site id
        import marslib
        site = next((s for s in marslib.SITES if s['id'] == site), {'id': site, 'name': site})
    n = sum(1 for k in STATION_PARAMS if measured.get(k))
    if site and n:
        return 'local', f"station records of {site.get('mission') or site['name']} ({n} surface parameter{'s' if n != 1 else ''} measured for this month)"
    if site:
        return 'global', f"known site {site['name']} but no station records for this month: global model"
    return 'global', 'no station within 10 km: global model (latitude + elevation + orbital maps)'

# Which spec features change with the date (checked by running the same points on dates months apart).
# Mars: temperatures, dust season, noon Sun and the seasonal pressure cycle (column mass); terrain, thermal inertia
# and the GRS water map are fixed. Moon: temperatures and the Sun; no atmosphere (dust 0, column mass 0) and fixed
# terrain/regolith. Exception: polar Moon temp_mean is Diviner's annual mean (measured) and therefore fixed.
TIME_VARYING = {
    'mars': dict(temp_mean=True, temp_diurnal_amp=True, thermal_inertia=False, surface_roughness=False,
                 soil_moisture=False, dust_aerosol=True, solar_elevation_max=True, radiation_proxy=True, slope_deg=False),
    'moon': dict(temp_mean=True, temp_diurnal_amp=True, thermal_inertia=False, surface_roughness=False,
                 soil_moisture=False, dust_aerosol=False, solar_elevation_max=True, radiation_proxy=False, slope_deg=False),
}

def time_varying(body, measured):
    tv = [TIME_VARYING[body][k] for k in ORDER]
    if body == 'moon' and measured and measured[0]:
        tv[0] = False                                   # polar Diviner annual-mean temperature
    return tv

def _series(body, records, labels, current, measured, axis):
    """p(t) for the features that change with time: 12 values per feature (raw units), one per month."""
    tv = time_varying(body, measured)
    keys = [k for k, v in zip(ORDER, tv) if v]
    vals = {k: [None if r.get(k) is None else round(float(r[k]), 3) for r in records] for k in keys}
    units = {k: RANGES[k]['unit'] for k in keys}
    return dict(axis=axis, labels=labels, current_index=current, values=vals, units=units)

MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

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
        model, basis = model_source(body, r['site'], r['measured'])
        out = dict(
            target_body=body, coordinates=dict(lat=lat, lon=lon), features_raw=raw, features_norm=normalise(raw),
            nearest_skylight_km=tp.get('nearest_skylight_km'),
            extra=dict(timestamp_iso=ts, model=model, model_basis=basis,
                       features_measured=tp['features_measured'],
                       features_time_varying=time_varying(body, tp['features_measured']), weights=[r['weights'][k] for k in ORDER],
                       season=dict(local_lunar_hour=r['values']['local_lunar_hour'], **r['sky']), site=r['site'],
                       base_suitability=r['base_suitability'], base_weights=r['base_weights'],
                       values=r['values'], measured=r['measured'], units=r['units'], norm_ranges='service/norm_ranges.json'))
        if req.get('series'):
            t = dt.datetime.fromisoformat(ts.replace('Z', '+00:00'))
            full = ch._moon_point(dict(lat=lat, lon=lon, year=t.year), float(req.get('site_radius_km', 10.0)))
            recs = [m['target_profile']['features_raw'] for m in full['months']]
            out['extra']['series'] = _series(body, recs, [f'{MONTHS[m["month"] - 1]} {t.year}' for m in full['months']],
                                             t.month - 1, tp['features_measured'], 'calendar_month_15th')
        return out
    full = None
    if req.get('series'):
        full = ch._mars_point(dict(lat=lat, lon=lon, timestamp_iso=ts, detail='full'), float(req.get('site_radius_km', 10.0)))
        t = dt.datetime.fromisoformat(ts.replace('Z', '+00:00')).replace(tzinfo=None)
        r = ch._simple(full, t, full['current']['ls'])
    else:
        r = ch._mars_point(dict(lat=lat, lon=lon, timestamp_iso=ts), float(req.get('site_radius_km', 10.0)))
    tp = r['target_profile']; raw = {k: tp['features_raw'].get(k) for k in ORDER}
    model, basis = model_source(body, r['site'], r['measured'])
    out = dict(
        target_body=body, coordinates=dict(lat=lat, lon=lon), features_raw=raw, features_norm=normalise(raw),
        nearest_skylight_km=tp.get('nearest_skylight_km'),
        extra=dict(timestamp_iso=ts, model=model, model_basis=basis,
                   features_measured=tp['features_measured'],
                   features_time_varying=time_varying(body, tp['features_measured']), weights=[r['weights'][k] for k in ORDER],
                   season=dict(ls=r['ls'], mars_year=r['mars_year'], mars_month=r['mars_month']), site=r['site'],
                   values=r['values'], measured=r['measured'], units=r['units'], storm_year=r['storm_year'],
                   norm_ranges='service/norm_ranges.json'))
    if full is not None:
        recs = [m['target_profile']['features_raw'] for m in full['months']]
        starts = _mars_month_starts(t)
        labels = [f"{MONTHS[d.month - 1]} {d.year}" for d in starts]
        out['extra']['series'] = _series(body, recs, labels, full['current']['month'] - 1, tp['features_measured'],
                                         'mars_month')
        out['extra']['series']['detail_labels'] = [
            f"Mars month {m['month']} (Ls {int(m['ls_start'])}–{int(m['ls_end'])}°), from {d.isoformat()}"
            for m, d in zip(full['months'], starts)]
    return out


def _mars_month_starts(t):
    """Earth date on which each of the 12 Mars months (Ls 0-30, 30-60, ...) begins, within the Mars year that
    contains date t; daily search with marslib.ls_from_utc (Mars months last 46-67 Earth days)."""
    import marslib as m
    day = dt.timedelta(days=1)
    d = dt.datetime(t.year, t.month, t.day, 12)
    ls_prev = m.ls_from_utc(d)
    while True:                                           # walk back to the start of this Mars year (Ls wraps 360 -> 0)
        ls = m.ls_from_utc(d - day)
        if ls > ls_prev + 180: break
        d -= day; ls_prev = ls
    starts, k = [d.date()], 1
    while k < 12:
        d += day
        if m.ls_from_utc(d) >= 30 * k: starts.append(d.date()); k += 1
    return starts
