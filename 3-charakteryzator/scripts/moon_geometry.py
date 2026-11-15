"""Where the Sun and the Earth are in the lunar sky, for any date.

Low-precision lunar and solar ephemeris (Meeus, Astronomical Algorithms, ch. 25, 47 and 53; largest periodic terms only)
gives the selenographic sub-solar point (b0, l0) and sub-Earth point (optical libration b, l). Accuracy ~0.1-0.3 deg,
plenty for illumination and line-of-sight checks. Topography is NOT included here (the LOLA illumination maps
carry the horizon); these functions describe a flat, unobstructed horizon.
"""
import datetime as dt, math
import numpy as np
I_EQ = 1.54242    # inclination of the lunar equator to the ecliptic, deg
SYNODIC_DAYS = 29.530589

def jd(t):
    if isinstance(t, str): t = dt.datetime.fromisoformat(t.replace('Z', '+00:00')).replace(tzinfo=None)
    return 2451545.0 + (t - dt.datetime(2000, 1, 1, 12)).total_seconds() / 86400.0

def _moon(T):
    r = math.radians
    Lp = 218.3164477 + 481267.88123421 * T; D = 297.8501921 + 445267.1114034 * T
    M = 357.5291092 + 35999.0502909 * T; Mp = 134.9633964 + 477198.8675055 * T; F = 93.2720950 + 483202.0175233 * T
    Om = 125.0445479 - 1934.1362891 * T
    lam = (Lp + 6.288774 * math.sin(r(Mp)) + 1.274027 * math.sin(r(2 * D - Mp)) + 0.658314 * math.sin(r(2 * D))
           + 0.213618 * math.sin(r(2 * Mp)) - 0.185116 * math.sin(r(M)) - 0.114332 * math.sin(r(2 * F))
           + 0.058793 * math.sin(r(2 * D - 2 * Mp)) + 0.057066 * math.sin(r(2 * D - M - Mp)) + 0.053322 * math.sin(r(2 * D + Mp))
           + 0.045758 * math.sin(r(2 * D - M)) - 0.040923 * math.sin(r(M - Mp)) - 0.034720 * math.sin(r(D)) - 0.030383 * math.sin(r(M + Mp)))
    beta = (5.128122 * math.sin(r(F)) + 0.280602 * math.sin(r(Mp + F)) + 0.277693 * math.sin(r(Mp - F)) + 0.173237 * math.sin(r(2 * D - F))
            + 0.055413 * math.sin(r(2 * D - F + Mp)) + 0.046271 * math.sin(r(2 * D - F - Mp)) + 0.032573 * math.sin(r(2 * D + F)))
    dist = (385000.56 - 20905.355 * math.cos(r(Mp)) - 3699.111 * math.cos(r(2 * D - Mp)) - 2955.968 * math.cos(r(2 * D))
            - 569.925 * math.cos(r(2 * Mp)))
    return lam % 360, beta, dist, F % 360, Om % 360, M

def _sun(T, M):
    r = math.radians; e = 0.016708634
    C = (1.914602 - 0.004817 * T) * math.sin(r(M)) + 0.019993 * math.sin(r(2 * M)) + 0.000289 * math.sin(r(3 * M))
    lon = (280.46646 + 36000.76983 * T + C) % 360
    R = 1.000001018 * (1 - e * e) / (1 + e * math.cos(r(M + C)))
    return lon, R

def _libration(lam, beta, F, Om):
    r, d = math.radians, math.degrees
    W = r(lam - Om); b = r(beta); I = r(I_EQ)
    A = math.atan2(math.sin(W) * math.cos(b) * math.cos(I) - math.sin(b) * math.sin(I), math.cos(W) * math.cos(b))
    l = (d(A) - F + 180) % 360 - 180
    bb = d(math.asin(-math.sin(W) * math.cos(b) * math.sin(I) - math.sin(b) * math.cos(I)))
    return l, bb

def subpoints(t):
    """Selenographic sub-Earth (lat, lon) and sub-solar (lat, lon) points in degrees (east longitude, -180..180),
    plus Earth-Moon distance (km) and Sun-Moon distance (AU)."""
    T = (jd(t) - 2451545.0) / 36525.0
    lam, beta, dist, F, Om, M = _moon(T); slon, R = _sun(T, M)
    le, be = _libration(lam, beta, F, Om)
    au = 149597870.7
    lam_h = slon + 180 + (dist / (R * au)) * math.degrees(math.cos(math.radians(beta)) * math.sin(math.radians(slon - lam)))
    beta_h = (dist / (R * au)) * beta
    ls, bs = _libration(lam_h, beta_h, F, Om)
    return dict(sub_earth_lat=round(be, 3), sub_earth_lon=round(le, 3), sub_solar_lat=round(bs, 3), sub_solar_lon=round(ls, 3),
                earth_moon_km=round(dist), sun_moon_au=round(R + dist / au * math.cos(math.radians(slon - lam)), 5))

def elevation(lat, lon, sub_lat, sub_lon):
    """Elevation (deg) of a body whose sub-point is (sub_lat, sub_lon), seen from (lat, lon) over a flat horizon."""
    p, q = math.radians(lat), math.radians(sub_lat)
    return math.degrees(math.asin(max(-1.0, min(1.0, math.sin(p) * math.sin(q) + math.cos(p) * math.cos(q) * math.cos(math.radians(lon - sub_lon))))))

def at(lat, lon, t):
    """Everything time-dependent about the sky at one point and one instant."""
    s = subpoints(t)
    sun = elevation(lat, lon, s['sub_solar_lat'], s['sub_solar_lon']); earth = elevation(lat, lon, s['sub_earth_lat'], s['sub_earth_lon'])
    hour = (((lon - s['sub_solar_lon']) % 360) / 15.0 + 12) % 24          # 12 = local noon
    flux = 1361.0 / s['sun_moon_au'] ** 2
    return dict(sun_elevation_deg=round(sun, 2), earth_elevation_deg=round(earth, 2), local_lunar_hour=round(hour, 2),
                sunlit_flat_horizon=sun > -0.27, earth_visible_flat_horizon=earth > -0.95,
                noon_sun_elevation_deg=round(max(0.0, 90 - abs(lat - s['sub_solar_lat'])), 2),
                solar_flux_toa_wm2=round(flux, 1), **s)

if __name__ == '__main__':
    # checks: at new moon the sub-solar point is on the far side (lon ~180), at full moon near 0; librations within limits
    for label, t in (('new moon 2024-04-08 18:21Z (total eclipse)', '2024-04-08T18:21:00Z'), ('full moon 2024-04-23 23:49Z', '2024-04-23T23:49:00Z')):
        s = subpoints(t); print(f"{label:<44} sub-solar lon {s['sub_solar_lon']:8.2f}  lat {s['sub_solar_lat']:6.2f} | sub-Earth lon {s['sub_earth_lon']:6.2f} lat {s['sub_earth_lat']:6.2f}")
    base = dt.datetime(2026, 1, 1); L = [subpoints(base + dt.timedelta(hours=6 * i)) for i in range(4 * 365 * 3)]
    print('3-year ranges: libration lon %.2f..%.2f (limit ~ +-7.9), lat %.2f..%.2f (+-6.9), sub-solar lat %.2f..%.2f (+-1.54)' % (
        min(x['sub_earth_lon'] for x in L), max(x['sub_earth_lon'] for x in L), min(x['sub_earth_lat'] for x in L), max(x['sub_earth_lat'] for x in L),
        min(x['sub_solar_lat'] for x in L), max(x['sub_solar_lat'] for x in L)))
    print('Apollo 11 site at 2026-11-14 12:00Z:', at(0.674, 23.473, '2026-11-14T12:00:00Z'))
