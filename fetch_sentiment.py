#!/usr/bin/env python3
import csv, io, json, datetime, statistics, urllib.parse, urllib.request, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "data" / "live"
LIVE.mkdir(parents=True, exist_ok=True)
OUT = LIVE / "sentiment.json"

def prev():
    if OUT.exists():
        try: return json.loads(OUT.read_text())
        except: pass
    return {}

def fetch(url, tries=2, sleep=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"AnthroMeter/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            if i+1 == tries: raise
            time.sleep(sleep)

def tones_30d():
    base = "https://api.gdeltproject.org/api/v2/doc/doc"
    url  = f"{base}?{urllib.parse.urlencode({'format':'CSV','mode':'timelinetone','timespan':'30d'})}"
    txt  = fetch(url)
    vals=[]
    for r in csv.reader(io.StringIO(txt)):
        if not r: continue
        if r[0].lower().startswith("date"): continue
        try: vals.append(float(r[1]))
        except: pass
    return vals

def map_score(tone: float)->float:
    t=max(-5.0, min(5.0, tone))
    base=10.0+(t+5.0)*(80.0/10.0)
    if tone<=-4.0: base-=5.0
    if tone>= 4.0: base+=5.0
    return max(0.0, min(100.0, base))

def main():
    out={"updated": datetime.datetime.utcnow().isoformat()+"Z"}
    old=prev()
    try:
        vals=tones_30d()
        if vals:
            avg=statistics.fmean(vals)
            med=statistics.median(vals)
            score=round(map_score(avg),2)
            out.update({
                "avg_tone_30d": round(avg,3),
                "median_tone_30d": round(med,3),
                "delta_tone": round(avg-med,3),
                "score": score
            })
        else:
            raise RuntimeError("No timelinetone rows")
    except Exception:
        traceback.print_exc()
        # carry forward previous if exists, else neutral
        out.update({
            "avg_tone_30d": old.get("avg_tone_30d", 0.0),
            "median_tone_30d": old.get("median_tone_30d", 0.0),
            "delta_tone": old.get("delta_tone", 0.0),
            "score": old.get("score", 50.0)
        })
    (OUT).write_text(json.dumps(out, indent=2))
    print("Sentiment updated:", out)

if __name__ == "__main__":
    main()
