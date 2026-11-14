"""Base-suitability characterization of any point on the Moon, for a given date.

Parameters follow the Mars schema {value, low, high, unit, measured, source}; measured = true for values read from
orbital maps at that point or from exact geometry, false for model predictions.
Base-suitability score (0-100) = weighted mean of seven component scores; weights in BASE_WEIGHTS (adjustable).
"""
import datetime as dt, math, numpy as np
import moon_maps as mm, moon_geometry as mg, moon_thermal as mt, moon_sites as ms

def P(value, unit, measured, source, low=None, high=None, nd=2):
    r = lambda x: None if x is None or (isinstance(x, float) and not math.isfinite(x)) else (round(float(x), nd) if isinstance(x, (int, float, np.floating, np.integer)) and not isinstance(x, bool) else x)
    return dict(value=r(value), low=r(low), high=r(high), unit=unit, measured=bool(measured), source=source)

SPEC = ['temp_mean', 'temp_diurnal_amp', 'thermal_inertia', 'surface_roughness', 'soil_moisture', 'dust_aerosol',
        'solar_elevation_max', 'radiation_proxy', 'slope_deg']
BASE_WEIGHTS = dict(power=0.25, water=0.20, communication=0.15, terrain=0.15, thermal=0.10, isru_oxygen=0.10, shelter=0.05)
FEATURE_WEIGHTS = dict(temp_mean=0.9, temp_diurnal_amp=0.8, thermal_inertia=0.6, surface_roughness=0.6, soil_moisture=0.0,
                       dust_aerosol=0.1, solar_elevation_max=1.0, radiation_proxy=0.2, slope_deg=0.8)

# ------------------------------------------------------------------ Earth visibility away from the polar maps
_LIB = None
def earth_fraction_flat(lat, lon):
    """Share of time the Earth's centre is above a flat horizon, from libration sampled every 6 h over 18.6 years."""
    global _LIB
    if _LIB is None:
        t0 = dt.datetime(2020, 1, 1); _LIB = np.array([[s['sub_earth_lat'], s['sub_earth_lon']] for s in
                (mg.subpoints(t0 + dt.timedelta(hours=6 * i)) for i in range(4 * 365 * 19))])
    p, q = np.radians(lat), np.radians(_LIB[:, 0])
    el = np.sin(p) * np.sin(q) + np.cos(p) * np.cos(q) * np.cos(np.radians(lon - _LIB[:, 1]))
    return float((el > 0).mean())

# ------------------------------------------------------------------ static description of a point
def point_static(lat, lon):
    t = mm.terrain(lat, lon); dv = mm.diviner_polar(lat, lon)
    sun, sun1, sres = mm.illumination(lat, lon); ear, ear1, _ = mm.illumination(lat, lon, earth=True)
    flat = sun is None
    if flat:
        sun, sun_src = 0.5, 'flat horizon: half of the time (14.8-day day / 14.8-day night)'
        ear = earth_fraction_flat(lat, lon); ear_src = 'flat horizon, libration over 18.6 years'
    else:
        sun_src = f'LOLA average illumination over 18.6 years, {sres} m pixel (Mazarico et al. 2011)'; ear_src = sun_src.replace('illumination', 'Earth visibility')
    ra = mm.rock_abundance(lat, lon); el = mm.elements(lat, lon); hi = mm.hydrogen_index(lat, lon)
    pit = mm.nearest_pit(lat, lon); ct = mm.nearest_cold_trap_km(lat, lon); ice_km = mm.nearest_ice_km(lat, lon)
    ti_reg = 55.0                                     # rock-free regolith near 250 K (Hayne et al. 2017 profile, top layer)
    ti = ti_reg if ra is None else (1 - ra) * ti_reg + ra * 2200.0
    st = dict(
        elevation=P(t['elevation_m'], 'm above 1737.4 km sphere', True, f"LOLA {t['dem']}", nd=0),
        slope_deg=P(t['slope_deg'], 'deg', True, f"LOLA DEM, over {t['slope_baseline_m']} m baseline"),
        surface_roughness=P(t['relief_13km_m'], 'm', True, 'LOLA, local relief: std of detrended elevation over ~13 km (same definition as Mars)', nd=1),
        lola_roughness=P(t['lola_roughness_m'], 'm', t['lola_roughness_m'] is not None, 'LOLA roughness product (small scale), where LOLA has data'),
        sun_visibility_fraction=P(sun, 'fraction of time sunlit', True, sun_src, nd=3),
        sun_visibility_best_within_1km=P(sun1, 'fraction', sun1 is not None, 'best pixel within 1 km (where a mast or panel could stand)', nd=3),
        earth_visibility_fraction=P(ear, 'fraction of time Earth visible', True, ear_src, nd=3),
        earth_visibility_best_within_1km=P(ear1, 'fraction', ear1 is not None, 'best pixel within 1 km', nd=3),
        nearest_cold_trap_km=P(ct, 'km', ct is not None, 'nearest permanently shadowed pixel within 15 km (LOLA illumination)' if ct is not None or not flat else 'outside the polar maps'),
        ice_depth=P(None if not dv else dv['ice_depth_m'], 'm (depth below which water ice is stable)', bool(dv),
                    'Diviner polar resource product' + (' (-1 code read as surface-stable)' if dv else ': outside 76-90 deg')),
        ice_within_1m_fraction=P(None if not dv else dv['ice_within_1m_fraction'], 'share of ground', bool(dv), 'Diviner polar resource product, 1.5 km neighbourhood'),
        nearest_ice_stable_ground_km=P(ice_km, 'km', ice_km is not None, 'nearest 500 m cell with ice stable within 1 m in half its area (Diviner), within 15 km'),
        annual_mean_temperature=P(None if not dv else dv['temp_avg_K'], 'K (2 cm depth)', bool(dv), 'Diviner polar resource product'),
        annual_max_temperature=P(None if not dv else dv['temp_max_K'], 'K', bool(dv), 'Diviner polar resource product'),
        hydrogen_index=P(hi, '0 = typical dry regolith; ~0.03-0.05 = polar enhancement', hi is not None, 'Lunar Prospector epithermal neutrons, 2 deg', nd=4),
        rock_abundance=P(ra, 'areal fraction', ra is not None, 'Diviner rock abundance (Bandfield et al. 2011), 60S-60N', nd=4),
        thermal_inertia=P(ti, 'J m-2 K-1 s-1/2', False, 'regolith 55 (Hayne et al. 2017) blended with rock 2200 by Diviner rock abundance' + ('' if ra is not None else ' (no rock data: regolith only)'), nd=0),
        feo_wt_pct=P(el.get('feo_wt_pct'), 'wt%', bool(el), 'Lunar Prospector GRS, 5 deg bins', nd=1),
        tio2_wt_pct=P(el.get('tio2_wt_pct'), 'wt% (ilmenite indicator)', bool(el), 'Lunar Prospector GRS, 5 deg bins'),
        nearest_skylight_km=P(pit[0], 'km', True, f'LROC Lunar Pit Atlas: {pit[1]} ({pit[2]} pit)', nd=1),
        gravity=P(1.625, 'm s-2', True, 'constant (0.17 g)', nd=3),
        atmosphere=P(0.0, 'g/cm2 overhead', True, 'vacuum: no shielding, no weather, no dust storms'),
    )
    return st

# ------------------------------------------------------------------ time-dependent part
def thermal_batch(lat, times):
    """Flat-ground temperature cycle for several dates at once (one model column per date)."""
    skies = [mg.at(lat, 0.0, t) for t in times]
    lo, hi, mean, hrs = mt.surface_temps([lat] * len(times), sub_solar_lat=[s['sub_solar_lat'] for s in skies],
                                         flux=[s['solar_flux_toa_wm2'] for s in skies], days=4, steps=6000)   # 6000: stability limit of the 2 mm top layer
    return [(float(lo[i]), float(hi[i]), float(mean[i]), hrs[i]) for i in range(len(times))]

def point_time(lat, lon, t, st, therm=None):
    sky = mg.at(lat, lon, t)
    lo, hi, mean, hrs = therm or thermal_batch(lat, [t])[0]
    now = float(np.interp(sky['local_lunar_hour'], np.arange(24), hrs, period=24))
    polar = st['annual_mean_temperature']['value'] is not None
    src = 'regolith heat model (Hayne et al. 2017 parameters), flat ground' + ('; real polar terrain is set by shadows, see Diviner values' if abs(lat) > 75 else '')
    p = dict(
        sun_elevation=P(sky['sun_elevation_deg'], 'deg', True, 'ephemeris, flat horizon'),
        earth_elevation=P(sky['earth_elevation_deg'], 'deg', True, 'ephemeris, flat horizon'),
        local_lunar_hour=P(sky['local_lunar_hour'], 'h (12 = noon)', True, 'ephemeris'),
        sunlit_now_flat_horizon=P(sky['sunlit_flat_horizon'], 'bool', True, 'ephemeris, flat horizon'),
        solar_elevation_max=P(sky['noon_sun_elevation_deg'], 'deg', True, 'noon sun on this date, flat horizon'),
        solar_flux=P(sky['solar_flux_toa_wm2'], 'W/m2', True, 'Sun distance on this date'),
        surface_temp_now=P(now, 'K', False, src, now - 10, now + 10, 1),
        surface_temp_min=P(lo, 'K', False, src, lo - 6, lo + 6, 1),
        surface_temp_max=P(hi, 'K', False, src, hi - 6, hi + 6, 1),
        surface_temp_mean=P(mean, 'K', False, src, nd=1),
    )
    if polar:   # measured annual values take over; the flat model is not valid among polar shadows
        tavg, tmax = st['annual_mean_temperature']['value'], st['annual_max_temperature']['value']
        tmin = max(25.0, min(lo, tavg))       # nights at the poles: no colder than the flat model, not warmer than the annual mean
        p['surface_temp_mean'] = P(tavg, 'K', True, 'Diviner annual mean (2 cm depth)', nd=1)
        p['surface_temp_max'] = P(tmax, 'K', True, 'Diviner annual maximum', nd=1)
        p['surface_temp_min'] = P(tmin, 'K', False, 'min(flat model night, Diviner annual mean)', tmin - 15, tmin + 10, 1)
        p['surface_temp_now'] = P(min(max(now, tmin), tmax), 'K', False, src + '; limited to the Diviner range', nd=1)
        p['surface_temp_amplitude'] = P(tmax - tmin, 'K', False, 'Diviner max - estimated min', nd=1)
    else:
        p['surface_temp_amplitude'] = P(hi - lo, 'K', False, src, nd=1)
    return p, sky

# ------------------------------------------------------------------ base suitability
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def base_score(st, tp):
    sun = st['sun_visibility_best_within_1km']['value'] or st['sun_visibility_fraction']['value']
    polar_map = st['sun_visibility_best_within_1km']['value'] is not None
    power = clamp(sun) if polar_map else 0.35        # non-polar: 50% sun but 14-day nights need large storage
    ear = st['earth_visibility_best_within_1km']['value'] or st['earth_visibility_fraction']['value'] or 0
    ice_km = st['nearest_ice_stable_ground_km']['value']; ct = st['nearest_cold_trap_km']['value']
    water = clamp(1 - ice_km / 15) if ice_km is not None else (0.3 * clamp(1 - ct / 15) if ct is not None else clamp((st['hydrogen_index']['value'] or 0) / 0.05) * 0.2)
    slope = st['slope_deg']['value'] or 0; rel = st['surface_roughness']['value'] or 0
    terrain = clamp(1 - max(slope - 2, 0) / 13) * 0.7 + clamp(1 - rel / 400) * 0.3
    tm, amp = tp['surface_temp_mean']['value'], tp['surface_temp_amplitude']['value']
    thermal = 0.0 if tm is None or amp is None else 0.5 * clamp(1 - abs(tm - 250) / 200) + 0.5 * clamp(1 - amp / 300)
    isru = clamp(((st['feo_wt_pct']['value'] or 0) / 20 + (st['tio2_wt_pct']['value'] or 0) / 10) / 2)
    shelter = clamp(1 - (st['nearest_skylight_km']['value'] - 50) / 450)
    comp = dict(power=power, water=water, communication=clamp(ear), terrain=terrain, thermal=thermal, isru_oxygen=isru, shelter=shelter)
    score = 100 * sum(BASE_WEIGHTS[k] * v for k, v in comp.items()) / sum(BASE_WEIGHTS.values())
    return round(score, 1), {k: round(v, 3) for k, v in comp.items()}

def target_profile(st, tp):
    raw = dict(temp_mean=round(tp['surface_temp_mean']['value'] - 273.15, 1), temp_diurnal_amp=round(tp['surface_temp_amplitude']['value'], 1),
               thermal_inertia=st['thermal_inertia']['value'], surface_roughness=st['surface_roughness']['value'], soil_moisture=None,
               dust_aerosol=0.0, solar_elevation_max=tp['solar_elevation_max']['value'], radiation_proxy=0.0, slope_deg=st['slope_deg']['value'])
    meas = [tp['surface_temp_mean']['measured'], False, False, True, False, True, True, True, True]
    return dict(features_raw=raw, features_measured=meas, nearest_skylight_km=st['nearest_skylight_km']['value'],
                soil_moisture_note='no defensible water percentage from orbit; see ice_depth, ice_within_1m_fraction, hydrogen_index')

# ------------------------------------------------------------------ refine approximate region points
def refine_region(lat, lon, radius_km, max_slope=8.0, candidates=250):
    """Best-lit point within radius_km whose slope is <= max_slope deg and Earth visibility >= 0.3."""
    w = mm.illum_window(lat, lon, radius_km)
    if w is None: return None
    f, x, y, _ = w; e = mm.illum_window(lat, lon, radius_km, earth=True)[0]
    order = np.argsort(-f)[:candidates * 4]
    for i in order:
        if e[i] < 0.3: continue
        la, lo = mm.polar_latlon(x[i], y[i], lat < 0); t = mm.terrain(float(la), float(lo))
        if t['slope_deg'] <= max_slope:
            return dict(lat=round(float(la), 4), lon=round(float(lo), 4), sun=round(float(f[i]), 3), earth=round(float(e[i]), 3), slope=t['slope_deg'])
    return None

def nearest_site(lat, lon, max_km=10.0):
    best = None
    for s in ms.SITES:
        a, b = math.radians(lat), math.radians(s['lat']); d = 1737.4 * 2 * math.asin(math.sqrt(math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(math.radians(s['lon'] - lon) / 2) ** 2))
        if d <= max_km and (best is None or d < best[1]): best = (s, d)
    return best

def characterize(lat, lon, t):
    lon = ((lon + 180) % 360) - 180
    st = point_static(lat, lon); tp, sky = point_time(lat, lon, t, st)
    score, comp = base_score(st, tp); ns = nearest_site(lat, lon)
    return dict(site=None if not ns else dict(id=ns[0]['id'], name=ns[0]['name'], kind=ns[0]['kind'], distance_km=round(ns[1], 2), coord_quality=ns[0]['coord_quality']),
                static=st, time=tp, sky=sky, base_suitability=dict(score=score, components=comp, weights=BASE_WEIGHTS,
                meaning='0-100; weighted mean of component scores (each 0-1); weights adjustable'),
                weights=dict(values=FEATURE_WEIGHTS, order=SPEC, rationale='Moon base analogs: illumination, temperature regime and terrain dominate; '
                             'soil_moisture has no lunar value and gets 0'), target_profile=target_profile(st, tp))

# ------------------------------------------------------------------ known sites, with approximate regions refined
REFINE_MAX_KM = 8.0
def site_points():
    """The 24 sites; 'region, approx' polar points are moved to the best-lit flat spot within their search radius."""
    out, used = [], set()
    for s in ms.SITES:
        p = dict(id=s['id'], lat=s['lat'], lon=s['lon'], name=s['name'], kind=s['kind'], coord_quality=s['coord_quality'])
        if s['coord_quality'].startswith('region') and abs(s['lat']) > 75:
            km = min(s.get('search_km', 5), REFINE_MAX_KM)
            r = refine_region(s['lat'], s['lon'], km)
            if r and (r['lat'], r['lon']) not in used: used.add((r['lat'], r['lon'])); p.update(lat=r['lat'], lon=r['lon'], refined_from=dict(lat=s['lat'], lon=s['lon'], search_km=km,
                           rule='best-lit pixel with slope <= 8 deg and Earth visibility >= 0.3'))
        elif abs(s['lat']) > 75 and s['kind'].startswith('Artemis'):
            r = refine_region(s['lat'], s['lon'], REFINE_MAX_KM)      # published point kept; best-lit flat spot nearby reported
            if r: p['best_nearby'] = dict(r, search_km=REFINE_MAX_KM, note='published point kept as the site; this is the best-lit '
                                          'flat spot within the radius (sun and Earth visibility fractions, slope in deg)')
        out.append(p)
    return out

def months_of_year(year):
    return [(k, dt.datetime(year, k, 15, 12)) for k in range(1, 13)]
