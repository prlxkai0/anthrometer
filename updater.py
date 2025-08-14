#!/usr/bin/env python3
"""
AnthroMeter updater (schema-agnostic, no changelog)
- Reads optional live inputs from data/live/*.json (planetary, sentiment, markets)
- Computes category scores (0–100) with neutral defaults if feeds missing
- Evolves GTI time series with zero-floor
- Writes:
  data/categories.json
  data/gti.json
  data/status.json        <-- drives the "Today's Signals" panel
"""

import json, datetime
from pathlib import Path

# ---------- Paths ----------
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
LIVE = DATA / "live"
DATA.mkdir(exist_ok=True)
LIVE.mkdir(parents=True, exist_ok=True)

GTI_PATH    = DATA / "gti.json"
CAT_PATH    = DATA / "categories.json"
STATUS_PATH = DATA / "status.json"

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

START_YEAR  = 1900
START_VALUE = 300.0
ZERO_FLOOR  = 0.0

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

def fnum(val, prev=None, default=0.0, nd=3):
    """Force to float with fallback (prev -> default); round to nd decimals."""
    try:
        if val is None:
            raise ValueError("None")
        v = float(val)
        return round(v, nd)
    except Exception:
        if prev is not None:
            try:
                return round(float(prev), nd)
            except Exception:
                pass
        return round(float(default), nd)

def read_live(name: str, default_obj: dict):
    """Read data/live/<name>.json; return dict (never raises)."""
    js = load_json(LIVE / f"{name}.json", default_obj)
    # ensure dict
    return js if isinstance(js, dict) else default_obj.copy()

def read_prev_status():
    js = load_json(STATUS_PATH, {})
    return js if isinstance(js, dict) else {}

# ---------- Categories ----------
def compute_categories():
    # Read live feeds; keep neutral defaults if missing
    planetary = read_live("planetary", {"score": 55.0})
    sentiment = read_live("sentiment", {"score": 50.0})
    markets   = read_live("markets",   {"econ_score": 60.0, "entropy_score": 60.0})

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
    if not isinstance(gti, dict):
        gti = {"updated": UTCNOW, "series": []}
    if not gti.get("series"):
        year, val = START_YEAR, START_VALUE
        series = []
        while year <= TODAY.year:
            series.append({"year": year, "gti": round(val, 2)})
            # placeholder evolution until true backfill
            val = max(ZERO_FLOOR, val * (0.9 if year < 1950 else 1.02))
            year += 1
        gti["series"] = series
    return gti

def update_today_point(gti_obj, cat_scores):
    w = DEFAULT_WEIGHTS
    base = sum(w[k] * clamp(cat_scores.get(k, 50.0), 0, 100) for k in w)  # 0..100
    entropy = clamp(cat_scores.get("Entropy Index", 55.0), 0, 100)
    drag = 0.98 + 0.02 * (entropy / 100.0)  # 0.98..1.00
    series = gti_obj["series"]
    last = series[-1]["gti"] if series else START_VALUE
    growth = 1.000 + ((base - 50.0) / 50.0) * 0.002  # ±0.2%/step max
    new_val = max(ZERO_FLOOR, last * growth * drag)
    if series and series[-1]["year"] == TODAY.year:
        series[-1]["gti"] = round(new_val, 2)
    else:
        series.append({"year": TODAY.year, "gti": round(new_val, 2)})
    gti_obj["updated"] = UTCNOW
    return gti_obj

# ---------- Safe accessors for legacy/new markets schema ----------
def _get_market_field(obj, key, subkey=None):
    """
    Accept both:
      - number form: markets['vix'] = 14.7
      - object form: markets['vix'] = {'last': 14.7, ...}
    """
    if not isinstance(obj, dict):
        return None
    val = obj.get(key, None)
    if subkey is None:
        # if val is dict, prefer 'last' / 'ret30' / 'vol30' in that order
        if isinstance(val, dict):
            for k in ("last", "ret30", "vol30"):
                if k in val:
                    return val.get(k)
            # fallback: any numeric in dict
            for k, v in val.items():
                if isinstance(v, (int, float)):
                    return v
            return None
        # if val is numeric, return it
        if isinstance(val, (int, float)):
            return val
        return None
    else:
        # expecting nested field
        if isinstance(val, dict):
            if subkey in val:
                return val.get(subkey)
            # legacy: sometimes nested key was flattened at top level
        # try flattened variants at top-level markets object
        flat_key = f"{key}_{subkey}"
        flat_val = obj.get(flat_key, None)
        if isinstance(flat_val, (int, float)):
            return flat_val
        # if original val is numeric and they asked for 'last' or 'ret30', return numeric
        if isinstance(val, (int, float)) and subkey in ("last", "ret30", "vol30"):
            return val
        return None

# ---------- Status.json (drives "Today's Signals") ----------
def write_status(gti_obj, raw_inputs):
    prev = read_prev_status()  # to carry forward values if new feed missing
    series = gti_obj.get("series", [])
    last = series[-1]["gti"] if series else START_VALUE
    window = [p["gti"] for p in series[-30:]] if len(series) >= 2 else []
    avg30 = (sum(window) / len(window)) if window else last

    planetary = raw_inputs.get("planetary", {}) or {}
    sentiment = raw_inputs.get("sentiment", {}) or {}
    markets   = raw_inputs.get("markets",   {}) or {}

    p_prev = (prev.get("planetary") or {}) if isinstance(prev.get("planetary"), dict) else {}
    s_prev = (prev.get("sentiment") or {}) if isinstance(prev.get("sentiment"), dict) else {}
    m_prev = (prev.get("markets")   or {}) if isinstance(prev.get("markets"), dict) else {}

    # Planetary
    co2_ppm        = fnum(planetary.get("co2_ppm"),        p_prev.get("co2_ppm"),        0.0, 3)
    gistemp_anom_c = fnum(planetary.get("gistemp_anom_c"), p_prev.get("gistemp_anom_c"), 0.0, 3)
    delta_ppm      = fnum(planetary.get("delta_ppm"),      p_prev.get("delta_ppm"),      0.0, 3)
    delta_anom     = fnum(planetary.get("delta_anom"),     p_prev.get("delta_anom"),     0.0, 3)

    # Sentiment
    avg_tone_30d   = fnum(sentiment.get("avg_tone_30d"), s_prev.get("avg_tone_30d"), 0.0, 2)
    delta_tone     = fnum(sentiment.get("delta_tone"),   s_prev.get("delta_tone"),   0.0, 2)

    # Markets (schema-agnostic)
    acwi_last_prev   = _get_market_field(m_prev, "acwi", "last")
    acwi_ret30_prev  = _get_market_field(m_prev, "acwi", "ret30")
    vix_last_prev    = _get_market_field(m_prev, "vix",  "last")
    brent_last_prev  = _get_market_field(m_prev, "brent","last")
    brent_vol30_prev = _get_market_field(m_prev, "brent","vol30")
    econ_prev        = _get_market_field(m_prev, "econ_score")
    entropy_prev     = _get_market_field(m_prev, "entropy_score")

    acwi_last   = fnum(_get_market_field(markets, "acwi", "last"),  acwi_last_prev,   0.0, 2)
    acwi_ret30  = fnum(_get_market_field(markets, "acwi", "ret30"), acwi_ret30_prev,  0.0, 4)
    vix_last    = fnum(_get_market_field(markets, "vix",  "last"),  vix_last_prev,    0.0, 2)
    brent_last  = fnum(_get_market_field(markets, "brent","last"),  brent_last_prev,  0.0, 2)
    brent_vol30 = fnum(_get_market_field(markets, "brent","vol30"), brent_vol30_prev, 0.0, 4)
    econ_score  = fnum(_get_market_field(markets, "econ_score"),    econ_prev,        60.0, 2)
    entropy_sc  = fnum(_get_market_field(markets, "entropy_score"), entropy_prev,     60.0, 2)

    status = {
        "updated_iso": UTCNOW,
        "gti_last": fnum(last, prev.get("gti_last"), default=START_VALUE, nd=2),
        "gti_30d_avg": fnum(avg30, prev.get("gti_30d_avg"), default=START_VALUE, nd=2),

        "planetary": {
            "co2_ppm":        co2_ppm,
            "gistemp_anom_c": gistemp_anom_c,
            "delta_ppm":      delta_ppm,
            "delta_anom":     delta_anom
        },
        "sentiment": {
            "avg_tone_30d": avg_tone_30d,
            "delta_tone":   delta_tone
        },
        "markets": {
            "acwi_last":   acwi_last,
            "acwi_ret30":  acwi_ret30,
            "vix":         vix_last,
            "brent_last":  brent_last,
            "brent_vol30": brent_vol30,
            "econ_score":  econ_score,
            "entropy_score": entropy_sc
        },
        "note": "Auto-refreshed; values coalesced from latest available data (schema-agnostic)."
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

    print("Updated:", UTCNOW, "Last GTI:", gti['series'][-1])

if __name__ == "__main__":
    main()