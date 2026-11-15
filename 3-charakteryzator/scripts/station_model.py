"""Local model: forecasts a Mars landing site's surface weather for any date from that site's own station records only.

For every station site and every quantity it recorded (air / ground temperature min-max-mean, pressure, wind, dust
optical depth), the daily values of all its Mars years are fitted with a seasonal curve in solar longitude Ls:

    y(Ls) = a0 + sum_{n=1..N} ( a_n cos(n Ls) + b_n sin(n Ls) )

The order N (1-3) is chosen by leave-one-Mars-year-out cross-validation where the station has two or more Mars years,
otherwise N = 2 for a full-year record and N = 1 for a record of a few months. Nothing from other sites or from the
global predictor enters the fit. Mars weather repeats closely from year to year (outside global dust storms), so the
fitted seasonal curve is the forecast for the same Ls in any future year.

Forecast band (low / high) = the fitted value plus the 10th / 90th percentile of the residuals of that Mars month
(day-to-day weather plus year-to-year differences), or of all residuals if the month has few sols.

Only months the station actually observed (>= MIN_SOLS sols) are forecast; elsewhere the site falls back to the
global predictor. Validation: python3 scripts/station_model.py -> outputs/local_model_validation.csv
"""
import os, sys
from functools import lru_cache
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import marslib as m

MIN_SOLS = 3            # a Mars month needs this many observed sols before the local model forecasts it
MIN_HOURS = m.MIN_HOURS

# site -> list of (daily file, quantities, optional row filter); same files and filters as the station records
FILES = {
    'vl1': [('vl1_daily.csv', ['air', 'p', 'wind', 'tau'], None)],
    'vl2': [('vl2_daily.csv', ['air', 'p', 'wind', 'tau'], None)],
    'pathfinder': [('pathfinder_daily.csv', ['air', 'p'], None)],
    'phoenix': [('phoenix_daily.csv', ['air', 'p', 'wind', 'tau'], None)],
    'curiosity': [('curiosity_daily.csv', ['air', 'ground', 'p'], None)],
    'insight': [('insight_twins_daily.csv', ['air', 'wind'], None), ('insight_daily.csv', ['p'], None)],
    'perseverance': [('perseverance_air_daily.csv', ['air'], None),
                     ('perseverance_daily.csv', ['ground', 'wind'], None),
                     ('perseverance_daily.csv', ['p'], lambda d: d.sol < 669)],   # later sols: rover climbed the crater rim
}
# quantity -> (parameter name, unit, decimals)
QUANT = {
    'air_temp_min': ('K', 1), 'air_temp_max': ('K', 1), 'air_temp_mean': ('K', 1),
    'ground_temp_min': ('K', 1), 'ground_temp_max': ('K', 1), 'ground_temp_mean': ('K', 1),
    'pressure': ('Pa', 0), 'wind_mean': ('m/s', 1), 'dust_tau': ('optical depth (visible)', 2),
}

@lru_cache(None)
def _read(f): return pd.read_csv(os.path.join(m.OUT, f))

def _series(site):
    """{quantity: DataFrame(ls, y, my)} of the site's daily values, with the station-record quality filters."""
    out = {}
    for f, kinds, filt in FILES.get(site, []):
        d = _read(f)
        if filt is not None: d = d[filt(d)]
        my = d['mars_year'] if 'mars_year' in d else pd.Series(np.nan, index=d.index)
        def add(q, mask, col):
            g = d[mask & d[col].notna()]
            if len(g): out[q] = pd.DataFrame(dict(ls=g.ls_deg.to_numpy(float), y=g[col].to_numpy(float), my=my[g.index].to_numpy(float)))
        if 'air' in kinds and 't_air_hours' in d:
            ok = d.t_air_hours >= MIN_HOURS
            for s in ('min', 'max', 'mean'): add(f'air_temp_{s}', ok, f't_air_{s}_K')
        if 'ground' in kinds and 't_ground_hours' in d:
            ok = d.t_ground_hours >= MIN_HOURS
            for s in ('min', 'max', 'mean'): add(f'ground_temp_{s}', ok, f't_ground_{s}_K')
        if 'p' in kinds: add('pressure', d.p_mean_Pa.notna(), 'p_mean_Pa')
        if 'wind' in kinds and 'wind_hours' in d: add('wind_mean', d.wind_hours >= 12, 'wind_mean_ms')
        if 'tau' in kinds and 'tau_dust' in d: add('dust_tau', d.tau_dust.notna(), 'tau_dust')
    return out

def _design(ls, n):
    x = np.radians(np.asarray(ls, float))
    cols = [np.ones_like(x)]
    for k in range(1, n + 1): cols += [np.cos(k * x), np.sin(k * x)]
    return np.stack(cols, axis=1)

def _fit(ls, y, n, ridge=1e-3):
    A = _design(ls, n)
    reg = ridge * len(y) * np.eye(A.shape[1]); reg[0, 0] = 0.0            # tiny ridge keeps short records stable
    return np.linalg.solve(A.T @ A + reg, A.T @ y)

def _months(ls): return (np.asarray(ls) // 30).astype(int) + 1

def _loyo(df, n):
    """Leave-one-Mars-year-out: RMSE of monthly means of the held-out year, forecast from the other years."""
    err = []
    for yr in np.unique(df.my[np.isfinite(df.my)]):
        tr, te = df[df.my != yr], df[df.my == yr]
        if len(tr) < 2 * n + 4 or len(te) == 0: continue
        c = _fit(tr.ls, tr.y, n)
        for k in np.unique(_months(te.ls)):
            t = te[_months(te.ls) == k]
            if len(t) < MIN_SOLS or not (_months(tr.ls) == k).any(): continue     # only months the training years saw
            err.append(float((_design(t.ls, n) @ c).mean() - t.y.mean()))
    return float(np.sqrt(np.mean(np.square(err)))) if err else None, len(err)

@lru_cache(None)
def site_models(site):
    """{quantity: model dict} for one site. Model: coef, order, covered months, residual percentiles per month."""
    models = {}
    for q, df in _series(site).items():
        cnt = np.bincount(_months(df.ls), minlength=13)
        covered = [k for k in range(1, 13) if cnt[k] >= MIN_SOLS]
        if not covered or len(df) < 8: continue
        years = np.unique(df.my[np.isfinite(df.my)])
        if len(years) >= 2:
            cands = [(n, _loyo(df, n)[0]) for n in (1, 2, 3) if len(df) >= 4 * (2 * n + 1)]
            cands = [c for c in cands if c[1] is not None]
            n = min(cands, key=lambda c: c[1])[0] if cands else (2 if len(covered) >= 9 else 1)
        else:
            n = 2 if len(covered) >= 9 else 1
        coef = _fit(df.ls, df.y, n)
        res = df.y.to_numpy() - _design(df.ls, n) @ coef
        mk = _months(df.ls)
        q_all = (float(np.percentile(res, 10)), float(np.percentile(res, 90)))
        band = {k: ((float(np.percentile(res[mk == k], 10)), float(np.percentile(res[mk == k], 90))) if (mk == k).sum() >= 8 else q_all)
                for k in covered}
        models[q] = dict(coef=coef, order=n, covered=covered, band=band, n_sols=int(len(df)),
                         years=[int(y) for y in years], ls_range=(float(df.ls.min()), float(df.ls.max())))
    return models

def predict(site, q, ls):
    """(value, low, high) forecast of quantity q at solar longitude ls (scalar or array, averaged), or None outside
    the months the station observed."""
    mod = site_models(site).get(q)
    if mod is None: return None
    ls = np.atleast_1d(np.asarray(ls, float)) % 360
    k = int(_months(ls.mean() if np.ptp(ls) < 180 else ls[0])[()])
    if k not in mod['covered']: return None
    v = float((_design(ls, mod['order']) @ mod['coef']).mean())
    lo, hi = mod['band'][k]
    return v, v + lo, v + hi

def describe(site, q):
    mod = site_models(site)[q]
    yrs = f"Mars years {mod['years'][0]}-{mod['years'][-1]}" if len(mod['years']) > 1 else (f"Mars year {mod['years'][0]}" if mod['years'] else 'its mission')
    return (f"local model: seasonal fit (order {mod['order']}) to {mod['n_sols']} sols of {site} records, {yrs}; "
            f"band = 10-90% of past departures from the fit")

def month_params(site, k, ls=None):
    """Local-model forecasts for Mars month k (or at the exact Ls if given) as parameter dicts; {} if none."""
    out = {}
    a = 30.0 * (k - 1)
    at = [ls] if ls is not None else np.linspace(a + 0.5, a + 29.5, 30)
    for q, (unit, nd) in QUANT.items():
        r = predict(site, q, at)
        if r is None: continue
        v, lo, hi = r
        if q in ('wind_mean', 'dust_tau'): v, lo = max(v, 0.0), max(lo, 0.0)
        rd = lambda x: round(float(x), nd)
        out[q] = dict(value=rd(v), low=rd(lo), high=rd(hi), unit=unit, measured=False, basis='local', source=describe(site, q))
    # keep min <= mean <= max after independent fits
    for pre in ('air_temp', 'ground_temp'):
        if all(f'{pre}_{s}' in out for s in ('min', 'mean', 'max')):
            lo_, me, hi_ = (out[f'{pre}_{s}']['value'] for s in ('min', 'mean', 'max'))
            out[f'{pre}_mean']['value'] = round(min(max(me, lo_), hi_), 1)
    return out

# ------------------------------------------------------------------ validation
def validate():
    """Leave-one-Mars-year-out forecast error of the local model vs the global predictor at the same site and month."""
    import mars_model as mm
    rows = []
    gmap = {'ground_temp_min': 'ground_temp_min', 'ground_temp_max': 'ground_temp_max', 'air_temp_min': 'air_temp_min',
            'air_temp_max': 'air_temp_max', 'pressure': 'pressure', 'dust_tau': 'dust_tau'}
    for s in m.SITES:
        site = s['id']
        if site not in FILES: continue
        st = mm.point_static(s['lat'], s['lon'] % 360)
        glob = {k: mm.derived(mm.point_month_model(s['lat'], s['lon'] % 360, st, k)[0], False) for k in range(1, 13)}
        for q, df in _series(site).items():
            mod = site_models(site).get(q)
            if mod is None: continue
            years = np.unique(df.my[np.isfinite(df.my)])
            for yr in years if len(years) >= 2 else []:
                tr, te = df[df.my != yr], df[df.my == yr]
                c = _fit(tr.ls, tr.y, mod['order'])
                for k in np.unique(_months(te.ls)):
                    t = te[_months(te.ls) == k]
                    if len(t) < MIN_SOLS or not (_months(tr.ls) == k).any(): continue
                    obs = float(t.y.mean()); loc = float((_design(t.ls, mod['order']) @ c).mean())
                    g = glob[k].get(gmap.get(q, ''), {}).get('value') if q in gmap else None
                    rows.append(dict(site=site, quantity=q, held_out_mars_year=int(yr), month=int(k), sols=len(t), observed=round(obs, 2),
                                     local_forecast=round(loc, 2), global_predictor=None if g is None else round(float(g), 2)))
    v = pd.DataFrame(rows)
    v.to_csv(os.path.join(m.OUT, 'local_model_validation.csv'), index=False)
    v['err_local'] = (v.local_forecast - v.observed).abs(); v['err_global'] = (v.global_predictor - v.observed).abs()
    summ = v.groupby(['site', 'quantity']).agg(months=('month', 'size'), mae_local=('err_local', 'mean'), mae_global=('err_global', 'mean')).round(2)
    return v, summ

if __name__ == '__main__':
    pd.set_option('display.width', 160)
    for s in FILES:
        for q, mod in site_models(s).items():
            print(f"{s:13s} {q:16s} order {mod['order']}  sols {mod['n_sols']:5d}  months {mod['covered']}")
    _, summ = validate()
    print(summ.to_string())
