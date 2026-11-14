"""Viking Lander 1 and 2: binned meteorology, daily pressure, optical depth and footpad temperature
-> outputs/vl1_daily.csv, vl2_daily.csv, *_seasonal.csv, *_diurnal_by_season.csv

Sources (PDS volumes vl_1001, vl_1002):
  vl_mbin.dat  VL1 sols 1-350: 25 equal bins per sol of pressure, zonal/meridional wind, air temperature
  vl_tbin.dat  VL2 sols 1-1050 (and VL1 1-45): same bins, with wind speed, flags and sample counts
  vl_avep.dat  daily pressure summary for the whole of both missions (VL1 sols 0-2245, VL2 0-1204)
  vl_opac.dat  optical depth from Sun images
  vl_avet.dat  daily footpad temperature (VL1 sols 1008-2245, VL2 1000-1050): a near-surface proxy, not air temperature
Air temperature is from the meteorology boom, 1.6 m above the surface.
"""
import os, datetime as dt
import numpy as np, pandas as pd
import marslib as m

LANDING = {'VL1': dt.datetime(1976, 7, 20, 11, 53), 'VL2': dt.datetime(1976, 9, 3, 22, 38)}
D = os.path.join(m.DATA, 'viking_met')

def bin_hour(b):               # 25 bins per sol -> local hour 0-23
    return np.floor((b - 0.5) * 24.0 / 25.0).astype(int)

# --- binned meteorology
mb = pd.read_csv(os.path.join(D, 'vl_mbin.dat'), sep=r'\s+', header=None,
                 names=['sc', 'vy', 'ls', 'sol', 'bin', 'p_mbar', 'u', 'v', 't'])
mb['wind'] = np.hypot(mb.u, mb.v)          # speed of the bin-mean wind vector (lower than the mean speed)
spec = {'sc': (0, 4), 'vy': (4, 6), 'ls': (6, 14), 'sol': (14, 19), 'bin': (19, 22), 'nwind': (22, 27), 'npress': (32, 37),
        'wflag': (61, 64), 'wspd': (64, 70), 'p_mbar': (76, 82), 'pflag': (82, 85), 't': (85, 92), 'tflag': (99, 102)}
tb = pd.read_fwf(os.path.join(D, 'vl_tbin.dat'), colspecs=list(spec.values()), names=list(spec.keys()), header=None,
                 dtype={'wflag': str, 'pflag': str, 'tflag': str}, keep_default_na=False, na_values=[])
for f in ('wflag', 'pflag', 'tflag'): tb[f] = tb[f].fillna('').astype(str).str.strip()
bad = lambda s: s.isin(['M', 'n', 'I'])
tb.loc[bad(tb.tflag) | (tb.t <= 0), 't'] = np.nan
tb.loc[bad(tb.pflag) | (tb.p_mbar <= 0), 'p_mbar'] = np.nan
tb.loc[bad(tb.wflag) | (tb.nwind == 0), 'wspd'] = np.nan
tb = tb.rename(columns={'wspd': 'wind'})
print('tbin flag counts T:', tb.tflag.value_counts().to_dict(), ' P:', tb.pflag.value_counts().to_dict(), ' W:', tb.wflag.value_counts().to_dict())

# --- daily pressure, opacity, footpad
ap = pd.read_csv(os.path.join(D, 'vl_avep.dat'), sep=r'\s+', header=None,
                 names=['sc', 'vy', 'ls', 'sol', 'pmean', 'pmin', 'prange', 'psig', 'gap', 'bh', 'bm', 'bs', 'eh', 'em', 'es', 'ber', 'flag'])
ap = ap.replace({-9.999: np.nan})
op = pd.read_csv(os.path.join(D, 'vl_opac.dat'), sep=r'\s+', header=None,
                 names=['sc', 'cam', 'vy', 'sol', 'hr', 'mn', 'tau', 'flag', 'eday', 'ls', 'e1', 'e2', 'e3', 'e4', 'etot'])
print('opacity flag counts:', op.groupby(['sc', 'flag']).tau.agg(['count', 'median']).round(2).to_dict('index'))
ft = pd.read_csv(os.path.join(m.DATA, 'viking_footpad', 'vl_avet.dat'), sep=r'\s+', header=None,
                 names=['sc', 'vy', 'ls', 'sol', 'tmean', 'tmin', 'trange', 'tsig', 'gap', 'bh', 'bm', 'bs', 'eh', 'em', 'es', 'flag'])
ft = ft.replace({-9.99: np.nan})

for sc, sid in (('VL1', 'vl1'), ('VL2', 'vl2')):
    src = mb[mb.sc == sc] if sc == 'VL1' else tb[tb.sc == sc]
    h = src[['sol', 'bin', 'ls', 't', 'p_mbar', 'wind']].copy()
    h['hour'] = bin_hour(h['bin'].to_numpy())
    h = h.groupby(['sol', 'hour'], as_index=False).agg(ls_deg=('ls', 'mean'), t_air=('t', 'mean'), p_mbar=('p_mbar', 'mean'), wind=('wind', 'mean'))
    h['p'] = h.p_mbar * 100.0
    h = h[h[['t_air', 'p', 'wind']].notna().any(axis=1)]
    h.drop(columns='p_mbar').round(3).to_csv(os.path.join(m.OUT, f'{sid}_hourly.csv'), index=False)
    daily = m.hourly_to_daily(h.assign(n=1))
    # pressure for the whole mission from the daily summary file (overrides the binned subset)
    a = ap[ap.sc == sc].set_index('sol')
    daily = daily.set_index('sol').reindex(sorted(set(daily.sol) | set(a.index)))
    daily['p_mean_Pa'] = (a.pmean * 100).round(1)
    daily['p_min_Pa'] = (a.pmin * 100).round(1)
    daily['p_max_Pa'] = ((a.pmin + a.prange) * 100).round(1)
    daily['p_gap_flag'] = a.flag
    # a daily pressure mean is trustworthy when the largest data gap is under 4 hours (flag BB) -> count as full coverage
    daily['p_hours'] = np.where(a.flag.reindex(daily.index) == 'BB', 24, np.where(daily.p_mean_Pa.notna(), 12, 0))
    o = op[(op.sc == sc) & (op.flag == 0)].groupby('sol').tau.median()
    daily['tau_dust'] = o.reindex(daily.index).round(3)
    oany = op[op.sc == sc].groupby('sol').tau.min()
    daily['tau_dust_incl_limits'] = oany.reindex(daily.index).round(3)
    f = ft[ft.sc == sc].set_index('sol')
    daily['t_footpad_min_K'] = f.tmin.reindex(daily.index)
    daily['t_footpad_max_K'] = (f.tmin + f.trange).reindex(daily.index)
    daily['t_footpad_mean_K'] = f.tmean.reindex(daily.index)
    daily['t_footpad_gap_flag'] = f.flag.reindex(daily.index)
    # season: Ls from the files where present, otherwise from the date
    lsmap = pd.concat([src.groupby('sol').ls.mean(), a.ls, f.ls]).groupby(level=0).first()
    daily['ls_deg'] = lsmap.reindex(daily.index)
    days = np.array([m.days_j2000(LANDING[sc]) + s * m.SOL_SECONDS / 86400.0 for s in daily.index])
    miss = daily.ls_deg.isna()
    daily.loc[miss, 'ls_deg'] = m.ls_from_days(days[miss.to_numpy()])
    daily['mars_year'] = [m.mars_year_from_days(d, l) for d, l in zip(days, daily.ls_deg)]
    daily = daily.reset_index().rename(columns={'index': 'sol'})
    for c in ('hours_covered', 'n_records'): daily[c] = daily[c].fillna(0).astype(int)
    daily['ls_deg'] = daily.ls_deg.round(2)
    m.write_daily(daily, sid)
    s = m.seasonal_summary(daily, sid)
    m.seasonal_diurnal(h, sid)
    full = daily[daily.t_air_hours >= m.MIN_HOURS]
    print(f"\n{sc}: sols {daily.sol.min()}-{daily.sol.max()}  rows {len(daily)}  air-T sols {daily.t_air_min_K.notna().sum()} (full {len(full)})"
          f"  pressure sols {daily.p_mean_Pa.notna().sum()}  tau sols {daily.tau_dust.notna().sum()}  footpad sols {daily.t_footpad_mean_K.notna().sum()}")
    print(f"  air T: daily min {full.t_air_min_K.min():.1f}..{full.t_air_min_K.max():.1f}  daily max {full.t_air_max_K.min():.1f}..{full.t_air_max_K.max():.1f} K;"
          f"  pressure {daily.p_mean_Pa.min():.0f}..{daily.p_mean_Pa.max():.0f} Pa;  tau {daily.tau_dust.min():.2f}..{daily.tau_dust.max():.2f};"
          f"  Mars years {sorted(daily.mars_year.unique())}")
    print(s[['ls_bin_start', 'sols_with_data', 't_air_full_sols', 't_air_min_median_K', 't_air_max_median_K', 'p_mean_any_coverage_Pa', 'wind_mean_ms_median', 'tau_dust_median']].to_string(index=False))
