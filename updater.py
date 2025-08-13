#!/usr/bin/env python3
# updater.py — GTI daily with live Planetary, Economic, Public Health, Peace & Conflict, Sentiment, Entropy.
# Robust to missing files/modules; clamps moves; exponential smoothing; writes changelog.

import json, os, datetime, traceback

# ================= CONFIG =================
MIN_FLOOR       = 100.0
ALPHA           = 4.0
BETA            = 0.20
GAMMA           = 1.5
MAX_DAILY_MOVE  = 25.0
SMOOTHING       = 0.60
DATA_DIR        = os.path.join(os.path.dirname(__file__), 'data')

WEIGHTS = {
    "Planetary Health":         0.18,
    "Economic Wellbeing":       0.12,
    "Global Peace & Conflict":  0.12,
    "Public Health":            0.18,
    "Civic Freedom & Rights":   0.12,
    "Technological Progress":   0.08,
    "Sentiment & Culture":      0.10,
    "Entropy Index":            0.10
}

GTI_PATH        = os.path.join(DATA_DIR, 'gti.json')
CATEGORIES_PATH = os.path.join(DATA_DIR, 'categories.json')
CHANGELOG_PATH  = os.path.join(DATA_DIR, 'changelog.json')

# ================ IO helpers =================
def load_json(path, default=None):
    try:
        with open(path) as f: return json.load(f)
    except Exception:
        return default

def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f: json.dump(obj, f, indent=2)

def clamp_floor(v, floor): return v if v >= floor else floor
def clamp_0_100(v): return 0 if v < 0 else (100 if v > 100 else v)
def clamp_abs(v, cap): return cap if v>cap else (-cap if v<-cap else v)

def compute_weighted_raw(scores_0_100: dict) -> float:
    return sum(float(scores_0_100.get(k, 50))*w for k,w in WEIGHTS.items())

def apply_modifiers(raw_0_100: float, entropy: float, sentiment: float) -> float:
    entropy = clamp_0_100(entropy); sentiment = clamp_0_100(sentiment)
    adjusted = raw_0_100 * (1.0 - (entropy/100.0)*BETA)  # multiplicative drag
    final    = adjusted + (sentiment - 50.0)*GAMMA       # additive boost
    return clamp_0_100(final)

def append_changelog_entry(date_str, change_str, max_entries=365):
    blob = load_json(CHANGELOG_PATH, {"entries": []})
    entries = blob.get("entries", [])
    if not entries or entries[-1].get("date") != date_str:
        entries.append({"date": date_str, "change": change_str})
        if len(entries) > max_entries: entries = entries[-max_entries:]
        blob["entries"] = entries
        save_json(CHANGELOG_PATH, blob)

def init_gti_if_missing():
    gti = load_json(GTI_PATH)
    if isinstance(gti, dict) and "series" in gti and isinstance(gti["series"], list) and gti["series"]:
        return gti
    # Initialize series 1900..current year with flat starting value
    start_year = 1900
    now_year = datetime.datetime.utcnow().year
    series = [{"year": y, "gti": 300.0} for y in range(start_year, now_year+1)]
    gti = {"updated": "", "series": series}
    save_json(GTI_PATH, gti)
    print(f"[init] Created gti.json with {len(series)} years starting at 300.0")
    return gti

def safe_module_score(mod_name, last_value, label):
    """Import module.mod.get_score() safely; on failure return last_value or 50."""
    try:
        mod = __import__(mod_name)
        val = float(mod.get_score())
        if not (val == val):  # NaN check
            raise ValueError("NaN score")
        return max(0.0, min(100.0, val))
    except Exception as e:
        print(f"[warn] {label}: using fallback ({last_value}) due to {type(e).__name__}: {e}")
        return 50.0 if last_value is None else float(last_value)

# ================ MAIN =================
def main():
    # Load or initialize GTI series
    gti_blob = init_gti_if_missing()
    series = gti_blob["series"]

    # Categories blob (scores+modifiers), tolerant load
    cat_blob = load_json(CATEGORIES_PATH, {"updated": "", "scores": {}, "modifiers": {}})
    scores   = dict(cat_blob.get("scores", {}))
    mods     = dict(cat_blob.get("modifiers", {}))

    # Last known category values (for graceful fallback)
    last_vals = {k: (scores.get(k, None)) for k in WEIGHTS.keys()}

    # Live stubs (all optional; fall back if missing)
    planet_score  = safe_module_score("planetary_live", last_vals.get("Planetary Health"), "Planetary")
    econ_score    = safe_module_score("economic_live",  last_vals.get("Economic Wellbeing"), "Economic")
    health_score  = safe_module_score("health_live",    last_vals.get("Public Health"), "Public Health")
    peace_score   = safe_module_score("peace_live",     last_vals.get("Global Peace & Conflict"), "Peace & Conflict")
    senti_score   = safe_module_score("sentiment_live", last_vals.get("Sentiment & Culture"), "Sentiment")
    entropy_live  = safe_module_score("entropy_live",   last_vals.get("Entropy Index"), "Entropy")

    # Merge into category scores
    scores.update({
        "Planetary Health":        planet_score,
        "Economic Wellbeing":      econ_score,
        "Public Health":           health_score,
        "Global Peace & Conflict": peace_score,
        "Sentiment & Culture":     senti_score,
        "Entropy Index":           entropy_live
    })

    # Modifiers (prefer live entropy; sentiment mod defaults to sentiment score)
    entropy_mod   = float(mods.get("entropy", entropy_live))
    sentiment_mod = float(mods.get("sentiment", senti_score))

    # Compute GTI (0–100 -> index delta)
    raw = compute_weighted_raw(scores)
    final_0_100   = apply_modifiers(raw, entropy_mod, sentiment_mod)
    proposed_delta= (final_0_100 - 50.0) * ALPHA
    clamped_delta = clamp_abs(proposed_delta, MAX_DAILY_MOVE)

    last_val   = float(series[-1]['gti'])
    target_val = clamp_floor(last_val + clamped_delta, MIN_FLOOR)
    smoothed   = clamp_floor(last_val + SMOOTHING*(target_val - last_val), MIN_FLOOR)
    series[-1]['gti'] = round(smoothed, 2)

    # Persist categories & GTI
    now_iso = datetime.datetime.utcnow().isoformat() + 'Z'
    cat_blob['updated']   = now_iso
    cat_blob['scores']    = scores
    cat_blob['modifiers'] = {"entropy": entropy_mod, "sentiment": sentiment_mod}
    save_json(CATEGORIES_PATH, cat_blob)

    gti_blob['updated'] = now_iso
    save_json(GTI_PATH, gti_blob)

    # Changelog
    date_str = now_iso.split('T')[0]
    change_str = (f"Econ={econ_score:.1f}, Planetary={planet_score:.1f}, Health={health_score:.1f}, "
                  f"Peace={peace_score:.1f}, Sentiment={senti_score:.1f}, Entropy={entropy_live:.1f} | "
                  f"RAW={raw:.1f}, FINAL={final_0_100:.1f}, Δ_prop={proposed_delta:.1f}, "
                  f"Δ_clamp={clamped_delta:.1f}, Index={smoothed:.1f}")
    append_changelog_entry(date_str, change_str)
    print(change_str)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Print full traceback so the Actions log points to the exact cause,
        # but exit with non-zero to make failures visible.
        print("[fatal] updater crashed:", repr(e))
        traceback.print_exc()
        raise
