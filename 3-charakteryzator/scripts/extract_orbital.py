"""Orbital and model products -> values at each of the 12 sites.

1. MGS TES visible (0.67 micron) column dust optical depth from emission-phase-function sequences, Mars years 24-27
   (PDS4 bundle mgs_tes_atmos_dust-ice). These are point retrievals at latitude nodes every 15 deg, not maps.
   Dust is normalised to 610 Pa with the surface pressure supplied in each record, then binned by latitude node and
   15-deg Ls bin. 'typical' pools MY24, MY26, MY27 and MY25 before Ls 180; 'storm_year' is MY25 from Ls 180 (2001 global storm).
   Water-ice optical depth (scaled from the infrared by the data producers) is binned the same way, not pressure-scaled.
   -> outputs/tes_dust_climatology.csv, outputs/site_dust_by_season.csv (interpolated in latitude to each site)
2. Mars Consortium global maps (Viking era): albedo 1x1 deg (60S-60N), thermal inertia 2x2 deg (60S-60N),
   topography 1x1 deg (56S-56N, metres above the 6.1 mbar datum, pre-MOLA). Longitudes in the files are WEST.
   Thermal inertia is in units of 1e-3 cal cm-2 s-1/2 K-1 (Palluconi & Kieffer convention; unit not stated in the label);
   multiply by 41.86 for SI (J m-2 K-1 s-1/2).
   -> outputs/site_map_values.csv
3. NASA Ames general circulation model output (1996 archive): surface temperature minimum and maximum on a
   7.5 x 9 deg grid for four seasons (Ls 10-24, 94-103, 202-220, 267-286). Longitudes are east-positive, -180..171.
   -> outputs/site_gcm_ground_temperature.csv
"""
import os, glob, re
import numpy as np, pandas as pd
import marslib as m

# ---------- 1. TES dust
fr = []
for f in sorted(glob.glob(os.path.join(m.DATA, 'tes_dust', 'MY*', '*.dat'))):
    d = pd.read_csv(f, sep=r'\s+'); d['my'] = int(re.search(r'MY(\d+)', f).group(1)); fr.append(d)
t = pd.concat(fr, ignore_index=True)
t = t[(t.VIS_CDOD > 0) & (t.PSURFMCD > 0)]
t['lat_node'] = (t.LAT / 15).round() * 15
t['ls_bin'] = (t.L_S // 15 * 15).astype(int)
t['dust610'] = t.VIS_CDOD * 610.0 / t.PSURFMCD
t['scenario'] = np.where((t.my == 25) & (t.L_S >= 180), 'storm_year', 'typical')
g = t.groupby(['scenario', 'lat_node', 'ls_bin'])
clim = g.agg(dust610_median=('dust610', 'median'), dust610_p25=('dust610', lambda x: x.quantile(.25)), dust610_p75=('dust610', lambda x: x.quantile(.75)),
             ice_median=('VIS_CWIOD', 'median'), n=('dust610', 'size'), years=('my', lambda x: ' '.join(str(v) for v in sorted(x.unique())))).round(3).reset_index()
clim.to_csv(os.path.join(m.OUT, 'tes_dust_climatology.csv'), index=False)
print('TES retrievals used', len(t), '; cells typical', (clim.scenario == 'typical').sum(), 'storm', (clim.scenario == 'storm_year').sum(), '; min n per cell', clim.n.min())

def grid(scn, col, minn=4):
    c = clim[(clim.scenario == scn) & (clim.n >= minn)]
    p = c.pivot(index='lat_node', columns='ls_bin', values=col).reindex(index=np.arange(-90, 91, 15), columns=np.arange(0, 360, 15))
    return p
def at_lat(p, lat):
    """Linear interpolation between latitude nodes; gaps along Ls filled by circular interpolation."""
    lo = np.floor(lat / 15) * 15; hi = lo + 15; w = (lat - lo) / 15
    a, b = p.loc[lo], p.loc[hi]
    v = a * (1 - w) + b * w
    v = v.where(v.notna(), a.where(a.notna(), b))
    return v
rows = []
G = {(s, c): grid(s, c) for s in ('typical', 'storm_year') for c in ('dust610_median', 'ice_median', 'n')}
for s in m.SITES:
    typ = at_lat(G[('typical', 'dust610_median')], s['lat']); ice = at_lat(G[('typical', 'ice_median')], s['lat'])
    sto = at_lat(G[('storm_year', 'dust610_median')], s['lat']); sice = at_lat(G[('storm_year', 'ice_median')], s['lat'])
    lo = np.floor(s['lat'] / 15) * 15
    ntyp = G[('typical', 'n')].loc[lo].fillna(0) + G[('typical', 'n')].loc[lo + 15].fillna(0)
    for b in range(0, 360, 15):
        rows.append(dict(site=s['id'], ls_bin_start=b, dust610_typical=typ.get(b), ice_typical=ice.get(b), dust610_storm_year=sto.get(b),
                         ice_storm_year=sice.get(b), retrievals_typical=int(ntyp.get(b, 0))))
sd = pd.DataFrame(rows).round(3)
sd.to_csv(os.path.join(m.OUT, 'site_dust_by_season.csv'), index=False)
print(sd.groupby('site').agg(dust_min=('dust610_typical', 'min'), dust_max=('dust610_typical', 'max'), storm_max=('dust610_storm_year', 'max'),
                             ice_max=('ice_typical', 'max'), gaps=('dust610_typical', lambda x: x.isna().sum()), n_med=('retrievals_typical', 'median')).round(2).to_string())

# ---------- 2. global maps (west longitudes)
def load(name, cols): return pd.read_csv(os.path.join(m.DATA, 'global_maps', name), sep=r'\s+', header=None, names=cols)
alb, ti, topo = load('albedo.dat', ['lat', 'lonw', 'v']), load('inertia.dat', ['lat', 'lonw', 'v']), load('topo.dat', ['lat', 'lonw', 'v'])
ti = ti[ti.v > 0]
def sample(df, lat, lone, radius):
    lonw = (360.0 - lone) % 360.0
    dlon = np.abs((df.lonw - lonw + 180) % 360 - 180)
    near = df[(np.abs(df.lat - lat) <= radius) & (dlon <= radius)]
    if near.empty or abs(lat) > df.lat.abs().max() + 0.6: return np.nan, np.nan, np.nan, 0
    d2 = (near.lat - lat) ** 2 + (dlon[near.index] * np.cos(np.radians(lat))) ** 2
    return float(near.v[d2.idxmin()]), float(near.v.min()), float(near.v.max()), len(near)
rows = []
for s in m.SITES:
    a, amin, amax, an = sample(alb, s['lat'], s['lon'], 1.5)
    i, imin, imax, inn = sample(ti, s['lat'], s['lon'], 3.0)
    z, zmin, zmax, zn = sample(topo, s['lat'], s['lon'], 1.5)
    rows.append(dict(site=s['id'], name=s['name'], lat=s['lat'], lon_east=s['lon'], lon_west=round((360 - s['lon']) % 360, 2),
                     albedo=a, albedo_min_nearby=amin, albedo_max_nearby=amax,
                     thermal_inertia_kieffer=i, thermal_inertia_SI=round(i * 41.86) if i == i else np.nan,
                     thermal_inertia_SI_min_nearby=round(imin * 41.86) if imin == imin else np.nan, thermal_inertia_SI_max_nearby=round(imax * 41.86) if imax == imax else np.nan,
                     viking_era_elevation_m=z, viking_era_elev_min_nearby_m=zmin, viking_era_elev_max_nearby_m=zmax,
                     assumed_mola_elevation_km=s['elev']))
mv = pd.DataFrame(rows); mv.to_csv(os.path.join(m.OUT, 'site_map_values.csv'), index=False)
print(mv[['site', 'albedo', 'thermal_inertia_SI', 'thermal_inertia_SI_min_nearby', 'thermal_inertia_SI_max_nearby', 'viking_era_elevation_m', 'assumed_mola_elevation_km']].to_string(index=False))

# ---------- 3. Ames GCM surface temperature
ll = pd.read_csv(os.path.join(m.DATA, 'ames_gcm', 'latlon.dat'), sep=r'\s+', header=None, names=['id', 'nd', 'ls0', 'ls1', 'tau', 'lat', 'lon', 'tmin', 'tmax', 'frost'])
rows = []
for s in m.SITES:
    lon = ((s['lon'] + 180) % 360) - 180
    glat = ll.lat.unique()[np.argmin(np.abs(ll.lat.unique() - s['lat']))]
    lons = ll.lon.unique(); glon = lons[np.argmin(np.abs((lons - lon + 180) % 360 - 180))]
    for _, r in ll[(ll.lat == glat) & (ll.lon == glon)].sort_values('ls0').iterrows():
        rows.append(dict(site=s['id'], grid_lat=glat, grid_lon_east=glon, ls_start=r.ls0, ls_end=r.ls1, model_dust_tau=r.tau,
                         ground_t_min_K=round(r.tmin, 1), ground_t_max_K=round(r.tmax, 1), co2_frost_kg_m2=round(r.frost, 2)))
gc = pd.DataFrame(rows); gc.to_csv(os.path.join(m.OUT, 'site_gcm_ground_temperature.csv'), index=False)
print(gc.pivot(index='site', columns='ls_start', values='ground_t_min_K').to_string()); print(gc.pivot(index='site', columns='ls_start', values='ground_t_max_K').to_string())
print(gc.pivot(index='site', columns='ls_start', values='co2_frost_kg_m2').max(axis=1).to_dict())
