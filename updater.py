#!/usr/bin/env python3
import json, os, datetime

# ================= CONFIG =================
MIN_FLOOR = 100.0   # Non-zero floor so the chart never touches 0
ALPHA     = 4.0     # Sensitivity: how much the index moves per point from 50
BETA      = 0.20    # Entropy sensitivity (0.20 = up to 20% drag at entropy=100)
GAMMA     = 1.5     # Sentiment additive boost per point above/below 50
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
    """Return weighted 0-100 composite based on WEIGHTS."""
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

    entropy_modifier = (entropy / 100.0) * BETA          # 0 .. BETA
    adjusted = raw_0_100 * (1.0 - entropy_modifier)      # drag

    sentiment_boost = (sentiment - 50.0) * GAMMA / 1.0   # additive points
    final = adjusted + sentiment_boost
    return clamp_0_100(final)

def main():
    # Load current GTI series and today’s category inputs
    gti_blob = load_json(GTI_PATH)
    cat_blob = load_json(CATEGORIES_PATH)

    series = gti_blob['series']
    today_scores = cat_blob.get('scores', {})
    mods = cat_blob.get('modifiers', {})
    entropy = float(mods.get('entropy', 50))
    sentiment = float(mods.get('sentiment', 50))

    # 1) Weighted composite (0-100)
    raw = compute_weighted_raw(today_scores)

    # 2) Modifiers in 0-100 space
    final_0_100 = apply_modifiers(raw, entropy, sentiment)

    # 3) Convert to stock-style delta
    delta = (final_0_100 - 50.0) * ALPHA

    # 4) Update last point in the series, respecting floor
    last_val = float(series[-1]['gti'])
    next_val = clamp_floor(last_val + delta, MIN_FLOOR)
    series[-1]['gti'] = round(next_val, 2)

    # 5) Timestamp and save
    gti_blob['updated'] = datetime.datetime.utcnow().isoformat() + 'Z'
    save_json(GTI_PATH, gti_blob)

    print(f"RAW={raw:.2f} FINAL={final_0_100:.2f} Δ={delta:.2f} → GTI={next_val:.2f} (floor {MIN_FLOOR})")

if __name__ == "__main__":
    main()
