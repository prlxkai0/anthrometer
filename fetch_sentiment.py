#!/usr/bin/env python3
import csv, io, json, datetime, statistics, urllib.parse, urllib.request, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "data" / "live"
LIVE.mkdir(parents=True, exist_ok=True)
OUT = LIVE / "sentiment.json"
UA = {"User-Agent":"AnthroMeter/1.0 (+github actions)"}

def fetch(url, tries=2, sleep=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            if i+1==tries: raise
            time.sleep(sleep)

def tones_csv():
    base="https://api.gdeltproject.org/api/v2/doc/doc"
    url=f"{base}?{urllib.parse.urlencode({'format':'CSV','mode':'timelinetone','timespan':'30d'})}"
    txt=fetch(url)
    vals=[]
    for r in csv.reader(io.StringIO(txt)):
        if not r: continue
        if r[0].lower().startswith("date"): continue
        try: vals.append(float(r[1]))
        except: pass
    return vals

def tones_json_fallback():
    # JSON fallback returns objects with fields date, value
    base="https://api.gdeltproject.org/api/v2/doc/doc"
    url=f"{base}?{urllib.parse.urlencode({'format':'JSON','mode':'timelinetone','timespan':'30d'})}"
    txt=fetch(url)
    data=json.loads(txt)
    vals=[]
    for row in data.get("timeline",[]):
        try: vals.append(float(row.get("value",0)))
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
    try:
        vals=tones_csv()
        if not vals:
            vals=tones_json_fallback()
        if vals:
            avg=statistics.fmean(vals)
            med=statistics.median(vals)
            out.update({
                "avg_tone_30d": round(avg,3),
                "median_tone_30d": round(med,3),
                "delta_tone": round(avg-med,3),
                "score": round(map_score(avg),2)
            })
    except Exception:
        traceback.print_exc()
        # leave out to allow updater to carry forward

    OUT.write_text(json.dumps(out, indent=2))
    print("Sentiment updated:", out)

if __name__ == "__main__":
    main()
