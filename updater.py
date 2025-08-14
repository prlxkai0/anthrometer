#!/usr/bin/env python3
"""
AnthroMeter updater (no-changelog; numeric coalescing)
- Reads live inputs from data/live/*.json (planetary, sentiment, markets)
- Computes category scores (0–100) with neutral defaults if feeds missing
- Evolves GTI with zero-floor
- Writes: data/categories.json, data/gti.json, data/status.json
"""

import json, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
LIVE = DATA / "live"
DATA.mkdir(exist_ok=True); LIVE.mkdir(parents=True, exist_ok=True)

GTI_PATH    = DATA / "gti.json"
CAT_PATH    = DATA / "categories.json"
STATUS_PATH = DATA / "status.json"

TODAY  = datetime.date.today()
UTCNOW = datetime.datetime.utcnow().isoformat() + "Z"

DEFAULT_WEIGHTS = {
    "Planetary Health":        0.18,
    "Economic Wellbeing":      0.16,
    "Global Peace & Conflict": 0.16,
    "Public Health":           0.16,
    "Civic Freedom & Rights":  0.12,
    "Technological Progress":  0.10,
    "Sentiment & Culture":     0.08,
    "Entropy Index":           0.04,
}

START_YEAR  = 1900
START_VALUE = 300.0
ZERO_FLOOR  = 0.0

def load_json(p: Path, default):
    try:
        if p.exists(): return json.loads(p.read_text())
    except Exception:
        pass
    return default

def clamp(x, lo, hi):
    try: return max(lo, min(hi, float(x)))
    except Exception: return lo

def fnum(val, prev=None, default=0.0, nd=3):
    try:
        if val is None: raise ValueError("None")
        return round(float(val), nd)
    except Exception:
        if prev is not None:
            try: return round(float(prev), nd)
            except Exception: pass
        return round(float(default), nd)

def read_live(name, default): return load_json(LIVE/f"{name}.json", default)
def read_prev_status(): return load_json(STATUS_PATH, {})

def compute_categories():
    planetary = read_live("planetary", {"score":55.0})
    sentiment = read_live("sentiment", {"score":50.0})
    markets   = read_live("markets",   {"econ_score":60.0, "entropy_score":60.0})

    scores = {
        "Planetary Health":        clamp(planetary.get("score", 55.0), 0, 100),
        "Economic Wellbeing":      clamp(markets.get("econ_score", 60.0), 0, 100),
        "Global Peace & Conflict": 55.0,
        "Public Health":           65.0,
        "Civic Freedom & Rights":  62.0,
        "Technological Progress":  70.0,
        "Sentiment & Culture":     clamp(sentiment.get("score", 50.0), 0, 100),
        "Entropy Index":           clamp(markets.get("entropy_score", 60.0), 0, 100),
    }
    raw = {"planetary": planetary, "sentiment": sentiment, "markets": markets}
    return scores, raw

def write_categories(scores):
    CAT_PATH.write_text(json.dumps({"updated": UTCNOW, "scores": scores}, indent=2))

def ensure_gti_series():
    gti = load_json(GTI_PATH, {"updated": UTCNOW, "series": []})
    if not gti.get("series"):
        year, val = START_YEAR, START_VALUE
        series=[]
        while year <= TODAY.year:
            series.append({"year": year, "gti": round(val, 2)})
            val = max(ZERO_FLOOR, val * (0.9 if year < 1950 else 1.02))
            year += 1
        gti["series"] = series
    return gti

def update_today_point(gti_obj, cat_scores):
    w = DEFAULT_WEIGHTS
    base = sum(w[k] * clamp(cat_scores.get(k, 50.0), 0, 100) for k in w)
    entropy = clamp(cat_scores.get("Entropy Index", 55.0), 0, 100)
    drag = 0.98 + 0.02 * (entropy / 100.0)
    series = gti_obj["series"]
    last = series[-1]["gti"] if series else START_VALUE
    growth = 1.000 + ((base - 50.0)/50.0) * 0.002
    new_val = max(ZERO_FLOOR, last * growth * drag)
    if series and series[-1]["year"] == TODAY.year:
        series[-1]["gti"] = round(new_val, 2)
    else:
        series.append({"year": TODAY.year, "gti": round(new_val, 2)})
    gti_obj["updated"] = UTCNOW
    return gti_obj

def write_status(gti_obj, raw_inputs):
    prev = read_prev_status()
    series = gti_obj.get("series", [])
    last = series[-1]["gti"] if series else START_VALUE
    window = [p["gti"] for p in series[-30:]] if len(series) >= 2 else []
    avg30 = (sum(window)/len(window)) if window else last

    planetary = raw_inputs.get("planetary", {})
    sentiment = raw_inputs.get("sentiment", {})
    markets   = raw_inputs.get("markets", {})

    p_prev = prev.get("planetary", {})
    s_prev = prev.get("sentiment", {})
    m_prev = prev.get("markets", {})

    status = {
        "updated_iso": UTCNOW,
        "gti_last": fnum(last, prev.get("gti_last"), default=START_VALUE, nd=2),
        "gti_30d_avg": fnum(avg30, prev.get("gti_30d_avg"), default=START_VALUE, nd=2),
        "planetary": {
            "co2_ppm":        fnum(planetary.get("co2_ppm"),        p_prev.get("co2_ppm"),        0.0, 3),
            "gistemp_anom_c": fnum(planetary.get("gistemp_anom_c"), p_prev.get("gistemp_anom_c"), 0.0, 3),
            "delta_ppm":      fnum(planetary.get("delta_ppm"),      p_prev.get("delta_ppm"),      0.0, 3),
            "delta_anom":     fnum(planetary.get("delta_anom"),     p_prev.get("delta_anom"),     0.0, 3)
        },
        "sentiment": {
            "avg_tone_30d": fnum(sentiment.get("avg_tone_30d"), s_prev.get("avg_tone_30d"), 0.0, 2),
            "delta_tone":   fnum(sentiment.get("delta_tone"),   s_prev.get("delta_tone"),   0.0, 2)
        },
        "markets": {
            "acwi_last":   fnum((markets.get("acwi") or {}).get("last"),  (m_prev.get("acwi") or {}).get("last"),  0.0, 2),
            "acwi_ret30":  fnum((markets.get("acwi") or {}).get("ret30"), (m_prev.get("acwi") or {}).get("ret30"), 0.0, 4),
            "vix":         fnum((markets.get("vix")  or {}).get("last"),  (m_prev.get("vix")  or {}).get("last"),  0.0, 2),
            "brent_last":  fnum((markets.get("brent")or {}).get("last"),  (m_prev.get("brent")or {}).get("last"),  0.0, 2),
            "brent_vol30": fnum((markets.get("brent")or {}).get("vol30"), (m_prev.get("brent")or {}).get("vol30"), 0.0, 4),
            "econ_score":  fnum(markets.get("econ_score"),  m_prev.get("econ_score"),  60.0, 2),
            "entropy_score": fnum(markets.get("entropy_score"), m_prev.get("entropy_score"), 60.0, 2)
        },
        "note": "Auto-refreshed; coalesced from latest available data."
    }
    STATUS_PATH.write_text(json.dumps(status, indent=2))

def main():
    scores, raw = compute_categories()
    write_categories(scores)

    gti = ensure_gti_series()
    gti = update_today_point(gti, scores)
    GTI_PATH.write_text(json.dumps(gti, indent=2))

    write_status(gti, raw)

    print("Updated:", UTCNOW, "Last GTI:", gti['series'][-1])

if __name__ == "__main__":
    main()
