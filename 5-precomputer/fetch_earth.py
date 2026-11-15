"""Component 5 (Precomputer): download the real Earth source data into a raw folder.

Usage (on the server, with an Earthdata login in ~/.netrc):
    python fetch_earth.py RAW_DIR [modis hwsd etopo gldas merra_aer merra_diurnal merra_const]
With no source names, fetches everything. Safe to re-run: existing files are skipped.

Sources (climatology window YEARS below, monthly):
  modis          MOD11C3 + MYD11C3 v061: MODIS Terra/Aqua land surface temperature, day+night, 0.05 deg (LP DAAC)
  hwsd           HWSD_1247: regridded Harmonized World Soil Database v1.2, 0.05 deg (ORNL DAAC)
  etopo          NOAA ETOPO 2022 v1, 60 arc-second surface elevation (incl. ice-sheet surfaces), global
  gldas          GLDAS_NOAH025_M v2.1: soil moisture / soil temperature by layer, 0.25 deg (GES DISC)
  merra_aer      M2TMNXAER: MERRA-2 monthly aerosol optical depth at 550 nm (GES DISC)
  merra_diurnal  M2TUNXSLV: MERRA-2 monthly mean diurnal cycle; only skin temperature TS is read remotely and
                 saved per month (the full files are ~900 MB each) (GES DISC)
  merra_const    M2C0NXASM: MERRA-2 constants (land and land-ice fractions)
GES DISC sources need the "NASA GESDISC DATA ARCHIVE" application approved once in the Earthdata profile.
"""
import os, sys, subprocess
import numpy as np

YEARS = (2019, 2023)
TEMPORAL = (f'{YEARS[0]}-01-01', f'{YEARS[1]}-12-31')
# 60 arc-second (1') grid = 1.85 km pixels, the same pixel size as the Mars MOLA grid (32 px/deg) that
# 3-charakteryzator uses for slope (3x3) and roughness (7x7), so Earth terrain features match the Mars definitions.
ETOPO_URL = ('https://www.ngdc.noaa.gov/thredds/fileServer/global/ETOPO2022/60s/60s_surface_elev_netcdf/'
             'ETOPO_2022_v1_60s_N90W180_surface.nc')
HWSD_FILES = ('T_SAND', 'T_CLAY', 'T_SILT', 'T_GRAVEL', 'T_REF_BULK', 'T_BULK_DEN', 'T_OC', 'S_SAND', 'S_CLAY',
              'S_REF_BULK', 'S_BULK_DEN')


def _ea():
    import earthaccess
    earthaccess.login(strategy='netrc')
    return earthaccess


def _download(short_name, version, out, **kw):
    ea = _ea()
    os.makedirs(out, exist_ok=True)
    q = dict(short_name=short_name, count=-1, **kw)
    if version: q['version'] = version
    grans = ea.search_data(**q)
    have = set(os.listdir(out))
    todo = [g for g in grans if not any(os.path.basename(u) in have for u in g.data_links())]
    print(f'{short_name}: {len(grans)} granules, {len(todo)} to download', flush=True)
    if todo:
        ea.download(todo, out, threads=8, show_progress=False)


def modis(raw):
    for sn in ('MOD11C3', 'MYD11C3'):
        _download(sn, '061', os.path.join(raw, 'modis'), temporal=TEMPORAL)


def hwsd(raw):
    ea = _ea(); out = os.path.join(raw, 'hwsd'); os.makedirs(out, exist_ok=True)
    grans = ea.search_data(short_name='HWSD_1247', count=-1)
    want = [g for g in grans if any(os.path.basename(u).split('.')[0] in HWSD_FILES or
                                    os.path.basename(u).replace('HWSD.', '').split('.')[0] in HWSD_FILES
                                    for u in g.data_links())]
    print(f'HWSD_1247: {len(grans)} granules, {len(want)} wanted', flush=True)
    ea.download(want, out, show_progress=False)


def etopo(raw):
    """Surface elevation, plus bedrock elevation: surface - bedrock = ice thickness, used as a 1' ice-sheet mask
    (MERRA-2's 0.5 deg land-ice fraction would mark ice-free areas such as the McMurdo Dry Valleys as ice)."""
    out = os.path.join(raw, 'etopo'); os.makedirs(out, exist_ok=True)
    for url in (ETOPO_URL, ETOPO_URL.replace('surface_elev', 'bed_elev').replace('_surface.nc', '_bed.nc')):
        dst = os.path.join(out, os.path.basename(url))
        subprocess.run(['curl', '-sS', '-L', '-C', '-', '--retry', '5', '-o', dst, url], check=True)
        print('ETOPO 2022:', os.path.basename(dst), round(os.path.getsize(dst) / 1e6), 'MB', flush=True)


def gldas(raw):
    _download('GLDAS_NOAH025_M', '2.1', os.path.join(raw, 'gldas'), temporal=TEMPORAL)


def merra_aer(raw):
    _download('M2TMNXAER', '5.12.4', os.path.join(raw, 'merra_aer'), temporal=TEMPORAL)


def merra_const(raw):
    _download('M2C0NXASM', '5.12.4', os.path.join(raw, 'merra_const'))


def merra_diurnal(raw):
    """Read only TS (24 hourly means, 361 x 576) from each monthly file; save as merra_ts_YYYYMM.npy."""
    import xarray as xr
    ea = _ea(); out = os.path.join(raw, 'merra_diurnal'); os.makedirs(out, exist_ok=True)
    grans = ea.search_data(short_name='M2TUNXSLV', version='5.12.4', temporal=TEMPORAL, count=-1)
    shard, nshards = (int(x) for x in os.environ.get('SHARD', '0/1').split('/'))   # parallel workers: SHARD=i/n
    for g in grans[shard::nshards]:
        name = os.path.basename(g.data_links()[0]); ym = name.split('.')[-2]
        dst = os.path.join(out, f'merra_ts_{ym}.npy')
        if os.path.exists(dst): continue
        for attempt in range(3):
            try:
                with xr.open_dataset(ea.open([g], show_progress=False)[0], engine='h5netcdf') as ds:
                    ts = ds['TS'].values.astype(np.float32)
                    if not os.path.exists(os.path.join(out, 'grid.npz')):
                        np.savez(os.path.join(out, 'grid.npz'), lat=ds['lat'].values, lon=ds['lon'].values,
                                 hour=ds['time'].values.astype('datetime64[m]').astype(str))
                np.save(dst, ts); print('MERRA-2 TS', ym, ts.shape, flush=True); break
            except Exception as e:
                print('retry', ym, e, flush=True)


SOURCES = dict(modis=modis, hwsd=hwsd, etopo=etopo, gldas=gldas, merra_aer=merra_aer, merra_const=merra_const,
               merra_diurnal=merra_diurnal)

if __name__ == '__main__':
    raw = sys.argv[1]
    for name in (sys.argv[2:] or SOURCES):
        print(f'== {name}', flush=True)
        SOURCES[name](raw)
