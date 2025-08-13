#!/usr/bin/env python3
"""
Planetary Health (stub): fetch latest CO₂ (ppm) and map to 0–100 (higher = better).
- Tries NOAA Mauna Loa monthly CSV (no API key).
- On failure, falls back to the last saved score in data/categories.json (if present), else 50.
- Mapping (clamped): 280 ppm -> 100, 500 ppm -> 0
"""
import os, json, math, csv, io, sys
from urllib.request import urlopen

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CATEGORIES_PATH = os.path.join(DATA_DIR, "categories.json")

# Candidate CSV URL (subject to change by NOAA; kept simple for a stub)
NOAA_CSV = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_trend_mlo.csv"

def clamp01(x):
    return 0.0 if x < 0 else (1.0 if x > 1 else x)

def ppm_to_score(ppm):
    # 280 -> 100, 500 -> 0 (linear), clamp
    t = (ppm - 280.0) / (500.0 - 280.0)
    return round((1.0 - clamp01(t)) * 100.0, 2)

def _read_last_categories_score():
    try:
        with open(CATEGORIES_PATH) as f:
            blob = json.load(f)
        return float(blob.get("scores", {}).get("Planetary Health", 50.0))
    except Exception:
        return 50.0

def get_score():
    try:
        # Fetch CSV and parse the last valid monthly mean from end
        with urlopen(NOAA_CSV, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        # CSV has comment lines at top; find numeric rows
        reader = csv.reader(io.StringIO(raw))
        rows = []
        for r in reader:
            if len(r) >= 2:
                try:
                    # Some rows: [year, month, decimal_date, average, deseasonalized, ...]
                    # We'll try 'average' (index 3 or 4 depending on file version)
                    # Safer: scan floats and pick a plausible ppm (300–500)
                    floats = [float(x) for x in r if x.replace('.', '', 1).replace('-', '', 1).isdigit()]
                    if floats:
                        rows.append(floats)
                except Exception:
                    pass
        # Walk backwards for a plausible ppm
        ppm = None
        for fr in reversed(rows):
            for x in reversed(fr):
                if 300.0 <= x <= 500.0:
                    ppm = x
                    break
            if ppm is not None:
                break
        if ppm is None:
            raise RuntimeError("No plausible ppm found in CSV.")
        return ppm_to_score(ppm)
    except Exception:
        # Fallback to last known value (or neutral 50)
        return _read_last_categories_score()

if __name__ == "__main__":
    print(get_score())
