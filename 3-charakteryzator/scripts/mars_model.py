"""Month-by-month Mars conditions for named sites and for any coordinate.

Every parameter is returned as {value, low, high, unit, measured, basis, source}:
  basis 'measured'  read at this exact point: an orbital map pixel (terrain, thermal inertia, albedo, water, minerals)
                    or exact orbital geometry / physical constant (noon Sun, daylight, gravity); measured = true
  basis 'local'     forecast for the date by the local model, fitted only to this landing site's own station records
                    (station_model.py); measured = false
  basis 'global'    the global predictor (latitude + elevation + surface properties, calibrated on all stations);
                    measured = false
  basis 'none'      no data at this point (value null for fixed properties, e.g. a thermal-inertia pixel the TES team
                    gap-filled, or wind away from stations)
low/high: local model = 10-90% of past departures from the site's seasonal fit; global = validated error band.

Month k (1..12) = Ls 30(k-1) to 30k  (Mars months; Ls 0 = northern spring equinox).
"""
import json, os, numpy as np, pandas as pd
import mars_maps as mm, mars_climate as mc, marslib as m, solar, station_model as sm
AIR = json.load(open(os.path.join(m.OUT, 'air_model_fit.json')))
ERR = dict(ground_min=6.1, ground_max=5.3, air=7.0, pressure_pct=2.3)     # from the validation files
SPEC_FEATURES = ['temp_mean', 'temp_diurnal_amp', 'thermal_inertia', 'surface_roughness', 'soil_moisture', 'dust_aerosol',
                 'solar_elevation_max', 'radiation_proxy', 'slope_deg']

def P(value, unit, measured, source, low=None, high=None, nd=2, basis=None):
    r = lambda x: None if x is None or (isinstance(x, float) and not np.isfinite(x)) else (round(float(x), nd) if isinstance(x, (int, float, np.floating, np.integer)) else x)
    v = r(value)
    if basis is None: basis = 'none' if v is None else ('measured' if measured else 'global')
    return dict(value=v, low=r(low), high=r(high), unit=unit, measured=bool(measured) and basis == 'measured', basis=basis, source=source)

def month_bounds(k): return 30.0 * (k - 1), 30.0 * k
def month_sols(k):
    a, b = month_bounds(k); s0, s1 = mc.sol_of_ls(a), mc.sol_of_ls(b if b < 360 else 359.999)
    return np.arange(np.ceil(s0), np.floor(s1) + 1)

# ------------------------------------------------------------------ static (does not change with season)
def point_static(lat, lon):
    t = mm.terrain(lat, lon); ti, ti_src = mm.thermal_inertia(lat, lon); alb = mm.albedo(lat, lon)
    w, w_src, w_ok = mm.water(lat, lon); hi = mm.hydrogen_index(lat, lon); hd, hn = mm.hydrated_minerals(lat, lon); cave = mm.nearest_cave_km(lat, lon)
    return dict(
        elevation=P(t['elevation_m'], 'm above areoid', True, 'MOLA topography, 1.85 km pixel', nd=0),
        slope_deg=P(t['slope_deg'], 'deg', True, 'MOLA, steepest slope over ~1.85 km baseline (not lander scale)'),
        surface_roughness=P(t['roughness_m'], 'm', True, 'MOLA, local relief: std of detrended elevation over ~13 km', nd=1),
        # only a direct TES retrieval counts; gap-filled / nearby-pixel values are kept for the temperature model but the
        # point itself has no thermal inertia measurement (basis 'none', excluded from the spec feature)
        thermal_inertia=P(ti, 'J m-2 K-1 s-1/2', ti_src == 'direct retrieval', f'TES nightside thermal inertia, 3 km pixel ({ti_src})', nd=0,
                          basis='measured' if ti is not None and ti_src == 'direct retrieval' else 'none'),
        albedo=P(alb, '', alb is not None, 'TES bolometric albedo, 7.4 km pixel', nd=3),
        soil_moisture=P(w, 'wt% water-equivalent hydrogen, top ~tens of cm', w_ok, w_src),
        hydrogen_index=P(hi, '0 = equatorial-dry, 0.4+ = ice-rich', hi is not None, 'Odyssey neutron spectrometer epithermal flux, 0.5 deg'),
        hydrated_minerals_nearest_km=P(hd, 'km', True, 'OMEGA/CRISM hydrated mineral detections (Carter et al. 2013)', nd=1),
        hydrated_minerals_within_100km=P(hn, 'count', True, 'OMEGA/CRISM hydrated mineral detections', nd=0),
        nearest_skylight_km=P(cave, 'km', cave is not None, 'Mars Global Cave Candidate Catalog' if cave is not None else
                              'missing: cave catalog not downloaded (USGS server unreachable)', nd=1),
        gravity=P(3.711, 'm s-2', True, 'constant (0.38 g); Earth cannot reproduce this'),
    )

# ------------------------------------------------------------------ global predictor, one month
def _sun(lat, k, tau_fn):
    sols = month_sols(k); ls = solar.orbit(sols)[0]
    _, top, surf, day = solar.daily(lat, tau_fn(ls), sols)
    dec = np.degrees(solar.orbit(sols)[2])
    return surf, top, day, float(np.max(np.clip(90 - np.abs(lat - dec), 0, 90)))

def point_month_model(lat, lon, st, k):
    a, b = month_bounds(k); lsm = np.array([a + 5, a + 15, a + 25]); elev = st['elevation']['value']
    p = mc.pressure_pa(lsm, elev); pm = float(p.mean())
    dust_t = float((mc.dust_tau(lat, lsm) * p / 610).mean()); dust_s = float((mc.dust_tau(lat, lsm, 'storm_year') * p / 610).mean())
    tau_t = float(mc.total_tau(lat, lsm, p).mean()); tau_s = float(mc.total_tau(lat, lsm, p, 'storm_year').mean())
    alb = st['albedo']['value'] or 0.22; ti = st['thermal_inertia']['value'] or 250
    gmin, gmax, gmean = [float(x[0]) for x in mc.ground_temps(lat, [a + 15], alb, ti, [pm], [tau_t])]
    smin, smax, smean = [float(x[0]) for x in mc.ground_temps(lat, [a + 15], alb, ti, [pm], [tau_s])]
    amin = AIR['air_min']['intercept'] + AIR['air_min']['slope'] * gmin; amax = AIR['air_max']['intercept'] + AIR['air_max']['slope'] * gmax
    tf = float(mc.frost_point(pm))
    amin, amax = max(min(amin, amax), tf), max(amin, amax, tf)          # keep order; air cannot sit below the CO2 frost point
    amean = (amin + amax) / 2
    warn = []
    if abs(lat) > 70: warn.append('poleward of the most poleward station (68N): temperatures extrapolated')
    if elev > 0 or elev < -5500: warn.append('elevation outside the stations\' range (-4.5 to -1.4 km): temperatures extrapolated')
    if gmin <= tf + 0.5: warn.append('ground at CO2 frost point (seasonal frost cover)')
    xs = ('; ' + '; '.join(warn)) if warn else ''
    surf, top, day, smax_el = _sun(lat, k, lambda ls: mc.total_tau(lat, ls, mc.pressure_pa(ls, elev)))
    surf_s, *_ = _sun(lat, k, lambda ls: mc.total_tau(lat, ls, mc.pressure_pa(ls, elev), 'storm_year'))
    G = 'global predictor'
    out = dict(
        ground_temp_min=P(gmin, 'K', False, f'{G}: surface energy balance model{xs}', gmin - ERR['ground_min'], gmin + ERR['ground_min'], 1),
        ground_temp_max=P(gmax, 'K', False, f'{G}: surface energy balance model{xs}', gmax - ERR['ground_max'], gmax + ERR['ground_max'], 1),
        ground_temp_mean=P(gmean, 'K', False, f'{G}: surface energy balance model', nd=1),
        air_temp_min=P(amin, 'K', False, f'{G}: air from modelled ground, fit on 7 stations{xs}', amin - ERR['air'], amin + ERR['air'], 1),
        air_temp_max=P(amax, 'K', False, f'{G}: air from modelled ground, fit on 7 stations{xs}', amax - ERR['air'], amax + ERR['air'], 1),
        air_temp_mean=P(amean, 'K', False, f'{G}: mean of predicted min and max', nd=1),
        pressure=P(pm, 'Pa', False, f'{G}: Viking 1 seasonal curve moved to MOLA elevation', pm * (1 - ERR['pressure_pct'] / 100), pm * (1 + ERR['pressure_pct'] / 100), 0),
        wind_mean=P(None, 'm/s', False, 'missing: no global wind data (stations only)'),
        dust_tau=P(dust_t, 'optical depth 0.67 um', False, f'{G}: MGS TES dust, zonal median for this latitude, scaled to local pressure'),
        sunlight_mean=P(surf.mean(), 'Wh/m2 per sol, flat ground', False, f'{G}: orbit geometry + predicted dust and ice', surf.min(), surf.max(), 0),
        daylight_hours=P(day.mean(), 'h', True, 'exact orbital geometry', day.min(), day.max(), 1),
        solar_elevation_max=P(smax_el, 'deg', True, 'exact orbital geometry (noon sun, highest in the month)', nd=1),
    )
    storm = dict(dust_tau=P(dust_s, 'optical depth 0.67 um', False, f'{G}: TES Mars year 25 (2001 global storm), zonal median'),
                 sunlight_mean=P(surf_s.mean(), 'Wh/m2 per sol, flat ground', False, f'{G}: storm-year dust', surf_s.min(), surf_s.max(), 0),
                 ground_temp_min=P(smin, 'K', False, f'{G}: storm-year dust', nd=1), ground_temp_max=P(smax, 'K', False, f'{G}: storm-year dust', nd=1))
    return out, storm

def derived(params, measured_both):
    p, t = params['pressure'], params['air_temp_mean']
    both_local = p['basis'] == 'local' and t['basis'] == 'local'
    params['air_density'] = P(mc.air_density(p['value'], t['value']) if p['value'] and t['value'] else None, 'kg/m3', False,
                              'pressure / (R * air temperature), R = 191.8 J/kg/K', nd=4, basis=None if not (p['value'] and t['value']) else ('local' if both_local else 'global'))
    params['radiation_proxy'] = P(mc.column_mass_g_cm2(p['value']) if p['value'] else None, 'g/cm2 atmosphere overhead (Earth sea level: 1033)',
                                  False, f"column mass = pressure / g; pressure from the {'local' if p['basis'] == 'local' else 'global'} model", nd=1,
                                  basis=None if not p['value'] else p['basis'])
    return params

def target_profile(static, params):
    """The nine features of the team spec (Component 3), in spec order and units, plus which of them were measured."""
    gm, gx, gn = params['ground_temp_mean'], params['ground_temp_max'], params['ground_temp_min']
    vals = dict(temp_mean=None if gm['value'] is None else round(gm['value'] - 273.15, 1),
                temp_diurnal_amp=None if gx['value'] is None or gn['value'] is None else round(gx['value'] - gn['value'], 1),
                thermal_inertia=static['thermal_inertia']['value'], surface_roughness=static['surface_roughness']['value'],
                soil_moisture=static['soil_moisture']['value'], dust_aerosol=params['dust_tau']['value'],
                solar_elevation_max=params['solar_elevation_max']['value'], radiation_proxy=params['radiation_proxy']['value'],
                slope_deg=static['slope_deg']['value'])
    ti = static['thermal_inertia']
    if ti['basis'] != 'measured': vals['thermal_inertia'] = None          # no measurement at this pixel -> no data
    amp_basis = 'none' if vals['temp_diurnal_amp'] is None else ('local' if gx['basis'] == 'local' and gn['basis'] == 'local' else 'global')
    src = dict(temp_mean=(gm['basis'], gm['source']), temp_diurnal_amp=(amp_basis, gx['source']),
               thermal_inertia=(ti['basis'], ti['source']), surface_roughness=('measured', static['surface_roughness']['source']),
               soil_moisture=(static['soil_moisture']['basis'], static['soil_moisture']['source']),
               dust_aerosol=(params['dust_tau']['basis'], params['dust_tau']['source']),
               solar_elevation_max=('measured', params['solar_elevation_max']['source']),
               radiation_proxy=(params['radiation_proxy']['basis'], params['radiation_proxy']['source']),
               slope_deg=('measured', static['slope_deg']['source']))
    basis = [src[f][0] if vals[f] is not None else 'none' for f in SPEC_FEATURES]
    return dict(features_raw=vals, features_measured=[b == 'measured' for b in basis], features_source=basis,
                features_detail=[src[f][1] for f in SPEC_FEATURES], nearest_skylight_km=static['nearest_skylight_km']['value'])

def predict_point(lat, lon, months=range(1, 13)):
    st = point_static(lat, lon); out = []
    for k in months:
        a, b = month_bounds(k); prm, storm = point_month_model(lat, lon, st, k); prm = derived(prm, False)
        out.append(dict(month=k, ls_start=a, ls_end=b, sols=int(len(month_sols(k))), params=prm, storm_year=storm, target_profile=target_profile(st, prm)))
    return st, out

# ------------------------------------------------------------------ station sites: local model in station_model.py
STATION_FILES = sm.FILES

# ------------------------------------------------------------------ importance weights (judgement; adjustable by the user)
BASE_WEIGHTS = dict(temp_mean=0.8, temp_diurnal_amp=0.7, thermal_inertia=0.7, surface_roughness=0.5, soil_moisture=0.5,
                    dust_aerosol=0.5, solar_elevation_max=0.4, radiation_proxy=0.2, slope_deg=0.5)
SITE_WEIGHTS = {
    'vl1': (dict(surface_roughness=0.7, thermal_inertia=0.8), 'Rocky outflow-channel plains: surface texture and rock cover define the site.'),
    'vl2': (dict(temp_mean=1.0, soil_moisture=0.8), 'Cold mid-latitude plains with seasonal frost: temperature and ground ice dominate.'),
    'pathfinder': (dict(surface_roughness=0.9, thermal_inertia=0.8), 'Flood-deposited, rock-strewn surface at a channel mouth.'),
    'spirit': (dict(thermal_inertia=0.9, slope_deg=0.6), 'Basaltic plains with loose sand (where Spirit was trapped): material strength matters.'),
    'opportunity': (dict(thermal_inertia=0.8, dust_aerosol=0.7, slope_deg=0.7), 'Flat sulfate sediments with ripples; long solar-powered record, so dust matters.'),
    'phoenix': (dict(soil_moisture=1.0, temp_mean=1.0, solar_elevation_max=0.8), 'Polar ice-cemented ground and long polar day/night: ice, cold and illumination.'),
    'curiosity': (dict(slope_deg=0.8, surface_roughness=0.8, thermal_inertia=0.8), 'Layered sediments on the flanks of a 5 km mound: terrain and rock exposure.'),
    'insight': (dict(slope_deg=0.9, surface_roughness=0.9, thermal_inertia=0.8), 'Chosen for being flat and smooth with fine regolith (geophysics station).'),
    'perseverance': (dict(thermal_inertia=0.9, surface_roughness=0.8, soil_moisture=0.6), 'River delta with clays and carbonates: sedimentary rock and past water.'),
    'zhurong': (dict(soil_moisture=0.7, temp_mean=0.9), 'Northern lowland plains with possible ancient shoreline and buried ice.'),
    'oxia': (dict(thermal_inertia=0.9, slope_deg=0.8, surface_roughness=0.8), 'Clay-bearing layered plains, deliberately flat for landing.'),
    'arcadia': (dict(soil_moisture=1.0, temp_mean=0.9, slope_deg=0.8, solar_elevation_max=0.7), 'Shallow ground ice for crewed missions, balanced against sunlight and warmth.'),
}
def weights_for(site):
    w = dict(BASE_WEIGHTS); note = 'Default weights for a point that is not a known site.'
    if site in SITE_WEIGHTS: w.update(SITE_WEIGHTS[site][0]); note = SITE_WEIGHTS[site][1]
    return w, note

def nearest_site(lat, lon, max_km=10.0):
    best = None
    for s in m.SITES:
        d = float(mm._gc_km(np.radians(lat), np.radians(lon % 360), np.radians(s['lat']), np.radians(s['lon'] % 360)))
        if d <= max_km and (best is None or d < best[1]): best = (s, d)
    return best

def characterize(lat, lon, months=range(1, 13), site_radius_km=10.0, ls_at=None):
    """Full record for one point: static parameters, 12 monthly parameter sets (local model forecasts where the point
    is a station site and the station observed that season, global predictor otherwise), storm-year variant, spec
    TargetProfile per month, weights. ls_at: forecast the month containing this Ls at exactly this Ls."""
    lon = lon % 360
    ns = nearest_site(lat, lon, site_radius_km); site = ns[0]['id'] if ns else None
    st = point_static(lat, lon); months_out = []
    for k in months:
        a, b = month_bounds(k); prm, storm = point_month_model(lat, lon, st, k)
        if site:
            at = ls_at if ls_at is not None and int(ls_at // 30) + 1 == k else None
            prm.update(sm.month_params(site, k, at))
        prm = derived(prm, True)
        months_out.append(dict(month=k, ls_start=a, ls_end=b, sols=int(len(month_sols(k))), params=prm, storm_year=storm,
                               target_profile=target_profile(st, prm)))
    w, note = weights_for(site)
    return dict(site=None if not ns else dict(id=site, name=ns[0]['name'], mission=ns[0]['mission'], kind=ns[0]['kind'], distance_km=round(ns[1], 2)),
                weights=dict(values=w, order=SPEC_FEATURES, rationale=note, meaning='importance of each feature for finding an Earth analog of this place (0-1, adjustable)'),
                static=st, months=months_out)
