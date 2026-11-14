"""Global climate predictor for any point on Mars (latitude, elevation and surface properties) and season.

pressure_pa(ls, elev_m)          Viking 1 multi-year seasonal curve moved to the point's elevation (scale height 10.8 km).
dust_tau(lat, ls, scenario)      MGS TES column dust optical depth at 0.67 um, zonal median by 15 deg latitude x 15 deg Ls,
                                 normalised to 610 Pa; multiply by p/610 for the point. scenario 'typical' or 'storm_year'.
ice_tau(lat, ls)                 TES water-ice cloud optical depth (same grid).
ground_temps(...)                1-D surface energy balance with heat conduction into the ground, solved to a periodic
                                 diurnal state for one season: absorbed sunlight (dust-attenuated, two-stream), downward
                                 infrared from the atmosphere (one calibrated coefficient), thermal emission, conduction set
                                 by thermal inertia, and a CO2 frost floor. Returns daily min/max/mean ground temperature.
"""
import os, numpy as np, pandas as pd
from functools import lru_cache
import solar
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'outputs')
SIGMA, EPS, RHO_C, SOL = 5.670e-8, 0.98, 1.2e6, 88775.0
H_SCALE, Z_VL1 = 10800.0, -3627.0
R_GAS = 191.8            # J kg-1 K-1, Mars atmosphere (95% CO2)
G_MARS = 3.711

# ------------------------------------------------------------------ pressure
@lru_cache(None)
def _pcurve():
    p = pd.read_csv(os.path.join(OUT, 'pressure_reference_vl1.csv'))
    return p.ls_bin_start.to_numpy() + 2.5, p.p_vl1_Pa.to_numpy()
def pressure_pa(ls, elev_m):
    x, y = _pcurve()
    pv = np.interp(np.asarray(ls) % 360, np.r_[x - 360, x, x + 360], np.r_[y, y, y])
    return pv * np.exp(-(elev_m - Z_VL1) / H_SCALE)

# ------------------------------------------------------------------ dust and ice
@lru_cache(None)
def _grid(scenario, col):
    d = pd.read_csv(os.path.join(OUT, 'tes_dust_climatology.csv'))
    lats = np.arange(-90, 91, 15.0); lss = np.arange(0, 360, 15)
    def piv(sc):
        g = d[d.scenario == sc].pivot_table(index='lat_node', columns='ls_bin', values=col).reindex(index=lats, columns=lss)
        return g
    g = piv(scenario)
    if scenario != 'typical':                       # storm-year gaps: fall back to the typical year
        g = g.fillna(piv('typical'))
    a = g.to_numpy(float)
    for i in range(a.shape[0]):                     # circular interpolation along Ls
        row = a[i]; ok = np.isfinite(row)
        if ok.sum() >= 2:
            xs = lss[ok]; a[i] = np.interp(lss, np.r_[xs - 360, xs, xs + 360], np.r_[row[ok]] .repeat(1)[np.r_[np.arange(ok.sum()), np.arange(ok.sum()), np.arange(ok.sum())]])
    for j in range(a.shape[1]):                     # then along latitude, nearest value at the poles (polar night)
        col_ = a[:, j]; ok = np.isfinite(col_)
        if ok.any(): a[:, j] = np.interp(lats, lats[ok], col_[ok])
    return lats, lss, a
def _bilinear(lat, ls, scenario, col):
    lats, lss, a = _grid(scenario, col)
    ls = np.asarray(ls, dtype=float) % 360
    x = np.r_[lss, 360.0]; A = np.c_[a, a[:, :1]]
    out = np.array([np.interp(l, x, [np.interp(lat, lats, A[:, k]) for k in range(len(x))]) for l in np.atleast_1d(ls) + 7.5 - 7.5])
    return out if np.ndim(ls) else float(out[0])
def dust_tau(lat, ls, scenario='typical'):   # at 610 Pa; bin centres are at ls_bin + 7.5
    return _bilinear(lat, np.asarray(ls) - 7.5, scenario, 'dust610_median')
def ice_tau(lat, ls):
    return _bilinear(lat, np.asarray(ls) - 7.5, 'typical', 'ice_median')
def total_tau(lat, ls, p_pa, scenario='typical'):
    return dust_tau(lat, ls, scenario) * p_pa / 610.0 + ice_tau(lat, ls)

# ------------------------------------------------------------------ orbit helpers
def sol_of_ls(ls):
    """Sol (0 = Ls 0) at which the orbit reaches this Ls, inverting solar.orbit."""
    s = np.arange(0, 669, 0.25); L = solar.orbit(s)[0]
    L = np.unwrap(np.radians(L)); L = np.degrees(L)
    return np.interp(np.asarray(ls) % 360, L, s)
def frost_point(p_pa):
    return 3148.0 / (23.102 - np.log(np.maximum(p_pa, 1.0) / 100.0))   # Clausius-Clapeyron for CO2, p in mbar

# ------------------------------------------------------------------ ground temperature
IR_COEF = 0.10     # calibrated on Curiosity (rms 5.7 K), tested on Perseverance (rms 5-6 K): outputs/thermal_model_validation.csv
def ground_temps(lat, ls, albedo, ti, p_pa, tau, ir_coef=None, n_sols=12, steps=720):
    """Vectorised over seasons: ls, p_pa, tau may be arrays of equal length. Returns (Tmin, Tmax, Tmean) arrays in K."""
    ir = IR_COEF if ir_coef is None else ir_coef
    ls = np.atleast_1d(np.asarray(ls, float)); p = np.broadcast_to(np.asarray(p_pa, float), ls.shape)
    tau = np.broadcast_to(np.asarray(tau, float), ls.shape); S = ls.size
    _, flux, dec = solar.orbit(sol_of_ls(ls))
    phi = np.radians(lat)
    k = ti ** 2 / RHO_C; kap = k / RHO_C
    skin = np.sqrt(kap * SOL / np.pi)
    dz = [skin / 8]
    while sum(dz) < 6 * skin: dz.append(dz[-1] * 1.18)
    dz = np.array(dz); N = len(dz)
    dt = SOL / steps
    if dt > 0.4 * dz[0] ** 2 / kap:                       # keep the explicit scheme stable
        steps = int(np.ceil(SOL / (0.4 * dz[0] ** 2 / kap))); dt = SOL / steps
    hour = 2 * np.pi * (np.arange(steps) / steps) - np.pi
    mu = np.sin(phi) * np.sin(dec)[:, None] + np.cos(phi) * np.cos(dec)[:, None] * np.cos(hour)[None, :]
    absorbed = np.where(mu > 0, (1 - albedo) * flux[:, None] * mu * solar.transmit(np.clip(mu, 1e-3, 1), tau[:, None]), 0.0)
    mean_toa = (flux[:, None] * np.clip(mu, 0, None)).mean(axis=1)
    l_down = ir * (1 + 0.8 * tau) * np.sqrt(p / 610.0) * mean_toa                     # constant through the sol
    tf = frost_point(p)
    t_eq = np.maximum(((absorbed.mean(axis=1) + l_down) / (EPS * SIGMA)) ** 0.25, tf)
    T = np.repeat(t_eq[:, None], N, axis=1)
    zc = np.cumsum(dz) - dz / 2; dzc = np.diff(zc)
    cap0 = RHO_C * dz[0]
    rec = np.empty((S, steps))
    for sol_i in range(n_sols):
        for i in range(steps):
            cond = k * (T[:, 1:] - T[:, :-1]) / dzc                                   # W/m2, positive = heat flows up
            q_top = absorbed[:, i] + l_down - EPS * SIGMA * T[:, 0] ** 4 + cond[:, 0]
            dT = np.empty_like(T)
            dT[:, 0] = q_top / cap0
            dT[:, 1:-1] = (cond[:, 1:] - cond[:, :-1]) / (RHO_C * dz[1:-1])
            dT[:, -1] = -cond[:, -1] / (RHO_C * dz[-1])
            T = T + dT * dt
            T[:, 0] = np.maximum(T[:, 0], tf)
            if sol_i == n_sols - 1: rec[:, i] = T[:, 0]
    return rec.min(axis=1), rec.max(axis=1), rec.mean(axis=1)

def air_density(p_pa, t_k): return p_pa / (R_GAS * t_k)
def column_mass_g_cm2(p_pa): return p_pa / G_MARS / 10.0
