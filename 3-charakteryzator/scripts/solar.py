"""Sunlight on flat ground through a Mars year. Python twin of model/solar_model.js (same constants and formulas),
used for the summary tables and to cross-check the interactive page.

orbit(sol)       sol 0 = Ls 0. Returns Ls (deg), top-of-atmosphere flux (W/m2), solar declination (rad).
transmit(mu,tau) total (direct + scattered) transmission for dust optical depth tau and cosine of solar zenith mu,
                 delta-Eddington two-stream solution (Meador & Weaver 1980) with single-scattering albedo 0.94, asymmetry 0.70.
daily(lat,tau,sol) energy per sol on a horizontal surface in Wh/m2: (top of atmosphere, surface), and daylight hours.
"""
import numpy as np
E, OBL, LSP, S0, YEAR, SOLSEC = 0.0934, np.radians(25.19), np.radians(251.0), 1361.0 / 1.5237 ** 2, 668.6, 88775.0

def orbit(sol):
    sol = np.asarray(sol, dtype=float)
    nu0 = (0 - LSP) % (2 * np.pi)
    E0 = 2 * np.arctan2(np.sqrt(1 - E) * np.sin(nu0 / 2), np.sqrt(1 + E) * np.cos(nu0 / 2))
    M = E0 - E * np.sin(E0) + 2 * np.pi * sol / YEAR
    Ea = M.copy()
    for _ in range(8): Ea = Ea - (Ea - E * np.sin(Ea) - M) / (1 - E * np.cos(Ea))
    nu = 2 * np.arctan2(np.sqrt(1 + E) * np.sin(Ea / 2), np.sqrt(1 - E) * np.cos(Ea / 2))
    ls = (nu + LSP) % (2 * np.pi)
    flux = S0 * ((1 + E * np.cos(nu)) / (1 - E * E)) ** 2
    return np.degrees(ls), flux, np.arcsin(np.sin(OBL) * np.sin(ls))

def transmit(mu, tau):
    mu = np.asarray(mu, dtype=float); tau = np.asarray(tau, dtype=float) + 0 * mu
    w, g = 0.94, 0.70; f = g * g
    t = (1 - w * f) * tau; w2 = (1 - f) * w / (1 - w * f); g2 = (g - f) / (1 - f)
    g1 = (7 - w2 * (4 + 3 * g2)) / 4; gg2 = -(1 - w2 * (4 - 3 * g2)) / 4
    k = np.sqrt(g1 * g1 - gg2 * gg2)
    mu = np.where(np.abs(1 - k * mu) < 1e-4, mu + 2e-4, mu)
    g3 = (2 - 3 * g2 * mu) / 4; g4 = 1 - g3
    a1 = g1 * g4 + gg2 * g3
    ek, em, et = np.exp(k * t), np.exp(-k * t), np.exp(-t / mu)
    D = (1 - k * k * mu * mu) * ((k + g1) * ek + (k - g1) * em)
    T = et * (1 - w2 / D * ((1 + k * mu) * (a1 + k * g4) * ek - (1 - k * mu) * (a1 - k * g4) * em)) + w2 / D * 2 * k * (g4 + a1 * mu)
    return np.where(tau <= 0, 1.0, np.clip(T, 0, 1))

def daily(lat_deg, tau, sol, n=48):
    ls, flux, dec = orbit(sol)
    phi = np.radians(lat_deg)
    x = -np.tan(phi) * np.tan(dec)
    h0 = np.where(x >= 1, 0.0, np.where(x <= -1, np.pi, np.arccos(np.clip(x, -1, 1))))
    top = np.zeros_like(h0); surf = np.zeros_like(h0)
    for i in range(n):
        h = (i + 0.5) / n * h0
        mu = np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(h)
        ok = mu > 0
        top += np.where(ok, mu, 0)
        surf += np.where(ok, mu * transmit(np.where(ok, mu, 0.5), tau), 0)
    kf = flux * (2 * h0 / n) * SOLSEC / (2 * np.pi) / 3600.0
    return ls, top * kf, surf * kf, h0 / np.pi * SOLSEC / 3600.0
