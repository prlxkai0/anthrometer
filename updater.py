#!/usr/bin/env python3
# updater.py — GTI daily with live Planetary, Economic, Public Health, Peace & Conflict, Sentiment, Entropy.
# Includes daily move clamp + exponential smoothing + changelog entry.

import json, os, datetime

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

def load_json(path):
    with open(path) as f: return json.load(f)

def save_json(path, obj):
    with open(path, 'w') as f: json.dump(obj, f, indent=2)

def clamp_floor(v, floor): return v if v >= floor else floor
def clamp_0_100(v): return 0 if v < 0 else (100 if v > 100 else v)
def clamp_abs(v, cap): return cap if v>cap else (-cap if v<-cap else v)

def compute_weighted_raw(scores_0_100: dict) -> float:
    return sum(float(scores_0_100.get(k, 50))*w for k,w in WEIGHTS.items())

def apply_modifiers(raw_0_100: float, entropy: float, sentiment: float) -> float:
    entropy = clamp_0_100(entropy); sentiment = clamp_0_100(sentiment)
    adjusted = raw_0_100 * (1.0 - (entropy/100.0)*BETA)         # multiplicative drag
    final    = adjusted + (sentiment - 50.0)*GAMMA              # additive boost
    return clamp_0_100(final)

def append_changelog_entry(date_str, change_str, max_entries=365):
    try:
        with open(CHANGELOG_PATH) as f:
            blob = json.load(f)
    except Exception:
        blob = {"entries": []}
    entries = blob.get("entries", [])
    if not entries or entries[-1].get("date") != date_str:
        entries.append({"date": date_str, "change": change_str})
        if len(entries) > max_entries: entries = entries[-max_entries:]
        blob["entries"] = entries
        with open(CHANGELOG_PATH, "w") as f:
            json.dump(blob, f, indent=2)

def main():
    gti_blob = load_json(GTI_PATH)
    series = gti_blob['series']
    try:
        cat_blob = load_json(CATEGORIES_PATH)
    except Exception:
        cat_blob = {"updated": "", "scores": {}, "modifiers": {}}

    scores = dict(cat_blob.get('scores', {}))
    mods   = dict(cat_blob.get('modifiers', {}))

    # -------- Live stubs (0–100) --------
    import planetary_live, economic_live, health_live, peace_live, sentiment_live, entropy_live
    planet_score  = float(planetary_live.get_score())
    econ_score    = float(economic_live.get_score())
    health_score  = float(health_live.get_score())
    peace_score   = float(peace_live.get_score())
    senti_score   = float(sentiment_live.get_score())
    entropy_score_live = float(entropy_live.get_score())

    # Merge into categories
    scores["Planetary Health"]         = planet_score
    scores["Economic Wellbeing"]       = econ_score
    scores["Public Health"]            = health_score
    scores["Global Peace & Conflict"]  = peace_score
    scores["Sentiment & Culture"]      = senti_score
    scores["Entropy Index"]            = entropy_score_live

    # Modifiers (prefer live entropy; sentiment mod defaults to sentiment score)
    entropy_mod   = float(mods.get("entropy", entropy_score_live))
    sentiment_mod = float(mods.get("sentiment", senti_score))

    # ---- GTI computation ----
    raw          = compute_weighted_raw(scores)
    final_0_100  = apply_modifiers(raw, entropy_mod, sentiment_mod)
    proposed_delta = (final_0_100 - 50.0) * ALPHA
    clamped_delta  = clamp_abs(proposed_delta, MAX_DAILY_MOVE)

    last_val   = float(series[-1]['gti'])
    target_val = clamp_floor(last_val + clamped_delta, MIN_FLOOR)
    smoothed   = clamp_floor(last_val + SMOOTHING*(target_val - last_val), MIN_FLOOR)
    series[-1]['gti'] = round(smoothed, 2)

    # Persist
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
                  f"Peace={peace_score:.1f}, Sentiment={senti_score:.1f}, Entropy={entropy_score_live:.1f} | "
                  f"RAW={raw:.1f}, FINAL={final_0_100:.1f}, Δ_prop={proposed_delta:.1f}, "
                  f"Δ_clamp={clamped_delta:.1f}, Index={smoothed:.1f}")
    append_changelog_entry(date_str, change_str)

    print(change_str)

if __name__ == "__main__":
    main()
