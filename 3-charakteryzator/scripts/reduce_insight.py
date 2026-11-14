"""InSight APSS event-request products (ERP), low-rate versions: pressure sensor (ps_lr) and TWINS wind/air temperature (twins_lr)
-> outputs/insight_hourly.csv, insight_daily.csv, insight_seasonal.csv, insight_diurnal_by_season.csv, insight_coverage.csv

IMPORTANT: these files are NOT a continuous record. Each numbered file (erp_009 ... erp_620) is a window of data
requested around an event, lasting minutes to hours. The numbers are event numbers, not sols.
Hourly means are therefore built only for the (sol, hour) cells the windows happen to cover.
Air temperature: tip-of-rod sensors on the two booms (about 1.2 m above ground); for each sample the boom flagged
'not affected by the lander thermal plume' is preferred, otherwise both are averaged.
Wind: the boom flagged 'wind coming from the front' is preferred, otherwise both are averaged.
"""
import os, glob
import numpy as np, pandas as pd
import marslib as m
D = os.path.join(m.DATA, 'insight_lowrate')

def utc_days(s):   # '2018-348T06:49:53.019Z' -> days since J2000
    t = pd.to_datetime(s, format='%Y-%jT%H:%M:%S.%fZ')
    return (t - pd.Timestamp(m.J2000)).total_seconds() / 86400.0

ps, tw, cov = [], [], []
for f in sorted(glob.glob(os.path.join(D, 'erp_*', '*_ps_lr.csv'))):
    d = pd.read_csv(f, usecols=['SCLK', 'LMST', 'UTC', 'PRESSURE'], dtype={'LMST': str, 'UTC': str})
    if d.empty: continue
    d['sol'], hr = m.parse_lmst(d.LMST); d['hour'] = np.floor(hr).astype(int)
    d0 = utc_days(d.UTC.iloc[0]); d['days'] = d0 + (d.SCLK - d.SCLK.iloc[0]) / 86400.0
    d.loc[(d.PRESSURE < 500) | (d.PRESSURE > 1000), 'PRESSURE'] = np.nan
    cov.append(dict(file=os.path.basename(f), kind='pressure', first_sol=int(d.sol.iloc[0]), start_hour=round(float(hr[0]), 2),
                    duration_h=round(float((d.SCLK.iloc[-1] - d.SCLK.iloc[0]) / 3600.0), 2), records=len(d)))
    ps.append(d.groupby(['sol', 'hour'], as_index=False).agg(days=('days', 'mean'), psum=('PRESSURE', 'sum'), pn=('PRESSURE', 'count')))
cols = ['SCLK', 'LMST', 'UTC', 'BMY_HORIZONTAL_WIND_SPEED', 'BMY_WS_OPERATIONAL_FLAGS', 'BMY_TIP_ROD_TEMP', 'BMY_AIR_TEMP_OPERATIONAL_FLAGS',
        'BPY_HORIZONTAL_WIND_SPEED', 'BPY_WS_OPERATIONAL_FLAGS', 'BPY_TIP_ROD_TEMP', 'BPY_AIR_TEMP_OPERATIONAL_FLAGS']
for f in sorted(glob.glob(os.path.join(D, 'erp_*', '*_twins_lr.csv'))):
    d = pd.read_csv(f, usecols=cols, dtype={c: str for c in cols if 'FLAGS' in c or c in ('LMST', 'UTC')})
    if d.empty: continue
    d['sol'], hr = m.parse_lmst(d.LMST); d['hour'] = np.floor(hr).astype(int)
    d0 = utc_days(d.UTC.iloc[0]); d['days'] = d0 + (d.SCLK - d.SCLK.iloc[0]) / 86400.0
    def pick(a, b, fa, fb, pos, lo, hi):
        a = a.where((a > lo) & (a < hi)); b = b.where((b > lo) & (b < hi))
        ga = fa.fillna('').str.zfill(4 if pos == 2 and fa.name.startswith('BMY_AIR') else 3).str[pos] == '1'
        gb = fb.fillna('').str.zfill(4 if pos == 2 and fb.name.startswith('BPY_AIR') else 3).str[pos] == '1'
        both = pd.concat([a, b], axis=1).mean(axis=1)
        out = both.copy()
        out[ga & ~gb & a.notna()] = a[ga & ~gb & a.notna()]
        out[gb & ~ga & b.notna()] = b[gb & ~ga & b.notna()]
        return out, (ga | gb)
    d['t'], d['t_clean'] = pick(d.BMY_TIP_ROD_TEMP, d.BPY_TIP_ROD_TEMP, d.BMY_AIR_TEMP_OPERATIONAL_FLAGS, d.BPY_AIR_TEMP_OPERATIONAL_FLAGS, 2, 140, 320)
    d['w'], _ = pick(d.BMY_HORIZONTAL_WIND_SPEED, d.BPY_HORIZONTAL_WIND_SPEED, d.BMY_WS_OPERATIONAL_FLAGS, d.BPY_WS_OPERATIONAL_FLAGS, 2, -0.001, 60)
    cov.append(dict(file=os.path.basename(f), kind='twins', first_sol=int(d.sol.iloc[0]), start_hour=round(float(hr[0]), 2),
                    duration_h=round(float((d.SCLK.iloc[-1] - d.SCLK.iloc[0]) / 3600.0), 2), records=len(d)))
    tw.append(d.groupby(['sol', 'hour'], as_index=False).agg(days_t=('days', 'mean'), tsum=('t', 'sum'), tn=('t', 'count'), tclean=('t_clean', 'sum'),
                                                              wsum=('w', 'sum'), wn=('w', 'count'), wind_max=('w', 'max')))
pd.DataFrame(cov).to_csv(os.path.join(m.OUT, 'insight_coverage.csv'), index=False)
hp = pd.concat(ps).groupby(['sol', 'hour'], as_index=False).agg(days=('days', 'mean'), psum=('psum', 'sum'), pn=('pn', 'sum'))
ht = pd.concat(tw).groupby(['sol', 'hour'], as_index=False).agg(days_t=('days_t', 'mean'), tsum=('tsum', 'sum'), tn=('tn', 'sum'), tclean=('tclean', 'sum'),
                                                                 wsum=('wsum', 'sum'), wn=('wn', 'sum'), wind_max=('wind_max', 'max'))
h = hp.merge(ht, on=['sol', 'hour'], how='outer')
h['days'] = h.days.fillna(h.days_t)
h['p'] = h.psum / h.pn.where(h.pn >= 60)          # at least a minute of 2 Hz data (or equivalent) in the hour
h['t_air'] = h.tsum / h.tn.where(h.tn >= 30)
h['wind'] = h.wsum / h.wn.where(h.wn >= 30)
h['wind_max'] = h.wind_max.where(h.wn >= 30)
h['t_air_plume_free_fraction'] = (h.tclean / h.tn).round(2)
h['n'] = h.pn.fillna(0) + h.tn.fillna(0)
h['ls_deg'] = m.ls_from_days(h.days.to_numpy())
h = h[h[['p', 't_air', 'wind']].notna().any(axis=1)]
h[['sol', 'hour', 'ls_deg', 't_air', 'p', 'wind', 'wind_max', 't_air_plume_free_fraction', 'n']].round(3).sort_values(['sol', 'hour']).to_csv(os.path.join(m.OUT, 'insight_hourly.csv'), index=False)
daily = m.hourly_to_daily(h)
x = h.groupby('sol').agg(days=('days', 'mean'))
daily = daily.merge(x.reset_index(), on='sol')
daily['ls_deg'] = np.round(m.ls_from_days(daily.days.to_numpy()), 2)
daily['mars_year'] = [m.mars_year_from_days(d, l) for d, l in zip(daily.days, daily.ls_deg)]
daily = daily.drop(columns='days')
m.write_daily(daily, 'insight')
s = m.seasonal_summary(daily, 'insight')
sd = m.seasonal_diurnal(h, 'insight')
c = pd.DataFrame(cov)
print('event files: pressure', (c.kind == 'pressure').sum(), 'twins', (c.kind == 'twins').sum(), '; sols touched', daily.sol.nunique(), 'range', daily.sol.min(), daily.sol.max(), 'MY', sorted(daily.mars_year.unique()))
print('window length (h): median', c.duration_h.median(), 'p90', c.duration_h.quantile(.9), 'max', c.duration_h.max(), '; total hours pressure', round(c[c.kind == 'pressure'].duration_h.sum()), 'twins', round(c[c.kind == 'twins'].duration_h.sum()))
print('sol-hours with data: pressure', h.p.notna().sum(), 'air T', h.t_air.notna().sum(), 'wind', h.wind.notna().sum(), ' of', (daily.sol.max() - daily.sol.min() + 1) * 24, 'possible')
print('sols by hours covered (air T):', daily.t_air_hours.fillna(0).astype(int).value_counts(bins=[-1, 0, 5, 11, 17, 24]).sort_index().to_dict())
print('sols by hours covered (pressure):', daily.p_hours.fillna(0).astype(int).value_counts(bins=[-1, 0, 5, 11, 17, 24]).sort_index().to_dict())
print(s[['ls_bin_start', 'sols_with_data', 't_air_full_sols', 't_air_min_median_K', 't_air_max_median_K', 'p_full_sols', 'p_mean_median_Pa', 'p_mean_any_coverage_Pa', 'wind_mean_ms_median']].to_string(index=False))
piv = sd.pivot(index='ls_bin_start', columns='hour', values='sols').fillna(0).astype(int)
print('sols contributing per season (rows) and local hour (columns):'); print(piv.to_string())
