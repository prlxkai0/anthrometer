#!/usr/bin/env python3
"""
Economic Wellbeing (stub via World Bank WLD, no API key).
Indicators (latest available year):
- Inflation, consumer prices (annual %)        FP.CPI.TOTL.ZG  (lower ~2% best)
- Unemployment, total (% of total labor force) SL.UEM.TOTL.ZS  (lower better)
- GDP per capita growth (annual %)             NY.GDP.PCAP.KD.ZG (higher up to ~4–5% best)

Outputs a 0–100 score (higher = better).
"""
import json, os, math
from urllib.request import urlopen
from urllib.error import URLError

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CATEGORIES_PATH = os.path.join(DATA_DIR, "categories.json")

BASE = "https://api.worldbank.org/v2/country/WLD/indicator/{code}?format=json&per_page=70"  # ~70 years

CODES = {
    "inflation": "FP.CPI.TOTL.ZG",
    "unemployment": "SL.UEM.TOTL.ZS",
    "gdp_pc_growth": "NY.GDP.PCAP.KD.ZG",
}

def _fetch_latest(code):
    url = BASE.format(code=code)
    with urlopen(url, timeout=15) as resp:
        data = json.load(resp)
    # data[1] is list of observations with latest first (not guaranteed)
    vals = []
    for row in data[1]:
        v = row.get("value", None)
        if v is not None:
            try:
                year = int(row.get("date", "0"))
                vals.append((year, float(v)))
            except Exception:
                pass
    if not vals:
        return None
    # pick the most recent year with a number
    vals.sort(key=lambda x: x[0], reverse=True)
    return vals[0][1]

def _last_econ():
    try:
        with open(CATEGORIES_PATH) as f:
            blob = json.load(f)
        return float(blob.get("scores", {}).get("Economic Wellbeing", 50.0))
    except Exception:
        return 50.0

def score_inflation(pct):
    # 2% -> 100; 5% -> ~70; 10% -> ~40; >=20% -> ~10; deflation (<0) penalized slightly
    if pct is None:
        return None
    # Penalize both high inflation and deflation
    if pct >= 0:
        # linear from 2%..20% to 100..10; below 2% up to 0 gets small penalty, < -2% worse
        if pct <= 2.0: return 95 + (2.0 - pct) * 2.5  # 2%->95, 0%->100, mild deflation improves slightly
        if pct >= 20.0: return 10.0
        return 100 - (pct - 2.0) * (90.0 / 18.0)
    else:
        # Deflation risk: -2% -> 70, lower gets worse
        if pct <= -4.0: return 40.0
        # 0 to -4 maps from 100 down to 40
        return 100 + (pct) * 15.0  # -2% -> 70

def score_unemployment(pct):
    # 3% -> 95; 5% -> 85; 10% -> 60; 20% -> ~25; >25% -> 15
    if pct is None:
        return None
    if pct <= 3.0: return 95.0
    if pct >= 25.0: return 15.0
    # map 3..25 to 95..15 linearly
    return 95.0 - (pct - 3.0) * (80.0 / 22.0)

def score_gdp_pc_growth(pct):
    # -10% -> 10; -2% -> 40; 0% -> 55; 2% -> 75; 4% -> 90; >=6% -> 95
    if pct is None:
        return None
    if pct <= -10.0: return 10.0
    if pct >= 6.0: return 95.0
    # piecewise linear
    if pct < -2.0:
        # -10..-2 -> 10..40
        return 10.0 + (pct + 10.0) * (30.0 / 8.0)
    if pct < 0.0:
        # -2..0 -> 40..55
        return 40.0 + (pct + 2.0) * (15.0 / 2.0)
    if pct < 2.0:
        # 0..2 -> 55..75
        return 55.0 + pct * 10.0
    if pct < 4.0:
        # 2..4 -> 75..90
        return 75.0 + (pct - 2.0) * 7.5
    # 4..6 -> 90..95
    return 90.0 + (pct - 4.0) * 2.5

def clamp01x100(v):
    if v is None: return None
    return max(min(v, 100.0), 0.0)

def get_score():
    try:
        infl = _fetch_latest(CODES["inflation"])
        une  = _fetch_latest(CODES["unemployment"])
        gdp  = _fetch_latest(CODES["gdp_pc_growth"])

        s_infl = clamp01x100(score_inflation(infl))
        s_une  = clamp01x100(score_unemployment(une))
        s_gdp  = clamp01x100(score_gdp_pc_growth(gdp))

        # Combine: inflation 0.4, unemployment 0.4, gdp_pc_growth 0.2
        parts = [(s_infl, 0.4), (s_une, 0.4), (s_gdp, 0.2)]
        vals = [v*w for (v,w) in parts if v is not None]
        wsum = sum(w for (v,w) in parts if v is not None)
        if not vals or wsum == 0:
            return _last_econ()
        return round(sum(vals)/wsum, 2)
    except URLError:
        return _last_econ()
    except Exception:
        return _last_econ()

if __name__ == "__main__":
    print(get_score())
