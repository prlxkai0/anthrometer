#!/usr/bin/env python3
"""
Sentiment & Culture (stub): read global headlines via RSS, do simple lexicon scoring.
- No API keys; uses public RSS.
- 50 = neutral; >50 positive, <50 negative.
- On failure, falls back to last saved value (or 50).
"""
import os, json, re, sys
from urllib.request import urlopen
from xml.etree import ElementTree as ET

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CATEGORIES_PATH = os.path.join(DATA_DIR, "categories.json")

RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml"
    # Add more if you want redundancy
]

POS = set("""
progress growth peace recovery relief innovation improve improved improving
record gain gains optimism optimistic resilient jobs surplus vaccine cure
""".split())

NEG = set("""
war conflict crisis crash shortage inflation recession strike protest outage
pandemic disease death deadly fear fearsome collapse catastrophic disaster
""".split())

WORD = re.compile(r"[A-Za-z']+")

def _last_sentiment():
    try:
        with open(CATEGORIES_PATH) as f:
            blob = json.load(f)
        return float(blob.get("scores", {}).get("Sentiment & Culture", 50.0))
    except Exception:
        return 50.0

def _fetch_feed(url):
    with urlopen(url, timeout=10) as resp:
        xml = resp.read()
    return ET.fromstring(xml)

def _extract_titles(root):
    titles = []
    for item in root.findall(".//item/title"):
        if item.text:
            titles.append(item.text.strip())
    if not titles:  # Atom fallback
        for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry/{http://www.w3.org/2005/Atom}title"):
            if entry.text:
                titles.append(entry.text.strip())
    return titles

def _score_text(text):
    words = [w.lower() for w in WORD.findall(text)]
    pos = sum(1 for w in words if w in POS)
    neg = sum(1 for w in words if w in NEG)
    return pos - neg

def get_score():
    try:
        scores = []
        for url in RSS_FEEDS:
            try:
                root = _fetch_feed(url)
                titles = _extract_titles(root)
                if not titles:
                    continue
                s = sum(_score_text(t) for t in titles)
                n = max(len(titles), 1)
                scores.append(s / n)
            except Exception:
                continue
        if not scores:
            return _last_sentiment()
        # Normalize: mean headline score → 0..100 (50 neutral)
        avg = sum(scores) / len(scores)  # typically around [-0.5, +0.5]
        # Map: -2 => 30, 0 => 50, +2 => 70 (clamp 0..100)
        mapped = 50.0 + max(min(avg, 2.0), -2.0) * 10.0
        return round(max(min(mapped, 100.0), 0.0), 2)
    except Exception:
        return _last_sentiment()

if __name__ == "__main__":
    print(get_score())
