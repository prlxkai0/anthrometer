#!/usr/bin/env python3
"""
Entropy Index (stub): estimate systemic stress via RSS headlines (no API keys).
Higher = worse (more disorder). Returns 0–100 and is used both as:
- Category score: "Entropy Index"
- Modifier: multiplicative drag in GTI calculation
"""
import os, json, re
from urllib.request import urlopen
from xml.etree import ElementTree as ET

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CATEGORIES_PATH = os.path.join(DATA_DIR, "categories.json")

# Broad risk/chaos lexicon (feel free to expand)
RISK = set("""
war conflict escalation attack bombing strike unrest riot coup sanctions
blackout outage shortage inflation recession default crisis protest cyberattack
""".split())

WORD = re.compile(r"[A-Za-z']+")

RSS_FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
]

def _last_entropy():
    try:
        with open(CATEGORIES_PATH) as f:
            blob = json.load(f)
        return float(blob.get("scores", {}).get("Entropy Index", 50.0))
    except Exception:
        return 50.0

def _fetch(url):
    with urlopen(url, timeout=10) as resp:
        return ET.fromstring(resp.read())

def _titles(root):
    out=[]
    for n in root.findall(".//item/title"):
        if n.text: out.append(n.text.strip())
    if not out:
        for n in root.findall(".//{http://www.w3.org/2005/Atom}entry/{http://www.w3.org/2005/Atom}title"):
            if n.text: out.append(n.text.strip())
    return out

def _risk_score(text):
    words = [w.lower() for w in WORD.findall(text)]
    return sum(1 for w in words if w in RISK)

def get_score():
    try:
        scores=[]
        for url in RSS_FEEDS:
            try:
                root=_fetch(url)
                titles=_titles(root)
                if not titles: continue
                # average risk tokens per headline
                s=sum(_risk_score(t) for t in titles)/max(len(titles),1)
                scores.append(s)
            except Exception:
                continue
        if not scores: return _last_entropy()
        avg=sum(scores)/len(scores)
        # Map average risk tokens to 0..100 (tune as needed)
        # 0 tokens -> 30, 0.5 -> 50, 1.5 -> 70, >=3 -> ~90+
        mapped = 30 + max(min(avg, 3.0), 0.0) * 20
        return round(max(min(mapped, 100.0), 0.0), 2)
    except Exception:
        return _last_entropy()

if __name__ == "__main__":
    print(get_score())
