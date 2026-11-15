"""Lunar surface temperature through a lunar day, for any latitude (flat ground, no horizon shading).

1-D heat conduction into regolith following the standard model of Hayne et al. (2017, JGR Planets, Diviner global
thermophysical properties): density rising from 1100 to 1800 kg/m3 with e-folding depth H = 0.06 m, contact
conductivity rising from 7.4e-4 to 3.4e-3 W/m/K, radiative conductivity term chi=2.7, temperature-dependent heat
capacity, albedo 0.12 increasing at low sun, emissivity 0.95, geothermal flux 0.018 W/m2.
Polar and shadowed ground is governed by topography; there the Diviner polar products are used instead of this model.
"""
import numpy as np
SIGMA, EMIS, Q_GEO = 5.670e-8, 0.95, 0.018
DAY = 29.530589 * 86400.0
RHO_S, RHO_D, H = 1100.0, 1800.0, 0.06
KS, KD, CHI = 7.4e-4, 3.4e-3, 2.7
C_POLY = (8.9093e-9, -1.234e-5, 2.36e-3, 2.763, -3.6125)      # heat capacity c(T) [J/kg/K], Hayne et al. 2017 (highest power first)

def heat_cap(T): return np.polyval(C_POLY, T)

def _grid():
    dz = [0.002]
    while sum(dz) < 1.5: dz.append(min(dz[-1] * 1.12, 0.05))
    dz = np.array(dz); z = np.cumsum(dz) - dz / 2
    rho = RHO_D - (RHO_D - RHO_S) * np.exp(-z / H); kc = KD - (KD - KS) * (RHO_D - rho) / (RHO_D - RHO_S)
    return dz, z, rho, kc

def albedo(inc_deg, a0=0.12):
    x = np.clip(inc_deg, 0, 90)
    return a0 + 0.06 * (x / 45.0) ** 3 + 0.25 * (x / 90.0) ** 8

def surface_temps(lat, sub_solar_lat=0.0, a0=0.12, flux=1361.0, days=6, steps=None):
    """Returns (Tmin, Tmax, Tmean, T_at_local_hours[24]) of the surface over one lunar day, in K."""
    lat = np.atleast_1d(np.asarray(lat, float)); n = lat.size
    dz, z, rho, kc = _grid(); N = dz.size
    if steps is None: steps = 6000
    dt = DAY / steps
    hour_angle = 2 * np.pi * np.arange(steps) / steps - np.pi
    phi = np.radians(lat)[:, None]
    d = np.radians(np.broadcast_to(np.asarray(sub_solar_lat, float), lat.shape))[:, None]   # scalars or one per column
    flux = np.broadcast_to(np.asarray(flux, float), lat.shape)[:, None]
    mu = np.sin(phi) * np.sin(d) + np.cos(phi) * np.cos(d) * np.cos(hour_angle)[None, :]
    inc = np.degrees(np.arccos(np.clip(mu, -1, 1)))
    absorbed = np.where(mu > 0, flux * mu * (1 - albedo(inc, a0)), 0.0)
    T = np.full((n, N), 1.0) * (220.0 * np.cos(phi) ** 0.25 + 40.0)
    dzc = np.diff(z); h0 = dz[0] / 2
    Ts = T[:, 0].copy(); rec = np.empty((n, steps))
    if _surface_kernel is not None:                       # compiled time loop (same scheme, ~100x faster)
        rec = _surface_kernel(np.ascontiguousarray(absorbed, dtype=np.float64), np.ascontiguousarray(T, dtype=np.float64),
                              Ts.astype(float), dz.astype(float), dzc.astype(float), rho.astype(float), kc.astype(float),
                              float(h0), float(dt), int(days), int(steps), np.array(C_POLY, float))
        hrs = rec[:, (np.arange(24) * steps // 24 + steps // 2) % steps]
        return rec.min(axis=1), rec.max(axis=1), rec.mean(axis=1), hrs
    for day_i in range(days):
        for i in range(steps):
            k0 = kc[0] * (1 + CHI * (T[:, 0] / 350.0) ** 3)
            for _ in range(4):        # surface skin temperature: absorbed + conduction from below = emitted (Newton)
                f = absorbed[:, i] + k0 * (T[:, 0] - Ts) / h0 - EMIS * SIGMA * Ts ** 4
                Ts = np.clip(Ts - f / (-k0 / h0 - 4 * EMIS * SIGMA * Ts ** 3), 15.0, 450.0)
            Tm = 0.5 * (T[:, 1:] + T[:, :-1])
            k = 0.5 * (kc[1:] + kc[:-1]) * (1 + CHI * (Tm / 350.0) ** 3)
            cond = k * (T[:, 1:] - T[:, :-1]) / dzc
            cap = rho * heat_cap(T)
            dT = np.empty_like(T)
            dT[:, 0] = (k0 * (Ts - T[:, 0]) / h0 + cond[:, 0]) / (cap[:, 0] * dz[0])
            dT[:, 1:-1] = (cond[:, 1:] - cond[:, :-1]) / (cap[:, 1:-1] * dz[1:-1])
            dT[:, -1] = (Q_GEO - cond[:, -1]) / (cap[:, -1] * dz[-1])
            T = T + dT * dt
            if day_i == days - 1: rec[:, i] = Ts
    hrs = rec[:, (np.arange(24) * steps // 24 + steps // 2) % steps]      # local hour 0..23 (12 = noon)
    return rec.min(axis=1), rec.max(axis=1), rec.mean(axis=1), hrs

def _surface_loop(absorbed, T, Ts, dz, dzc, rho, kc, h0, dt, days, steps, cpoly):
    """The time loop of surface_temps for numba, with the same operations in the same order as the numpy version:
    4 Newton steps for the skin temperature, then one explicit conduction step of the whole column."""
    n, N = T.shape
    rec = np.empty((n, steps))
    cond = np.empty(N - 1); dT = np.empty(N)
    for c in range(n):
        ts = Ts[c]
        for day_i in range(days):
            for i in range(steps):
                k0 = kc[0] * (1 + CHI * (T[c, 0] / 350.0) ** 3)
                for _ in range(4):
                    f = absorbed[c, i] + k0 * (T[c, 0] - ts) / h0 - EMIS * SIGMA * ts ** 4
                    ts = ts - f / (-k0 / h0 - 4 * EMIS * SIGMA * ts ** 3)
                    if ts < 15.0: ts = 15.0
                    elif ts > 450.0: ts = 450.0
                for j in range(N - 1):
                    tm = 0.5 * (T[c, j + 1] + T[c, j])
                    kk = 0.5 * (kc[j + 1] + kc[j]) * (1 + CHI * (tm / 350.0) ** 3)
                    cond[j] = kk * (T[c, j + 1] - T[c, j]) / dzc[j]
                for j in range(N):
                    t = T[c, j]
                    cp = (((cpoly[0] * t + cpoly[1]) * t + cpoly[2]) * t + cpoly[3]) * t + cpoly[4]   # Horner, as np.polyval
                    cap = rho[j] * cp
                    if j == 0:
                        dT[j] = (k0 * (ts - T[c, 0]) / h0 + cond[0]) / (cap * dz[0])
                    elif j == N - 1:
                        dT[j] = (Q_GEO - cond[N - 2]) / (cap * dz[N - 1])
                    else:
                        dT[j] = (cond[j] - cond[j - 1]) / (cap * dz[j])
                for j in range(N):
                    T[c, j] = T[c, j] + dT[j] * dt
                if day_i == days - 1: rec[c, i] = ts
    return rec

try:                                                      # optional: falls back to the numpy loop without numba
    import numba
    _surface_kernel = numba.njit(cache=True)(_surface_loop)
except ImportError:
    _surface_kernel = None

if __name__ == '__main__':
    import time
    t = time.time(); lo, hi, me, hrs = surface_temps([0, 26.1, 45, 60, 75, 85])
    print(f'{time.time()-t:.1f} s')
    for la, a, b, c in zip([0, 26.1, 45, 60, 75, 85], lo, hi, me): print(f'lat {la:5.1f}: min {a:6.1f} K  max {b:6.1f} K  mean {c:6.1f} K')
