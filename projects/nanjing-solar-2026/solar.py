"""Core solar position calculations (pure Python, no third-party dependencies).

Implements the NOAA Solar Calculator algorithm (based on the Astronomical
Almanac / Jean Meeus).  Accurate to roughly 0.01 degree (about 1 minute of
time) for the quantities we report.

Reference:
    NOAA Global Monitoring Division - Solar Calculator:
    https://gml.noaa.gov/grad/solcalc/
"""

from __future__ import annotations

import math
from datetime import datetime, time as dtime, timedelta, timezone

DEG = math.pi / 180.0


def _normalize_deg(x: float) -> float:
    """Wrap an angle in degrees to [0, 360)."""
    return ((x % 360.0) + 360.0) % 360.0


def _julian_day(dt: datetime) -> float:
    """Julian Day (Meeus formula) for a timezone-aware UTC datetime."""
    dt = dt.astimezone(timezone.utc)
    y, m = dt.year, dt.month
    day = dt.day + (dt.hour + dt.minute / 60.0 + dt.second / 3600.0) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd = (math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1))
          + day + b - 1524.5)
    return jd


def _julian_centuries(dt: datetime) -> float:
    """Julian centuries T since J2000.0 (2000-01-01 12:00 UT)."""
    return (_julian_day(dt) - 2451545.0) / 36525.0


def solar_declination_equation_of_time(dt: datetime) -> tuple[float, float]:
    """Sun's (apparent) declination in degrees and equation of time in minutes.

    ``dt`` may be naive (treated as UTC) or timezone-aware (converted to UTC).
    """
    utc = dt if dt.tzinfo is None else dt.astimezone(timezone.utc)
    t = _julian_centuries(utc)
    l0 = _normalize_deg(280.46646 + t * (36000.76983 + t * 0.0003032))   # mean longitude
    m = _normalize_deg(357.52911 + t * (35999.05029 - t * 0.0001537))    # mean anomaly
    e = 0.016708634 - t * (0.000042037 + t * 0.0000001267)               # eccentricity

    # Sun's equation of centre (deg)
    c = (math.sin(m * DEG) * (1.914602 - t * (0.004817 + t * 0.000014))
         + math.sin(2 * m * DEG) * (0.019993 - t * 0.000101)
         + math.sin(3 * m * DEG) * 0.000289)
    true_long = l0 + c

    omega = 125.04 - 1934.136 * t                                        # perigee nutation
    app_long = true_long - 0.00569 - 0.00478 * math.sin(omega * DEG)     # apparent longitude
    epsilon = 23.439291 - t * 0.0130042 + 0.00256 * math.cos(omega * DEG)  # obliquity

    dec = math.degrees(math.asin(math.sin(epsilon * DEG) * math.sin(app_long * DEG)))

    # Equation of time (minutes): solar_time - mean_solar_time
    y = math.tan(epsilon * DEG / 2.0) ** 2
    eqt = 4.0 * math.degrees(
        y * math.sin(2 * l0 * DEG) - 2 * e * math.sin(m * DEG)
        + 4 * e * y * math.sin(m * DEG) * math.cos(2 * l0 * DEG)
        - 0.5 * y * y * math.sin(4 * l0 * DEG)
        - 1.25 * e * e * math.sin(2 * m * DEG))

    return dec, eqt


def sun_position(local_dt: datetime, lat_deg: float, lon_deg: float,
                 timezone_hours: float) -> tuple[float, float, float]:
    """Solar azimuth and altitude at an instant of LOCAL standard time.

    Parameters
    ----------
    local_dt :
        Timezone-aware datetime carrying the local clock time to evaluate at
        (e.g. an aware datetime in UTC+08:00).  The actual wall-clock value is
        used; only the offset is read to derive UTC.
    lat_deg, lon_deg :
        Geographic latitude (deg, north positive) and longitude (deg, east
        positive).
    timezone_hours :
        Fixed UTC offset of the local standard time, e.g. 8 for China (UTC+8).

    Returns
    -------
    (azimuth, altitude_geom, altitude_app) in degrees.
        azimuth        : measured clockwise from north (0=N, 90=E, 180=S, 270=W).
        altitude_geom  : geometric elevation above the horizon (no refraction).
        altitude_app   : apparent elevation including standard atmospheric
                         refraction (NOAA), i.e. what an observer sees.
    """
    dec, eqt = solar_declination_equation_of_time(local_dt)

    # --- True solar time and hour angle ----------------------------------
    # Wall-clock minutes of the local standard time.
    clock_minutes = local_dt.hour * 60 + local_dt.minute + local_dt.second / 60.0
    # True solar time in minutes; 4 min per degree of longitude offset from
    # the zone meridian, plus the equation of time.
    tst = clock_minutes + 4.0 * lon_deg - 60.0 * timezone_hours + eqt
    ha = _normalize_deg(tst / 4.0 - 180.0)      # hour angle in degrees, 0..360
    if ha > 180.0:
        ha -= 360.0                             # -> -180..180 (west positive)

    # --- Zenith angle and geometric elevation -----------------------------
    lat_r, dec_r, ha_r = lat_deg * DEG, dec * DEG, ha * DEG
    cos_zen = (math.sin(lat_r) * math.sin(dec_r)
               + math.cos(lat_r) * math.cos(dec_r) * math.cos(ha_r))
    cos_zen = max(-1.0, min(1.0, cos_zen))
    alt_geom = 90.0 - math.degrees(math.acos(cos_zen))

    # --- Atmospheric refraction (NOAA), returns correction in degrees -----
    if alt_geom > 85.0:
        refrac = 0.0
    elif alt_geom > 5.0:
        tan_el = math.tan(alt_geom * DEG)
        refrac = (58.1 / tan_el - 0.07 / tan_el ** 3 + 0.000086 / tan_el ** 5) / 3600.0
    elif alt_geom > -0.575:
        refrac = (1735.0 + alt_geom * (-518.2 + alt_geom * (103.4 + alt_geom
                  * (-12.79 + alt_geom * 0.711)))) / 3600.0
    else:
        refrac = -20.772 / math.tan(alt_geom * DEG) / 3600.0
    alt_app = alt_geom + refrac

    # --- Azimuth, clockwise from north (0..360) ---------------------------
    # sin(A) and cos(A) share a positive common factor cos(alt), so the ratio
    # atan2(sinA, cosA) is exact and continuous (no branch problems at noon).
    sin_a = -math.cos(dec_r) * math.sin(ha_r)
    cos_a = (math.cos(lat_r) * math.sin(dec_r)
             - math.sin(lat_r) * math.cos(dec_r) * math.cos(ha_r))
    az = _normalize_deg(math.degrees(math.atan2(sin_a, cos_a)))

    return az, alt_geom, alt_app


def find_azimuth_crossing(lat_deg: float, lon_deg: float, timezone_hours: float,
                          target_az: float, day, start_local, end_local) -> datetime:
    """Time of day (local standard time) when azimuth crosses ``target_az``.

    Solves azimuth(t) = target_az on the interval ``[start_local, end_local]``
    (times given as ``datetime.time``) of the given calendar day, by bisection
    on the full solar position so the changing declination is accounted for.

    The azimuth is monotone increasing through the day, so a single crossing
    exists on the chosen half-day interval.  ``start_local``/``end_local`` must
    bracket the crossing and must not straddle the 0/360 wrap of the azimuth.
    """
    tz = timezone(timedelta(hours=timezone_hours))
    lo = datetime.combine(day, start_local, tzinfo=tz)
    hi = datetime.combine(day, end_local, tzinfo=tz)

    def f(dt: datetime) -> float:
        az, _, _ = sun_position(dt, lat_deg, lon_deg, timezone_hours)
        return az - target_az

    flo, fhi = f(lo), f(hi)
    if flo == 0.0:
        return lo
    if fhi == 0.0:
        return hi
    if flo * fhi > 0.0:
        raise ValueError(
            f"no sign change on [{start_local}, {end_local}] for target "
            f"azimuth {target_az:.1f} deg on {day} (f0={flo:.3f}, f1={fhi:.3f})")

    for _ in range(80):                     # ~24 h / 2**80 -> far below 1 ms
        mid = lo + (hi - lo) / 2.0
        fm = f(mid)
        if fm == 0.0:
            return mid
        if flo * fm < 0.0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return lo + (hi - lo) / 2.0


def due_east_and_west(lat_deg: float, lon_deg: float, timezone_hours: float,
                      day) -> tuple[datetime, datetime]:
    """Times the sun is exactly due east (az 90) and due west (az 270).

    The geometric crossing exists every day at this latitude (for Nanjing,
    |tan(declination)/tan(latitude)| < 1 throughout the year).  Note the sun
    may be below the horizon at those instants (in winter the due-east/du-west
    crossings happen before sunrise / after sunset).

    The search brackets avoid the azimuth's 0/360 wrap, which sits at solar
    midnight (between ~23:48 and ~00:19 local).  Morning: azimuth < 90 at
    02:00 and > 90 by noon for every day of the year.  Evening: azimuth ~180
    at 12:00 and in 325..360 by 23:30 (before the wrap), for every day.
    """
    time_a = find_azimuth_crossing(lat_deg, lon_deg, timezone_hours, 90.0,
                                   day, dtime(2, 0), dtime(11, 59, 59))
    time_b = find_azimuth_crossing(lat_deg, lon_deg, timezone_hours, 270.0,
                                   day, dtime(12, 0), dtime(23, 30, 0))
    return time_a, time_b
