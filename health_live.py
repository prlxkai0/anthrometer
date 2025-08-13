#!/usr/bin/env python3
"""
Public Health (stub)
Input: WHO disease outbreak RSS + major outlets' health feeds.
Heuristic severity token density -> map to 0–100 (higher = better health).
"""
import json, os, re
from urllib.request import urlopen
from xml.etree import ElementTree as ET

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CATEGORIES_PATH = os.path.join(DATA_DIR, "categories.json")

RSS_FEEDS = [
    "https://www.who.int/feeds/entity/csr/don/en/rss.xml",     # WHO Disease Outbreak News
    "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml",
    "https://feeds.bbci.co.uk/news/health/rss.xml"
]

SEVERITY = set("""
outbreak epidemic pandemic cholera ebola influenza covid-19 covid coronavirus
measles polio dengue malaria mpox zika plague fatal deaths mortality
icu intensive-care hospitalization shortage shortage oxygen
""".split())

WORD = re.compile(r"[A-Za-z0-9\\-']+")

def _last_health():
    try:
        with open(CATEGORIES_PATH) as f: blob = json.load(f)
        return float(blob.get("scores", {}).get("Public Health", 50.0))
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

def _severity_per_headline(titles):
    if not titles: return 0.0
    s=0.0
    for t in titles:
        words=[w.lower() for w in WORD.findall(t)]
        hits=sum(1 for w in words if w in SEVERITY)
        s += min(hits, 3)
    return s/len(titles)

def get_score():
    try:
        vals=[]
        for url in RSS_FEEDS:
            try:
                root=_fetch(url)
                titles=_titles(root)
                vals.append(_severity_per_headline(titles))
            except Exception:
                continue
        if not vals: return _last_health()
        avg=sum(vals)/len(vals)  # ~0..2 typically
        # Invert to "health" (higher better). 0 severity→90; 0.5→80; 1.0→70; 2.0→55
        sev = max(0.0, min(avg, 2.0))
        health = 90.0 - sev*17.5
        return round(max(0.0, min(100.0, health)), 2)
    except Exception:
        return _last_health()

if __name__ == "__main__":
    print(get_score())
