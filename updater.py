#!/usr/bin/env python3
import json, os, datetime

# ================= CONFIG =================
MIN_FLOOR = 100.0   # Non-zero floor
ALPHA     = 4.0     # Sensitivity for stock-style delta
BETA      = 0.20    # Entropy multiplicative drag
GAMMA     = 1.5     # Sentiment additive boost
DATA_DIR  = os.path.join(os.path.dirname(__file__), 'data')

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

def compute_weighted_raw(scores_0_100: dict) -> float:
    total = 0.0
    for k, w in WEIGHTS.items():
        total += float(scores_0_100.get(k, 50)) * w
    return total

def apply_modifiers(raw_0_100: float, entropy: float, sentiment: float) -> float:
    entropy = clamp_0_100(entropy)
    sentiment = clamp_0_100(sentiment)
    entropy_modifier = (entropy / 100.0) * BETA
    adjusted = raw_0_100 * (1.0 - entropy_modifier)
    sentiment_boost = (sentiment - 50.0) * GAMMA
    final = adjusted + sentiment_boost
    return clamp_0_100(final)

def main():
    # 0) Load existing files
    gti_blob = load_json(GTI_PATH)
    series = gti_blob['series']
    try:
        cat_blob = load_json(CATEGORIES_PATH)
    except Exception:
        cat_blob = {"updated": "", "scores": {}, "modifiers": {}}

    scores = cat_blob.get('scores', {})
    mods   = cat_blob.get('modifiers', {})

    # 1) Import the two live stubs (they return 0–100)
    import planetary_live, sentiment_live
    planet_score = planetary_live.get_score()
    senti_score  = sentiment_live.get_score()

    # 2) Merge into categories
    scores["Planetary Health"]   = float(planet_score)
    scores["Sentiment & Culture"] = float(senti_score)

    # 3) Use sentiment for the sentiment modifier by default
    entropy_score   = float(mods.get("entropy", 50))  # keep user-set or future live
    sentiment_mod   = float(mods.get("sentiment", senti_score))

    # 4) Compute GTI
    raw = compute_weighted_raw(scores)
    final_0_100 = apply_modifiers(raw, entropy_score, sentiment_mod)
    delta = (final_0_100 - 50.0) * ALPHA

    last_val = float(series[-1]['gti'])
    next_val = clamp_floor(last_val + delta, MIN_FLOOR)
    series[-1]['gti'] = round(next_val, 2)

    # 5) Save updated categories & gti
    cat_blob['updated'] = datetime.datetime.utcnow().isoformat() + 'Z'
    cat_blob['scores'] = scores
    cat_blob['modifiers'] = {"entropy": entropy_score, "sentiment": sentiment_mod}
    save_json(CATEGORIES_PATH, cat_blob)

    gti_blob['updated'] = cat_blob['updated']
    save_json(GTI_PATH, gti_blob)

    print(f"Planetary={planet_score:.2f} Sentiment={senti_score:.2f} | RAW={raw:.2f} FINAL={final_0_100:.2f} Δ={delta:.2f} → GTI={next_val:.2f}")

if __name__ == "__main__":
    main()
