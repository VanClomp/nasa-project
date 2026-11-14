"""Phoenix lander: 512-second pressure/temperature averages, Sun-image dust opacity, telltale wind
-> outputs/phoenix_daily.csv, phoenix_hourly.csv, phoenix_seasonal.csv, phoenix_diurnal_by_season.csv

Sources: PDS volumes phmt_0001-3 (MET RDR "RML" tables), phxao_1001 (opacity), phxwnd_0001 (telltale).
Air temperature is the top-of-mast thermocouple (1000 mm above the deck, about 2 m above the ground).
Each RML label gives the start time (UTC), the local true solar time at start and the sol number;
the table's first column is seconds since that start.
"""
import os, re, glob, datetime as dt
import numpy as np, pandas as pd
import marslib as m

cols = ['dur', 'p', 'p_sd', 'p_min', 'p_max', 't250', 't250_sd', 't250_min', 't250_max', 't500', 't500_sd', 't500_min', 't500_max',
        't1000', 't1000_sd', 't1000_min', 't1000_max', 'tref', 'tref_sd', 'tref_min', 'tref_max', 'event']
frames = []
for lbl in sorted(glob.glob(os.path.join(m.DATA, 'phoenix_met', 'phmt_*', '*RML_*.LBL'))):
    txt = open(lbl, errors='replace').read()
    g = lambda k: re.search(r'^\s*' + k + r'\s*=\s*"?([^"\r\n]+)"?', txt, flags=re.M).group(1).strip()
    sol0 = int(g('PLANET_DAY_NUMBER')); hh, mm, ss = [float(x) for x in g('LOCAL_TRUE_SOLAR_TIME').split(':')]
    t0 = dt.datetime.strptime(g('START_TIME')[:19], '%Y-%m-%dT%H:%M:%S')
    d = pd.read_csv(lbl[:-4] + '.TAB', header=None, names=cols, skipinitialspace=True)
    lt = hh + mm / 60 + ss / 3600 + d.dur * 24.0 / m.SOL_SECONDS
    d['sol'] = sol0 + np.floor(lt / 24).astype(int)
    d['hour'] = np.floor(lt % 24).astype(int)
    d['days'] = m.days_j2000(t0) + d.dur / 86400.0
    frames.append(d)
r = pd.concat(frames, ignore_index=True)
print('RML records', len(r), 'files', len(frames))
for c in ('t250', 't500', 't1000'): r.loc[(r[c] < 140) | (r[c] > 300), c] = np.nan
r.loc[(r.p < 600) | (r.p > 950), 'p'] = np.nan
print(r[['p', 't250', 't500', 't1000', 'tref']].describe().round(1).loc[['count', 'min', '50%', 'max']].to_string())
r['ls'] = m.ls_from_days(r.days.to_numpy())
h = r.groupby(['sol', 'hour'], as_index=False).agg(ls_deg=('ls', 'mean'), t_air=('t1000', 'mean'), t_air_250mm=('t250', 'mean'),
                                                     p=('p', 'mean'), n=('dur', 'size'), days=('days', 'mean'))
# telltale wind
w = pd.concat([pd.read_csv(f, header=None, names=['sol', 'ltst', 'lmst', 'v', 'dvp', 'dvm', 'dir', 'ddir', 'exp', 'file'], skipinitialspace=True)
               for f in sorted(glob.glob(os.path.join(m.DATA, 'phoenix_wind', '*.TAB')))], ignore_index=True)
w['hour'] = np.floor(w.ltst * 24).astype(int) % 24
print('telltale records', len(w), 'sols', w.sol.nunique(), 'speed median/max', round(w.v.median(), 2), round(w.v.max(), 2))
wh = w.groupby(['sol', 'hour'], as_index=False).agg(wind=('v', 'mean'), wind_max=('v', 'max'))
h = h.merge(wh, on=['sol', 'hour'], how='outer')
# fill season for wind-only hours from the sol's known Ls
lsmap = h.groupby('sol').ls_deg.mean(); dmap = h.groupby('sol').days.mean()
h['ls_deg'] = h.ls_deg.fillna(h.sol.map(lsmap).interpolate())
h['n'] = h.n.fillna(0)
h.drop(columns='days').round(3).sort_values(['sol', 'hour']).to_csv(os.path.join(m.OUT, 'phoenix_hourly.csv'), index=False)
daily = m.hourly_to_daily(h)
# opacity at 887 nm, cumulative file through sol 151
f = os.path.join(m.DATA, 'phoenix_opacity', 'PHX_TAU887_151_20090414A.TAB')
rows = [ln for ln in open(f, errors='replace') if ln.lstrip().startswith('"')]
o = pd.DataFrame([[x.strip().strip('"') for x in ln.split(',')] for ln in rows], columns=['pid', 'ls', 'dist', 'lt', 'elev', 'flux', 'tau', 'err'])
for c in ('ls', 'lt', 'elev', 'tau', 'err'): o[c] = o[c].astype(float)
o = o[o.tau > 0]; o['sol'] = np.floor(o['lt']).astype(int)
print('opacity measurements', len(o), 'sols', o.sol.nunique(), 'tau median', round(o.tau.median(), 2), 'range', o.tau.min(), o.tau.max())
daily = daily.set_index('sol')
daily['tau_dust'] = o.groupby('sol').tau.median().reindex(daily.index).round(3)
sols = daily.index.to_numpy()
days0 = dmap.reindex(sols).interpolate(limit_direction='both').to_numpy()
daily['ls_deg'] = np.round(m.ls_from_days(days0), 2)
daily['mars_year'] = [m.mars_year_from_days(d, l) for d, l in zip(days0, daily.ls_deg)]
daily = daily.reset_index()
m.write_daily(daily, 'phoenix')
s = m.seasonal_summary(daily, 'phoenix')
m.seasonal_diurnal(h, 'phoenix')
full = daily[daily.t_air_hours >= m.MIN_HOURS]
print(f"sols {daily.sol.min()}-{daily.sol.max()} rows {len(daily)}; air-T sols {daily.t_air_min_K.notna().sum()} (full {len(full)}); Ls {daily.ls_deg.min()}-{daily.ls_deg.max()}; MY {sorted(daily.mars_year.unique())}")
print(f"air T daily min {full.t_air_min_K.min():.1f}..{full.t_air_min_K.max():.1f}, daily max {full.t_air_max_K.min():.1f}..{full.t_air_max_K.max():.1f} K; "
      f"pressure {daily.p_mean_Pa.min():.0f}..{daily.p_mean_Pa.max():.0f} Pa; wind sols {daily.wind_mean_ms.notna().sum()}")
print(s[s.sols_with_data > 0][['ls_bin_start', 'sols_with_data', 't_air_full_sols', 't_air_min_median_K', 't_air_max_median_K', 'p_mean_any_coverage_Pa', 'wind_mean_ms_median', 'tau_dust_median']].to_string(index=False))
dd = h.groupby('hour')[['t_air', 'p', 'wind']].mean().round(1)
print(dd.T.to_string())
