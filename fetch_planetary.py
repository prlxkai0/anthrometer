#!/usr/bin/env python3
import csv, io, json, datetime, urllib.request, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "data" / "live"
LIVE.mkdir(parents=True, exist_ok=True)
OUT = LIVE / "planetary.json"

def fetch(url, tries=2, sleep=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"AnthroMeter/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception:
            if i+1 == tries: raise
            time.sleep(sleep)

def prev():
    if OUT.exists():
        try: return json.loads(OUT.read_text())
        except: pass
    return {}

def parse_noaa():
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
    # If any piece is missing, use neutral mid
    if co2 is None or yoy is None or anom is None: return 55.0
    co2_score = 100 - (max(300.0, min(450.0, co2)) - 300.0) * (90.0/150.0)
    yoy_score = 100 - (max(0.0, min(4.0, yoy))) * (90.0/4.0)
    anom_clip = max(0.0, min(1.5, abs(anom)))
    temp_score = 100 - anom_clip * (90.0/1.5)
    return max(0.0, min(100.0, 0.35*co2_score + 0.30*yoy_score + 0.35*temp_score))

def main():
    out = {"updated": datetime.datetime.utcnow().isoformat()+"Z"}
    old = prev()
    try:
        co2, yoy, delta_ppm = parse_noaa()
    except Exception:
        traceback.print_exc()
        co2 = old.get("co2_ppm"); yoy = old.get("co2_ppm_yoy"); delta_ppm = old.get("delta_ppm")
    try:
        anom = parse_gistemp()
    except Exception:
        traceback.print_exc()
        anom = old.get("gistemp_anom_c")

    # delta_anom placeholder (vs historical baseline if you later compute it)
    delta_anom = old.get("delta_anom", 0.0)

    s = round(score(co2, yoy, anom), 2)
    out.update({
        "co2_ppm": None if co2 is None else round(co2,3),
        "co2_ppm_yoy": None if yoy is None else round(yoy,3),
        "gistemp_anom_c": None if anom is None else round(anom,3),
        "delta_ppm": None if delta_ppm is None else round(delta_ppm,3),
        "delta_anom": 0.0 if delta_anom is None else delta_anom,
        "score": s
    })
    OUT.write_text(json.dumps(out, indent=2))
    print("Planetary updated:", out)

if __name__ == "__main__":
    main()
