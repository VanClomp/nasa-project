"""Express the Mars site data in Component 3's TargetProfile feature order (ARCHITECTURE_SPEC 4.2).

Output: outputs/target_profiles_mars_sites.csv, one row per site and 15-degree Ls bin, with the nine
features in spec units and a source column for each. Empty = not available yet.
  0 temp_mean           [C]   mean of daily ground min and max (measured if the station has it, else 1996 Ames model)
  1 temp_diurnal_amp    [C]   daily ground max - min, same sources
  2 thermal_inertia     [SI]  Viking-era 2-degree map
  3 surface_roughness         missing
  4 soil_moisture       [%]   missing (needs neutron / gamma-ray water-equivalent hydrogen map)
  5 dust_aerosol        [-]   TES dust optical depth (0.67 um) at the site's estimated pressure, ice excluded
  6 solar_elevation_max [deg] noon sun elevation from orbit geometry: 90 - |lat - declination|
  7 radiation_proxy     [g/cm2] atmospheric column mass above the site = pressure / g (Earth sea level: 1033)
  8 slope_deg                 missing
  nearest_skylight_km         missing
"""
import os, numpy as np, pandas as pd
O = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'outputs')
G_MARS, OBL = 3.711, np.radians(25.19)
st = pd.read_csv(f'{O}/station_series.csv'); est = pd.read_csv(f'{O}/site_seasonal_estimates.csv')
gcm = pd.read_csv(f'{O}/site_gcm_ground_temperature.csv'); mp = pd.read_csv(f'{O}/site_map_values.csv').set_index('site')
rows = []
for r in est.itertuples():
    s, b = r.site, r.ls_bin_start; ls = b + 7.5; lat = mp.loc[s, 'lat']
    m = st[(st.site == s) & (st.ls_bin_start == b)]
    if len(m) and pd.notna(m.t_ground_min.iloc[0]) and pd.notna(m.t_ground_max.iloc[0]):
        tmin, tmax, tsrc = m.t_ground_min.iloc[0], m.t_ground_max.iloc[0], 'measured ground'
    else:                                     # nearest of the four model seasons (circular in Ls)
        g = gcm[gcm.site == s].copy(); g['d'] = np.minimum(abs(g.ls_start + (g.ls_end - g.ls_start) / 2 - ls) % 360, 360 - abs(g.ls_start + (g.ls_end - g.ls_start) / 2 - ls) % 360)
        g = g.sort_values('d').iloc[0]; tmin, tmax, tsrc = g.ground_t_min_K, g.ground_t_max_K, f'Ames model, season {g.d:.0f} deg away'
    decl = np.degrees(np.arcsin(np.sin(OBL) * np.sin(np.radians(ls))))
    rows.append(dict(site=s, name=mp.loc[s, 'name'], lat=lat, lon_east=mp.loc[s, 'lon_east'], ls_bin_start=b,
        temp_mean=round((tmin + tmax) / 2 - 273.15, 1), temp_diurnal_amp=round(tmax - tmin, 1), temp_source=tsrc,
        thermal_inertia=mp.loc[s, 'thermal_inertia_SI'], surface_roughness=None, soil_moisture=None,
        dust_aerosol=round(r.dust_at_610Pa_typical * r.p_estimate_Pa / 610, 3),
        solar_elevation_max=round(max(0.0, 90 - abs(lat - decl)), 1),
        radiation_proxy_column_g_cm2=round(r.p_estimate_Pa / G_MARS / 10, 1), slope_deg=None, nearest_skylight_km=None))
df = pd.DataFrame(rows); df.to_csv(f'{O}/target_profiles_mars_sites.csv', index=False)
pd.set_option('display.width', 220)
print(df.groupby('site', sort=False).agg(T_mean=('temp_mean', 'mean'), amp=('temp_diurnal_amp', 'mean'), TI=('thermal_inertia', 'first'),
      dust=('dust_aerosol', 'mean'), sun_max=('solar_elevation_max', 'max'), sun_min=('solar_elevation_max', 'min'), col=('radiation_proxy_column_g_cm2', 'mean'),
      measured_T=('temp_source', lambda x: (x == 'measured ground').sum())).round(1).to_string())
