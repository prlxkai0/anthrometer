#!/usr/bin/env python3
"""
Updater — builds categories, evolves GTI, and writes status.json for live UI.
"""
import json, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LIVE = DATA / "live"
DATA.mkdir(exist_ok=True); LIVE.mkdir(parents=True, exist_ok=True)

GTI_PATH = DATA / "gti.json"
CAT_PATH = DATA / "categories.json"
SRC_PATH = DATA / "sources.json"     # assumed present
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

def read_live(name, default_score=50.0):
    obj = load_json(LIVE/f"{name}.json", {})
    score = float(obj.get("score", default_score))
    return clamp(score,0.0,100.0), obj

def compute_categories():
    planetary_score, planetary_raw = read_live("planetary", 55.0)
    sentiment_score, sentiment_raw = read_live("sentiment", 50.0)
    scores = {
        "Planetary Health": planetary_score,
        "Economic Wellbeing": 60.0,
        "Global Peace & Conflict": 55.0,
        "Public Health": 65.0,
        "Civic Freedom & Rights": 62.0,
        "Technological Progress": 70.0,
        "Sentiment & Culture": sentiment_score,
        "Entropy Index": 55.0
    }
    return scores, {"planetary":planetary_raw, "sentiment":sentiment_raw}

def write_categories(scores):
    obj = {"updated": UTCNOW, "scores": scores}
    CAT_PATH.write_text(json.dumps(obj, indent=2))
    return obj

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
    weights = DEFAULT_WEIGHTS
    base = sum(weights[k] * clamp(cat_scores.get(k,50.0),0.0,100.0) for k in weights)
    entropy = clamp(cat_scores.get("Entropy Index", 55.0),0.0,100.0)
    drag = 0.98 + 0.02 * (entropy/100.0)
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

def write_status(gti_obj, raw_inputs):
    # build 30-day avg for KPI delta (approx using last 30 points if available)
    series = gti_obj["series"]
    last = series[-1]["gti"] if series else None
    window = [p["gti"] for p in series[-30:]] if len(series)>=2 else []
    avg30 = sum(window)/len(window) if window else last or 0.0
    status = {
        "updated_iso": UTCNOW,
        "gti_last": last,
        "gti_30d_avg": round(avg30,2),
        "planetary": {
          "co2_ppm": raw_inputs.get("planetary",{}).get("co2_ppm"),
          "gistemp_anom_c": raw_inputs.get("planetary",{}).get("gistemp_anom_c"),
          "delta_ppm": raw_inputs.get("planetary",{}).get("delta_ppm"),
          "delta_anom": raw_inputs.get("planetary",{}).get("delta_anom"),
        },
        "sentiment": {
          "avg_tone_30d": raw_inputs.get("sentiment",{}).get("avg_tone_30d"),
          "delta_tone": raw_inputs.get("sentiment",{}).get("delta_tone"),
        },
        "note": "Auto-refreshed every 60s; deltas vs recent baselines."
    }
    STATUS_PATH.write_text(json.dumps(status, indent=2))

def main():
    scores, raw_inputs = compute_categories()
    write_categories(scores)
    gti = ensure_gti_series()
    gti = update_today_point(gti, scores)
    GTI_PATH.write_text(json.dumps(gti, indent=2))
    write_status(gti, raw_inputs)
    append_changelog(f"Daily update. Planetary={scores['Planetary Health']}, Sentiment={scores['Sentiment & Culture']}.")
    print("Updated:", UTCNOW, "Last GTI:", gti['series'][-1])

if __name__ == "__main__":
    main()
