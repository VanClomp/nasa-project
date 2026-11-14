"""Point lookups in the lunar maps (data/moon, or MOON_DATA_DIR). Latitude deg N, longitude deg E.

Polar maps are polar stereographic (spherical, R = 1737.4 km, true scale at the pole); the finest map that covers a
point is used: 40 m (|lat| >= 85), 240 m (|lat| >= 75), otherwise the 16 px/deg (~1.9 km) global map.
"""
import os, re, glob, numpy as np, pandas as pd
from functools import lru_cache
MOON = os.environ.get('MOON_DATA_DIR') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'moon')
R_M = 1737400.0

def _lbl(path):
    t = open(path, errors='replace').read()
    g = lambda k, d=None: (re.search(r'^\s*' + k + r'\s*=\s*"?([-\d.Ee+]+)', t, re.M) or [None, d])[1]
    st = (re.search(r'SAMPLE_TYPE\s*=\s*(\w+)', t) or [None, 'LSB_INTEGER'])[1]
    return dict(lines=int(g('LINES')), samples=int(g('LINE_SAMPLES')), scale=float(g('SCALING_FACTOR', 1)), offset=float(g('OFFSET', 0)),
                missing=float(g('MISSING_CONSTANT', 'nan')), lo=float(g('LINE_PROJECTION_OFFSET')), so=float(g('SAMPLE_PROJECTION_OFFSET')),
                mscale=float(g('MAP_SCALE')), res=float(g('MAP_RESOLUTION')), dtype='<i2' if st.startswith('LSB') else '>i2')

@lru_cache(None)
def _img(name):
    p = os.path.join(MOON, name); L = _lbl(p.replace('.img', '.lbl').replace('.IMG', '.LBL'))
    return np.memmap(p, L['dtype'], 'r', shape=(L['lines'], L['samples'])), L

def polar_xy(lat, lon):
    """Polar stereographic metres (x east of the 0-meridian line, y), south pole if lat < 0."""
    la, lo = np.radians(lat), np.radians(lon)
    if lat < 0:
        rho = 2 * R_M * np.tan(np.pi / 4 + la / 2); return rho * np.sin(lo), rho * np.cos(lo)
    rho = 2 * R_M * np.tan(np.pi / 4 - la / 2); return rho * np.sin(lo), -rho * np.cos(lo)

def _polar_rc(lat, lon, L, mscale=None):
    x, y = polar_xy(lat, lon); s = mscale or L['mscale']
    return int(round(L['lo'] - y / s)), int(round(L['so'] + x / s))

def _read_polar(name, lat, lon, mscale=None, win=0):
    a, L = _img(name); r, c = _polar_rc(lat, lon, L, mscale)
    if not (win <= r < a.shape[0] - win and win <= c < a.shape[1] - win): return None
    v = np.asarray(a[r - win:r + win + 1, c - win:c + win + 1], dtype=float)
    v[v == L['missing']] = np.nan
    return v * L['scale'] + L['offset']

def _read_cyl(name, lat, lon, ppd, lat_max=90.0):
    a, L = _img(name)
    r = int((lat_max - lat) * ppd); c = int((lon % 360) * ppd)
    if not (0 <= r < a.shape[0]): return None
    v = float(a[r, c % a.shape[1]])
    return None if v == L['missing'] else v * L['scale'] + L['offset']

def _dem_window(lat, lon, h):
    """(window of elevation in m, pixel size m) from the finest DEM covering the point, half-width h pixels."""
    nm = 'lola/ldem_85{}_40m.img' if abs(lat) >= 85.3 else ('lola/ldem_75{}_240m.img' if abs(lat) >= 75.5 else None)
    if nm:
        nm = nm.format('s' if lat < 0 else 'n'); w = _read_polar(nm, lat, lon, win=h)
        if w is not None and not np.isnan(w).any(): return w - R_M, _img(nm)[1]['mscale'], nm
    a, L = _img('lola/ldem_16.img'); r = int((90 - lat) * 16); c = int((lon % 360) * 16)
    rows = np.clip(np.arange(r - h, r + h + 1), 0, a.shape[0] - 1); cols = np.arange(c - h, c + h + 1) % a.shape[1]
    w = np.asarray(a[np.ix_(rows, cols)], float) * L['scale'] + L['offset'] - R_M
    return w, L['mscale'], 'lola/ldem_16.img'

def _slope(w, px):
    gy = ((w[2] - w[0]).sum() / 6) / px; gx = ((w[:, 2] - w[:, 0]).sum() / 6) / px
    return float(np.degrees(np.arctan(np.hypot(gx, gy))))

def _relief(w, px):
    n = w.shape[0]; yy, xx = np.mgrid[:n, :n] * px
    A = np.c_[np.ones(w.size), xx.ravel(), yy.ravel()]
    return float((w.ravel() - A @ np.linalg.lstsq(A, w.ravel(), rcond=None)[0]).std())

def terrain(lat, lon):
    """elevation (m above 1737.4 km sphere) and slope from the finest LOLA DEM (40 m near the poles, 240 m to 75 deg,
    1.9 km elsewhere); relief = std of detrended elevation over ~13 km (same definition as the Mars characterizer);
    lola_roughness_m = LOLA's own small-scale roughness product where it has data."""
    w, px, src = _dem_window(lat, lon, 1)
    slope = _slope(w, px); elev = float(w[1, 1])
    if px < 100:                                 # at 40 m: take the 13 km relief from the 240 m map at the same point
        nm240 = 'lola/ldem_75{}_240m.img'.format('s' if lat < 0 else 'n')
        w13 = _read_polar(nm240, lat, lon, win=27); px13 = 240.0
        if w13 is None or np.isnan(w13).any(): w13, px13 = w, px
        else: w13 = w13 - R_M
    else:
        w13, px13, _ = _dem_window(lat, lon, int(round(6500 / px)))
    rough = None
    nm = 'lola/ldrm_85{}_40m.img' if abs(lat) >= 85.3 else ('lola/ldrm_75{}_240m.img' if abs(lat) >= 75.5 else None)
    if nm:
        v = _read_polar(nm.format('s' if lat < 0 else 'n'), lat, lon); rough = None if v is None or np.isnan(v[0, 0]) else round(float(v[0, 0]), 2)
    return dict(elevation_m=round(elev), slope_deg=round(slope, 2), slope_baseline_m=round(2 * px), relief_13km_m=round(_relief(w13, px13), 1),
                lola_roughness_m=rough, dem=src)

# ---------------- illumination and Earth visibility (fraction of time over 18.6 years, flat-panel at the surface)
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
@lru_cache(None)
def _illum(pole, res, earth):
    f = os.path.join(MOON, 'illumination', f'AVGVISIB_{65 if res == 240 else 85}{pole}_{res:03d}M_201608{"_EARTH" if earth else ""}')
    L = _lbl(f + '.LBL'); a = np.asarray(Image.open(f + '.TIF'), dtype=np.int32)
    return a, L
def illumination(lat, lon, earth=False):
    """Fraction of time the Sun (or Earth) is visible, and the fraction within ~1 km around (best nearby spot)."""
    if abs(lat) < 65.5: return None, None, None
    pole = 'S' if lat < 0 else 'N'
    for res in ((60, 240) if abs(lat) >= 85.5 else (240,)):
        a, L = _illum(pole, res, earth); r, c = _polar_rc(lat, lon, L)
        if 8 <= r < a.shape[0] - 8 and 8 <= c < a.shape[1] - 8:
            h = max(1, int(round(1000 / L['mscale'])))
            w = a[r - h:r + h + 1, c - h:c + h + 1] * L['scale']
            return round(float(a[r, c] * L['scale']), 3), round(float(w.max()), 3), res
    return None, None, None

# ---------------- Diviner polar resource products, gridded once to 500 m and cached as .npy
GRID_M = 500.0
@lru_cache(None)
def _prp(pole):
    cache = os.path.join(MOON, 'diviner', f'prp_{pole}_grid500m_v3.npz')
    if os.path.exists(cache):
        z = np.load(cache); return z['tavg'], z['tmax'], z['ice'], z['ice1m'], float(z['half'])
    d = pd.read_csv(os.path.join(MOON, 'diviner', f'dlre_prp_{pole}.tab'), skipinitialspace=True,
                    usecols=['tri_clon', 'tri_clat', 'temp_avg', 'temp_max', 'ice_depth'])
    x, y = polar_xy(-90 if pole == 'south' else 90, 0)  # dummy to keep signature
    la, lo = np.radians(d.tri_clat.to_numpy()), np.radians(d.tri_clon.to_numpy())
    rho = 2 * R_M * (np.tan(np.pi / 4 + la / 2) if pole == 'south' else np.tan(np.pi / 4 - la / 2))
    X = rho * np.sin(lo); Y = rho * np.cos(lo) * (1 if pole == 'south' else -1)
    half = float(np.ceil(np.abs(np.r_[X, Y]).max() / GRID_M)); n = int(2 * half + 1)
    r = (half - Y / GRID_M).round().astype(int); c = (half + X / GRID_M).round().astype(int); idx = r * n + c
    out = []
    for col in ('temp_avg', 'temp_max'):
        v = d[col].to_numpy(float); ok = np.isfinite(v) & (v > 0)
        s = np.bincount(idx[ok], v[ok], n * n); k = np.bincount(idx[ok], None, n * n)
        out.append(np.where(k > 0, s / np.maximum(k, 1), np.nan).reshape(n, n).astype(np.float32))
    ice = d.ice_depth.to_numpy(float)
    ice = np.where(ice == -1.0, 0.0, ice)   # -1 occurs only where Tmax < 100 K: ice stable at the surface (undocumented code; interpreted)
    valid = ice >= 0                        # -999 = ice only stable deeper than 2.87 m
    imin = np.full(n * n, np.inf); np.minimum.at(imin, idx[valid], ice[valid])
    out.append(np.where(np.isfinite(imin), imin, np.nan).reshape(n, n).astype(np.float32))      # shallowest stable depth in cell
    k_all = np.bincount(idx, None, n * n); k1 = np.bincount(idx[valid & (ice <= 1.0)], None, n * n)
    out.append(np.where(k_all > 0, k1 / np.maximum(k_all, 1), np.nan).reshape(n, n).astype(np.float32))  # share with ice within 1 m
    try: np.savez_compressed(cache, tavg=out[0], tmax=out[1], ice=out[2], ice1m=out[3], half=half)
    except OSError: pass        # read-only /data in Docker: ship the .npz (11 MB each) with the data instead of the 600 MB tables
    return out[0], out[1], out[2], out[3], half
def diviner_polar(lat, lon):
    """Annual mean temperature (2 cm depth), annual max surface temperature, depth to stable water ice (m)."""
    if abs(lat) < 76.0: return None
    tavg, tmax, ice, ice1m, half = _prp('south' if lat < 0 else 'north')
    x, y = polar_xy(lat, lon); r, c = int(round(half - y / GRID_M)), int(round(half + x / GRID_M))
    if not (1 <= r < tavg.shape[0] - 1 and 1 <= c < tavg.shape[1] - 1): return None
    w = lambda g: g[r - 1:r + 2, c - 1:c + 2]
    mean = lambda g: (lambda a: None if np.all(np.isnan(a)) else round(float(np.nanmean(a)), 1))(w(g))
    iw = w(ice); dmin = None if np.all(np.isnan(iw)) else round(float(np.nanmin(iw)), 3)
    return dict(temp_avg_K=mean(tavg), temp_max_K=mean(tmax), ice_depth_m=dmin, ice_deeper_than_2_87m=dmin is None,
                ice_within_1m_fraction=mean(ice1m))

# ---------------- Diviner global (60S-60N): rock abundance, regolith temperature anomaly
def rock_abundance(lat, lon):
    if abs(lat) > 59.9: return None
    v = _read_cyl('diviner/dgdr_ra_avg_cyl_032_img.img', lat, lon, 32, 60.0)
    return None if v is None else round(max(v, 0.0), 4)
def regolith_t_anomaly(lat, lon):
    if abs(lat) > 59.9: return None
    v = _read_cyl('diviner/dgdr_st_avg_cyl_032_img.img', lat, lon, 32, 60.0)
    return None if v is None else round(v, 2)

# ---------------- Lunar Prospector: epithermal neutrons (hydrogen) and element abundances
@lru_cache(None)
def _epis():
    rows = [l.split(',') for l in open(os.path.join(MOON, 'lunar_prospector', 'epis.txt')) if l.strip() and not l.startswith('#')]
    return pd.DataFrame([[float(x) for x in r[:6]] for r in rows if len(r) >= 6], columns=['la0', 'la1', 'lo0', 'lo1', 'counts', 'sd'])
def hydrogen_index(lat, lon):
    """1 - epithermal counts / median counts at |lat| < 60. ~0 = typical dry regolith; polar cold traps reach ~0.05-0.1
    (lunar hydrogen signals are weak; Lunar Prospector resolution ~2 deg)."""
    e = _epis(); lo = ((lon + 180) % 360) - 180
    m = e[(e.la0 <= lat) & (lat <= e.la1) & (e.lo0 <= lo) & (lo <= e.lo1)]
    ref = float(e[(e.la1 <= 60) & (e.la0 >= -60)].counts.median())
    return None if m.empty else round(1 - float(m.counts.iloc[0]) / ref, 4)

ELEM_COLS = ['PIXEL_INDEX', 'MIN_LAT', 'MAX_LAT', 'MIN_LON', 'MAX_LON', 'AM', 'NEUTRON_DEN', 'W_MGO', 'W_AL2O3', 'W_SIO2', 'W_CAO',
             'W_TIO2', 'W_FEO', 'W_K', 'W_TH', 'W_U']
@lru_cache(None)
def _elem():
    d = pd.read_csv(os.path.join(MOON, 'lunar_prospector', 'lpgrs_high1_elem_abundance_5deg.tab'), sep=r'\s+', header=None, usecols=range(16))
    d.columns = ELEM_COLS; return d
def elements(lat, lon):
    """Oxide weight % from Lunar Prospector GRS, 5 deg equal-area bins. FeO and TiO2 (ilmenite) matter for oxygen extraction."""
    d = _elem(); lo = ((lon + 180) % 360) - 180
    m = d[(d.MIN_LAT <= lat) & (lat <= d.MAX_LAT) & (d.MIN_LON <= lo) & (lo <= d.MAX_LON)]
    if m.empty: return {}
    r = m.iloc[0]
    return dict(feo_wt_pct=round(100 * r.W_FEO, 1), tio2_wt_pct=round(100 * r.W_TIO2, 2), al2o3_wt_pct=round(100 * r.W_AL2O3, 1))

# ---------------- pits / lava-tube skylights
@lru_cache(None)
def _pits():
    p = pd.read_csv(os.path.join(MOON, 'pits', 'LUNAR_PIT_LOCATIONS.CSV'), encoding='latin-1')
    return p[['Name', 'Terrain', 'Latitude', 'Longitude_360']].dropna(subset=['Latitude', 'Longitude_360'])
def nearest_pit(lat, lon):
    p = _pits(); la, lo = np.radians(p.Latitude.to_numpy()), np.radians(p.Longitude_360.to_numpy())
    a, b = np.radians(lat), np.radians(lon % 360)
    d = 1737.4 * 2 * np.arcsin(np.sqrt(np.sin((la - a) / 2) ** 2 + np.cos(a) * np.cos(la) * np.sin((lo - b) / 2) ** 2))
    i = int(np.argmin(d)); return round(float(d[i]), 1), p.Name.iloc[i], p.Terrain.iloc[i]

# ---------------- searches around a point
def polar_latlon(x, y, south):
    rho = np.hypot(x, y)
    if south: return np.degrees(-(np.pi / 2 - 2 * np.arctan(rho / (2 * R_M)))), np.degrees(np.arctan2(x, y))
    return np.degrees(np.pi / 2 - 2 * np.arctan(rho / (2 * R_M))), np.degrees(np.arctan2(x, -y))

def illum_window(lat, lon, radius_km, earth=False):
    """(sun-or-earth fraction array, x array, y array) for all map pixels within radius_km of the point (polar maps only)."""
    if abs(lat) < 65.5: return None
    pole = 'S' if lat < 0 else 'N'; res = 60 if abs(lat) >= 85.5 else 240
    a, L = _illum(pole, res, earth); r0, c0 = _polar_rc(lat, lon, L); h = int(radius_km * 1000 / L['mscale'])
    r1, r2, c1, c2 = max(r0 - h, 0), min(r0 + h + 1, a.shape[0]), max(c0 - h, 0), min(c0 + h + 1, a.shape[1])
    w = a[r1:r2, c1:c2] * L['scale']; rr, cc = np.mgrid[r1:r2, c1:c2]
    x = (cc - L['so']) * L['mscale']; y = (L['lo'] - rr) * L['mscale']
    x0, y0 = polar_xy(lat, lon); inside = np.hypot(x - x0, y - y0) <= radius_km * 1000
    return w[inside], x[inside], y[inside], np.hypot(x - x0, y - y0)[inside] / 1000

def nearest_cold_trap_km(lat, lon, radius_km=15):
    """Distance to the nearest permanently shadowed pixel (average sunlight 0 over 18.6 years) within radius_km."""
    w = illum_window(lat, lon, radius_km)
    if w is None: return None
    f, _, _, d = w; dark = f <= 0.0
    return round(float(d[dark].min()), 2) if dark.any() else None

def nearest_ice_km(lat, lon, radius_km=15, share=0.5):
    """Distance to the nearest 500 m cell where water ice is stable within 1 m in at least `share` of the ground (Diviner)."""
    if abs(lat) < 76: return None
    *_, ice1m, half = _prp('south' if lat < 0 else 'north')
    x0, y0 = polar_xy(lat, lon); h = int(radius_km * 1000 / GRID_M)
    r0, c0 = int(round(half - y0 / GRID_M)), int(round(half + x0 / GRID_M))
    sub = ice1m[max(r0 - h, 0):r0 + h + 1, max(c0 - h, 0):c0 + h + 1]
    rr, cc = np.mgrid[max(r0 - h, 0):max(r0 - h, 0) + sub.shape[0], max(c0 - h, 0):max(c0 - h, 0) + sub.shape[1]]
    d = np.hypot(rr - r0, cc - c0) * GRID_M / 1000; ok = (sub >= share) & (d <= radius_km)
    return round(float(d[ok].min()), 2) if ok.any() else None
