"""Combine the reduced station tables, orbital dust, maps and model output into the cross-site products:

  outputs/pressure_reference_vl1.csv     Viking 1 multi-year seasonal pressure curve (5-deg Ls bins)
  outputs/pressure_model_validation.csv  that curve scaled by elevation vs pressure measured at the other stations
  outputs/station_series.csv             per station and 15-deg Ls bin: typical daily min/max temperature, pressure, wind, dust
  outputs/site_seasonal_estimates.csv    per site and 15-deg Ls bin: estimated pressure, total optical depth, sunlight
  outputs/dust_validation.csv            orbital dust climatology vs optical depth measured from the surface
  outputs/coverage.csv                   Full / Partial / Missing per site and parameter
  outputs/site_summary.csv               one row per site and parameter, with provenance
  outputs/page_data.json                 everything the interactive page needs
"""
import os, json
import numpy as np, pandas as pd
import marslib as m, solar

O = m.OUT
H_SCALE = 10.8                      # km, pressure scale height used to move pressure between elevations
ELEV = {s['id']: s['elev'] for s in m.SITES}
ELEV.update(vl1=-3.627, vl2=-4.505, pathfinder=-3.682, phoenix=-4.126, curiosity=-4.501, insight=-2.613, perseverance=-2.569,
            spirit=-1.940, opportunity=-1.385, zhurong=-4.099, oxia=-3.0, arcadia=-3.9)
STATIONS = ['vl1', 'vl2', 'pathfinder', 'phoenix', 'curiosity', 'insight', 'perseverance']
SENSOR = {'vl1': 'boom thermocouple, 1.6 m', 'vl2': 'boom thermocouple, 1.6 m', 'pathfinder': 'top of mast, about 1 m above the lander petal',
          'phoenix': 'top of mast, about 2 m above ground', 'curiosity': 'REMS estimated ambient, booms at 1.6 m',
          'insight': 'TWINS boom tips, about 1.2 m', 'perseverance': 'not in downloaded product'}
def daily(s): return pd.read_csv(os.path.join(O, f'{s}_daily.csv'))
B15 = np.arange(0, 360, 15)

# ---------------------------------------------------------------- 1. pressure reference from Viking 1
v1 = daily('vl1')
ref = v1[(v1.p_gap_flag == 'BB') & v1.p_mean_Pa.notna()].copy()
ref['b'] = (ref.ls_deg // 5 * 5).astype(int)
pcurve = ref.groupby('b').p_mean_Pa.median().reindex(range(0, 360, 5)).interpolate(limit_direction='both')
pv = ref.pivot_table(index='b', columns='mars_year', values='p_mean_Pa', aggfunc='median')
pd.DataFrame({'ls_bin_start': pcurve.index, 'p_vl1_Pa': pcurve.round(1).values, 'sols': ref.groupby('b').size().reindex(pcurve.index).fillna(0).astype(int).values,
              'year_to_year_spread_pct': (100 * (pv.max(axis=1) - pv.min(axis=1)) / pv.mean(axis=1)).reindex(pcurve.index).round(2).values}
             ).to_csv(os.path.join(O, 'pressure_reference_vl1.csv'), index=False)
def p_est(site, ls):
    """Estimated daily-mean pressure (Pa) at a site: Viking 1 seasonal curve moved to the site's elevation."""
    ls = np.asarray(ls, dtype=float) % 360
    x = np.arange(2.5, 360, 5); y = pcurve.values
    base = np.interp(ls, np.r_[x[-1] - 360, x, x[0] + 360], np.r_[y[-1], y, y[0]])
    return base * np.exp(-(ELEV[site] - ELEV['vl1']) / H_SCALE)

# ---------------------------------------------------------------- 2. station series on 15-deg bins
def good(d, s, q):
    if q == 'p' and s in ('vl1', 'vl2'): return d[(d.p_gap_flag == 'BB') & d.p_mean_Pa.notna()]
    hrs = d.get(f'{q}_hours')
    return d[hrs >= m.MIN_HOURS] if hrs is not None else d.iloc[0:0]
rows = []
for s in STATIONS:
    d = daily(s)
    if s == 'perseverance': d['landing_area'] = d.sol <= 680      # rover later climbed several hundred metres
    d['b'] = (d.ls_deg // 15 * 15).astype(int)
    for b in B15:
        r = dict(site=s, ls_bin_start=int(b), sols_any=int((d.b == b).sum()))
        for q, unit in (('t_air', 'K'), ('t_ground', 'K')):
            g = good(d, s, q); g = g[g.b == b]
            r[f'{q}_sols'] = len(g)
            r[f'{q}_min'] = round(g[f'{q}_min_{unit}'].median(), 1) if len(g) else np.nan
            r[f'{q}_max'] = round(g[f'{q}_max_{unit}'].median(), 1) if len(g) else np.nan
            r[f'{q}_coldest'] = round(g[f'{q}_min_{unit}'].min(), 1) if len(g) else np.nan
            r[f'{q}_warmest'] = round(g[f'{q}_max_{unit}'].max(), 1) if len(g) else np.nan
        g = good(d, s, 'p')
        if s == 'perseverance': g = g[g.landing_area]
        g = g[g.b == b]
        r['p_sols'] = len(g); r['p_mean'] = round(g.p_mean_Pa.median(), 1) if len(g) else np.nan
        g = d[(d.b == b) & d.wind_mean_ms.notna()]
        r['wind_sols'] = len(g); r['wind_mean'] = round(g.wind_mean_ms.median(), 2) if len(g) else np.nan
        r['wind_max'] = round(g.wind_max_ms.max(), 1) if len(g) else np.nan
        g = d[(d.b == b) & d.tau_dust.notna()]
        r['tau_sols'] = len(g); r['tau'] = round(g.tau_dust.median(), 3) if len(g) else np.nan
        if s == 'vl1':
            g = d[(d.b == b) & (d.t_footpad_gap_flag == 'BB') & d.t_footpad_mean_K.notna()]
            r['t_footpad_sols'] = len(g)
            r['t_footpad_min'] = round(g.t_footpad_min_K.median(), 1) if len(g) else np.nan
            r['t_footpad_max'] = round(g.t_footpad_max_K.median(), 1) if len(g) else np.nan
        rows.append(r)
ser = pd.DataFrame(rows)
# InSight: composite day built from event windows, per 30-deg season, where the windows together cover >= 22 local hours
ih = pd.read_csv(os.path.join(O, 'insight_hourly.csv')); ih['b30'] = (ih.ls_deg // 30 * 30).astype(int)
comp = []
for b, g in ih.groupby('b30'):
    hm = g.groupby('hour')[['t_air', 'p']].mean()
    r = dict(ls_bin_start=int(b), hours_t=int(hm.t_air.notna().sum()), hours_p=int(hm.p.notna().sum()), sols=int(g.sol.nunique()))
    if r['hours_t'] >= 22: r.update(t_air_min=round(hm.t_air.min(), 1), t_air_max=round(hm.t_air.max(), 1))
    if r['hours_p'] >= 22: r.update(p_mean=round(hm.p.mean(), 1))
    comp.append(r)
comp = pd.DataFrame(comp); comp.to_csv(os.path.join(O, 'insight_composite_by_season.csv'), index=False)
ser['source'] = 'full sols'
for _, c in comp.iterrows():
    for b in (c.ls_bin_start, c.ls_bin_start + 15):
        i = ser[(ser.site == 'insight') & (ser.ls_bin_start == b)].index
        if pd.notna(c.get('t_air_min')) and ser.loc[i, 't_air_sols'].iloc[0] == 0:
            ser.loc[i, ['t_air_min', 't_air_max']] = [c.t_air_min, c.t_air_max]; ser.loc[i, 'source'] = 'composite of event windows'
        if pd.notna(c.get('p_mean')) and ser.loc[i, 'p_sols'].iloc[0] == 0:
            ser.loc[i, 'p_mean'] = c.p_mean; ser.loc[i, 'source'] = 'composite of event windows'
ser.to_csv(os.path.join(O, 'station_series.csv'), index=False)

# Viking 1 footpad vs boom air temperature in the seasons where both exist
fp = ser[(ser.site == 'vl1') & ser.t_air_min.notna() & ser.t_footpad_min.notna()]
print('VL1 footpad minus air (K), same season different year: min %.1f (range %.1f..%.1f), max %.1f (range %.1f..%.1f), bins %d' % (
    (fp.t_footpad_min - fp.t_air_min).median(), (fp.t_footpad_min - fp.t_air_min).min(), (fp.t_footpad_min - fp.t_air_min).max(),
    (fp.t_footpad_max - fp.t_air_max).median(), (fp.t_footpad_max - fp.t_air_max).min(), (fp.t_footpad_max - fp.t_air_max).max(), len(fp)))

# ---------------------------------------------------------------- 3. pressure model validation
val = []
for s in STATIONS[1:]:
    g = ser[(ser.site == s) & ser.p_mean.notna()]
    if g.empty: continue
    pred = p_est(s, g.ls_bin_start + 7.5); ratio = g.p_mean.to_numpy() / pred
    val.append(dict(site=s, seasons_compared=len(g), measured_over_estimate_median=round(float(np.median(ratio)), 3), lowest=round(float(ratio.min()), 3),
                    highest=round(float(ratio.max()), 3), rms_error_pct=round(float(100 * np.sqrt(np.mean((ratio - 1) ** 2))), 1),
                    elevation_used_km=ELEV[s], elevation_implied_by_pressure_km=round(float(ELEV[s] - H_SCALE * np.log(np.median(ratio))), 2)))
val = pd.DataFrame(val); val.to_csv(os.path.join(O, 'pressure_model_validation.csv'), index=False)
print(val.to_string(index=False))
allr = np.concatenate([ser[(ser.site == s) & ser.p_mean.notna()].p_mean.to_numpy() / p_est(s, ser[(ser.site == s) & ser.p_mean.notna()].ls_bin_start + 7.5) for s in STATIONS[1:]])
P_ERR = float(100 * np.sqrt(np.mean((allr - 1) ** 2)))
print('pressure model: rms error %.1f%%, worst %.1f%% over %d station-seasons' % (P_ERR, 100 * np.abs(allr - 1).max(), len(allr)))

# ---------------------------------------------------------------- 4. dust and sunlight at every site
sd = pd.read_csv(os.path.join(O, 'site_dust_by_season.csv'))
def circ_fill(a):
    a = np.asarray(a, dtype=float)
    if np.isnan(a).all(): return a
    n = len(a); idx = np.arange(n); ok = ~np.isnan(a)
    return np.interp(idx, np.r_[idx[ok] - n, idx[ok], idx[ok] + n], np.r_[a[ok], a[ok], a[ok]])
def at_ls(vals15, ls):
    x = B15 + 7.5; y = np.asarray(vals15)
    return np.interp(np.asarray(ls) % 360, np.r_[x[-1] - 360, x, x[0] + 360], np.r_[y[-1], y, y[0]])
sols = np.arange(669); LS_SOL = solar.orbit(sols)[0]
est, site_tau = [], {}
for s in m.SITES:
    g = sd[sd.site == s['id']].sort_values('ls_bin_start')
    gaps = int(g.dust610_typical.isna().sum())
    d_typ, i_typ = circ_fill(g.dust610_typical), circ_fill(g.ice_typical)
    d_sto = np.where(g.dust610_storm_year.notna(), g.dust610_storm_year, d_typ); i_sto = np.where(g.ice_storm_year.notna(), g.ice_storm_year, i_typ)
    p15 = p_est(s['id'], B15 + 7.5)
    tau_typ = d_typ * p15 / 610.0 + i_typ; tau_sto = d_sto * p15 / 610.0 + i_sto
    site_tau[s['id']] = dict(typ=tau_typ, sto=tau_sto, gaps=gaps, dust610=d_typ, ice=i_typ)
    out = {}
    for name, t15 in (('typical', tau_typ), ('storm_year', tau_sto), ('no_dust', np.zeros(24))):
        ls, top, surf, dh = solar.daily(s['lat'], at_ls(t15, LS_SOL), sols)
        out[name] = surf
    for i, b in enumerate(B15):
        sel = (LS_SOL >= b) & (LS_SOL < b + 15)
        est.append(dict(site=s['id'], ls_bin_start=int(b), p_estimate_Pa=round(float(p15[i]), 1), dust_at_610Pa_typical=round(float(d_typ[i]), 3),
                        ice_typical=round(float(i_typ[i]), 3), tau_total_typical=round(float(tau_typ[i]), 3), tau_total_storm_year=round(float(tau_sto[i]), 3),
                        sunlight_typical_Wh_m2_sol=round(float(out['typical'][sel].mean())), sunlight_storm_year_Wh_m2_sol=round(float(out['storm_year'][sel].mean())),
                        sunlight_no_dust_Wh_m2_sol=round(float(out['no_dust'][sel].mean())), daylight_hours=round(float(dh[sel].mean()), 2)))
    site_tau[s['id']].update(sun=out, dh=dh)
est = pd.DataFrame(est); est.to_csv(os.path.join(O, 'site_seasonal_estimates.csv'), index=False)

# orbital dust vs optical depth measured from the surface (Viking 1, Viking 2, Phoenix)
dv = []
for s in ('vl1', 'vl2', 'phoenix'):
    g = ser[(ser.site == s) & ser.tau.notna()]
    e = est[est.site == s].set_index('ls_bin_start')
    for _, r in g.iterrows():
        dv.append(dict(site=s, ls_bin_start=int(r.ls_bin_start), sols=int(r.tau_sols), tau_measured_surface=r.tau,
                       tau_orbital_typical=e.tau_total_typical[r.ls_bin_start], tau_orbital_storm_year=e.tau_total_storm_year[r.ls_bin_start]))
dv = pd.DataFrame(dv); dv['measured_minus_orbital'] = (dv.tau_measured_surface - dv.tau_orbital_typical).round(3)
dv.to_csv(os.path.join(O, 'dust_validation.csv'), index=False)
for s, g in dv.groupby('site'):
    clear = g[g.ls_bin_start < 180]
    print(f"dust check {s}: Ls 0-180 measured {clear.tau_measured_surface.median():.2f} vs orbital {clear.tau_orbital_typical.median():.2f};"
          f" Ls 180-360 measured {g[g.ls_bin_start >= 180].tau_measured_surface.median():.2f} vs orbital typical {g[g.ls_bin_start >= 180].tau_orbital_typical.median():.2f}"
          f" / storm-year {g[g.ls_bin_start >= 180].tau_orbital_storm_year.median():.2f}")

# ---------------------------------------------------------------- 5. coverage
def bins30(series_ok):          # boolean per 15-deg bin row -> number of 30-deg seasons with data
    return int(pd.Series(np.asarray(series_ok)).groupby(np.arange(24) // 2).any().sum())
def level(n): return 'Full' if n >= 12 else ('Partial' if n > 0 else 'Missing')
mv = pd.read_csv(os.path.join(O, 'site_map_values.csv')).set_index('site')
gc = pd.read_csv(os.path.join(O, 'site_gcm_ground_temperature.csv'))
cov = []
def add(site, param, lev, detail): cov.append(dict(site=site, parameter=param, coverage=lev, detail=detail))
vimp = val.set_index('site').elevation_implied_by_pressure_km
for s in m.SITES:
    sid = s['id']; g = ser[ser.site == sid].sort_values('ls_bin_start') if sid in STATIONS else None
    for param, col, cnt, label in (('Air temperature', 't_air_min', 't_air_sols', 'sols with 18+ hours'), ('Ground temperature', 't_ground_min', 't_ground_sols', 'sols with 18+ hours'),
                                   ('Pressure', 'p_mean', 'p_sols', 'full-day sols'), ('Wind', 'wind_mean', 'wind_sols', 'sols'), ('Dust opacity from the surface', 'tau', 'tau_sols', 'sols')):
        if g is None:
            add(sid, param, 'Missing', 'No weather station data' + ('' if s['kind'] == 'Landed' else ' (nothing has landed here)') +
                ('; pressure is estimated from the Viking 1 curve and elevation' if param == 'Pressure' else '')); continue
        n = bins30(g[col].notna()); nsol = int(g[cnt].sum())
        det = f"{n} of 12 seasons; {nsol} {label}"
        if n == 0: det = 'Not measured by this mission' if param in ('Ground temperature', 'Dust opacity from the surface') else 'No usable data in the downloaded files'
        if sid == 'insight' and param in ('Air temperature', 'Pressure'):
            nfull = bins30(g[cnt] > 0); det = f"{n} of 12 seasons, {nfull} from complete sols and the rest from a composite of event windows; {nsol} complete sols"
        if sid == 'vl1' and param == 'Air temperature': det += '; the footpad sensor covers all 12 seasons but reads well above air temperature, so it is not used as a stand-in'
        if sid == 'perseverance' and param == 'Air temperature': det = 'In the calibrated product, which was not downloaded'
        if sid == 'perseverance' and param == 'Ground temperature': det += '; derived from thermal flux, 2 sols rejected'
        if sid == 'perseverance' and param == 'Pressure': det += ' in the first Mars year (landing area); later sols are at higher elevation'
        if sid == 'curiosity' and param == 'Wind': n = 0; det = 'Wind speed present in under 0.1% of records'
        if sid == 'pathfinder' and param == 'Wind': det = 'Wind columns are raw sensor temperatures, not speeds'
        if sid in ('curiosity', 'perseverance') and n > 0: det += '; every ' + ('10th' if sid == 'curiosity' else '20th') + ' sol sampled'
        if sid == 'vl1' and param == 'Wind': det += '; speed of the mean wind vector, lower than the mean speed'
        if param == 'Dust opacity from the surface' and n == 0 and sid in ('pathfinder', 'curiosity', 'insight', 'perseverance'): det = 'Measured by the mission cameras, not in the downloaded files'
        add(sid, param, level(n), det)
    t = site_tau[sid]
    add(sid, 'Dust opacity from orbit', 'Full' if t['gaps'] == 0 else 'Partial',
        f"TES climatology at this latitude, {24 - t['gaps']} of 24 half-seasons with retrievals" + ('' if t['gaps'] == 0 else '; gaps (polar night) filled by interpolation'))
    ti = mv.thermal_inertia_SI.get(sid)
    add(sid, 'Thermal inertia and albedo', 'Partial' if ti == ti else 'Missing',
        'Viking-era regional maps (2 deg and 1 deg cells); superseded by TES and THEMIS maps' if ti == ti else 'Site is outside the map (coverage ends at 60 N)')
    add(sid, 'Elevation', 'Partial', 'Published MOLA value entered by hand, not read from archive data' +
        (f"; pressure-implied elevation agrees within {abs(vimp[sid] - ELEV[sid]):.1f} km" if sid in vimp.index else '') + '. The Viking-era topography map in the folder is not usable.')
    add(sid, 'Slopes, rocks, minerals, ice', 'Missing', 'No data downloaded yet (MOLA, TES/THEMIS, CRISM, neutron data, or published site studies)')
cov = pd.DataFrame(cov); cov.to_csv(os.path.join(O, 'coverage.csv'), index=False)
pd.set_option('display.width', 250)
print(cov.pivot(index='site', columns='parameter', values='coverage').reindex([s['id'] for s in m.SITES]).rename(columns=lambda c: c[:14]).to_string())

# ---------------------------------------------------------------- 6. site summary (long table with provenance)
S = []
def put(site, group, param, value, unit, prov, note=''):
    S.append(dict(site=site, group=group, parameter=param, value=value, unit=unit, provenance=prov, note=note))
def rng(a, nd=0):
    a = np.asarray(a, dtype=float); a = a[~np.isnan(a)]
    if not len(a): return ''
    f = f'{{:.{nd}f}}'
    return f.format(a.min()) if round(a.min(), nd) == round(a.max(), nd) else f.format(a.min()) + ' to ' + f.format(a.max())
cvl = cov.set_index(['site', 'parameter']).coverage
for s in m.SITES:
    sid = s['id']; e = est[est.site == sid]; t = site_tau[sid]
    put(sid, 'Location', 'Latitude', s['lat'], 'deg N', 'published (entered by hand)')
    put(sid, 'Location', 'Longitude', s['lon'], 'deg E', 'published (entered by hand)')
    put(sid, 'Terrain', 'Elevation', ELEV[sid], 'km (MOLA)', 'published (entered by hand)', 'representative point' if sid in ('oxia', 'arcadia') else '')
    ti, al = mv.thermal_inertia_SI.get(sid), mv.albedo.get(sid)
    if ti == ti:
        put(sid, 'Surface', 'Thermal inertia', int(ti), 'J m-2 K-1 s-1/2', 'map-derived (Viking-era, 2 deg cell)',
            f"nearby cells {int(mv.thermal_inertia_SI_min_nearby[sid])} to {int(mv.thermal_inertia_SI_max_nearby[sid])}; unit conversion assumed")
        put(sid, 'Surface', 'Albedo', al, '', 'map-derived (Viking-era, 1 deg cell)', f"nearby cells {mv.albedo_min_nearby[sid]} to {mv.albedo_max_nearby[sid]}")
        cls = 'dust-dominated' if ti < 150 else ('fine sand to mixed sand and crust' if ti < 300 else ('coarser sand, crusts and scattered rock' if ti < 450 else 'rocky or strongly cemented'))
        put(sid, 'Surface', 'Regional surface class', cls, '', 'interpretation of the map value', 'regional average over roughly 120 km; not a site-scale result')
    else:
        put(sid, 'Surface', 'Thermal inertia', '', '', 'missing', 'outside map coverage'); put(sid, 'Surface', 'Albedo', '', '', 'missing', 'outside map coverage')
    if sid in STATIONS:
        g = ser[ser.site == sid]; d = daily(sid)
        for q, name in (('t_air', 'Air temperature'), ('t_ground', 'Ground temperature')):
            if g[f'{q}_min'].notna().any():
                prov = 'measured' + (' and composite of event windows' if sid == 'insight' else '') + (' (derived from thermal flux)' if (sid == 'perseverance' and q == 't_ground') else '')
                note = f"{cvl[(sid, name)].lower()} seasonal coverage" + (f"; sensor: {SENSOR[sid]}" if q == 't_air' else '')
                put(sid, 'Atmosphere', f'{name}: typical daily minimum across seasons', rng(g[f'{q}_min']), 'K', prov, note)
                put(sid, 'Atmosphere', f'{name}: typical daily maximum across seasons', rng(g[f'{q}_max']), 'K', prov, note)
                put(sid, 'Atmosphere', f'{name}: typical day-night swing', rng(g[f'{q}_max'] - g[f'{q}_min']), 'K', prov, note)
                if g[f'{q}_coldest'].notna().any():
                    put(sid, 'Atmosphere', f'{name}: coldest and warmest hourly mean on record', f"{g[f'{q}_coldest'].min():.0f} and {g[f'{q}_warmest'].max():.0f}", 'K', 'measured', note)
        if sid == 'vl1':
            for k, nm in (('min', 'minimum'), ('max', 'maximum')):
                put(sid, 'Atmosphere', f'Footpad temperature: typical daily {nm} across seasons', rng(g[f't_footpad_{k}']), 'K', 'measured (lander hardware)',
                    'all 12 seasons; in overlapping seasons it reads about 23 K above the air minimum and 9 K above the air maximum, so it is not a stand-in for air temperature')
        if g.p_mean.notna().any():
            put(sid, 'Atmosphere', 'Pressure: daily mean, lowest to highest season', rng(g.p_mean), 'Pa', 'measured' + (' and composite of event windows' if sid == 'insight' else ''),
                f"{cvl[(sid, 'Pressure')].lower()} seasonal coverage")
            dd = d[(d.p_min_Pa.notna()) & (d.p_hours >= m.MIN_HOURS)]
            if len(dd): put(sid, 'Atmosphere', 'Pressure: typical daily swing', f"{(100 * (dd.p_max_Pa - dd.p_min_Pa) / dd.p_mean_Pa).median():.1f}", '% of the mean', 'measured', 'thermal tide')
        if g.wind_mean.notna().any() and cvl[(sid, 'Wind')] != 'Missing':
            put(sid, 'Atmosphere', 'Wind: typical daily mean speed across seasons', rng(g.wind_mean, 1), 'm/s', 'measured', f"{cvl[(sid, 'Wind')].lower()} seasonal coverage")
            put(sid, 'Atmosphere', 'Wind: highest hourly value on record', f"{g.wind_max.max():.1f}", 'm/s', 'measured', '')
        if g.tau.notna().any():
            put(sid, 'Atmosphere', 'Optical depth measured from the surface, across seasons', rng(g.tau, 2), '', 'measured', f"{cvl[(sid, 'Dust opacity from the surface')].lower()} seasonal coverage")
        if sid == 'curiosity':
            put(sid, 'Atmosphere', 'Relative humidity: highest daily peak', f"{d.rh_max_pct.max():.0f}", '%', 'measured', 'peaks before dawn')
            put(sid, 'Atmosphere', 'Ultraviolet (200-380 nm): highest daily peak', f"{d.uv_abc_max_Wm2.max():.1f}", 'W/m2', 'measured', '')
        if sid == 'perseverance':
            put(sid, 'Atmosphere', 'Downward thermal flux from the sky: daily mean across the record', rng(d.lw_down_mean_Wm2), 'W/m2', 'measured', '')
    put(sid, 'Atmosphere', 'Pressure: estimated daily mean, lowest to highest season', rng(e.p_estimate_Pa), 'Pa', 'model-derived (Viking 1 curve scaled by elevation)',
        f"rms error {P_ERR:.1f}% against six stations")
    put(sid, 'Atmosphere', 'Optical depth from orbit (dust + ice), across seasons, typical year', rng(e.tau_total_typical, 2), '', 'orbital (TES, by latitude)', 'zonal average, scaled to site pressure')
    put(sid, 'Atmosphere', 'Optical depth from orbit, highest half-season in the 2001 storm year', f"{e.tau_total_storm_year.max():.2f}", '', 'orbital (TES, by latitude)', 'retrievals may miss the storm peak')
    gg = gc[gc.site == sid]
    put(sid, 'Atmosphere', 'Ground temperature in a climate model: daily minimum over four seasons', rng(gg.ground_t_min_K), 'K', 'model-derived (Ames GCM, 1996)', '7.5 x 9 deg grid; coarse')
    put(sid, 'Atmosphere', 'Ground temperature in a climate model: daily maximum over four seasons', rng(gg.ground_t_max_K), 'K', 'model-derived (Ames GCM, 1996)', '7.5 x 9 deg grid; coarse')
    fr = gg[(gg.co2_frost_kg_m2 > 0.01)]
    if len(fr):
        put(sid, 'Surface', 'Seasonal CO2 frost in the climate model', 'yes, ' + ', '.join(f"Ls {int(a)}-{int(b)}" for a, b in zip(fr.ls_start, fr.ls_end)), '', 'model-derived (Ames GCM, 1996)', '')
    for scn, nm in (('typical', 'typical dust year'), ('storm_year', '2001 storm-year dust')):
        v = t['sun'][scn]; i = int(np.argmin(v))
        put(sid, 'Sunlight', f'Energy on flat ground, annual mean, {nm}', int(round(v.mean())), 'Wh/m2 per sol', 'computed (orbit geometry + orbital dust)', '')
        put(sid, 'Sunlight', f'Energy on flat ground, worst sol, {nm}', int(round(v[i])), 'Wh/m2 per sol', 'computed (orbit geometry + orbital dust)', f"at Ls {LS_SOL[i]:.0f}")
    put(sid, 'Sunlight', 'Daylight, shortest to longest', f"{t['dh'].min():.1f} to {t['dh'].max():.1f}", 'hours', 'computed (orbit geometry)',
        f"{int((t['dh'] == 0).sum())} sols of polar night" if (t['dh'] == 0).any() else '')
    for prm in ('Slopes and roughness', 'Rock abundance', 'Mineralogy', 'Ice depth'):
        put(sid, 'Terrain' if prm == 'Slopes and roughness' else 'Surface', prm, '', '', 'missing', 'not downloaded or compiled yet')
S = pd.DataFrame(S); S.to_csv(os.path.join(O, 'site_summary.csv'), index=False)
print('summary rows', len(S), '; provenance counts:', S.provenance.str.split(' ').str[0].value_counts().to_dict())

# ---------------------------------------------------------------- 7. data for the page
def clean(v):
    if isinstance(v, (np.floating, float)): return None if (v != v) else round(float(v), 3)
    if isinstance(v, (np.integer,)): return int(v)
    return v
clim = pd.read_csv(os.path.join(O, 'tes_dust_climatology.csv'))
nodes = list(range(-90, 91, 15)); grid = {}
for scn in ('typical', 'storm_year'):
    c = clim[(clim.scenario == scn) & (clim.n >= 4)]
    for col, key in (('dust610_median', 'dust'), ('ice_median', 'ice')):
        p = c.pivot(index='lat_node', columns='ls_bin', values=col).reindex(index=nodes, columns=B15)
        grid[f'{key}_{scn}'] = [[clean(v) for v in p.loc[n].values] for n in nodes]
sv = lambda sid, c: [clean(v) for v in ser[ser.site == sid].sort_values('ls_bin_start')[c].values]
page = dict(
    generated='2026-11-14', h_scale=H_SCALE, p_err=round(P_ERR, 1), p_ref=[round(float(v), 1) for v in pcurve.values], p_ref_elev=ELEV['vl1'],
    lat_nodes=nodes, dust_grid=grid,
    sites=[dict(id=s['id'], n=s['name'], m=s['mission'], k=s['kind'], lat=s['lat'], lon=s['lon'], el=ELEV[s['id']]) for s in m.SITES],
    series={sid: {c: sv(sid, c) for c in ('t_air_min', 't_air_max', 't_ground_min', 't_ground_max', 'p_mean', 'wind_mean', 'tau', 't_air_sols', 't_ground_sols', 'p_sols')} for sid in STATIONS},
    footpad=dict(min=sv('vl1', 't_footpad_min'), max=sv('vl1', 't_footpad_max')),
    gcm={s['id']: [dict(ls=float((r.ls_start + r.ls_end) / 2), tmin=float(r.ground_t_min_K), tmax=float(r.ground_t_max_K)) for _, r in gc[gc.site == s['id']].iterrows()] for s in m.SITES},
    coverage=cov.to_dict('records'),
    summary=[{k: (clean(v) if not isinstance(v, str) else v) for k, v in r.items()} for r in S.fillna('').to_dict('records')],
    check={sid: dict(mean_typ=int(round(site_tau[sid]['sun']['typical'].mean())), min_typ=int(round(site_tau[sid]['sun']['typical'].min())),
                     mean_storm=int(round(site_tau[sid]['sun']['storm_year'].mean())), min_storm=int(round(site_tau[sid]['sun']['storm_year'].min()))) for sid in site_tau},
    validation=dict(pressure=val.to_dict('records'), dust=dv.round(3).to_dict('records')))
json.dump(page, open(os.path.join(O, 'page_data.json'), 'w'), separators=(',', ':'))
print('page_data.json', os.path.getsize(os.path.join(O, 'page_data.json')), 'bytes')
print(pd.DataFrame(page['check']).T.to_string())
