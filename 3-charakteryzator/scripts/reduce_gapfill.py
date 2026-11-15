"""Reduce the gap-fill downloads to per-sol tables in the common schema.

Perseverance MEDA ATS (calibrated air temperature, every 20th sol): the three mast sensors (ATS 1-3, about 1.45 m)
  are combined with the median, which suppresses the sensor that sits downwind of the rover body.
  Rover-body sensors (ATS 4-5) are not used. Output: outputs/perseverance_air_daily.csv
InSight TWINS derived (air temperature both booms, horizontal wind, every 20th sol): boom mean, sol-long files.
  Output: outputs/insight_twins_daily.csv (+ _hourly.csv)
"""
import glob, os, numpy as np, pandas as pd
import marslib as m

def hourly(sol, hour, days, **cols):
    d = pd.DataFrame(dict(sol=sol, hour=np.floor(hour).astype(int), days=days, **cols))
    agg = {k: (k, 'mean') for k in cols}; agg['days'] = ('days', 'mean'); agg['n'] = ('sol', 'size')
    if 'wind' in cols: agg['wind_max'] = ('wind', 'max')
    return d.groupby(['sol', 'hour'], as_index=False).agg(**agg)

# ---------------- Perseverance air temperature
parts = []
for f in sorted(glob.glob(os.path.join(m.DATA, 'perseverance_meda_ats', '*CAL_ATS_*.CSV'))):
    d = pd.read_csv(f, usecols=['SCLK', 'LMST', 'ATS_LOCAL_TEMP1', 'ATS_LOCAL_TEMP2', 'ATS_LOCAL_TEMP3'], dtype={'LMST': str})
    t = d[['ATS_LOCAL_TEMP1', 'ATS_LOCAL_TEMP2', 'ATS_LOCAL_TEMP3']].where(lambda x: (x > 120) & (x < 320)).median(axis=1)
    sol, hr = m.parse_lmst(d.LMST)
    parts.append(hourly(sol, hr, d.SCLK.to_numpy() / 86400.0, t_air=t.to_numpy()))
h = pd.concat(parts); h['ls_deg'] = m.ls_from_days(h.days.to_numpy())
h.to_csv(os.path.join(m.OUT, 'perseverance_air_hourly.csv'), index=False)
daily = m.hourly_to_daily(h)
daily = daily.merge(h.groupby('sol', as_index=False).days.mean(), on='sol')
daily['ls_deg'] = np.round(m.ls_from_days(daily.days.to_numpy()), 2)
daily.drop(columns='days').to_csv(os.path.join(m.OUT, 'perseverance_air_daily.csv'), index=False)
full = daily[daily.t_air_hours >= m.MIN_HOURS]
print(f'Perseverance air: {len(daily)} sols, {len(full)} with 18+ hours, Ls bins covered: {sorted(set((full.ls_deg // 30 * 30).astype(int)))}')
print('  typical daily min/max K:', round(full.t_air_min_K.median(), 1), round(full.t_air_max_K.median(), 1))

# ---------------- InSight TWINS derived
def utc_days(s):
    t = pd.to_datetime(s.str.replace('Z', ''), format='%Y-%jT%H:%M:%S.%f')
    return ((t - pd.Timestamp('2000-01-01 12:00:00')).dt.total_seconds() / 86400.0).to_numpy()
parts = []
for f in sorted(glob.glob(os.path.join(m.DATA, 'insight_twins_derived', 'twins_model_*.csv'))):
    d = pd.read_csv(f, usecols=['LMST', 'UTC', 'HORIZONTAL_WIND_SPEED', 'BMY_AIR_TEMP', 'BPY_AIR_TEMP'], dtype={'LMST': str, 'UTC': str})
    t = d[['BMY_AIR_TEMP', 'BPY_AIR_TEMP']].where(lambda x: (x > 120) & (x < 320)).mean(axis=1)
    w = d.HORIZONTAL_WIND_SPEED.where((d.HORIZONTAL_WIND_SPEED >= 0) & (d.HORIZONTAL_WIND_SPEED < 60))
    sol, hr = m.parse_lmst(d.LMST)
    parts.append(hourly(sol, hr, utc_days(d.UTC), t_air=t.to_numpy(), wind=w.to_numpy()))
h = pd.concat(parts); h['ls_deg'] = m.ls_from_days(h.days.to_numpy())
h.to_csv(os.path.join(m.OUT, 'insight_twins_hourly.csv'), index=False)
daily = m.hourly_to_daily(h)
daily = daily.merge(h.groupby('sol', as_index=False).days.mean(), on='sol')
daily['ls_deg'] = np.round(m.ls_from_days(daily.days.to_numpy()), 2)
daily.drop(columns='days').to_csv(os.path.join(m.OUT, 'insight_twins_daily.csv'), index=False)
full = daily[daily.t_air_hours >= m.MIN_HOURS]
print(f'InSight TWINS: {len(daily)} sols, {len(full)} with 18+ hours, Ls bins covered: {sorted(set((full.ls_deg // 30 * 30).astype(int)))}')
print('  typical daily min/max K:', round(full.t_air_min_K.median(), 1), round(full.t_air_max_K.median(), 1), ' wind mean m/s:', round(daily.wind_mean_ms.median(), 1))
