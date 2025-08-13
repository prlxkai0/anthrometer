#!/usr/bin/env python3
"""
Global Peace & Conflict (stub)
Input: world news RSS, count conflict/violence tokens per headline.
Output: 0–100 (higher = better peace). We invert + scale a risk score.
"""
import json, os, re
from urllib.request import urlopen
from xml.etree import ElementTree as ET

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CATEGORIES_PATH = os.path.join(DATA_DIR, "categories.json")

RSS_FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml"
]

VIOLENCE = set("""
war invasion offensive bombardment shelling missile drone strike airstrike
armed militia insurgent rebel casualty casualties killed wounded dead
conflict clashes skirmish siege assault raid frontline front line
ceasefire truce escalation escalation escalated genocide ethnic cleansing
terror terrorism bombing explosion suicide-bomb
""".split())

WORD = re.compile(r"[A-Za-z']+")

def _last_peace():
    try:
        with open(CATEGORIES_PATH) as f: blob = json.load(f)
        return float(blob.get("scores", {}).get("Global Peace & Conflict", 50.0))
    except Exception:
        return 50.0

def _fetch(url):
    with urlopen(url, timeout=12) as resp:
        return ET.fromstring(resp.read())

def _titles(root):
    out=[]
    for n in root.findall(".//item/title"):
        if n.text: out.append(n.text.strip())
    if not out:
        for n in root.findall(".//{http://www.w3.org/2005/Atom}entry/{http://www.w3.org/2005/Atom}title"):
            if n.text: out.append(n.text.strip())
    return out

def _risk_per_headline(titles):
    import math
    if not titles: return 0.0
    s=0.0
    for t in titles:
        words=[w.lower() for w in WORD.findall(t)]
        # cap per‑headline contribution to avoid outliers
        hits=sum(1 for w in words if w in VIOLENCE)
        s += min(hits, 3)
    return s/len(titles)

def get_score():
    try:
        vals=[]
        for url in RSS_FEEDS:
            try:
                root=_fetch(url)
                titles=_titles(root)
                vals.append(_risk_per_headline(titles))
            except Exception:
                continue
        if not vals: return _last_peace()
        avg=sum(vals)/len(vals)  # ~0..2 typically
        # Map risk→peace (invert). 0 risk→90, 0.5→75, 1.0→60, 2.0→40
        risk = max(0.0, min(avg, 2.0))
        peace = 90.0 - risk*25.0
        return round(max(0.0, min(100.0, peace)), 2)
    except Exception:
        return _last_peace()

if __name__ == "__main__":
    print(get_score())
