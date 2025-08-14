#!/usr/bin/env python3
# fetch_foodaccess.py — OWID: share of people undernourished (World)
# Writes: data/live/foodaccess.json
import json, io, time, pathlib
from urllib.request import urlopen, Request
import pandas as pd

OUT = pathlib.Path("data/live/foodaccess.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

URLS = [
    "https://ourworldindata.org/grapher/undernourishment.csv",               # often: Entity,Code,Year,Undernourishment (%)
    "https://ourworldindata.org/grapher/undernourishment.csv?download-format=tab",
]

def fetch_csv(url):
    req = Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urlopen(req, timeout=45) as r:
        raw = r.read()
    try:
        return pd.read_csv(io.BytesIO(raw))
    except Exception:
        return pd.read_csv(io.BytesIO(raw), sep="\t")

def main():
    updated_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    last = prev = None

    for url in URLS:
        try:
            df = fetch_csv(url)
            cols = [c.strip().lower() for c in df.columns]
            df.columns = cols
            # Typical shape: entity, code, year, undernourishment
            if "entity" in cols and "year" in cols:
                val_col = [c for c in cols if "undernourish" in c]
                if val_col:
                    vc = val_col[0]
                    world = df[df["entity"].str.lower()=="world"].sort_values("year")
                    if len(world) >= 2:
                        last = float(world[vc].iloc[-1])
                        prev = float(world[vc].iloc[-2])
                        break
        except Exception:
            continue

    if last is None:
        # cache fallback
        if OUT.exists():
            try:
                data = json.loads(OUT.read_text())
                data["note"] = "cached (fetch failed)"
                OUT.write_text(json.dumps(data, indent=2))
                print("foodaccess.json: cached")
                return
            except Exception:
                pass

    data = {
        "updated_iso": updated_iso,
        "undernourished_pct": round(last, 2) if last is not None else None,
        "delta_pct": round((last - prev), 2) if (last is not None and prev is not None) else None,
        "note": "Lower is better (fewer undernourished). Source: OWID/FAO."
    }
    OUT.write_text(json.dumps(data, indent=2))
    print("foodaccess.json:", json.dumps(data)[:200] + ("..." if len(json.dumps(data))>200 else ""))

if __name__ == "__main__":
    main()
