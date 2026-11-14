"""Shared helpers for the reduction scripts: Mars time, site list, common output schema.

Mars season (Ls) from an Earth date follows Allison & McEwen (2000), the algorithm behind NASA's Mars24.
Mars years follow the Clancy et al. convention: Mars Year 1 began at Ls 0 on 1955-04-11.
"""
import math, os, datetime as dt
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, 'data')
OUT = os.path.join(HERE, 'outputs')
SOL_SECONDS = 88775.244
YEAR_DAYS = 686.9725          # tropical Mars year in Earth days
YEAR_SOLS = 668.5921
J2000 = dt.datetime(2000, 1, 1, 12, 0, 0)
MY1_START = dt.datetime(1955, 4, 11)

_PBS = [(0.0071, 2.2353, 49.409), (0.0057, 2.7543, 168.173), (0.0039, 1.1177, 191.837), (0.0037, 15.7866, 21.736),
        (0.0021, 2.1354, 15.704), (0.0020, 2.4694, 95.528), (0.0018, 32.8493, 49.095)]

def ls_from_days(d):
    """Areocentric solar longitude (deg) from days since J2000 (TT; UTC is close enough). Works on arrays."""
    d = np.asarray(d, dtype=float)
    M = np.radians(19.3871 + 0.52402073 * d)
    afms = 270.3871 + 0.524038496 * d
    pbs = sum(A * np.cos(np.radians(0.985626 * d / tau + phi)) for A, tau, phi in _PBS)
    eoc = ((10.691 + 3.0e-7 * d) * np.sin(M) + 0.623 * np.sin(2 * M) + 0.050 * np.sin(3 * M)
           + 0.005 * np.sin(4 * M) + 0.0005 * np.sin(5 * M) + pbs)
    return (afms + eoc) % 360.0

def days_j2000(t):
    return (t - J2000).total_seconds() / 86400.0

def ls_from_utc(t):
    return float(ls_from_days(days_j2000(t)))

def year_fraction(ls):
    """Fraction of the Mars year elapsed since Ls 0, from Kepler's equation (e=0.0934, perihelion at Ls 251)."""
    e, lsp = 0.0934, math.radians(251.0)
    def mean_anom(L):
        nu = math.radians(L) - lsp
        E = 2 * math.atan2(math.sqrt(1 - e) * math.sin(nu / 2), math.sqrt(1 + e) * math.cos(nu / 2))
        return E - e * math.sin(E)
    return ((mean_anom(ls) - mean_anom(0.0)) / (2 * math.pi)) % 1.0

def mars_year_from_days(d, ls):
    """Mars Year number; uses Ls to place the year boundary exactly."""
    elapsed = (d + (J2000 - MY1_START).total_seconds() / 86400.0) / YEAR_DAYS
    return int(round(elapsed - year_fraction(ls))) + 1

def sol_of_year(ls):
    return year_fraction(ls) * YEAR_SOLS

def parse_lmst(series):
    """'SSSSSMHH:MM:SS.sss' strings (pandas Series) -> (sol int array, local mean solar hour float array)."""
    s = series.astype(str).str.strip().str.strip('"')
    parts = s.str.split('M', n=1, expand=True)
    sol = parts[0].astype(int).to_numpy()
    hms = parts[1].str.split(':', expand=True)
    hour = hms[0].astype(float).to_numpy() + hms[1].astype(float).to_numpy() / 60.0 + hms[2].astype(float).to_numpy() / 3600.0
    return sol, hour

# Site list. Latitude north-positive, longitude east-positive (0-360), elevation in km relative to the MOLA areoid.
# Coordinates and elevations are approximate published values (entered from memory; to be replaced by MOLA-derived values).
SITES = [
    dict(id='vl1', name='Chryse Planitia', mission='Viking 1', kind='Landed', lat=22.27, lon=312.05, elev=-3.6),
    dict(id='vl2', name='Utopia Planitia', mission='Viking 2', kind='Landed', lat=47.64, lon=134.29, elev=-4.5),
    dict(id='pathfinder', name='Ares Vallis', mission='Pathfinder', kind='Landed', lat=19.10, lon=326.75, elev=-3.7),
    dict(id='spirit', name='Gusev crater', mission='Spirit', kind='Landed', lat=-14.57, lon=175.47, elev=-1.9),
    dict(id='opportunity', name='Meridiani Planum', mission='Opportunity', kind='Landed', lat=-1.95, lon=354.47, elev=-1.4),
    dict(id='phoenix', name='Northern plains', mission='Phoenix', kind='Landed', lat=68.22, lon=234.25, elev=-4.1),
    dict(id='curiosity', name='Gale crater', mission='Curiosity', kind='Landed', lat=-4.59, lon=137.44, elev=-4.5),
    dict(id='insight', name='Elysium Planitia', mission='InSight', kind='Landed', lat=4.50, lon=135.62, elev=-2.6),
    dict(id='perseverance', name='Jezero crater', mission='Perseverance', kind='Landed', lat=18.44, lon=77.45, elev=-2.6),
    dict(id='zhurong', name='Utopia Planitia south', mission='Zhurong', kind='Landed', lat=25.07, lon=109.93, elev=-4.1),
    dict(id='oxia', name='Oxia Planum', mission='Rosalind Franklin (2030)', kind='Candidate', lat=18.20, lon=335.45, elev=-3.0),
    dict(id='arcadia', name='Arcadia Planitia', mission='crewed-landing studies', kind='Candidate', lat=40.0, lon=202.0, elev=-3.9),
]

DAILY_COLUMNS = ['sol', 'ls_deg', 'mars_year', 'hours_covered', 'n_records',
                 't_air_min_K', 't_air_max_K', 't_air_mean_K',
                 't_ground_min_K', 't_ground_max_K', 't_ground_mean_K',
                 'p_min_Pa', 'p_max_Pa', 'p_mean_Pa',
                 'wind_mean_ms', 'wind_max_ms', 'tau_dust']

def hourly_to_daily(h):
    """h: DataFrame with columns sol, hour (int 0-23) and any of t_air, t_ground, p, wind (hourly means),
    plus optional n. Returns one row per sol in the common schema. Min/max are of hourly means, so they are
    comparable between instruments with different sampling rates. Means are means of hourly means."""
    import pandas as pd
    rows = []
    for sol, g in h.groupby('sol'):
        r = {'sol': int(sol), 'hours_covered': int(g['hour'].nunique()), 'n_records': int(g['n'].sum()) if 'n' in g else len(g)}
        for src, pre in (('t_air', 't_air'), ('t_ground', 't_ground'), ('p', 'p')):
            if src in g and g[src].notna().any():
                unit = 'Pa' if src == 'p' else 'K'
                r[f'{pre}_min_{unit}'] = round(float(g[src].min()), 2)
                r[f'{pre}_max_{unit}'] = round(float(g[src].max()), 2)
                r[f'{pre}_mean_{unit}'] = round(float(g[src].mean()), 2)
                r[f'{pre}_hours'] = int(g[src].notna().sum())
        if 'wind' in g and g['wind'].notna().any():
            r['wind_mean_ms'] = round(float(g['wind'].mean()), 2)
            r['wind_max_ms'] = round(float(g['wind_max'].max() if 'wind_max' in g else g['wind'].max()), 2)
            r['wind_hours'] = int(g['wind'].notna().sum())
        rows.append(r)
    return pd.DataFrame(rows)

def write_daily(df, site_id):
    import pandas as pd
    extra = [c for c in df.columns if c not in DAILY_COLUMNS]
    for c in DAILY_COLUMNS:
        if c not in df: df[c] = np.nan
    df = df[DAILY_COLUMNS + extra].sort_values('sol')
    path = os.path.join(OUT, f'{site_id}_daily.csv')
    df.to_csv(path, index=False)
    return path

MIN_HOURS = 18   # a sol needs this many of its 24 local hours observed before its min/max count as daily extremes

def seasonal_summary(daily, site_id, min_hours=MIN_HOURS):
    """12 bins of 30 deg Ls. Temperature extremes use only sols with >= min_hours hours of that quantity."""
    import pandas as pd
    d = daily.copy()
    d['ls_bin'] = (d['ls_deg'] // 30 * 30).astype('Int64')
    rows = []
    for b in range(0, 360, 30):
        g = d[d['ls_bin'] == b]
        r = {'ls_bin_start': b, 'ls_bin_end': b + 30, 'sols_with_data': len(g)}
        for q, unit in (('t_air', 'K'), ('t_ground', 'K'), ('p', 'Pa')):
            hrs = g.get(f'{q}_hours')
            ok = g[hrs >= min_hours] if hrs is not None else g.iloc[0:0]
            r[f'{q}_full_sols'] = len(ok)
            for stat in ('min', 'max', 'mean'):
                col = f'{q}_{stat}_{unit}'
                r[f'{q}_{stat}_median_{unit}'] = round(float(ok[col].median()), 1) if len(ok) and col in ok and ok[col].notna().any() else np.nan
            if q != 'p':
                r[f'{q}_coldest_{unit}'] = round(float(ok[f'{q}_min_{unit}'].min()), 1) if len(ok) and ok[f'{q}_min_{unit}'].notna().any() else np.nan
                r[f'{q}_warmest_{unit}'] = round(float(ok[f'{q}_max_{unit}'].max()), 1) if len(ok) and ok[f'{q}_max_{unit}'].notna().any() else np.nan
        # pressure daily means are usable with partial coverage too, but flag it
        if 'p_mean_Pa' in g and g['p_mean_Pa'].notna().any():
            r['p_mean_any_coverage_Pa'] = round(float(g['p_mean_Pa'].median()), 1)
        for col in ('wind_mean_ms', 'wind_max_ms', 'tau_dust'):
            r[col + '_median'] = round(float(g[col].median()), 2) if col in g and g[col].notna().any() else np.nan
        rows.append(r)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, f'{site_id}_seasonal.csv'), index=False)
    return out

def seasonal_diurnal(hourly, site_id):
    """Mean value per 30-deg Ls bin and local hour, from an hourly table with columns ls_deg, hour and data columns."""
    import pandas as pd
    h = hourly.copy()
    h['ls_bin_start'] = (h['ls_deg'] // 30 * 30).astype(int)
    cols = [c for c in ('t_air', 't_ground', 'p', 'wind') if c in h]
    g = h.groupby(['ls_bin_start', 'hour'])
    out = g[cols].mean().round(2)
    out['sols'] = g['sol'].nunique()
    out = out.reset_index()
    out.to_csv(os.path.join(OUT, f'{site_id}_diurnal_by_season.csv'), index=False)
    return out
