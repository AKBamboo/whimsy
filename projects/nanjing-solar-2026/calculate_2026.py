"""Compute and report the 2026 solar geometry for Nanjing, China.

Nanjing:  32°03′39″N  118°46′44″E   (UTC/GMT+08:00)

For every day of 2026 this script reports:
  * solar azimuth & altitude at 06:00 and 18:00 (Beijing time, UTC+08:00)
  * the times the sun is exactly due east (timeA, azimuth 90 deg) and due
    west (timeB, azimuth 270 deg)
  * the elapsed time from timeA to timeB

Output:
  * a per-day CSV file  output/nanjing_solar_2026.csv
  * a console summary with annual extremes and the seasonal benchmarks
    (equinoxes and solstices)

Run:  python calculate_2026.py
"""

from __future__ import annotations

import csv
from datetime import date, datetime, time as dtime, timezone, timedelta
from pathlib import Path

from solar import sun_position, due_east_and_west, solar_declination_equation_of_time

# --- Location & time zone -------------------------------------------------
LAT_DEG = 32.0 + 3 / 60 + 39 / 3600        # 32°03′39″N
LON_DEG = 118.0 + 46 / 60 + 44 / 3600      # 118°46′44″E
TZ_HOURS = 8.0                             # UTC/GMT+08:00 (China standard time)
TZ = timezone(timedelta(hours=TZ_HOURS))

YEAR = 2026
OUT_DIR = Path(__file__).resolve().parent / "output"
CSV_PATH = OUT_DIR / "nanjing_solar_2026.csv"


def fmt_time(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S")


def fmt_duration(secs: float) -> str:
    total = max(0.0, secs)
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = int(round(total % 60))
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        h += 1
    return f"{h:02d}:{m:02d}:{s:02d}"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    first_day = date(YEAR, 1, 1)
    last_day = date(YEAR, 12, 31)
    ndays = (last_day - first_day).days + 1

    for day in (first_day + timedelta(days=i) for i in range(ndays)):
        # Reference declination / equation of time at local noon.
        noon = datetime.combine(day, dtime(12, 0), tzinfo=TZ)
        decl, eqt = solar_declination_equation_of_time(noon)

        dt_0600 = datetime.combine(day, dtime(6, 0), tzinfo=TZ)
        dt_1800 = datetime.combine(day, dtime(18, 0), tzinfo=TZ)
        az6, alt6, alt6a = sun_position(dt_0600, LAT_DEG, LON_DEG, TZ_HOURS)
        az18, alt18, alt18a = sun_position(dt_1800, LAT_DEG, LON_DEG, TZ_HOURS)

        time_a, time_b = due_east_and_west(LAT_DEG, LON_DEG, TZ_HOURS, day)
        az_a, alt_a, alt_aa = sun_position(time_a, LAT_DEG, LON_DEG, TZ_HOURS)
        az_b, alt_b, alt_ba = sun_position(time_b, LAT_DEG, LON_DEG, TZ_HOURS)

        duration_s = (time_b - time_a).total_seconds()

        rows.append({
            "date": day.isoformat(),
            "declination_deg": f"{decl:+.3f}",
            "eqt_min": f"{eqt:+.2f}",
            "az_0600_deg": f"{az6:.2f}",
            "alt_0600_deg": f"{alt6:.2f}",
            "alt_app_0600_deg": f"{alt6a:.2f}",
            "az_1800_deg": f"{az18:.2f}",
            "alt_1800_deg": f"{alt18:.2f}",
            "alt_app_1800_deg": f"{alt18a:.2f}",
            "timeA": fmt_time(time_a),
            "azA_deg": f"{az_a:.2f}",
            "altA_deg": f"{alt_a:.2f}",
            "sun_up_at_A": "yes" if alt_aa > 0.0 else "no",
            "timeB": fmt_time(time_b),
            "azB_deg": f"{az_b:.2f}",
            "altB_deg": f"{alt_b:.2f}",
            "sun_up_at_B": "yes" if alt_ba > 0.0 else "no",
            "duration_hms": fmt_duration(duration_s),
            "duration_hours": f"{duration_s / 3600.0:.3f}",
        })

    # --- Write CSV ---------------------------------------------------------
    fieldnames = list(rows[0].keys())
    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # --- Console summary ---------------------------------------------------
    print(f"Nanjing {LAT_DEG:.5f}N {LON_DEG:.5f}E, UTC+{TZ_HOURS:g}  |  {YEAR}")
    print(f"Days computed: {len(rows)}  ({first_day.isoformat()} .. {last_day.isoformat()})")
    print(f"CSV written to: {CSV_PATH}\n")

    head = ["date", "az_0600_deg", "alt_0600_deg", "az_1800_deg", "alt_1800_deg",
            "timeA", "timeB", "duration_hms"]
    print(f"{'date':<11}{'az6':>8}{'alt6':>8}{'az18':>8}{'alt18':>8} "
          f"{'timeA':>9}{'timeB':>9}{'A->B':>9}")
    for r in rows[:5]:
        print(f"{r['date']:<11}{r['az_0600_deg']:>8}{r['alt_0600_deg']:>8}"
              f"{r['az_1800_deg']:>8}{r['alt_1800_deg']:>8}"
              f"{r['timeA']:>9}{r['timeB']:>9}{r['duration_hms']:>9}")
    print("  ...")
    for r in rows[-3:]:
        print(f"{r['date']:<11}{r['az_0600_deg']:>8}{r['alt_0600_deg']:>8}"
              f"{r['az_1800_deg']:>8}{r['alt_1800_deg']:>8}"
              f"{r['timeA']:>9}{r['timeB']:>9}{r['duration_hms']:>9}")

    # Annual extremes of the duration timeA -> timeB.
    dur = [float(r["duration_hours"]) for r in rows]
    imin = dur.index(min(dur))
    imax = dur.index(max(dur))
    print("\nDuration timeA -> timeB (time sun's azimuth lies between due-east "
          "and due-west):")
    print(f"  shortest: {rows[imin]['date']}  {rows[imin]['duration_hms']} "
          f"(timeA {rows[imin]['timeA']} -> timeB {rows[imin]['timeB']})")
    print(f"  longest:  {rows[imax]['date']}  {rows[imax]['duration_hms']} "
          f"(timeA {rows[imax]['timeA']} -> timeB {rows[imax]['timeB']})")

    # Seasonal benchmarks.
    print("\nBenchmark days (equinoxes / solstices, UTC+8):")
    for target in ("2026-03-20", "2026-06-21", "2026-09-23", "2026-12-21"):
        row = next((r for r in rows if r["date"] == target), None)
        if row:
            print(f"  {row['date']}  timeA {row['timeA']} (sun up: {row['sun_up_at_A']}), "
                  f"timeB {row['timeB']} (sun up: {row['sun_up_at_B']}), "
                  f"duration {row['duration_hms']}")

    print("\nNote: 'sun up' uses the apparent (refraction-corrected) altitude "
          "at timeA/timeB.  In winter the due-east and due-west crossings "
          "occur while the sun is below the horizon (see README).")


if __name__ == "__main__":
    main()
