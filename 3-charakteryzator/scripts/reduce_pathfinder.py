"""Mars Pathfinder ASI/MET surface tables (PDS volume mpam_0001, surf_rdr/scidata)
-> outputs/pathfinder_daily.csv, pathfinder_hourly.csv, pathfinder_seasonal.csv, pathfinder_diurnal_by_season.csv

Each file is one data session: a header line (last value = Ls) followed by records of
sol, hour, minute, second (local solar time), top/mid/bottom mast air temperature (K; about 1.0, 0.5 and 0.25 m
up the mast), a descent thermocouple, and pressure in mbar from two transducers (the 6-10 mbar one is used).
The wind sensor columns are raw sensor temperatures, not wind speeds, so no wind is derived.
"""
import os, glob
import numpy as np, pandas as pd
import marslib as m
recs = []
for f in sorted(glob.glob(os.path.join(m.HERE, 'pathfinder_met', 'scidata', '*', '*.tab'))):
    with open(f) as fh: lines = fh.read().splitlines()
    if len(lines) < 2: continue
    try: ls = float(lines[0].split()[-1])
    except ValueError: continue
    for ln in lines[1:]:
        p = ln.split()
        if len(p) < 10: continue
        try: recs.append((int(p[0]), int(p[1]), float(p[4]), float(p[5]), float(p[6]), float(p[8]), ls))
        except ValueError: pass
r = pd.DataFrame(recs, columns=['sol', 'hour', 't_top', 't_mid', 't_bot', 'p_mbar', 'ls'])
r = r[(r.hour >= 0) & (r.hour <= 23)]
for c in ('t_top', 't_mid', 't_bot'): r.loc[(r[c] < 150) | (r[c] > 320), c] = np.nan
r.loc[(r.p_mbar < 5.5) | (r.p_mbar > 8.5), 'p_mbar'] = np.nan
h = r.groupby(['sol', 'hour'], as_index=False).agg(ls_deg=('ls', 'mean'), t_air=('t_top', 'mean'), t_air_025m=('t_bot', 'mean'), p_mbar=('p_mbar', 'mean'), n=('ls', 'size'))
h['p'] = h.p_mbar * 100.0
h = h.drop(columns='p_mbar')
h.round(3).to_csv(os.path.join(m.OUT, 'pathfinder_hourly.csv'), index=False)
daily = m.hourly_to_daily(h)
daily['ls_deg'] = daily.sol.map(h.groupby('sol').ls_deg.mean()).round(2)
daily['mars_year'] = 23
m.write_daily(daily, 'pathfinder')
s = m.seasonal_summary(daily, 'pathfinder')
m.seasonal_diurnal(h, 'pathfinder')
full = daily[daily.t_air_hours >= m.MIN_HOURS]
print('records', len(r), 'sols', len(daily), 'range', daily.sol.min(), daily.sol.max(), 'Ls', daily.ls_deg.min(), daily.ls_deg.max(), 'full sols', len(full))
print(f"air T daily min {full.t_air_min_K.min():.1f}..{full.t_air_min_K.max():.1f}, max {full.t_air_max_K.min():.1f}..{full.t_air_max_K.max():.1f} K; pressure daily mean {daily.p_mean_Pa.min():.0f}..{daily.p_mean_Pa.max():.0f} Pa")
print(s[s.sols_with_data > 0][['ls_bin_start', 'sols_with_data', 't_air_full_sols', 't_air_min_median_K', 't_air_max_median_K', 'p_full_sols', 'p_mean_median_Pa', 'p_mean_any_coverage_Pa']].to_string(index=False))
print('sols by hours covered:', daily.hours_covered.value_counts(bins=[0, 5, 11, 17, 24]).sort_index().to_dict())
