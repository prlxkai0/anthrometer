#!/usr/bin/env python3
import csv, io, json, datetime, urllib.request, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "data" / "live"
LIVE.mkdir(parents=True, exist_ok=True)
OUT = LIVE / "planetary.json"
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

def parse_noaa_monthly():
    txt = fetch("https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv")
    rows=[]
    for line in txt.splitlines():
        if line.startswith("#") or not line.strip(): continue
        parts=[p.strip() for p in line.split(",")]
        if len(parts)<5: continue
        y=int(parts[0]); m=int(parts[1])
        avg=parts[3]
        val=float(avg) if avg!="-99.99" else float(parts[4])
        rows.append((y,m,val))
    rows.sort()
    latest = rows[-1][2]
    prev12 = rows[-13][2] if len(rows)>12 else latest
    yoy = latest - prev12
    base = sum(v for *_,v in rows[-30:]) / max(1, min(30,len(rows)))
    delta_ppm = latest - base
    return latest, yoy, delta_ppm

def parse_noaa_weekly():
    txt = fetch("https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_week_mlo.csv")
    rows=[]
    for line in txt.splitlines():
        if line.startswith("#") or not line.strip(): continue
        parts=[p.strip() for p in line.split(",")]
        if len(parts)<6: continue
        # year, month, day, decimal, average, season_adj
        y=int(parts[0]); m=int(parts[1]); d=int(parts[2])
        avg=parts[4]
        if avg == "-99.99": continue
        val=float(avg)
        rows.append((y,m,d,val))
    rows.sort()
    latest = rows[-1][3]
    # approximate YoY using 52 weeks back if available
    prev_idx = -53 if len(rows) >= 53 else -1
    prev = rows[prev_idx][3]
    yoy = latest - prev
    # baseline: last ~30 weekly values
    tail = [v for *_,v in rows[-30:]]
    base = sum(tail)/len(tail) if tail else latest
    delta_ppm = latest - base
    return latest, yoy, delta_ppm

def parse_gistemp():
    txt = fetch("https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv")
    last=None
    for row in csv.reader(io.StringIO(txt)):
        if not row or "Year" in row[0]: continue
        try: int(row[0])
        except: continue
        vals=[]
        for i in range(1,13):
            cell=row[i].strip()
            if cell and cell!="*****":
                try: vals.append(float(cell))
                except: pass
        if vals: last=vals[-1]
    return float(last) if last is not None else None

def score(co2, yoy, anom):
    if co2 is None or yoy is None or anom is None: return 55.0
    co2_score = 100 - (max(300.0, min(450.0, co2)) - 300.0) * (90.0/150.0)
    yoy_score = 100 - (max(0.0, min(4.0, yoy))) * (90.0/4.0)
    anom_clip = max(0.0, min(1.5, abs(anom)))
    temp_score = 100 - anom_clip * (90.0/1.5)
    return max(0.0, min(100.0, 0.35*co2_score + 0.30*yoy_score + 0.35*temp_score))

def main():
    out={"updated": datetime.datetime.utcnow().isoformat()+"Z"}
    try:
        try:
            co2, yoy, dppm = parse_noaa_monthly()
        except Exception:
            co2, yoy, dppm = parse_noaa_weekly()  # fallback
        anom = parse_gistemp()
        out.update({
            "co2_ppm": round(co2,3) if co2 is not None else None,
            "co2_ppm_yoy": round(yoy,3) if yoy is not None else None,
            "gistemp_anom_c": round(anom,3) if anom is not None else None,
            "delta_ppm": round(dppm,3) if dppm is not None else None,
            "delta_anom": 0.0,
            "score": round(score(co2, yoy, anom),2)
        })
    except Exception:
        traceback.print_exc()
        # leave out to let updater carry forward previous status

    OUT.write_text(json.dumps(out, indent=2))
    print("Planetary updated:", out)

if __name__ == "__main__":
    main()
