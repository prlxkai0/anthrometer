#!/usr/bin/env python3
# Fetches a simple "global sentiment" proxy from GDELT timelinetone (last 30 days),
# maps it to a 0–100 score, and writes data/live/sentiment.json
#
# References:
# GDELT Doc API + timelinetone mode: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
#
# Output:
# {
#   "updated": "...Z",
#   "avg_tone_30d": -1.23,
#   "score": 0-100
# }

import csv, io, json, datetime, statistics, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "live"
OUT.mkdir(parents=True, exist_ok=True)

def fetch_url(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def get_avg_tone(days=30) -> float:
    # GDELT Doc API timelinetone supports CSV with format=CSV
    # We query everything (no keyword) over timespan=30d
    base = "https://api.gdeltproject.org/api/v2/doc/doc"
    qs = {
        "format": "CSV",
        "mode": "timelinetone",
        "timespan": f"{days}d"
    }
    url = f"{base}?{urllib.parse.urlencode(qs)}"
    txt = fetch_url(url)
    # CSV columns usually: Date,Average Tone, ... (we'll read 2nd column)
    reader = csv.reader(io.StringIO(txt))
    tones = []
    for row in reader:
        if not row: 
            continue
        # header guard
        if row[0].lower().startswith("date"):
            continue
        try:
            tone = float(row[1])
            tones.append(tone)
        except Exception:
            continue
    if not tones:
        # Fallback to neutral if API had a transient hiccup
        return 0.0
    return statistics.fmean(tones)

def tone_to_score(tone: float) -> float:
    """
    GDELT tone is centered near 0 (negative = bad, positive = good),
    roughly spanning ~[-5, +5] in daily averages.
    We'll map -5..+5 → 10..90 (clip), then widen to allow 0..100 edges.
    """
    t = max(-5.0, min(5.0, tone))
    base = 10.0 + (t + 5.0) * (80.0 / 10.0)  # 10..90
    # Lightly expand extremes if very positive/negative:
    if tone <= -4.0: base -= 5.0
    if tone >=  4.0: base += 5.0
    return max(0.0, min(100.0, base))

def main():
    avg = get_avg_tone(30)
    score = round(tone_to_score(avg), 2)
    out = {
        "updated": datetime.datetime.utcnow().isoformat() + "Z",
        "avg_tone_30d": round(avg, 3),
        "score": score
    }
    (OUT / "sentiment.json").write_text(json.dumps(out, indent=2))
    print("Sentiment updated:", out)

if __name__ == "__main__":
    main()
