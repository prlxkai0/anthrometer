#!/usr/bin/env python3
# updater.py — computes GTI daily using live stubs for Planetary, Sentiment, and Entropy.
# Includes a gentle daily change clamp to avoid jumpy moves.

import json, os, datetime

# ================= CONFIG =================
MIN_FLOOR       = 100.0   # Non-zero floor so the index never touches 0
ALPHA           = 4.0     # Sensitivity: index delta per (final_0_100 - 50)
BETA            = 0.20    # Entropy drag (0..20% multiplicative)
GAMMA           = 1.5     # Sentiment additive boost per pt above/below 50
MAX_DAILY_MOVE  = 25.0    # <-- clamp absolute daily index move to ± this many points
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
# ===========================================

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, obj):
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2)

def clamp_floor(v, floor):
    return v if v >= floor else floor

def clamp_0_100(v):
    return 0 if v < 0 else (100 if v > 100 else v)

def clamp_abs(v, cap):
    """Clamp v to ±cap."""
    if v > cap: return cap
    if v < -cap: return -cap
    return v

def compute_weighted_raw(scores_0_100: dict) -> float:
    total = 0.0
    for k, w in WEIGHTS.items():
        total += float(scores_0_100.get(k, 50)) * w
    return total

def apply_modifiers(raw_0_100: float, entropy: float, sentiment: float) -> float:
    """
    Apply entropy as multiplicative drag and sentiment as additive boost
    in the 0-100 space, then clamp to 0..100.
    """
    entropy = clamp_0_100(entropy)
    sentiment = clamp_0_100(sentiment)
    entropy_modifier = (entropy / 100.0) * BETA      # 0..BETA
    adjusted = raw_0_100 * (1.0 - entropy_modifier)  # multiplicative drag
    sentiment_boost = (sentiment - 50.0) * GAMMA     # additive points
    final = adjusted + sentiment_boost
    return clamp_0_100(final)

def main():
    # --- Load existing GTI series & categories ---
    gti_blob = load_json(GTI_PATH)
    series = gti_blob['series']
    try:
        cat_blob = load_json(CATEGORIES_PATH)
    except Exception:
        cat_blob = {"updated": "", "scores": {}, "modifiers": {}}

    scores = dict(cat_blob.get('scores', {}))     # copy to be safe
    mods   = dict(cat_blob.get('modifiers', {}))

    # --- Live stubs (0–100) ---
    # Ensure these files exist at repo root:
    #   planetary_live.py, sentiment_live.py, entropy_live.py
    import planetary_live, sentiment_live, entropy_live

    planet_score       = float(planetary_live.get_score())
    senti_score        = float(sentiment_live.get_score())
    entropy_live_score = float(entropy_live.get_score())

    # --- Merge live scores into categories ---
    scores["Planetary Health"]    = planet_score
    scores["Sentiment & Culture"] = senti_score
    scores["Entropy Index"]       = entropy_live_score

    # --- Modifiers (use live entropy by default; sentiment modifier defaults to senti_score) ---
    entropy_mod   = float(mods.get("entropy", entropy_live_score))
    sentiment_mod = float(mods.get("sentiment", senti_score))

    # --- Compute GTI in 0–100 space, then stock-style delta ---
    raw = compute_weighted_raw(scores)                 # weighted composite (0–100)
    final_0_100 = apply_modifiers(raw, entropy_mod, sentiment_mod)

    # Proposed delta before clamps
    proposed_delta = (final_0_100 - 50.0) * ALPHA

    # Clamp the *daily index move* (gentle changes)
    clamped_delta = clamp_abs(proposed_delta, MAX_DAILY_MOVE)

    last_val = float(series[-1]['gti'])
    next_val = clamp_floor(last_val + clamped_delta, MIN_FLOOR)
    series[-1]['gti'] = round(next_val, 2)

    # --- Persist categories & GTI ---
    now_iso = datetime.datetime.utcnow().isoformat() + 'Z'
    cat_blob['updated']   = now_iso
    cat_blob['scores']    = scores
    cat_blob['modifiers'] = {"entropy": entropy_mod, "sentiment": sentiment_mod}
    save_json(CATEGORIES_PATH, cat_blob)

    gti_blob['updated'] = now_iso
    save_json(GTI_PATH, gti_blob)

    print(
        f"Planetary={planet_score:.2f}  Sentiment={senti_score:.2f}  Entropy={entropy_live_score:.2f} | "
        f"RAW={raw:.2f}  FINAL={final_0_100:.2f}  Δ_proposed={proposed_delta:.2f}  Δ_clamped={clamped_delta:.2f} "
        f"→ GTI={next_val:.2f} (floor {MIN_FLOOR}, cap ±{MAX_DAILY_MOVE})"
    )

if __name__ == "__main__":
    main()
