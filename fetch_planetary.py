#!/usr/bin/env python3
# fetch_planetary.py — robust CO2 ppm + global temp anomaly
# Writes: data/live/planetary.json
import json, io, time, pathlib, re, csv
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
import pandas as pd

OUT = pathlib.Path("data/live/planetary.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

NOAA_CO2 = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv"
OWID_CO2 = [
    "https://ourworldindata.org/grapher/co2-concentration.csv",
    "https://ourworldindata.org/grapher/co2-concentration.csv?download-format=tab",
]
OWID_TEMP = [
    "https://ourworldindata.org/grapher/temperature-anomaly.csv",
    "https://ourworldindata.org/grapher/temperature-anomaly.csv?download-format=tab",
]

def fetch_bytes(url, timeout=45):
    req = Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urlopen(req, timeout=timeout) as r:
        return r.read()

def fetch_noaa_co2():
    """Return (last_ppm, prev_ppm) from NOAA monthly MLO, skipping -99.99."""
    raw = fetch_bytes(NOAA_CO2).decode("utf-8", errors="ignore")
    rows = []
    reader = csv.reader([ln for ln in raw.splitlines() if not ln.startswith("#")])
    for r in reader:
        # Format: year, month, decimal_date, average, interpolated, trend, #days
        if len(r) < 5: 
            continue
        try:
            avg = float(r[3])
        except Exception:
            continue
        if avg > 0:
            rows.append(avg)
    if len(rows) >= 2:
        return rows[-1], rows[-2]
    return None, None

def fetch_owid_co2():
    """Return (last_ppm, prev_ppm) from OWID concentration (World/Global)."""
    for url in OWID_CO2:
        try:
            raw = fetch_bytes(url)
            try:
                df = pd.read_csv(io.BytesIO(raw))
            except Exception:
                df = pd.read_csv(io.BytesIO(raw), sep="\t")
            cols = [c.strip().lower() for c in df.columns]
            df.columns = cols
            # Typical: entity, code, year, co2 concentration (ppm)
            cand = [c for c in cols if "ppm" in c or "concentration" in c]
            if "entity" in cols and "year" in cols and cand:
                vc = cand[-1]
                world = df[df["entity"].str.lower().isin(["world","global","globe"])].sort_values("year")
                if world.empty:
                    # fallback: take mean across all for each year (approx)
                    world = df.groupby("year", as_index=False)[vc].mean(numeric_only=True)
                if len(world) >= 2:
                    last = float(world[vc].iloc[-1])
                    prev = float(world[vc].iloc[-2])
                    return last, prev
        except Exception:
            continue
    return None, None

def fetch_owid_temp():
    """Return (last_anom, prev_anom) from OWID global temperature anomaly."""
    for url in OWID_TEMP:
        try:
            raw = fetch_bytes(url)
            try:
                df = pd.read_csv(io.BytesIO(raw))
            except Exception:
                df = pd.read_csv(io.BytesIO(raw), sep="\t")
            cols = [c.strip().lower() for c in df.columns]
            df.columns = cols
            # Grapher variant A: columns: Year, World
            if "year" in cols and "world" in cols:
                df = df.sort_values("year")
                if len(df) >= 2:
                    return float(df["world"].iloc[-1]), float(df["world"].iloc[-2])
            # Variant B: entity/year/value, filter World
            cand = [c for c in cols if "anomaly" in c or "value" in c if c != "year" and c != "entity" and c != "code"]
            if "entity" in cols and "year" in cols and cand:
                vc = cand[-1]
                world = df[df["entity"].str.lower()=="world"].sort_values("year")
                if len(world) >= 2:
                    return float(world[vc].iloc[-1]), float(world[vc].iloc[-2])
        except Exception:
            continue
    return None, None

def main():
    upd = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # CO2 ppm
    co2_last, co2_prev = None, None
    try:
        co2_last, co2_prev = fetch_noaa_co2()
    except Exception:
        pass
    if co2_last is None:
        try:
            co2_last, co2_prev = fetch_owid_co2()
        except Exception:
            pass

    # Temp anomaly
    ta_last, ta_prev = None, None
    try:
        ta_last, ta_prev = fetch_owid_temp()
    except Exception:
        pass

    data = {
        "updated_iso": upd,
        "co2_ppm": round(co2_last, 2) if co2_last is not None else None,
        "delta_ppm": round(co2_last - co2_prev, 2) if (co2_last is not None and co2_prev is not None) else None,
        "gistemp_anom_c": round(ta_last, 2) if ta_last is not None else None,
        "delta_anom": round(ta_last - ta_prev, 2) if (ta_last is not None and ta_prev is not None) else None,
        "note": "CO₂ from NOAA MLO (fallback OWID); temperature anomaly from OWID."
    }

    # Cache fallback if everything is missing
    if data["co2_ppm"] is None and data["gistemp_anom_c"] is None and OUT.exists():
        try:
            cached = json.loads(OUT.read_text())
            cached["note"] = "cached (fetch failed)"
            OUT.write_text(json.dumps(cached, indent=2))
            print("planetary.json: cached")
            return
        except Exception:
            pass

    OUT.write_text(json.dumps(data, indent=2))
    print("planetary.json:", json.dumps(data)[:220] + ("..." if len(json.dumps(data))>220 else ""))

if __name__ == "__main__":
    main()
