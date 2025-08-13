#!/usr/bin/env python3
import json, os, random, datetime

# ---- CONFIG ----
MIN_FLOOR = 100.0   # soft floor for the GTI index (adjust as you like)
NUDGE_RANGE = (-3.0, 3.0)  # daily drift (placeholder until real scoring)

DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'gti.json')

def clamp_floor(value: float, floor: float) -> float:
    """Never let the GTI fall below the configured floor."""
    return value if value >= floor else floor

def load_series(path: str):
    with open(path) as f:
        return json.load(f)

def save_series(path: str, blob):
    with open(path, 'w') as f:
        json.dump(blob, f, indent=2)

def main():
    blob = load_series(DATA_PATH)
    series = blob['series']

    # Current last value
    last_val = float(series[-1]['gti'])

    # Placeholder daily change (replace with real GTI calculation later)
    nudge = random.uniform(*NUDGE_RANGE)
    new_val = last_val + nudge

    # Enforce non-zero soft floor
    new_val = clamp_floor(new_val, MIN_FLOOR)

    # Update the last point only (we're still in 2025 in this prototype)
    series[-1]['gti'] = round(new_val, 2)

    # Timestamp
    blob['updated'] = datetime.datetime.utcnow().isoformat() + 'Z'

    save_series(DATA_PATH, blob)
    print('Updated:', blob['updated'], 'Last GTI:', series[-1]['gti'], 'Floor:', MIN_FLOOR)

if __name__ == "__main__":
    main()
