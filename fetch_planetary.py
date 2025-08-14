#!/usr/bin/env python3
import csv, io, json, datetime, urllib.request, sys, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "live"
OUT.mkdir(parents=True, exist_ok=True)

def fetch(url:str)->str:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def parse_noaa():
    url = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv"
    txt = fetch(url)
    rows = []
    for line in txt.splitlines():
        if line.startswith("#") or not line.strip(): continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5: continue
        y, m = int(parts[0]), int(parts[1])
        avg = parts[3]
        val = float(avg) if avg != "-99.99" else float(parts[4])
        rows.append((y, m, val))
    rows.sort()
    latest = rows[-1][2]
    prev12 = rows[-13][2] if len(rows) > 12 else latest
    yoy = latest - prev12
    # simple baseline ~ last 30 records
    base = sum(v for _,_,v in rows[-30:]) / max(1, min(30, len(rows)))
    return latest, yoy, latest - base

def parse_gistemp():
    url = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
    txt = fetch(url)
    last = None
    for row in csv.reader(io.StringIO(txt)):
        if not row or "Year" in row[0]: continue
        try: int(row[0])
        except: continue
        vals = []
        for i in range(1,13):
            cell = row[i].strip()
            if cell and cell != "*****":
                try: vals.append(float(cell))
                except: pass
        if vals: last = vals[-1]
    return float(last) if last is not None else 0.0

def score(co2, yoy, anom):
    co2_score = 100 - (max(300.0, min(450.0, co2)) - 300.0) * (90.0/150.0)
    yoy_score = 100 - (max(0.0, min(4.0, yoy))) * (90.0/4.0)
    anom_clip = max(0.0, min(1.5, abs(anom)))
    temp_score = 100 - anom_clip * (90.0/1.5)
    return max(0.0, min(100.0, 0.35*co2_score + 0.30*yoy_score + 0.35*temp_score))

def main():
    out = {
        "updated": datetime.datetime.utcnow().isoformat()+"Z",
        "co2_ppm": None,
        "co2_ppm_yoy": None,
        "gistemp_anom_c": None,
        "delta_ppm": None,
        "delta_anom": None,
        "score": 55.0  # neutral fallback
    }
    try:
        co2, yoy, delta_ppm = parse_noaa()
        anom = parse_gistemp()
        s = round(score(co2, yoy, anom), 2)
        out.update({
            "co2_ppm": round(co2,3),
            "co2_ppm_yoy": round(yoy,3),
            "gistemp_anom_c": round(anom,3),
            "delta_ppm": round(delta_ppm,3),
            "delta_anom": 0.0,
            "score": s
        })
    except Exception as e:
        traceback.print_exc()
        # keep fallback values; do not raise
    (OUT/"planetary.json").write_text(json.dumps(out, indent=2))
    print("Planetary updated:", out)

if __name__ == "__main__":
    main()
