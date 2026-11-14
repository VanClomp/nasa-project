"""Air temperature (about 1-2 m) from modelled ground temperature, fitted on all seven weather stations.
Daily air min = a + b * ground min; air max = c + d * ground max. Tested leave-one-station-out.
Writes outputs/air_model_fit.json and outputs/air_model_validation.csv."""
import os, json, numpy as np, pandas as pd
import mars_climate as mc, mars_maps as mm, marslib as m
S = {s['id']: s for s in m.SITES}; B = np.arange(0, 360, 15)
st = pd.read_csv(os.path.join(m.OUT, 'station_series.csv'))
def from_daily(f):
    d = pd.read_csv(os.path.join(m.OUT, f)); d = d[d.t_air_hours >= m.MIN_HOURS].copy(); d['b'] = (d.ls_deg // 15 * 15).astype(int)
    g = d.groupby('b').agg(t_air_min=('t_air_min_K', 'median'), t_air_max=('t_air_max_K', 'median')).reindex(B)
    return g
air = {s: st[st.site == s].set_index('ls_bin_start')[['t_air_min', 't_air_max']].reindex(B) for s in ('vl1', 'vl2', 'pathfinder', 'phoenix', 'curiosity')}
air['insight'] = from_daily('insight_twins_daily.csv'); air['perseverance'] = from_daily('perseverance_air_daily.csv')
rows = []
for site, a in air.items():
    s = S[site]; ls = B + 7.5; t = mm.terrain(s['lat'], s['lon']); p = mc.pressure_pa(ls, t['elevation_m'])
    gmin, gmax, gmean = mc.ground_temps(s['lat'], ls, mm.albedo(s['lat'], s['lon']), mm.thermal_inertia(s['lat'], s['lon'])[0], p, mc.total_tau(s['lat'], ls, p))
    rows.append(pd.DataFrame(dict(site=site, ls_bin_start=B, g_min=gmin, g_max=gmax, a_min=a.t_air_min.to_numpy(), a_max=a.t_air_max.to_numpy())))
d = pd.concat(rows).dropna(); d.to_csv(os.path.join(m.OUT, 'air_model_training.csv'), index=False)
fit = lambda x, y: np.polyfit(x, y, 1)
res = []
for site in d.site.unique():
    tr, te = d[d.site != site], d[d.site == site]
    pmin, pmax = fit(tr.g_min, tr.a_min), fit(tr.g_max, tr.a_max)
    emin = np.polyval(pmin, te.g_min) - te.a_min; emax = np.polyval(pmax, te.g_max) - te.a_max
    res.append(dict(site=site, seasons=len(te), air_min_bias_K=round(emin.mean(), 1), air_min_rms_K=round(np.sqrt((emin ** 2).mean()), 1),
                    air_max_bias_K=round(emax.mean(), 1), air_max_rms_K=round(np.sqrt((emax ** 2).mean()), 1)))
v = pd.DataFrame(res); v.to_csv(os.path.join(m.OUT, 'air_model_validation.csv'), index=False)
pmin, pmax = fit(d.g_min, d.a_min), fit(d.g_max, d.a_max)
json.dump(dict(air_min=dict(intercept=round(pmin[1], 3), slope=round(pmin[0], 4)), air_max=dict(intercept=round(pmax[1], 3), slope=round(pmax[0], 4)),
               training_points=len(d), stations=sorted(d.site.unique().tolist())), open(os.path.join(m.OUT, 'air_model_fit.json'), 'w'), indent=1)
print('fit: air_min = %.1f + %.3f*ground_min ; air_max = %.1f + %.3f*ground_max  (%d station-seasons)' % (pmin[1], pmin[0], pmax[1], pmax[0], len(d)))
print('leave-one-station-out test:'); print(v.to_string(index=False))
