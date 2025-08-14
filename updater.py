#!/usr/bin/env python3
"""
AnthroMeter updater (failsafe)
- Reads optional live inputs from data/live/*.json (planetary, sentiment, markets)
- Computes category scores (0–100) with defaults if feeds missing
- Evolves GTI time series with zero-floor rule
- Writes:
  data/categories.json
  data/gti.json
  data/status.json        <-- drives the "Today's Signals" panel
  data/changelog.json
"""

import json, datetime
from pathlib import Path

# ---------- Paths ----------
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
LIVE = DATA / "live"
DATA.mkdir(exist_ok=True)
LIVE.mkdir(parents=True, exist_ok=True)

GTI_PATH   = DATA / "gti.json"
CAT_PATH   = DATA / "categories.json"
CL_PATH    = DATA / "changelog.json"
STATUS_PATH= DATA / "status.json"

TODAY  = datetime.date.today()
UTCNOW = datetime.datetime.utcnow().isoformat() + "Z"

# ---------- Config ----------
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

START_YEAR   = 1900
START_VALUE  = 300.0
ZERO_FLOOR   = 0.0

# ---------- Utils ----------
def load_json(p: Path, default):
    try:
        if p.exists():
            return json.loads(p.read_text())
    except Exception:
        pass
    return default

def clamp(x, lo, hi): 
    try:
        return max(lo, min(hi, float(x)))
    except Exception:
        return lo

# ---------- Inputs ----------
def read_live(name: str, default_obj: dict):
    """Read data/live/<name>.json; return dict (never raises)."""
    return load_json(LIVE / f"{name}.json", default_obj).copy()

# ---------- Categories ----------
def compute_categories():
    # Read live feeds; keep neutral defaults if missing
    planetary = read_live("planetary", {
        "score": 55.0, "co2_ppm": None, "gistemp_anom_c": None,
        "delta_ppm": None, "delta_anom": None
    })
    sentiment = read_live("sentiment", {
        "score": 50.0, "avg_tone_30d": 0.0, "delta_tone": 0.0
    })
    markets   = read_live("markets",   {
        "econ_score": 60.0, "entropy_score": 60.0,
        "acwi": {"last": None, "ret30": 0.0},
        "vix":  {"last": None},
        "brent":{"last": None, "vol30": 0.0}
    })

    scores = {
        "Planetary Health":        clamp(planetary.get("score", 55.0), 0, 100),
        "Economic Wellbeing":      clamp(markets.get("econ_score", 60.0), 0, 100),
        "Global Peace & Conflict": 55.0,  # TODO: wire UCDP/UNHCR
        "Public Health":           65.0,  # TODO: wire WHO/OWID
        "Civic Freedom & Rights":  62.0,  # TODO: wire Freedom House/V-Dem
        "Technological Progress":  70.0,  # TODO: wire arXiv/Crossref
        "Sentiment & Culture":     clamp(sentiment.get("score", 50.0), 0, 100),
        "Entropy Index":           clamp(markets.get("entropy_score", 60.0), 0, 100),
    }
    raw = {"planetary": planetary, "sentiment": sentiment, "markets": markets}
    return scores, raw

def write_categories(scores):
    CAT_PATH.write_text(json.dumps({"updated": UTCNOW, "scores": scores}, indent=2))

# ---------- GTI series ----------
def ensure_gti_series():
    gti = load_json(GTI_PATH, {"updated": UTCNOW, "series": []})
    if not gti.get("series"):
        year, val = START_YEAR, START_VALUE
        series = []
        while year <= TODAY.year:
            series.append({"year": year, "gti": round(val, 2)})
            # gentle history until we backfill for real
            val = max(ZERO_FLOOR, val * (0.9 if year < 1950 else 1.02))
            year += 1
        gti["series"] = series
    return gti

def update_today_point(gti_obj, cat_scores):
    w = DEFAULT_WEIGHTS
    # weighted base (0..100)
    base = sum(w[k] * clamp(cat_scores.get(k, 50.0), 0, 100) for k in w)
    # entropy drag (closer to 100 → less drag)
    entropy = clamp(cat_scores.get("Entropy Index", 55.0), 0, 100)
    drag = 0.98 + 0.02 * (entropy / 100.0)  # 0.98..1.00

    series = gti_obj["series"]
    last = series[-1]["gti"] if series else START_VALUE
    growth = 1.000 + ((base - 50.0) / 50.0) * 0.002  # ±0.2% per step max
    new_val = max(ZERO_FLOOR, last * growth * drag)

    if series and series[-1]["year"] == TODAY.year:
        series[-1]["gti"] = round(new_val, 2)
    else:
        series.append({"year": TODAY.year, "gti": round(new_val, 2)})

    gti_obj["updated"] = UTCNOW
    return gti_obj

# ---------- Change log ----------
def append_changelog(msg: str):
    cl = load_json(CL_PATH, {"entries": []})
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    cl["entries"].append({"date": ts, "change": msg})
    CL_PATH.write_text(json.dumps(cl, indent=2))

# ---------- Status.json (drives "Today's Signals") ----------
def write_status(gti_obj, raw_inputs):
    series = gti_obj.get("series", [])
    last = series[-1]["gti"] if series else None
    window = [p["gti"] for p in series[-30:]] if len(series) >= 2 else []
    avg30 = (sum(window) / len(window)) if window else (last or 0.0)

    planetary = raw_inputs.get("planetary", {})
    sentiment = raw_inputs.get("sentiment", {})
    markets   = raw_inputs.get("markets", {})

    status = {
        "updated_iso": UTCNOW,
        "gti_last": last,
        "gti_30d_avg": round(avg30, 2),

        "planetary": {
            "co2_ppm":        planetary.get("co2_ppm"),
            "gistemp_anom_c": planetary.get("gistemp_anom_c"),
            "delta_ppm":      planetary.get("delta_ppm"),
            "delta_anom":     planetary.get("delta_anom"),
        },
        "sentiment": {
            "avg_tone_30d": sentiment.get("avg_tone_30d"),
            "delta_tone":   sentiment.get("delta_tone"),
        },
        "markets": {
            "acwi_last":   (markets.get("acwi", {}) or {}).get("last"),
            "acwi_ret30":  (markets.get("acwi", {}) or {}).get("ret30"),
            "vix":         (markets.get("vix", {})  or {}).get("last"),
            "brent_last":  (markets.get("brent", {})or {}).get("last"),
            "brent_vol30": (markets.get("brent", {})or {}).get("vol30"),
            "econ_score":  markets.get("econ_score"),
            "entropy_score": markets.get("entropy_score"),
        },

        "note": "Auto-refreshed; signals compare to recent baselines. Lower VIX/volatility = more ordered (higher Entropy)."
    }
    STATUS_PATH.write_text(json.dumps(status, indent=2))

# ---------- Main ----------
def main():
    scores, raw = compute_categories()
    write_categories(scores)

    gti = ensure_gti_series()
    gti = update_today_point(gti, scores)
    GTI_PATH.write_text(json.dumps(gti, indent=2))

    write_status(gti, raw)
    append_changelog(f"Daily update. Econ={scores['Economic Wellbeing']}, Entropy={scores['Entropy Index']}.")

    print("Updated:", UTCNOW, "Last GTI:", gti['series'][-1])

if __name__ == "__main__":
    main()
