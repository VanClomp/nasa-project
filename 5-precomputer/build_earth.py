"""Component 5 (Precomputer): build the real Earth feature matrices for 4-szukacz from the sources that
fetch_earth.py downloaded.

Usage:
    python build_earth.py RAW_DIR WORK_DIR OUT_DIR [terrain modis assemble] [--bbox LAT0,LAT1,LON0,LON1]
Stages (default: all three, in order):
  terrain   ETOPO 2022 1' grid -> per 0.2 deg cell: mean elevation, median slope, median roughness  (WORK/terrain.npz)
  modis     MODIS LST 0.05 deg -> per month: mean ground temperature, day-night range, land coverage   (WORK/modis_MM.npz)
  assemble  all sources -> OUT/earth_features_raw.npy, earth_features_norm.npy, earth_metadata.parquet/.npy
--bbox limits the assembled points to a box (for quick tests); the full run omits it.

Output contract (spec 4.1, read by 4-szukacz/szukacz/data.py): (N, 12, 9) float32, months 0..11, features in the
order of 3-charakteryzator/service/norm_ranges.json, normalised with exactly those ranges (clamp + min-max), no NaN.

Feature definitions match the Mars/Moon side (3-charakteryzator):
  0 temp_mean           deg C   mean ground (skin) temperature: mean of the four MODIS overpasses (Terra 10:30/22:30,
                                Aqua 13:30/01:30), 2019-2023 monthly climatology; MERRA-2 daily-mean TS where MODIS has none
  1 temp_diurnal_amp    K       daily max - min of ground temperature. MODIS sees only 4 times of day, so its range
                                (warmest day - coldest night pass) is scaled to MERRA-2's full 24-hour skin-temperature range
                                with a factor fitted per month and 20-deg latitude band over pure-land cells; MERRA-2 where
                                MODIS has no range (polar night)
  2 thermal_inertia     SI      sqrt(k * rho * c) of the top soil, from HWSD texture + bulk density and GLDAS 0-10 cm
                                moisture/temperature (Johansen conductivity, Peters-Lidard 1998 form); varies by month with
                                soil water and freezing. Ice sheets: snow/firn surface value
  3 surface_roughness   m       std of elevation after removing a best-fit plane over 7x7 px of a 1' (~1.85 km) grid
                                (~13 km), identical to mars_maps.terrain(); cell value = median over the 0.2 deg cell
  4 soil_moisture       wt%     water mass / (dry soil + water) in the top 10 cm (GLDAS 0-10 cm; the deeper Noah
                                layer is pinned at a model floor in deserts), compared with the Mars GRS "water-equivalent
                                hydrogen, top tens of cm"; ice sheets 100
  5 dust_aerosol        -       total aerosol optical depth at 550 nm (MERRA-2), monthly climatology
  6 solar_elevation_max deg     noon sun elevation on the 15th of the month
  7 radiation_proxy     g/cm2   atmospheric column mass overhead, from elevation (standard atmosphere); sea level 1033
  8 slope_deg           deg     steepest slope from a 3x3 neighbourhood of the 1' grid (Sobel-like), as on Mars;
                                cell value = median over the 0.2 deg cell
Caves: no global Earth cave catalogue is used yet, so nearest_cave_km is NaN (the search turns it into null and the
"require caves" filter matches nothing on Earth).
"""
import datetime as dt, glob, json, os, re, sys, time
import numpy as np

RES = 0.2
NLAT, NLON = int(180 / RES), int(360 / RES)                      # 900 x 1800 cells
LAT_C = -90 + RES / 2 + RES * np.arange(NLAT)                    # ascending (south -> north)
LON_C = -180 + RES / 2 + RES * np.arange(NLON)
MID_DOY = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]
ORDER = ['temp_mean', 'temp_diurnal_amp', 'thermal_inertia', 'surface_roughness', 'soil_moisture', 'dust_aerosol',
         'solar_elevation_max', 'radiation_proxy', 'slope_deg']
HERE = os.path.dirname(os.path.abspath(__file__))
NORM_RANGES = os.path.join(HERE, '..', '3-charakteryzator', 'service', 'norm_ranges.json')
HEAT_W, HEAT_H = 1024, 512
R_EARTH_KM = 6371.0
TI_ICE_SHEET = 600.0       # snow/firn surface (k ~0.4 W/m/K, rho ~400 kg/m3, c ~2000 J/kg/K -> ~570), rounded
SM_ICE_SHEET = 100.0       # wt% water (as ice)
DEFAULT_SOIL = dict(sand=60.0, clay=5.0, bulk=1.6)   # dry coarse regolith, only where no soil data exists within reach


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def block(a, f, fn):
    """Aggregate a (NLAT*f, NLON*f) ascending-lat grid to (NLAT, NLON) with fn over f x f blocks."""
    return fn(a.reshape(NLAT, f, NLON, f).swapaxes(1, 2).reshape(NLAT, NLON, f * f), axis=-1)


# ------------------------------------------------------------------------------------------------ terrain (ETOPO 1')
def stage_terrain(raw, work):
    import netCDF4
    from scipy.ndimage import correlate
    path = glob.glob(os.path.join(raw, 'etopo', 'ETOPO_2022_v1_60s_*.nc'))[0]
    with netCDF4.Dataset(path) as ds:
        lat = ds['lat'][:]; z = np.asarray(ds['z'][:], dtype=np.float32)
    assert z.shape == (10800, 21600) and lat[0] < lat[-1], (z.shape, lat[:2])
    # ETOPO gives sea-floor depth over the ocean. For land terrain the sea surface is the boundary, so negative values
    # are set to 0 m; otherwise coastal cells get the continental shelf in their roughness/slope and a below-sea-level
    # mean elevation. (Land below sea level - Dead Sea, Caspian depression - then counts as 0 m: <0.1% of land.)
    land_px = z > 0
    # Ice-sheet / glacier mask at 1': surface - bedrock = ice thickness (ETOPO 2022 bedrock uses BedMachine under the
    # Antarctic and Greenland ice sheets). Ice-free ground such as the McMurdo Dry Valleys stays land.
    with netCDF4.Dataset(path.replace('surface_elev', 'bed_elev').replace('_surface.nc', '_bed.nc')) as ds:
        ice_px = (z - np.asarray(ds['z'][:], dtype=np.float32)) > 10.0
    np.maximum(z, 0, out=z)
    icefrac = np.empty((NLAT, NLON), np.float32)
    f = 12                                             # 0.2 deg = 12 x 1' pixels
    px_y = 1000 * np.pi * R_EARTH_KM / (180 * 60)      # m per 1' of latitude (~1853 m), as px_y in mars_maps.terrain
    k_gy = np.array([[-1, -1, -1], [0, 0, 0], [1, 1, 1]], float) / 6
    k_gx = k_gy.T
    u = np.tile(np.arange(-3, 4, dtype=float), (7, 1))   # column offset in the 7x7 window
    v = u.T
    ones = np.ones((7, 7))
    elev = np.empty((NLAT, NLON), np.float32); slope = np.empty_like(elev); rough = np.empty_like(elev)
    rows_per = 12 * 10
    for r0 in range(0, 10800, rows_per):
        r1 = r0 + rows_per
        idx = np.clip(np.arange(r0 - 3, r1 + 3), 0, 10799)
        zz = z[idx].astype(np.float64)
        zz = np.concatenate([zz[:, -3:], zz, zz[:, :3]], axis=1)          # wrap in longitude
        gy = correlate(zz, k_gy, mode='nearest') / px_y
        coslat = np.maximum(np.cos(np.radians(lat[idx].astype(float))), 0.02)[:, None]
        gx = correlate(zz, k_gx, mode='nearest') / (px_y * coslat)
        sl = np.degrees(np.arctan(np.hypot(gx, gy)))
        n = 49.0
        sz = correlate(zz, ones, mode='nearest'); szz = correlate(zz * zz, ones, mode='nearest')
        szu = correlate(zz, u, mode='nearest'); szv = correlate(zz, v, mode='nearest')
        rss = szz - sz * sz / n - szu * szu / 196.0 - szv * szv / 196.0     # sum(u^2) = sum(v^2) = 7 * 28
        rg = np.sqrt(np.maximum(rss, 0) / n)
        sl, rg = sl[3:-3, 3:-3], rg[3:-3, 3:-3]
        i0 = r0 // f
        nb = (r1 - r0) // f
        cells = lambda a: a.reshape(nb, f, NLON, f).swapaxes(1, 2).reshape(nb, NLON, f * f)
        lp = cells(land_px[r0:r1])
        anyland = lp.any(axis=-1, keepdims=True)
        use = np.where(anyland, lp, True)                 # statistics over the land pixels of each cell
        with np.errstate(all='ignore'):
            elev[i0:i0 + nb] = np.nanmean(np.where(use, cells(z[r0:r1].astype(np.float64)), np.nan), axis=-1)
            slope[i0:i0 + nb] = np.nanmedian(np.where(use, cells(sl), np.nan), axis=-1)
            rough[i0:i0 + nb] = np.nanmedian(np.where(use, cells(rg), np.nan), axis=-1)
            icefrac[i0:i0 + nb] = np.nanmean(np.where(use, cells(ice_px[r0:r1]), np.nan), axis=-1)
        if r0 % 1200 == 0: log(f'terrain rows {r0}/{10800}')
    np.savez(os.path.join(work, 'terrain.npz'), elev=elev, slope=slope, rough=rough, icefrac=icefrac)
    log('terrain done: elev', np.nanmin(elev), np.nanmax(elev), 'slope p99', np.percentile(slope, 99),
        'rough p99', np.percentile(rough, 99))


# ------------------------------------------------------------------------------------------------ MODIS LST
def _modis_month(path):
    doy = int(re.search(r'\.A\d{4}(\d{3})\.', os.path.basename(path)).group(1))
    return (dt.date(2001, 1, 1) + dt.timedelta(doy - 1)).month


def stage_modis(raw, work):
    from pyhdf.SD import SD, SDC
    files = sorted(glob.glob(os.path.join(raw, 'modis', '*.hdf')))
    log(f'MODIS: {len(files)} files')
    for m in range(1, 13):
        acc = {}
        for p in [p for p in files if _modis_month(p) == m]:
            prod = os.path.basename(p)[:3]                       # MOD (Terra) / MYD (Aqua)
            sd = SD(p, SDC.READ)
            for which in ('Day', 'Night'):
                a = sd.select(f'LST_{which}_CMG').get()
                valid = a > 0
                key = (prod, which)
                s, c = acc.get(key, (np.zeros(a.shape, np.float64), np.zeros(a.shape, np.int16)))
                s += np.where(valid, a * 0.02, 0.0); c += valid
                acc[key] = (s, c)
            sd.end()
        clim = {k: np.flipud(np.where(c > 0, s / np.maximum(c, 1), np.nan)).astype(np.float32) for k, (s, c) in acc.items()}
        stack = np.stack([clim[k] for k in sorted(clim)])        # 4 overpasses, 3600 x 7200, ascending lat
        with np.errstate(all='ignore'):
            tmean = np.nanmean(stack, axis=0)
            day = np.fmax(clim[('MOD', 'Day')], clim[('MYD', 'Day')])
            night = np.fmin(clim[('MOD', 'Night')], clim[('MYD', 'Night')])
            drange = day - night
            valid_any = np.isfinite(stack).any(axis=0).astype(np.float32)
            out = dict(tmean=block(tmean, 4, np.nanmean), drange=block(drange, 4, np.nanmean),
                       valid=block(valid_any, 4, np.mean))
        np.savez(os.path.join(work, f'modis_{m:02d}.npz'), **out)
        log(f'MODIS month {m}: land coverage {np.mean(out["valid"] > 0.5):.3f}, '
            f'tmean {np.nanmin(out["tmean"]):.1f}..{np.nanmax(out["tmean"]):.1f} K')


# ------------------------------------------------------------------------------------------------ helpers for assemble
def _merra_interp(field, lat_pts, lon_pts):
    """Bilinear from the MERRA-2 grid (361 x 576: lat -90..90 step 0.5, lon -180..179.375 step 0.625), periodic lon."""
    from scipy.interpolate import RegularGridInterpolator
    lat = np.linspace(-90, 90, 361); lon = -180 + 0.625 * np.arange(577)
    f = np.concatenate([field, field[:, :1]], axis=1)
    return RegularGridInterpolator((lat, lon), f)(np.c_[lat_pts, lon_pts])


def _gldas_index(lat_pts, lon_pts):
    i = np.floor((lat_pts + 60.0) / 0.25).astype(int); j = np.floor((lon_pts + 180.0) / 0.25).astype(int) % 1440
    return i, j


def _gldas_sample(field, i, j):
    """Nearest GLDAS cell; where that is NaN (coast), the mean of the valid cells in its 3x3 neighbourhood."""
    out = np.full(i.shape, np.nan)
    inside = (i >= 0) & (i < 600)
    out[inside] = field[i[inside], j[inside]]
    miss = inside & np.isnan(out)
    if miss.any():
        vals = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                ii = np.clip(i[miss] + di, 0, 599); jj = (j[miss] + dj) % 1440
                vals.append(field[ii, jj])
        with np.errstate(all='ignore'):
            out[miss] = np.nanmean(np.stack(vals), axis=0)
    return out


def _xyz(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    return np.c_[np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)]


def _nearest_fill(values, xyz, max_km=None):
    """Fill NaN entries with the nearest finite entry (great-circle via chord distance); returns filled, n_filled."""
    from scipy.spatial import cKDTree
    bad = ~np.isfinite(values)
    if not bad.any() or bad.all(): return values, 0
    tree = cKDTree(xyz[~bad])
    d, k = tree.query(xyz[bad])
    src = values[~bad][k]
    if max_km is not None:
        src = np.where(d * R_EARTH_KM <= max_km, src, np.nan)
    out = values.copy(); out[bad] = src
    return out, int(np.isfinite(src).sum())


def _thermal_inertia(sand, clay, bulk, theta, frozen):
    """Johansen-type conductivity (Peters-Lidard et al. 1998, as in the Noah land model) and volumetric heat
    capacity of a moist mineral soil; returns sqrt(k * C) in J m-2 K-1 s-1/2."""
    rho_b = np.clip(bulk, 0.8, 2.0) * 1000.0                 # kg/m3 dry bulk density
    phi = np.clip(1.0 - rho_b / 2650.0, 0.25, 0.70)          # porosity
    theta = np.clip(theta, 0.0, phi)
    sr = np.clip(theta / phi, 1e-4, 1.0)                     # degree of saturation
    q = np.clip(sand / 100.0, 0.0, 1.0)                      # quartz fraction ~ sand fraction
    k_other = np.where(q > 0.2, 2.0, 3.0)
    k_solid = 7.7 ** q * k_other ** (1 - q)
    k_sat = np.where(frozen, k_solid ** (1 - phi) * 2.2 ** phi, k_solid ** (1 - phi) * 0.57 ** phi)
    k_dry = (0.135 * rho_b + 64.7) / (2700.0 - 0.947 * rho_b)
    coarse = sand >= 50.0
    ke_unfrozen = np.where(coarse, np.where(sr > 0.05, 0.7 * np.log10(sr) + 1.0, 0.0),
                           np.where(sr > 0.1, np.log10(sr) + 1.0, 0.0))
    ke = np.where(frozen, sr, np.clip(ke_unfrozen, 0.0, 1.0))
    k = k_dry + ke * (k_sat - k_dry)
    c_water = np.where(frozen, 917.0 * 2100.0, 1000.0 * 4180.0)
    C = rho_b * 800.0 + theta * c_water
    return np.sqrt(k * C)


def _column_mass_g_cm2(elev_m):
    h = np.clip(elev_m, -500.0, 9000.0)
    p = 101325.0 * (1.0 - 2.25577e-5 * h) ** 5.25588         # Pa, ICAO standard atmosphere
    return p / 9.80665 / 10.0                                 # kg/m2 -> g/cm2


def _solar_elevation_max(lat, m):
    doy = MID_DOY[m]
    dec = 23.44 * np.sin(np.radians(360.0 * (284 + doy) / 365.0))
    return np.maximum(0.0, 90.0 - np.abs(lat - dec))


# ------------------------------------------------------------------------------------------------ assemble
def stage_assemble(raw, work, out, bbox=None):
    import xarray as xr
    prov = dict(grid_deg=RES, years='2019-2023', fills={}, sources={})
    t = np.load(os.path.join(work, 'terrain.npz'))
    modis = [np.load(os.path.join(work, f'modis_{m:02d}.npz')) for m in range(1, 13)]
    LAT, LON = np.meshgrid(LAT_C, LON_C, indexing='ij')

    # --- MERRA-2 constants and land mask
    const = xr.open_dataset(glob.glob(os.path.join(raw, 'merra_const', '*.nc4'))[0])
    frland_g = const['FRLAND'].values[0]; frice_g = const['FRLANDICE'].values[0]
    valid_max = np.max([mm['valid'] for mm in modis], axis=0)
    cand = valid_max >= 0.5
    if bbox:
        la0, la1, lo0, lo1 = bbox
        cand &= (LAT >= la0) & (LAT <= la1) & (LON >= lo0) & (LON <= lo1)
    lat, lon = LAT[cand], LON[cand]
    frice = _merra_interp(frice_g, lat, lon); frland = _merra_interp(frland_g, lat, lon)
    ice = t['icefrac'][cand] >= 0.5                          # ETOPO surface - bedrock > 10 m on most of the cell

    # --- GLDAS climatology (12 months) at the candidate points
    gfiles = sorted(glob.glob(os.path.join(raw, 'gldas', '*.nc4')))
    gi, gj = _gldas_index(lat, lon)
    g = {k: np.zeros((12, len(lat))) for k in ('sm0', 'sm1', 'tsoil')}
    gn = np.zeros(12)
    for p in gfiles:
        m = int(re.search(r'\.A\d{4}(\d{2})\.', os.path.basename(p)).group(1)) - 1
        with xr.open_dataset(p) as ds:
            for key, var in (('sm0', 'SoilMoi0_10cm_inst'), ('sm1', 'SoilMoi10_40cm_inst'), ('tsoil', 'SoilTMP0_10cm_inst')):
                g[key][m] += _gldas_sample(ds[var].values[0], gi, gj)
        gn[m] += 1
    for key in g: g[key] /= gn[:, None]
    gldas_ok = np.isfinite(g['sm0']).any(axis=0)
    land = gldas_ok | ice | (lat < -60.0)                     # drops large lakes / inland seas (no GLDAS soil)
    log(f'candidates {cand.sum()}, land points {land.sum()} (ice {int((ice & land).sum())}), '
        f'dropped as water {int((~land).sum())}')
    sel = np.flatnonzero(land)
    lat, lon, ice, frland, frice = lat[sel], lon[sel], ice[sel], frland[sel], frice[sel]
    for key in g: g[key] = g[key][:, sel]
    rows, cols = np.nonzero(cand); rows, cols = rows[sel], cols[sel]
    N = len(lat); xyz = _xyz(lat, lon)

    # --- MERRA-2 aerosol and diurnal skin temperature climatologies
    aer = np.zeros((12, 361, 576)); an = np.zeros(12)
    for p in sorted(glob.glob(os.path.join(raw, 'merra_aer', '*.nc4'))):
        m = int(re.search(r'\.(\d{4})(\d{2})\.nc4$', p).group(2)) - 1
        with xr.open_dataset(p) as ds: aer[m] += ds['TOTEXTTAU'].values[0]
        an[m] += 1
    aer /= an[:, None, None]
    ts_amp = np.zeros((12, 361, 576)); ts_mean = np.zeros((12, 361, 576)); tn = np.zeros(12)
    for p in sorted(glob.glob(os.path.join(raw, 'merra_diurnal', 'merra_ts_*.npy'))):
        m = int(p[-6:-4]) - 1; ts = np.load(p)
        ts_amp[m] += ts.max(axis=0) - ts.min(axis=0); ts_mean[m] += ts.mean(axis=0); tn[m] += 1
    assert tn.min() >= 1, f'MERRA-2 diurnal months missing: {tn}'
    ts_amp /= tn[:, None, None]; ts_mean /= tn[:, None, None]
    prov['sources']['merra_diurnal_years_per_month'] = tn.tolist()

    # --- HWSD soil (0.05 -> 0.2 deg block means)
    # HWSD stores non-soil map units (dunes / shifting sand, rock outcrops, salt flats) as 0 % sand AND 0 % clay with
    # no bulk density. Those subpixels are marked "non-soil" instead of being averaged in as 0 %; a cell that is mostly
    # non-soil gets dune-sand properties on flat ground and rock properties on steep ground. Cells with no HWSD data
    # at all (water, glaciers, Antarctica) borrow the nearest soil within 500 km, else a dry-regolith default.
    def _hwsd(n):
        with xr.open_dataset(os.path.join(raw, 'hwsd', f'{n}.nc4')) as ds:
            a = ds[n].values.astype(np.float32)
            return a[::-1] if ds['lat'].values[0] > ds['lat'].values[-1] else a
    sand_f, clay_f = _hwsd('T_SAND'), _hwsd('T_CLAY')
    nonsoil_f = (sand_f == 0) & (clay_f == 0)
    sand_f[nonsoil_f] = np.nan; clay_f[nonsoil_f] = np.nan
    bulk_f = _hwsd('T_REF_BULK'); bulk_f = np.where(np.isfinite(bulk_f), bulk_f, _hwsd('T_BULK_DEN'))
    bulk_f[nonsoil_f] = np.nan
    with np.errstate(all='ignore'):
        nonsoil = block(nonsoil_f.astype(np.float32), 4, np.mean)[rows, cols] > 0.5
        soil = {k: block(a, 4, np.nanmean)[rows, cols] for k, a in (('sand', sand_f), ('clay', clay_f), ('bulk', bulk_f))}
    del sand_f, clay_f, bulk_f, nonsoil_f
    steep = t['slope'][rows, cols] > 5.0
    DUNE, ROCK = dict(sand=92.0, clay=3.0, bulk=1.60), dict(sand=50.0, clay=10.0, bulk=1.90)
    for key in soil:
        v = soil[key]
        ns = nonsoil & ~ice & ~np.isfinite(v)
        v[ns] = np.where(steep[ns], ROCK[key], DUNE[key])
        v[ice] = np.nan
        v, nf = _nearest_fill(np.where(~ice, v, np.nan), xyz, max_km=500)
        miss = ~ice & ~np.isfinite(v)
        v[miss] = DEFAULT_SOIL[key]
        soil[key] = v
        prov['fills'][f'soil_{key}'] = dict(nonsoil_dune_or_rock=int(ns.sum()), neighbour=nf, default=int(miss.sum()))

    # --- features
    raw_f = np.full((N, 12, 9), np.nan, np.float32)
    T = np.full((12, N), np.nan); D = np.full((12, N), np.nan)
    for m in range(12):
        T[m] = modis[m]['tmean'][rows, cols]; D[m] = modis[m]['drange'][rows, cols]
    merra_amp = np.stack([_merra_interp(ts_amp[m], lat, lon) for m in range(12)])
    merra_tm = np.stack([_merra_interp(ts_mean[m], lat, lon) for m in range(12)])

    # temp_mean
    tm = np.where(np.isfinite(T), T, merra_tm) - 273.15
    prov['fills']['temp_mean_from_merra'] = int((~np.isfinite(T)).sum())
    # temp_diurnal_amp: MODIS range scaled to MERRA-2 full 24 h range, per month and 20-deg band, over pure land
    fit = (frland >= 0.95) & (frice < 0.1)
    kfac = np.ones((12, N)); prov['amp_scale'] = {}
    bands = np.arange(-90, 91, 20)
    for m in range(12):
        ok = fit & np.isfinite(D[m]) & (D[m] > 3)
        r = merra_amp[m] / np.where(ok, D[m], np.nan)
        glob_k = float(np.nanmedian(r[ok])) if ok.sum() > 100 else 1.0
        ks = []
        for b0, b1 in zip(bands[:-1], bands[1:]):
            inb = (lat >= b0) & (lat < b1)
            kb = float(np.nanmedian(r[ok & inb])) if (ok & inb).sum() >= 300 else glob_k
            kfac[m, inb] = kb; ks.append(round(kb, 3))
        prov['amp_scale'][m + 1] = dict(global_k=round(glob_k, 3), band_k=ks)
    amp = np.where(np.isfinite(D) & (D > 0), kfac * D, merra_amp)
    prov['fills']['temp_diurnal_amp_from_merra'] = int((~(np.isfinite(D) & (D > 0))).sum())
    # soil water and thermal inertia
    # Only the 0-10 cm GLDAS layer is used: in hyperarid regions Noah's 10-40 cm layer stays pinned at the soil's
    # wilting-point floor all year (Atacama, Rub al Khali ~44 kg/m2 constant), which is a model floor, not a moisture
    # signal; the top layer responds (Sahara 2-5 kg/m2).
    theta = g['sm0'] / 100.0                                  # kg/m2 over 0.1 m -> m3/m3
    tsoil = g['tsoil']
    for m in range(12):
        v = np.where(ice, np.nan, theta[m]); v, nf = _nearest_fill(v, xyz, max_km=500); theta[m] = v
    prov['fills']['theta_neighbour'] = nf
    dry = ~ice & ~np.isfinite(theta[0])                      # ice-free land far from any GLDAS cell (Antarctic oases)
    theta[:, dry] = 0.01                                      # very dry polar regolith
    prov['fills']['dry_polar_ground'] = int(dry.sum())
    frozen = np.where(np.isfinite(tsoil), tsoil < 273.15, tm < 0.0)
    ti = np.stack([_thermal_inertia(soil['sand'], soil['clay'], soil['bulk'], theta[m], frozen[m]) for m in range(12)])
    ti[:, ice] = TI_ICE_SHEET
    rho_b = np.clip(soil['bulk'], 0.8, 2.0) * 1000.0
    w = theta * 1000.0 * 0.1                                  # kg/m2 water in the top 10 cm
    sm = 100.0 * w / (rho_b * 0.1 + w); sm[:, ice] = SM_ICE_SHEET   # wt% = water / (dry soil + water)
    # dust, sun, column mass, terrain
    dust = np.stack([_merra_interp(aer[m], lat, lon) for m in range(12)])
    sun = np.stack([_solar_elevation_max(lat, m) for m in range(12)])
    elev = t['elev'][rows, cols].astype(float)
    col = np.broadcast_to(_column_mass_g_cm2(elev), (12, N))
    rough = np.broadcast_to(t['rough'][rows, cols], (12, N)); slope = np.broadcast_to(t['slope'][rows, cols], (12, N))

    for k, arr in enumerate((tm, amp, ti, rough, sm, dust, sun, col, slope)):
        raw_f[:, :, k] = np.asarray(arr, dtype=np.float32).T
    # last-resort fill: nearest finite point (same month and feature)
    for k in range(9):
        for m in range(12):
            v = raw_f[:, m, k].astype(float)
            if np.isfinite(v).all(): continue
            v, nf = _nearest_fill(v, xyz); raw_f[:, m, k] = v
            prov['fills'][f'final_{ORDER[k]}_m{m + 1}'] = nf
    assert np.isfinite(raw_f).all(), 'NaN left in features'

    # --- normalise with the shared ranges
    rng = json.load(open(NORM_RANGES))
    assert rng['order'] == ORDER, rng['order']
    lo = np.array([rng[k]['min'] for k in ORDER], np.float32); hi = np.array([rng[k]['max'] for k in ORDER], np.float32)
    norm = np.clip((raw_f - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)

    # --- metadata and write
    ids = ((NLAT - 1 - rows) * NLON + cols).astype(np.int32)  # row 0 = northernmost
    order = np.argsort(ids, kind='stable')
    raw_f, norm = np.ascontiguousarray(raw_f[order]), np.ascontiguousarray(norm[order])
    meta = dict(id=ids[order], lat=lat[order].astype(np.float32), lon=lon[order].astype(np.float32),
                px_x=np.clip(((lon[order] + 180) / 360 * HEAT_W).astype(np.int32), 0, HEAT_W - 1),
                px_y=np.clip(((90 - lat[order]) / 180 * HEAT_H).astype(np.int32), 0, HEAT_H - 1),
                elevation_m=elev[order].astype(np.float32),
                nearest_cave_km=np.full(N, np.nan, np.float32))
    os.makedirs(out, exist_ok=True)
    for f in ('UWAGA_DANE_MOCK_HEURYSTYKA.txt',):
        if os.path.exists(os.path.join(out, f)): os.remove(os.path.join(out, f))
    np.save(os.path.join(out, 'earth_features_raw.npy'), raw_f)
    np.save(os.path.join(out, 'earth_features_norm.npy'), norm)
    import pyarrow as pa, pyarrow.parquet as pq
    pq.write_table(pa.table(meta), os.path.join(out, 'earth_metadata.parquet'))
    rec = np.zeros(N, dtype=[(k, v.dtype.str) for k, v in meta.items()])
    for k, v in meta.items(): rec[k] = v
    np.save(os.path.join(out, 'earth_metadata.npy'), rec)
    prov.update(n_points=int(N), n_ice=int(ice.sum()), bbox=bbox,
                raw_ranges={k: [float(raw_f[:, :, i].min()), float(np.median(raw_f[:, :, i])), float(raw_f[:, :, i].max())]
                            for i, k in enumerate(ORDER)},
                built=dt.datetime.utcnow().isoformat(timespec='seconds') + 'Z')
    json.dump(prov, open(os.path.join(out, 'earth_provenance.json'), 'w'), indent=1)
    log(f'wrote {N} points to {out}')
    for i, k in enumerate(ORDER):
        a = raw_f[:, :, i]
        log(f'  {k:20} min {a.min():9.2f}  p05 {np.percentile(a, 5):9.2f}  median {np.median(a):9.2f}  '
            f'p95 {np.percentile(a, 95):9.2f}  max {a.max():9.2f}   norm at 0/1: {np.mean(norm[:, :, i] <= 0):.3f}/{np.mean(norm[:, :, i] >= 1):.3f}')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    bbox = None
    if '--bbox' in sys.argv:
        bbox = [float(x) for x in sys.argv[sys.argv.index('--bbox') + 1].split(',')]
        args = [a for a in args if a != sys.argv[sys.argv.index('--bbox') + 1]]
    raw, work, out = (os.path.expanduser(a) for a in args[:3])
    os.makedirs(work, exist_ok=True)
    stages = args[3:] or ['terrain', 'modis', 'assemble']
    for s in stages:
        log('== stage', s)
        if s == 'terrain': stage_terrain(raw, work)
        elif s == 'modis': stage_modis(raw, work)
        elif s == 'assemble': stage_assemble(raw, work, out, bbox)
        else: raise SystemExit(f'unknown stage {s}')
