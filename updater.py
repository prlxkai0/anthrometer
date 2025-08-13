#!/usr/bin/env python3
"""
Updater for AnthroMeter GTI
- Reads live proxies from data/live/*.json
- Updates data/categories.json (scores 0–100)
- Evolves data/gti.json time series with zero-floor rule (soft floor already on front-end)
- Appends data/changelog.json
"""

import json, math, datetime, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0].parent
DATA = ROOT / "data"
LIVE = DATA / "live"
DATA.mkdir(exist_ok=True)
LIVE.mkdir(parents=True, exist_ok=True)

GTI_PATH = DATA / "gti.json"
CAT_PATH = DATA / "categories.json"
SRC_PATH = DATA / "sources.json"
CL_PATH  = DATA / "changelog.json"

TODAY = datetime.date.today()
UTCNOW = datetime.datetime.utcnow().isoformat() + "Z"

# ---------- helpers ----------
def load_json(p: Path, default):
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return default
    return default

def clamp(x, lo, hi): return max(lo, min(hi, x))

# ---------- live feeds (optional) ----------
def read_live_score(name: str, default_score: float = 50.0) -> tuple[float, dict]:
    """
    Reads data/live/<name>.json and returns (score, payload)
    """
    fp = LIVE / f"{name}.json"
    if not fp.exists():
        return default_score, {}
    try:
        obj = json.loads(fp.read_text())
        score = float(obj.get("score", default_score))
        return clamp(score, 0.0, 100.0), obj
    except Exception:
        return default_score, {}

# ---------- category model ----------
DEFAULT_WEIGHTS = {
    "Planetary Health": 0.18,
    "Economic Wellbeing": 0.16,
    "Global Peace & Conflict": 0.16,
    "Public Health": 0.16,
    "Civic Freedom & Rights": 0.12,
    "Technological Progress": 0.10,
    "Sentiment & Culture": 0.08,
    "Entropy Index": 0.04
}

def compute_categories():
    # Live inputs
    planetary_score, planetary_raw = read_live_score("planetary", 55.0)
    sentiment_score, sentiment_raw = read_live_score("sentiment", 50.0)

    # Simple placeholders for other categories until we wire them
    # (keep stable mid values so the GTI doesn’t jump erratically)
    scores = {
        "Planetary Health": planetary_score,
        "Economic Wellbeing": 60.0,
        "Global Peace & Conflict": 55.0,
        "Public Health": 65.0,
        "Civic Freedom & Rights": 62.0,
        "Technological Progress": 70.0,
        "Sentiment & Culture": sentiment_score,
        "Entropy Index": 55.0  # remember: in GTI math, entropy acts as a drag
    }
    return scores, {"planetary": planetary_raw, "sentiment": sentiment_raw}

def write_categories(scores: dict):
    obj = {
        "updated": UTCNOW,
        "scores": scores
    }
    CAT_PATH.write_text(json.dumps(obj, indent=2))
    return obj

# ---------- GTI evolution ----------
START_YEAR = 1900
START_VALUE = 300.0
ZERO_FLOOR = 0.0

def ensure_gti_series():
    gti = load_json(GTI_PATH, {"updated": UTCNOW, "series": []})
    if not gti.get("series"):
        # seed 1900..(today.year)
        year = START_YEAR
        series = []
        val = START_VALUE
        while year <= TODAY.year:
            series.append({"year": year, "gti": round(val, 2)})
            # simple gentle change until we have historical feeds
            val = max(ZERO_FLOOR, val * 0.9 if year < 1950 else val * 1.02)
            year += 1
        gti["series"] = series
    return gti

def update_today_point(gti_obj: dict, cat_scores: dict):
    # Map categories to GTI increment with the weighted‑hybrid approach:
    # base = weighted sum of normalized 0–100 categories
    weights = DEFAULT_WEIGHTS
    base = 0.0
    for k, w in weights.items():
        base += w * clamp(cat_scores.get(k, 50.0), 0.0, 100.0)

    # sentiment additive (already included via weights), entropy multiplicative drag:
    entropy = clamp(cat_scores.get("Entropy Index", 55.0), 0.0, 100.0)
    drag = 0.98 + 0.02 * (entropy / 100.0)   # 0.98..1.0 (healthier entropy → less drag)

    # evolve last value → today (unbounded above, zero‑floor below)
    series = gti_obj["series"]
    last = series[-1]["gti"] if series else START_VALUE
    # Normalize base (0..100) into a daily growth factor around ~1.000 ± few bps
    growth = 1.000 + ((base - 50.0) / 50.0) * 0.002   # +/- 0.2% max per step
    new_val = max(ZERO_FLOOR, last * growth * drag)

    # Write/replace this year’s value (we store annual, but update daily same number)
    if series and series[-1]["year"] == TODAY.year:
        series[-1]["gti"] = round(new_val, 2)
    else:
        series.append({"year": TODAY.year, "gti": round(new_val, 2)})

    gti_obj["updated"] = UTCNOW
    return gti_obj

# ---------- Change log ----------
def append_changelog(change_str: str):
    cl = load_json(CL_PATH, {"entries": []})
    # one entry per run with timestamp
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    cl["entries"].append({"date": ts, "change": change_str})
    CL_PATH.write_text(json.dumps(cl, indent=2))

# ---------- main ----------
def main():
    # 1) Compute category scores (reads live/* if present)
    scores, raw = compute_categories()
    write_categories(scores)

    # 2) Update GTI time series
    gti = ensure_gti_series()
    gti = update_today_point(gti, scores)
    GTI_PATH.write_text(json.dumps(gti, indent=2))

    # 3) Log change
    append_changelog(f"Daily update. Planetary={scores['Planetary Health']}, Sentiment={scores['Sentiment & Culture']}.")

    print("Updated:", UTCNOW, "Last GTI:", gti['series'][-1])

if __name__ == "__main__":
    main()
