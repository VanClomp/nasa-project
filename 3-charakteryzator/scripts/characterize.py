#!/usr/bin/env python3
"""Characterize places on Mars or the Moon from a JSON request; writes a JSON response.

Usage
  python3 scripts/characterize.py request.json                 -> prints the response
  python3 scripts/characterize.py request.json -o response.json
  python3 scripts/characterize.py --all-sites -o outputs/mars_sites.json
  python3 scripts/characterize.py --all-sites --body moon -o outputs/moon_sites.json
  from characterize import handle; response = handle(request_dict)   (for the team's API service)

Request (any of these shapes)
  {"target_body": "mars", "lat": 18.44, "lon": 77.45, "timestamp_iso": "2026-11-14T12:00:00Z"}     # spec form
  {"target_body": "mars", "points": [{"id": "jezero", "lat": 18.44, "lon": 77.45},
                                     {"lat": 40.0, "lon": -158.0, "months": [1, 7]}],
   "site_radius_km": 10}
  {"target_body": "mars", "sites": "all"}                         # the twelve known landing/candidate sites
  {"target_body": "moon", "sites": "all", "timestamp_iso": "..."} # 24 lunar sites (Artemis III regions, landings, pits)
  Moon: without a date -> 12 records (15th of each month of the current year); with a date -> one flat record.
  lat: planetocentric degrees north. lon: degrees east, either -180..180 or 0..360.
  timestamp_iso (optional): with a date the answer is SIMPLE: one flat set of values for that date (the Mars month
                 containing it; sun elevation and daylight for the exact date). Add "detail": "full" to get all 12 months.
                 Without a date: all 12 months (or those listed in "months").
"""
import argparse, datetime as dt, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import marslib as m

SCHEMA = '1.0'

def _clean(o):
    if isinstance(o, dict): return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_clean(v) for v in o]
    if isinstance(o, float) and not math.isfinite(o): return None
    if hasattr(o, 'item'): return _clean(o.item())
    return o

def _mars_point(p, radius):
    import mars_model as mm
    lat, lon = float(p['lat']), float(p['lon'])
    if not (-90 <= lat <= 90): raise ValueError(f'latitude {lat} outside -90..90')
    months = [int(k) for k in p.get('months', range(1, 13))]
    if any(k < 1 or k > 12 for k in months): raise ValueError('months must be 1..12')
    r = mm.characterize(lat, lon, months, radius)
    cur = None
    if p.get('timestamp_iso'):
        t = dt.datetime.fromisoformat(p['timestamp_iso'].replace('Z', '+00:00')).replace(tzinfo=None)
        ls = m.ls_from_utc(t); k = int(ls // 30) + 1
        cur = dict(timestamp_iso=p['timestamp_iso'], ls=round(ls, 2), mars_year=m.mars_year_from_days(m.days_j2000(t), ls), month=k,
                   entry=next((x for x in r['months'] if x['month'] == k), None))
    full = dict(input=p, coordinates=dict(lat=lat, lon_east=round(lon % 360, 4)), site=r['site'], current=cur,
                weights=r['weights'], static=r['static'], months=r['months'])
    if cur is None or p.get('detail') == 'full':
        return full
    return _simple(full, t, ls)

def _simple(full, t, ls):
    """Flat answer for one date: every parameter's value, unit and measured flag, for the Mars month containing that date.
    Sun elevation and daylight are computed for the exact date, not the month."""
    import numpy as np, mars_climate as mc, solar
    e = full['current']['entry']; lat = full['coordinates']['lat']
    sol = float(mc.sol_of_ls(ls)); _, _, dec = solar.orbit(sol); dec = float(np.degrees(dec))
    x = -np.tan(np.radians(lat)) * np.tan(np.radians(dec)); h0 = 0.0 if x >= 1 else (np.pi if x <= -1 else float(np.arccos(x)))
    vals, meas, unit = {}, {}, {}
    for src in (full['static'], e['params']):
        for k, v in src.items():
            vals[k] = v['value']; meas[k] = v['measured']; unit[k] = v['unit']
    vals['solar_elevation_max'] = round(max(0.0, 90 - abs(lat - dec)), 1); meas['solar_elevation_max'] = True
    vals['daylight_hours'] = round(h0 / np.pi * 24.66, 1); meas['daylight_hours'] = True
    tp = dict(e['target_profile']); tp['features_raw'] = dict(tp['features_raw'], solar_elevation_max=vals['solar_elevation_max'])
    return dict(id=full['input'].get('id'), date=full['current']['timestamp_iso'], lat=lat, lon_east=full['coordinates']['lon_east'],
                ls=full['current']['ls'], mars_year=full['current']['mars_year'], mars_month=e['month'],
                site=full['site']['id'] if full['site'] else None,
                values=vals, measured=meas, units=unit,
                storm_year={k: v['value'] for k, v in e['storm_year'].items()},
                target_profile=tp, weights=full['weights']['values'])


def _moon_point(p, radius):
    import moon_model as mo
    lat, lon = float(p['lat']), float(p['lon'])
    if not (-90 <= lat <= 90): raise ValueError(f'latitude {lat} outside -90..90')
    lon = ((lon + 180) % 360) - 180
    if p.get('timestamp_iso'):
        t = dt.datetime.fromisoformat(p['timestamp_iso'].replace('Z', '+00:00')).replace(tzinfo=None); dates = [(None, t)]
    else:
        t = None; dates = mo.months_of_year(int(p.get('year') or dt.datetime.utcnow().year))
        if 'months' in p: dates = [d for d in dates if d[0] in [int(k) for k in p['months']]]
    st = mo.point_static(lat, lon); ns = mo.nearest_site(lat, lon, radius)
    site = None if not ns else dict(id=ns[0]['id'], name=ns[0]['name'], kind=ns[0]['kind'], distance_km=round(ns[1], 2), coord_quality=ns[0]['coord_quality'])
    recs = []; therm = mo.thermal_batch(lat, [d for _, d in dates])
    for (k, d), th in zip(dates, therm):
        tp, sky = mo.point_time(lat, lon, d, st, th); score, comp = mo.base_score(st, tp)
        recs.append(dict(month=k, date=d.isoformat() + 'Z', params=tp, base_suitability=dict(score=score, components=comp),
                         target_profile=mo.target_profile(st, tp),
                         sky=dict(sub_solar_lat=sky['sub_solar_lat'], sub_earth_lat=sky['sub_earth_lat'], sub_earth_lon=sky['sub_earth_lon'])))
    weights = dict(values=mo.FEATURE_WEIGHTS, base_weights=mo.BASE_WEIGHTS,
                   rationale='feature weights: importance of each spec feature when matching Earth analogs for a Moon base; '
                             'base weights: importance of each component in the base-suitability score (power, water, communication, '
                             'terrain, thermal, ISRU oxygen, shelter)')
    if t is not None and p.get('detail') != 'full':
        e = recs[0]; vals, meas, unit = {}, {}, {}
        for src in (st, e['params']):
            for kk, v in src.items(): vals[kk] = v['value']; meas[kk] = v['measured']; unit[kk] = v['unit']
        return dict(id=p.get('id'), date=p['timestamp_iso'], lat=lat, lon=lon, site=site['id'] if site else None,
                    sky=e['sky'],
                    values=vals, measured=meas, units=unit, base_suitability=e['base_suitability'],
                    target_profile=e['target_profile'], weights=weights['values'], base_weights=weights['base_weights'])
    return dict(input=p, coordinates=dict(lat=lat, lon=lon), site=site, weights=weights, static=st, months=recs)

BODIES = {'mars': _mars_point, 'moon': _moon_point}

MARS_CONVENTIONS = dict(
            date_mode='with timestamp_iso: one flat record per point for that date (values / measured / units); without: 12 Mars months',
            month='Mars month k = solar longitude Ls 30(k-1) to 30k; Ls 0 = northern spring equinox; months differ in length (sols given)',
            longitude='degrees east, 0-360', latitude='planetocentric degrees north',
            parameter='{value, low, high, unit, measured, source}',
            measured='true = data taken at this place (lander/rover record, orbital map read at this point, or exact orbital geometry); '
                     'false = global predictor from latitude, elevation and surface properties; value null = no data and no defensible prediction',
            low_high='measured: 10th-90th percentile of daily values in the month; predicted: validated model error band',
            storm_year='same month in a global dust storm year (TES, 2001)',
            target_profile='team spec Component 3 features in spec order with spec units; features_measured holds the yes/no per feature. '
                           'Normalisation to [0,1] is left to the Earth search, which owns the Earth min/max ranges.',
            validation='outputs/thermal_model_validation.csv, outputs/air_model_validation.csv, outputs/pressure_model_validation.csv, outputs/dust_validation.csv')
MOON_CONVENTIONS = dict(
    date_mode='with timestamp_iso: one flat record per point for that date; without: 12 records (15th of each month)',
    longitude='degrees east, -180..180', latitude='selenographic degrees north',
    parameter='{value, low, high, unit, measured, source}',
    measured='true = orbital map read at this point (LOLA, Diviner, Lunar Prospector, LROC) or exact ephemeris; '
             'false = model prediction (regolith heat model, thermal inertia from rock abundance, polar night estimate); null = no data',
    base_suitability='0-100, weighted mean of power, water, communication, terrain, thermal, ISRU oxygen and shelter scores (each 0-1); '
                     'priority: a permanent base, not only a landing',
    sunlight='sun/earth visibility fractions are 18.6-year averages including terrain shadows (LOLA, poleward of 65 deg); '
             'elsewhere flat horizon (sun 50%)',
    target_profile='team spec Component 3 features with spec units (temp_mean in deg C); dust_aerosol and radiation_proxy are 0 '
                   '(no atmosphere: column mass 0 g/cm2); soil_moisture null (no defensible orbital value)')

def handle(req):
    body = str(req.get('target_body', 'mars')).lower()
    radius = float(req.get('site_radius_km', 10.0))
    if req.get('sites') == 'all':
        if body == 'moon':
            import moon_model as mo; points = mo.site_points()
        else:
            points = [dict(id=s['id'], lat=s['lat'], lon=s['lon']) for s in m.SITES]
        for q in points:
            for k in ('timestamp_iso', 'months', 'detail'):
                if k in req: q[k] = req[k]
    elif 'points' in req:
        points = req['points']
    else:
        points = [{k: req[k] for k in ('id', 'lat', 'lon', 'timestamp_iso', 'months', 'detail') if k in req}]
    results = []
    for p in points:
        if body not in BODIES:
            results.append(dict(input=p, error=f"target_body '{body}' is not implemented yet (available: {', '.join(BODIES)})")); continue
        try: results.append(BODIES[body](p, radius))
        except Exception as e: results.append(dict(input=p, error=f'{type(e).__name__}: {e}'))
    conv = MOON_CONVENTIONS if body == 'moon' else MARS_CONVENTIONS
    return _clean(dict(
        schema_version=SCHEMA, target_body=body, generated_utc=dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
        conventions=conv,
        results=results))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('request', nargs='?'); ap.add_argument('-o', '--out'); ap.add_argument('--all-sites', action='store_true'); ap.add_argument('--body', default='mars')
    a = ap.parse_args()
    if a.all_sites: req = dict(target_body=a.body, sites='all')
    elif a.request: req = json.load(open(a.request))
    else: req = json.load(sys.stdin)
    txt = json.dumps(handle(req), indent=1, allow_nan=False)
    if a.out: open(a.out, 'w').write(txt); print(f'wrote {a.out} ({len(txt) // 1024} KB)', file=sys.stderr)
    else: print(txt)

if __name__ == '__main__':
    main()
