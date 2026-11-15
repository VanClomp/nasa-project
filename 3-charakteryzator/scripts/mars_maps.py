"""Point lookups in the global Mars maps. Every function takes planetocentric latitude (deg N) and east longitude (deg, 0-360).

elevation_m        MOLA MEGDR 32 px/deg (~1.85 km), metres above the areoid
slope_deg          steepest slope from a 3x3 neighbourhood of that grid (so at ~1.85 km baseline, not lander scale)
roughness_m        local relief: standard deviation of elevation after removing a best-fit plane, 7x7 pixels (~13 km)
thermal_inertia    TES nightside map 20 px/deg (Putzig & Mellon 2007), SI units; flag says whether the pixel was infilled
albedo             TES bolometric Lambert albedo 8 px/deg
water_wt_pct       Odyssey GRS H2O, smoothed 5x5 deg map; hydrogen_index from the neutron map everywhere incl. poles
hydrated_minerals  distance to the nearest OMEGA/CRISM hydrated-mineral detection, and count within 100 km
"""
import os, numpy as np, pandas as pd
from functools import lru_cache
GEO = os.environ.get('MARS_DATA_DIR') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'geology')   # docker: /data/mars
R_MARS = 3389.5  # km

@lru_cache(None)
def _mola(): return np.memmap(os.path.join(GEO, 'mola_meg032', 'megt90n000fb.img'), '>i2', 'r', shape=(5760, 11520))
@lru_cache(None)
def _ti(): return np.memmap(os.path.join(GEO, 'tes_thermal_inertia', 'global_ti_night_2007.img'), '>i2', 'r', shape=(3600, 7200))
@lru_cache(None)
def _ti_mask(): return np.memmap(os.path.join(GEO, 'tes_thermal_inertia', 'global_ti_msk_night_2007.img'), 'u1', 'r', shape=(3600, 7200))
@lru_cache(None)
def _albedo(): return np.memmap(os.path.join(GEO, 'tes_albedo', 'global_albedo_8ppd.img'), '<f4', 'r', shape=(1440, 2880))

def _rc(lat, lon, ppd, lon0):          # lon0 = longitude of the first sample's left edge (0 or -180)
    r = int(np.clip((90 - lat) * ppd, 0, 180 * ppd - 1))
    c = int(((lon - lon0) % 360) * ppd) % (360 * ppd)
    return r, c

def _window(a, r, c, h):
    rows = np.clip(np.arange(r - h, r + h + 1), 0, a.shape[0] - 1)
    cols = np.arange(c - h, c + h + 1) % a.shape[1]
    return np.asarray(a[np.ix_(rows, cols)], dtype=float)

def terrain(lat, lon):
    z = _mola(); r, c = _rc(lat, lon, 32, 0)
    elev = float(z[r, c])
    px_y = 1000 * np.pi * R_MARS / (180 * 32); px_x = px_y * max(np.cos(np.radians(lat)), 0.02)
    w3 = _window(z, r, c, 1)
    gy = ((w3[2] - w3[0]).sum() / 6) / px_y; gx = ((w3[:, 2] - w3[:, 0]).sum() / 6) / px_x   # Sobel-like mean differences
    slope = float(np.degrees(np.arctan(np.hypot(gx, gy))))
    w7 = _window(z, r, c, 3); yy, xx = np.mgrid[-3:4, -3:4]
    A = np.c_[np.ones(49), (xx * px_x).ravel(), (yy * px_y).ravel()]
    resid = w7.ravel() - A @ np.linalg.lstsq(A, w7.ravel(), rcond=None)[0]
    return dict(elevation_m=elev, slope_deg=round(slope, 2), roughness_m=round(float(resid.std()), 1))

def thermal_inertia(lat, lon):
    r, c = _rc(lat, lon, 20, -180); v = float(_ti()[r, c])
    if v <= 0:   # no retrieval: median of valid pixels within ~15 km
        w = _window(_ti(), r, c, 5); w = w[w > 0]
        return (float(np.median(w)) if w.size else None), 'nearby pixels (no value at this pixel)'
    return v, ('interpolated pixel' if _ti_mask()[r, c] == 0 else 'direct retrieval')

def albedo(lat, lon):
    r, c = _rc(lat, lon, 8, -180); v = float(_albedo()[r, c])
    return round(v, 3) if np.isfinite(v) and v > 0 else None

@lru_cache(None)
def _grs():
    w = pd.read_fwf(os.path.join(GEO, 'grs_water', 'h2o_2x2.tab'), header=None, names=['lat', 'lon', 'wt', 'sig', 'sig_cfs'])
    return w[w.wt < 9000].reset_index(drop=True)
@lru_cache(None)
def _neutron():
    n = pd.read_csv(os.path.join(GEO, 'grs_neutron', 'ns_epithermal_020917.tab'), header=None, names=['lon', 'lat', 'flux'])
    n['lon'] = n.lon % 360
    return n[n.flux > 0].reset_index(drop=True)
@lru_cache(None)
def _grs_smooth():
    w = pd.read_fwf(os.path.join(GEO, 'grs_water', 'h2o_sr_5x5.tab'), header=None, names=['lat', 'lon', 'wt', 'sig', 'sig_cfs'])
    return w[w.wt < 9000].reset_index(drop=True)

def water(lat, lon):
    """Water-equivalent hydrogen in the top tens of cm, weight %. Smoothed 5x5 deg GRS map (the 2x2 map is too noisy at
    single-bin level: many bins are negative). Returns (value or None, source, measured_at_point)."""
    g = _grs_smooth()
    la, lo = np.floor(lat / 5) * 5 + 2.5, np.floor((lon % 360) / 5) * 5 + 2.5
    m = g[(g.lat == la) & (g.lon == lo)]
    if len(m): return round(float(m.wt.iloc[0]), 2), 'Odyssey GRS water map (5x5 deg, smoothed)', True
    return None, 'outside the GRS water map (poleward of its coverage); see hydrogen_index', False

@lru_cache(None)
def _flux_ref(): n = _neutron(); return float(n[abs(n.lat) < 20].flux.median())

def hydrogen_index(lat, lon):
    """1 - epithermal neutron flux / equatorial median flux (Odyssey NS, 0.5 deg, first 26 days of mapping).
    About 0 = as dry as typical equatorial ground; 0.4+ = hydrogen-rich (ground ice likely in the top metre)."""
    n = _neutron(); d = n[(abs(n.lat - lat) <= 0.75) & (abs(((n.lon - lon + 180) % 360) - 180) <= 0.75 / max(np.cos(np.radians(lat)), 0.05))]
    return round(1 - float(d.flux.mean()) / _flux_ref(), 2) if len(d) else None

@lru_cache(None)
def _hydrous():
    h = pd.read_csv(os.path.join(GEO, 'omega_minerals', 'hydrous_sites_geo_map.csv'), header=None, usecols=[0, 1], names=['lon', 'lat'])
    return np.radians(h.lat.to_numpy()), np.radians(h.lon.to_numpy() % 360)

def _gc_km(lat1, lon1, lat2, lon2):
    return R_MARS * 2 * np.arcsin(np.sqrt(np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2))

def hydrated_minerals(lat, lon):
    la, lo = _hydrous(); d = _gc_km(np.radians(lat), np.radians(lon % 360), la, lo)
    return round(float(d.min()), 1), int((d <= 100).sum())

CAVES = os.path.join(GEO, 'caves')
def nearest_cave_km(lat, lon):
    """Needs the Mars Global Cave Candidate Catalog unpacked in data/geology/caves; returns None until it is there."""
    import glob
    files = [f for f in glob.glob(os.path.join(CAVES, '**', '*.csv'), recursive=True)]
    if not files: return None
    c = pd.read_csv(files[0]); cols = {k.lower(): k for k in c.columns}
    la = next((cols[k] for k in cols if k.startswith('lat')), None); lo = next((cols[k] for k in cols if k.startswith('lon')), None)
    if la is None or lo is None: return None
    d = _gc_km(np.radians(lat), np.radians(lon % 360), np.radians(c[la].to_numpy(float)), np.radians(c[lo].to_numpy(float) % 360))
    return round(float(np.nanmin(d)), 1)

if __name__ == '__main__':
    import marslib as m
    for s in m.SITES:
        t = terrain(s['lat'], s['lon']); ti = thermal_inertia(s['lat'], s['lon'])
        print(f"{s['id']:<13} elev {t['elevation_m']:>6.0f} m (table {s['elev']*1000:>5.0f})  slope {t['slope_deg']:>5.2f}  rough {t['roughness_m']:>6.1f} m  "
              f"TI {ti[0]} ({ti[1]})  albedo {albedo(s['lat'], s['lon'])}  water {water(s['lat'], s['lon'])[0]}  H-index {hydrogen_index(s['lat'], s['lon'])}  hydrated {hydrated_minerals(s['lat'], s['lon'])}")
