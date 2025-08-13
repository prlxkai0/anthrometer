#!/usr/bin/env python3
import json, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LIVE = DATA / "live"
DATA.mkdir(exist_ok=True); LIVE.mkdir(parents=True, exist_ok=True)

GTI_PATH = DATA / "gti.json"
CAT_PATH = DATA / "categories.json"
CL_PATH  = DATA / "changelog.json"
STATUS_PATH = DATA / "status.json"

TODAY = datetime.date.today()
UTCNOW = datetime.datetime.utcnow().isoformat() + "Z"

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
START_YEAR = 1900
START_VALUE = 300.0
ZERO_FLOOR = 0.0

def load_json(p: Path, default):
    if p.exists():
        try: return json.loads(p.read_text())
        except Exception: return default
    return default

def clamp(x, lo, hi): return max(lo, min(hi, x))

def read_live(name, default=None):
    return load_json(LIVE/f"{name}.json", default or {})

def compute_categories():
    planetary  = read_live("planetary", {"score":55.0})
    sentiment  = read_live("sentiment", {"score":50.0})
    markets    = read_live("markets",   {"econ_score":60.0, "entropy_score":60.0})

    scores = {
        "Planetary Health": float(planetary.get("score", 55.0)),
        "Economic Wellbeing": float(markets.get("econ_score", 60.0)),
        "Global Peace & Conflict": 55.0,   # will wire later
        "Public Health": 65.0,             # will wire later
        "Civic Freedom & Rights": 62.0,    # will wire later
        "Technological Progress": 70.0,    # will wire later
        "Sentiment & Culture": float(sentiment.get("score", 50.0)),
        "Entropy Index": float(markets.get("entropy_score", 60.0))
    }
    return scores, {"planetary":planetary, "sentiment":sentiment, "markets":markets}

def write_categories(scores):
    CAT_PATH.write_text(json.dumps({"updated":UTCNOW, "scores":scores}, indent=2))

def ensure_gti_series():
    gti = load_json(GTI_PATH, {"updated":UTCNOW, "series":[]})
    if not gti["series"]:
        year = START_YEAR; val = START_VALUE
        while year <= TODAY.year:
            gti["series"].append({"year":year, "gti": round(val,2)})
            val = max(ZERO_FLOOR, val * (0.9 if year < 1950 else 1.02))
            year += 1
    return gti

def update_today_point(gti_obj, cat_scores):
    w = DEFAULT_WEIGHTS
    base = sum(w[k] * clamp(cat_scores.get(k,50.0), 0.0, 100.0) for k in w)
    entropy = clamp(cat_scores.get("Entropy Index", 55.0), 0.0, 100.0)
    drag = 0.98 + 0.02 * (entropy / 100.0)
    series = gti_obj["series"]
    last = series[-1]["gti"] if series else START_VALUE
    growth = 1.000 + ((base - 50.0)/50.0) * 0.002
    new_val = max(ZERO_FLOOR, last * growth * drag)
    if series and series[-1]["year"] == TODAY.year:
        series[-1]["gti"] = round(new_val,2)
    else:
        series.append({"year":TODAY.year, "gti": round(new_val,2)})
    gti_obj["updated"] = UTCNOW
    return gti_obj

def append_changelog(change_str):
    cl = load_json(CL_PATH, {"entries":[]})
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    cl["entries"].append({"date": ts, "change": change_str})
    CL_PATH.write_text(json.dumps(cl, indent=2))

def write_status(gti_obj, raw):
    series = gti_obj["series"]
    last = series[-1]["gti"] if series else None
    window = [p["gti"] for p in series[-30:]] if len(series)>=2 else []
    avg30 = sum(window)/len(window) if window else last or 0.0
    status = {
        "updated_iso": UTCNOW,
        "gti_last": last,
        "gti_30d_avg": round(avg30,2),
        "planetary": {
          "co2_ppm": raw.get("planetary",{}).get("co2_ppm"),
          "gistemp_anom_c": raw.get("planetary",{}).get("gistemp_anom_c"),
          "delta_ppm": raw.get("planetary",{}).get("delta_ppm"),
          "delta_anom": raw.get("planetary",{}).get("delta_anom"),
        },
        "sentiment": {
          "avg_tone_30d": raw.get("sentiment",{}).get("avg_tone_30d"),
          "delta_tone": raw.get("sentiment",{}).get("delta_tone"),
        },
        "markets": {
          "acwi_last": raw.get("markets",{}).get("acwi",{}).get("last"),
          "acwi_ret30": raw.get("markets",{}).get("acwi",{}).get("ret30"),
          "vix": raw.get("markets",{}).get("vix",{}).get("last"),
          "brent_last": raw.get("markets",{}).get("brent",{}).get("last"),
          "brent_vol30": raw.get("markets",{}).get("brent",{}).get("vol30"),
          "econ_score": raw.get("markets",{}).get("econ_score"),
          "entropy_score": raw.get("markets",{}).get("entropy_score"),
        },
        "note": "Signals compare to recent baselines. Lower VIX/volatility = more ordered (higher Entropy score)."
    }
    STATUS_PATH.write_text(json.dumps(status, indent=2))

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
