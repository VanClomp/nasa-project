"""Perseverance MEDA derived products, every 20th sol of sols 20-1840
-> outputs/perseverance_daily.csv, perseverance_hourly.csv, perseverance_seasonal.csv, perseverance_diurnal_by_season.csv

  DER_PS    pressure (Pa)
  DER_TIRS  upward and downward thermal (long-wave) flux in W/m2. Ground temperature is NOT in this product;
            it is recovered here as T = (F_up / sigma)^(1/4), following the label's statement that the upward flux
            assumes Stefan-Boltzmann emission from the ground. Treat it as a brightness temperature good to a few K.
            Only samples with the rover still are used; a second variant also requires the footprint out of the rover's shadow.
  DER_WS    wind speed (present only for sols 40-300 in this sample)
Air temperature is not in the derived products (it is in the calibrated 'ATS' product, not downloaded yet).
"""
import os, glob
import numpy as np, pandas as pd
import marslib as m
SIGMA = 5.670374e-8
D = os.path.join(m.DATA, 'perseverance_meda')
parts = []
for f in sorted(glob.glob(os.path.join(D, '*DER_PS_*.CSV'))):
    d = pd.read_csv(f, usecols=['SCLK', 'LMST', 'PRESSURE'])
    d['sol'], hr = m.parse_lmst(d.LMST); d['hour'] = np.floor(hr).astype(int)
    d.loc[(d.PRESSURE < 500) | (d.PRESSURE > 1000), 'PRESSURE'] = np.nan
    parts.append(d.groupby(['sol', 'hour'], as_index=False).agg(days=('SCLK', lambda x: x.mean() / 86400.0), p=('PRESSURE', 'mean'), n=('SCLK', 'size')))
hp = pd.concat(parts, ignore_index=True)
parts = []
for f in sorted(glob.glob(os.path.join(D, '*DER_TIRS_*.CSV'))):
    d = pd.read_csv(f, usecols=['SCLK', 'LMST', 'DOWNWARD_LW_IRRADIANCE', 'UPWARD_LW_IRRADIANCE', 'TIRS_GROUND_FOOTPRINT_NOT_IN_SHADOW', 'ROVER_STILL'])
    d['sol'], hr = m.parse_lmst(d.LMST); d['hour'] = np.floor(hr).astype(int)
    up = d.UPWARD_LW_IRRADIANCE.where((d.UPWARD_LW_IRRADIANCE > 20) & (d.UPWARD_LW_IRRADIANCE < 700) & (d.ROVER_STILL == 1))
    d['tg'] = (up / SIGMA) ** 0.25
    d['tg_ns'] = d.tg.where(d.TIRS_GROUND_FOOTPRINT_NOT_IN_SHADOW == 1)
    d['lwd'] = d.DOWNWARD_LW_IRRADIANCE.where((d.DOWNWARD_LW_IRRADIANCE > 0) & (d.DOWNWARD_LW_IRRADIANCE < 300))
    parts.append(d.groupby(['sol', 'hour'], as_index=False).agg(t_ground=('tg', 'median'), t_ground_noshadow=('tg_ns', 'median'), lw_down=('lwd', 'mean'),
                                                                 days_t=('SCLK', lambda x: x.mean() / 86400.0)))
ht = pd.concat(parts, ignore_index=True)
parts = []
for f in sorted(glob.glob(os.path.join(D, '*DER_WS_*.CSV'))):
    d = pd.read_csv(f, usecols=['LMST', 'HORIZONTAL_WIND_SPEED', 'ROVER_STILL'])
    d['sol'], hr = m.parse_lmst(d.LMST); d['hour'] = np.floor(hr).astype(int)
    v = d.HORIZONTAL_WIND_SPEED.where((d.HORIZONTAL_WIND_SPEED >= 0) & (d.HORIZONTAL_WIND_SPEED < 60) & (d.ROVER_STILL == 1))
    d['v'] = v
    parts.append(d.groupby(['sol', 'hour'], as_index=False).agg(wind=('v', 'mean'), wind_max=('v', lambda x: x.quantile(0.99))))
hw = pd.concat(parts, ignore_index=True)
h = hp.merge(ht, on=['sol', 'hour'], how='outer').merge(hw, on=['sol', 'hour'], how='outer')
h['days'] = h.days.fillna(h.days_t); h['n'] = h.n.fillna(0)
keep = h.groupby('sol').n.sum(); h = h[h.sol.isin(keep[keep > 2000].index)].copy()
h['ls_deg'] = m.ls_from_days(h.days.to_numpy())
# plausibility check: a sol whose hourly ground temperature leaves 150-305 K anywhere is rejected whole
# (two sols in this sample, 1560 and 1580, carry flux values that are physically impossible)
bad = h[(h.t_ground < 150) | (h.t_ground > 305)].sol.unique()
print('ground temperature rejected for sols:', sorted(bad))
h.loc[h.sol.isin(bad), ['t_ground', 't_ground_noshadow']] = np.nan
h.drop(columns=['days', 'days_t']).round(3).sort_values(['sol', 'hour']).to_csv(os.path.join(m.OUT, 'perseverance_hourly.csv'), index=False)
daily = m.hourly_to_daily(h)
x = h.groupby('sol').agg(days=('days', 'mean'), lw_down_mean_Wm2=('lw_down', 'mean'), lw_down_min_Wm2=('lw_down', 'min'), lw_down_max_Wm2=('lw_down', 'max'),
                         t_ground_noshadow_min_K=('t_ground_noshadow', 'min'), t_ground_noshadow_max_K=('t_ground_noshadow', 'max'),
                         t_ground_noshadow_hours=('t_ground_noshadow', 'count')).round(2)
daily = daily.merge(x.reset_index(), on='sol')
daily['ls_deg'] = np.round(m.ls_from_days(daily.days.to_numpy()), 2)
daily['mars_year'] = [m.mars_year_from_days(d, l) for d, l in zip(daily.days, daily.ls_deg)]
daily = daily.drop(columns='days')
m.write_daily(daily, 'perseverance')
s = m.seasonal_summary(daily, 'perseverance')
m.seasonal_diurnal(h, 'perseverance')
print('sols', len(daily), 'range', daily.sol.min(), daily.sol.max(), 'MY', sorted(daily.mars_year.unique()))
print('full-coverage sols: ground', (daily.t_ground_hours >= m.MIN_HOURS).sum(), 'ground no-shadow', (daily.t_ground_noshadow_hours >= m.MIN_HOURS).sum(),
      'pressure', (daily.p_hours >= m.MIN_HOURS).sum(), 'wind sols', daily.wind_mean_ms.notna().sum())
f = daily[daily.t_ground_hours >= m.MIN_HOURS]
print(f"ground T daily min {f.t_ground_min_K.min():.1f}..{f.t_ground_min_K.max():.1f}, max {f.t_ground_max_K.min():.1f}..{f.t_ground_max_K.max():.1f} K; "
      f"no-shadow max {f.t_ground_noshadow_max_K.min():.1f}..{f.t_ground_noshadow_max_K.max():.1f}")
print(f"pressure daily mean {daily.p_mean_Pa.min():.0f}..{daily.p_mean_Pa.max():.0f} Pa; wind mean {daily.wind_mean_ms.min():.1f}..{daily.wind_mean_ms.max():.1f}, max {daily.wind_max_ms.max():.1f} m/s; LW down {daily.lw_down_mean_Wm2.min():.0f}..{daily.lw_down_mean_Wm2.max():.0f} W/m2")
print(s[['ls_bin_start', 'sols_with_data', 't_ground_full_sols', 't_ground_min_median_K', 't_ground_max_median_K', 'p_full_sols', 'p_mean_median_Pa', 'wind_mean_ms_median']].to_string(index=False))
print(h.groupby('hour')[['t_ground', 't_ground_noshadow', 'p', 'wind', 'lw_down']].mean().round(1).T.to_string())
