#!/usr/bin/env python3
# fetch_food.py — FAO/OWID Food Price Index (monthly). Robust, no API key.
# Writes: data/live/food.json
import json, os, sys, time, pathlib, io
from urllib.request import urlopen, Request
import pandas as pd

OUT = pathlib.Path("data/live/food.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

SOURCES = [
    # Primary (OWID Grapher)
    "https://ourworldindata.org/grapher/food_price_index.csv",
    # Fallback (OWID tab-delimited sometimes more lenient)
    "https://ourworldindata.org/grapher/food_price_index.csv?download-format=tab",
]

def fetch_csv(url: str) -> pd.DataFrame:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as r:
        raw = r.read()
    # Try to read as CSV or TSV automatically
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception:
        df = pd.read_csv(io.BytesIO(raw), sep="\t")
    return df

def main():
    # Expect OWID format: columns ["Entity","Code","Year","Food price index"]
    # BUT grapher CSVs often come as ["Year","food_price_index"] (single series)
    last_val = None
    prev_val = None
    updated_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    for url in SOURCES:
        try:
            df = fetch_csv(url)
            # Normalize columns
            cols = [c.strip().lower() for c in df.columns]
            df.columns = cols
            # Common cases:
            # Case A: ["year","food_price_index"]
            if "year" in cols and "food_price_index" in cols:
                df = df.sort_values("year")
                # Monthly vs yearly: OWID series for FAO FPI is monthly index with "Year" like 2024.75 sometimes;
                # but typically it's monthly wide. If numeric year fractional, it's ok; we just take last two rows.
                if len(df) >= 2:
                    last_val = float(df["food_price_index"].iloc[-1])
                    prev_val = float(df["food_price_index"].iloc[-2])
                    break
            # Case B: wide grapher: ["date","value"] or ["year","value"]
            if "value" in cols:
                key = "date" if "date" in cols else ("year" if "year" in cols else None)
                if key:
                    df = df.sort_values(key)
                    if len(df) >= 2:
                        last_val = float(df["value"].iloc[-1])
                        prev_val = float(df["value"].iloc[-2])
                        break
        except Exception as e:
            # try next source
            continue

    data = {}
    if last_val is not None:
        mom = last_val - (prev_val if prev_val is not None else last_val)
        yoy = None  # not guaranteed monthly cadence; leave None for now
        data = {
            "updated_iso": updated_iso,
            "fpi_last": round(last_val, 2),
            "fpi_mom": round(mom, 2),
            "fpi_yoy": yoy,
            "source": "FAO/OWID Food Price Index",
        }
    else:
        # Keep previous data if exists, to avoid zeroing the UI
        if OUT.exists():
            try:
                data = json.loads(OUT.read_text())
                data["note"] = "Using cached food.json (fetch failed)."
            except Exception:
                data = {"updated_iso": updated_iso, "fpi_last": None, "fpi_mom": None, "fpi_yoy": None, "source": "unavailable"}

    OUT.write_text(json.dumps(data, indent=2))
    print("food.json:", json.dumps(data)[:200] + ("..." if len(json.dumps(data))>200 else ""))

if __name__ == "__main__":
    main()
