#!/usr/bin/env python3
# Fetches Planetary Health proxies and writes data/live/planetary.json
# Inputs (no API keys):
# - NOAA GML Mauna Loa CO2 monthly CSV (ppm)
# - NASA GISTEMP Global mean temperature anomaly (°C), monthly
#
# References:
# NOAA GML CO2 monthly data page (CSV links): https://gml.noaa.gov/ccgg/trends/data.html
# NASA GISTEMP global-mean monthly data: https://data.giss.nasa.gov/gistemp/
#
# Output schema:
# {
#   "updated": "UTC ISO",
#   "co2_ppm": 420.12,
#   "co2_ppm_yoy": 2.81,
#   "gistemp_anom_c": 1.29,
#   "score": 0-100
# }

import csv, io, json, math, datetime, statistics
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "live"
OUT.mkdir(parents=True, exist_ok=True)

def fetch_url(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def parse_noaa_co2_monthly() -> tuple[float, float]:
    """
    Returns (latest_ppm, yoy_ppm) using NOAA GML Mauna Loa monthly mean CSV.
    File format: comment lines start with '#', columns: year, month, decimal, average, interpolated, trend, #days
    """
    # Stable CSV link (monthly means)
    # (The "co2_mm_mlo.csv" path is documented on NOAA GML's trends page.)
    url = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv"
    txt = fetch_url(url)
    rows = []
    for line in txt.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7:
            continue
        year = int(parts[0]); month = int(parts[1])
        avg = parts[3]
        # Some months may have -99.99; prefer "interpolated" in col 4 if avg invalid
        if avg == "-99.99":
            val = float(parts[4])
        else:
            val = float(avg)
        rows.append((year, month, val))
    if not rows:
        raise RuntimeError("No CO2 rows parsed")
    rows.sort()
    latest_year, latest_month, latest_ppm = rows[-1]

    # YoY: compare to same month previous year if present, else last 12 months
    prev_candidates = [(y, m, v) for (y, m, v) in rows if y == latest_year - 1 and m == latest_month]
    if prev_candidates:
        yoy = latest_ppm - prev_candidates[-1][2]
    elif len(rows) > 12:
        yoy = latest_ppm - rows[-13][2]
    else:
        yoy = 0.0
    return latest_ppm, yoy

def parse_gistemp_global_monthly() -> float:
    """
    Returns latest global mean monthly temperature anomaly (°C).
    We use the CSV listed on the GISTEMP page (global-mean monthly).
    """
    # CSV with global mean monthly anomalies
    # GISTEMP offers multiple CSVs; this one is stable for global monthly means.
    url = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
    txt = fetch_url(url)

    # The file contains header lines and a table with months Jan..Dec and 'J-D'
    last_anom = None
    reader = csv.reader(io.StringIO(txt))
    header_passed = False
    for row in reader:
        if not row or "Year" in row[0]:
            header_passed = True
            continue
        if not header_passed:
            continue
        # Expect: [Year, Jan, Feb, ..., Dec, J-D]
        try:
            year = int(row[0])
        except Exception:
            continue
        # find the last non-empty monthly anomaly in the row
        monthly = []
        for i in range(1, 13):
            cell = row[i].strip()
            if cell in ("", "*****"):
                monthly.append(None)
            else:
                # Values are in 0.01°C in some tables; in v4 CSV they are usually °C already
                # Many GISTEMP CSVs store values as strings like "1.24"
                try:
                    monthly.append(float(cell))
                except:
                    monthly.append(None)
        # pick the last month with a value
        for v in reversed(monthly):
            if isinstance(v, (int, float)):
                last_anom = float(v)
                break
    if last_anom is None:
        raise RuntimeError("No GISTEMP anomaly parsed")
    return last_anom

def score_planetary(co2_ppm: float, yoy: float, anom_c: float) -> float:
    """
    Heuristic 0–100 scoring (higher = healthier).
    - Penalize higher CO2 and faster YoY growth.
    - Penalize higher positive temp anomaly.
    We map each component to 0–100, then average.
    """
    # CO2 level score: map 300–450 ppm → 100–10 (clip)
    co2_score = 100 - (max(300.0, min(450.0, co2_ppm)) - 300.0) * (90.0 / 150.0)
    # YoY growth score: 0–4 ppm → 100–10 (clip)
    yoy_score = 100 - (max(0.0, min(4.0, yoy))) * (90.0 / 4.0)
    # Temperature anomaly score: 0–1.5°C → 100–10 (clip); >1.5°C trends toward 5
    anom = max(0.0, min(1.5, abs(anom_c)))
    temp_score = 100 - anom * (90.0 / 1.5)
    # Heavy weight temp & growth relative to absolute CO2 level
    score = 0.35*co2_score + 0.30*yoy_score + 0.35*temp_score
    return max(0.0, min(100.0, score))

def main():
    co2_ppm, yoy = parse_noaa_co2_monthly()
    anom_c = parse_gistemp_global_monthly()
    score = round(score_planetary(co2_ppm, yoy, anom_c), 2)
    out = {
        "updated": datetime.datetime.utcnow().isoformat() + "Z",
        "co2_ppm": round(co2_ppm, 3),
        "co2_ppm_yoy": round(yoy, 3),
        "gistemp_anom_c": round(anom_c, 3),
        "score": score
    }
    (OUT / "planetary.json").write_text(json.dumps(out, indent=2))
    print("Planetary updated:", out)

if __name__ == "__main__":
    main()
