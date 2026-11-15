"""Calibrate the one free parameter of the ground-temperature model (downward infrared coefficient) on Curiosity's
measured ground temperatures, then test it, unchanged, on Perseverance. Writes outputs/thermal_model_validation.csv."""
import os, numpy as np, pandas as pd
import mars_climate as mc, mars_maps as mm, marslib as m
st = pd.read_csv(os.path.join(m.OUT, 'station_series.csv'))
S = {s['id']: s for s in m.SITES}
def model(site, ir):
    s = S[site]; ls = np.arange(0, 360, 15) + 7.5
    t = mm.terrain(s['lat'], s['lon']); p = mc.pressure_pa(ls, t['elevation_m'])
    return mc.ground_temps(s['lat'], ls, mm.albedo(s['lat'], s['lon']), mm.thermal_inertia(s['lat'], s['lon'])[0], p, mc.total_tau(s['lat'], ls, p), ir_coef=ir)
def errs(site, ir):
    g = st[st.site == site].sort_values('ls_bin_start'); lo, hi, _ = model(site, ir)
    ok = g.t_ground_min.notna().to_numpy() & g.t_ground_max.notna().to_numpy()
    return lo[ok] - g.t_ground_min.to_numpy()[ok], hi[ok] - g.t_ground_max.to_numpy()[ok]
grid = np.round(np.arange(0.00, 0.161, 0.01), 3)
score = []
for ir in grid:
    a, b = errs('curiosity', ir); score.append(np.sqrt(np.mean(np.r_[a, b] ** 2)))
best = float(grid[int(np.argmin(score))])
rows = []
for site, role in (('curiosity', 'calibration'), ('perseverance', 'independent test')):
    a, b = errs(site, best)
    rows.append(dict(site=site, role=role, ir_coef=best, seasons=len(a), tmin_bias_K=round(a.mean(), 1), tmin_rms_K=round(np.sqrt((a ** 2).mean()), 1),
                     tmax_bias_K=round(b.mean(), 1), tmax_rms_K=round(np.sqrt((b ** 2).mean()), 1)))
v = pd.DataFrame(rows); v.to_csv(os.path.join(m.OUT, 'thermal_model_validation.csv'), index=False)
print('rms by coefficient:', dict(zip(grid.tolist(), np.round(score, 1).tolist())))
print(v.to_string(index=False))
