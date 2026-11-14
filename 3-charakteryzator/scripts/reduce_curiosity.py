"""Curiosity REMS (models-level reduced data, 'RMD' tables), every 10th sol of sols 10-1340
-> outputs/curiosity_daily.csv, curiosity_hourly.csv, curiosity_seasonal.csv, curiosity_diurnal_by_season.csv

Fields used (PDS4 label): LMST, AMBIENT_TEMP (estimated air temperature, booms at 1.6 m), BRIGHTNESS_TEMP
(ground temperature from the thermal sensor), PRESSURE, HORIZONTAL_WIND_SPEED, LOCAL_RELATIVE_HUMIDITY, UV_ABC.
Missing values are -999. Ground temperature is kept only when its confidence string shows power in range and the
rover still (bytes 0 and 2 = 1); values outside 140-330 K are dropped and hourly medians are used, because
single readings contain occasional unphysical spikes.
"""
import os, glob
import numpy as np, pandas as pd
import marslib as m

names = ['ts', 'lmst', 'ltst', 'wsh', 'wsv', 'wdir', 'wconf', 'tb', 'tb_lu', 'tb_su', 'gconf', 't1', 't1c', 't2', 't2c', 'ta', 'tac',
         'uva', 'uvb', 'uvc', 'uvabc', 'uvd', 'uve', 'ua', 'ub', 'uc', 'uabc', 'ud', 'ue', 'uvconf', 'rh', 'hst', 'rhu', 'vmr', 'vmru',
         'hconf', 'pcfg', 'p', 'pu', 'pconf']
use = ['ts', 'lmst', 'wsh', 'tb', 'gconf', 'ta', 'uvabc', 'rh', 'p']
hourly = []
files = sorted(glob.glob(os.path.join(m.DATA, 'curiosity_rems', '*.TAB')))
for f in files:
    d = pd.read_csv(f, header=None, names=names, usecols=use, quotechar='"', skipinitialspace=True,
                    na_values=[-999.0, -999], dtype={'gconf': str, 'lmst': str}, low_memory=False)
    d['sol'], hr = m.parse_lmst(d.lmst)
    d['hour'] = np.floor(hr).astype(int)
    g = d.gconf.fillna('').str.strip()
    ok_g = (g.str.len() == 4) & (g.str[0] == '1') & (g.str[2] == '1')
    d['tb_all'] = d.tb.where((d.tb > 140) & (d.tb < 330))
    d['tb'] = d.tb_all.where(ok_g)
    d['tb_noshadow'] = d.tb_all.where(g == '1111')
    d.loc[(d.ta < 140) | (d.ta > 320), 'ta'] = np.nan
    d.loc[(d.p < 500) | (d.p > 1100), 'p'] = np.nan
    h = d.groupby(['sol', 'hour'], as_index=False).agg(
        days=('ts', lambda x: x.mean() / 86400.0), t_air=('ta', 'median'), t_ground=('tb', 'median'), t_ground_noshadow=('tb_noshadow', 'median'),
        p=('p', 'mean'), wind=('wsh', 'mean'), wind_max=('wsh', 'max'), wind_n=('wsh', 'count'), rh=('rh', 'max'), uv_abc=('uvabc', 'max'), n=('ts', 'size'))
    hourly.append(h)
h = pd.concat(hourly, ignore_index=True)
# a file can spill a few seconds into the neighbouring sol; keep sols that have real coverage
keep = h.groupby('sol').n.sum(); h = h[h.sol.isin(keep[keep > 2000].index)]
h['ls_deg'] = m.ls_from_days(h.days.to_numpy())
h.drop(columns='days').round(3).to_csv(os.path.join(m.OUT, 'curiosity_hourly.csv'), index=False)
daily = m.hourly_to_daily(h)
x = h.groupby('sol').agg(days=('days', 'mean'), rh_max_pct=('rh', 'max'), uv_abc_max_Wm2=('uv_abc', 'max'), wind_records=('wind_n', 'sum'),
                         t_ground_noshadow_min_K=('t_ground_noshadow', 'min'), t_ground_noshadow_max_K=('t_ground_noshadow', 'max'),
                         t_ground_noshadow_hours=('t_ground_noshadow', 'count'))
daily = daily.merge(x.reset_index(), on='sol')
daily['ls_deg'] = np.round(m.ls_from_days(daily.days.to_numpy()), 2)
daily['mars_year'] = [m.mars_year_from_days(d, l) for d, l in zip(daily.days, daily.ls_deg)]
daily = daily.drop(columns='days')
m.write_daily(daily, 'curiosity')
s = m.seasonal_summary(daily, 'curiosity')
m.seasonal_diurnal(h, 'curiosity')
print('files', len(files), 'sols', len(daily), 'range', daily.sol.min(), daily.sol.max(), 'MY', sorted(daily.mars_year.unique()))
print('full-coverage sols: air', (daily.t_air_hours >= m.MIN_HOURS).sum(), 'ground', (daily.t_ground_hours >= m.MIN_HOURS).sum(),
      'ground no-shadow', (daily.t_ground_noshadow_hours >= m.MIN_HOURS).sum(), 'pressure', (daily.p_hours >= m.MIN_HOURS).sum())
print('wind records per sol: median', daily.wind_records.median(), 'of', int(daily.n_records.median()), 'records')
f = daily[daily.t_air_hours >= m.MIN_HOURS]
print(f"air T daily min {f.t_air_min_K.min():.1f}..{f.t_air_min_K.max():.1f}, max {f.t_air_max_K.min():.1f}..{f.t_air_max_K.max():.1f} K")
f = daily[daily.t_ground_hours >= m.MIN_HOURS]
print(f"ground T daily min {f.t_ground_min_K.min():.1f}..{f.t_ground_min_K.max():.1f}, max {f.t_ground_max_K.min():.1f}..{f.t_ground_max_K.max():.1f} K")
print(f"pressure daily mean {daily.p_mean_Pa.min():.0f}..{daily.p_mean_Pa.max():.0f} Pa; RH max {daily.rh_max_pct.max():.0f}%; UV max {daily.uv_abc_max_Wm2.max():.1f} W/m2")
print(s[['ls_bin_start', 'sols_with_data', 't_air_full_sols', 't_air_min_median_K', 't_air_max_median_K', 't_ground_full_sols', 't_ground_min_median_K', 't_ground_max_median_K', 'p_mean_median_Pa', 'wind_mean_ms_median']].to_string(index=False))
print(h.groupby('hour')[['t_air', 't_ground', 'p']].mean().round(1).T.to_string())
