#!/usr/bin/env python3
# backfill_historical.py — Build annual GTI from public datasets (OWID/UCDP) with robust fallbacks.
# Writes: data/gti.json
import io, json, time, pathlib, sys, math
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
import pandas as pd
import numpy as np

DATA = pathlib.Path("data")
DATA.mkdir(exist_ok=True)

# ---- Candidate URLs per series (try in order; some OWID series change ids occasionally) ----
CANDIDATES = {
    "co2": [
        "https://ourworldindata.org/grapher/co2.csv",  # country-year CO2 (Mt)
        "https://ourworldindata.org/grapher/co2.csv?download-format=tab",
        # fallback alt series (total CO2), used rarely:
        "https://ourworldindata.org/grapher/Global_CO2_emissions.csv",
        "https://ourworldindata.org/grapher/Global_CO2_emissions.csv?download-format=tab",
    ],
    "temp": [
        "https://ourworldindata.org/grapher/temperature-anomaly.csv",
        "https://ourworldindata.org/grapher/temperature-anomaly.csv?download-format=tab",
        # alt (Berkeley Earth global anomalies)
        "https://ourworldindata.org/grapher/berkeley-earth-temperature-anomaly.csv",
        "https://ourworldindata.org/grapher/berkeley-earth-temperature-anomaly.csv?download-format=tab",
    ],
    "gdp_pc": [
        "https://ourworldindata.org/grapher/gdp-per-capita-maddison-2020.csv",
        "https://ourworldindata.org/grapher/gdp-per-capita-maddison-2020.csv?download-format=tab",
    ],
    "lifeexp": [
        "https://ourworldindata.org/grapher/life-expectancy.csv",
        "https://ourworldindata.org/grapher/life-expectancy.csv?download-format=tab",
    ],
    "vdem": [
        "https://ourworldindata.org/grapher/vdem_libdem.csv",
        "https://ourworldindata.org/grapher/vdem_libdem.csv?download-format=tab",
    ],
    "internet": [
        "https://ourworldindata.org/grapher/share-of-individuals-using-the-internet.csv",
        "https://ourworldindata.org/grapher/share-of-individuals-using-the-internet.csv?download-format=tab",
    ],
    "energyint": [
        "https://ourworldindata.org/grapher/energy-intensity.csv",
        "https://ourworldindata.org/grapher/energy-intensity.csv?download-format=tab",
        # alt id sometimes seen:
        "https://ourworldindata.org/grapher/energy-intensity-of-gdp.csv",
        "https://ourworldindata.org/grapher/energy-intensity-of-gdp.csv?download-format=tab",
    ],
    "battle": [
        "https://ourworldindata.org/grapher/battle-deaths-from-external-and-internal-conflicts-per-100-000.csv",
        "https://ourworldindata.org/grapher/battle-deaths-from-external-and-internal-conflicts-per-100-000.csv?download-format=tab",
        # alt aggregate:
        "https://ourworldindata.org/grapher/battle-deaths-absolute.csv",
        "https://ourworldindata.org/grapher/battle-deaths-absolute.csv?download-format=tab",
    ],
}

def fetch_csv_any(keys):
    """Try a list of URLs; return (DataFrame, url_used) or (None, None) if all fail."""
    last_err = None
    for url in keys:
        try:
            req = Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urlopen(req, timeout=60) as r:
                raw = r.read()
            # try CSV first, then TSV
            try:
                df = pd.read_csv(io.BytesIO(raw))
            except Exception:
                df = pd.read_csv(io.BytesIO(raw), sep="\t")
            return df, url
        except (HTTPError, URLError, TimeoutError) as e:
            last_err = e
            continue
        except Exception as e:
            last_err = e
            continue
    print(f"[warn] all candidates failed: {keys[0]} … ({len(keys)} tried). Last error: {last_err}", file=sys.stderr)
    return None, None

def norm_minmax(s, lo=None, hi=None, invert=False):
    ss = pd.Series(s, dtype="float64")
    if not ss.notna().any():  # all NaN
        return pd.Series([50.0]*len(ss), index=ss.index)
    if lo is None: lo = np.nanpercentile(ss.dropna(), 5)
    if hi is None: hi = np.nanpercentile(ss.dropna(), 95)
    if hi is None or lo is None or not math.isfinite(hi-lo) or (hi <= lo):
        # degenerate range; return 50s
        return pd.Series([50.0]*len(ss), index=ss.index)
    x = (ss - lo) / (hi - lo)
    x = x.clip(lower=0, upper=1)
    if invert: x = 1 - x
    return (x * 100.0)

def safe_merge(left, right, on="year"):
    return pd.merge(left, right, on=on, how="outer")

def shape_world(df, value_hint=None, entity_col="Entity", year_col="Year"):
    """Extract World time series; guess value column if needed."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["year","value"])
    cols_low = [c.lower() for c in df.columns]
    df.columns = cols_low
    ent = "entity" if "entity" in df.columns else (entity_col.lower() if entity_col.lower() in df.columns else None)
    year = "year"   if "year" in df.columns   else (year_col.lower()   if year_col.lower() in df.columns   else None)
    if ent and year:
        cand_vals = []
        if value_hint:
            cand_vals = [c for c in df.columns if value_hint in c]
        if not cand_vals:
            cand_vals = [c for c in df.columns if c not in (ent,year,"code") and df[c].dtype != "O"]
        world = df[df[ent].str.lower()=="world"] if ent in df.columns else df
        if world.empty and ent in df.columns:
            # some series store "World" as "OWID_WRL" under Code only; fallback to aggregate mean
            world = df.groupby(year, as_index=False).mean(numeric_only=True)
            world["entity"] = "world"
        if not world.empty and cand_vals:
            col = cand_vals[-1]  # prefer the last numeric column (often the series)
            out = world[[year,col]].dropna()
            return out.rename(columns={year:"year", col:"value"})
    # Grapher variant: sometimes just [year, value]
    if "year" in df.columns and len(df.columns)==2:
        vcol = [c for c in df.columns if c != "year"][0]
        return df.rename(columns={vcol:"value"})
    return pd.DataFrame(columns=["year","value"])

def main():
    # ---- Load each series with fallbacks ----
    used = {}  # track which URL worked (for debugging)
    co2_df, used["co2"]     = fetch_csv_any(CANDIDATES["co2"])
    temp_df, used["temp"]   = fetch_csv_any(CANDIDATES["temp"])
    gdp_df,  used["gdp_pc"] = fetch_csv_any(CANDIDATES["gdp_pc"])
    life_df, used["lifeexp"]= fetch_csv_any(CANDIDATES["lifeexp"])
    vdem_df, used["vdem"]   = fetch_csv_any(CANDIDATES["vdem"])
    net_df,  used["internet"]= fetch_csv_any(CANDIDATES["internet"])
    eint_df, used["energyint"]= fetch_csv_any(CANDIDATES["energyint"])
    bat_df,  used["battle"] = fetch_csv_any(CANDIDATES["battle"])

    # ---- Shape into global-year series ----
    # CO2: sum by year (Mt)
    if co2_df is not None and not co2_df.empty:
        cols = [c.lower() for c in co2_df.columns]
        co2_df.columns = cols
        if "year" in cols and ("co2" in cols or "co2 (mt)" in "".join(cols)):
            # country-year: sum numeric columns except year/code/entity
            keep = [c for c in co2_df.columns if c not in ("entity","code","year")]
            tmp = co2_df[["year"] + keep].copy()
            tmp = tmp.groupby("year", as_index=False).sum(numeric_only=True)
            co2g = tmp.rename(columns={keep[-1]:"co2_mt"}) if keep else pd.DataFrame(columns=["year","co2_mt"])
        else:
            # maybe already an aggregated series [year,value]
            shaped = shape_world(co2_df)
            co2g = shaped.rename(columns={"value":"co2_mt"})
    else:
        co2g = pd.DataFrame(columns=["year","co2_mt"])

    # Temperature anomaly (World)
    if temp_df is not None and not temp_df.empty:
        shaped = shape_world(temp_df, value_hint="anomaly")
        tempg = shaped.rename(columns={"value":"temp_anom"})
    else:
        tempg = pd.DataFrame(columns=["year","temp_anom"])

    # GDP per capita (World)
    gdpw = shape_world(gdp_df)
    gdpw = gdpw.rename(columns={"value":"gdp_pc"})

    # Life expectancy (World)
    lifew = shape_world(life_df).rename(columns={"value":"life_exp"})

    # V-Dem liberal democracy index (World)
    vd = shape_world(vdem_df).rename(columns={"value":"vdem"})

    # Internet users share (World)
    netw = shape_world(net_df).rename(columns={"value":"internet_share"})

    # Energy intensity (World)
    eintw = shape_world(eint_df).rename(columns={"value":"energy_intensity"})

    # Battle deaths (per 100k world) — try direct per-capita; if not present, use absolute and scale
    batw = shape_world(bat_df)
    if "value" in batw.columns:
        batw = batw.rename(columns={"value":"battle_raw"})
        # If values look very large, assume absolute and min-max normalize later anyway.
        # (If actual per-100k exists, magnitudes will be small; both cases handled by normalization.)
        batw.rename(columns={"battle_raw":"battle_deaths"}, inplace=True)
    else:
        batw = pd.DataFrame(columns=["year","battle_deaths"])

    # ---- Join on year ----
    df = None
    for piece in [co2g, tempg, gdpw, lifew, vd, netw, eintw, batw]:
        df = piece if df is None else safe_merge(df, piece, on="year")
    if df is None or df.empty:
        # Nothing fetched — fail gracefully with a clear message (but don't 404 the run)
        raise SystemExit("No historical series could be fetched. Please re-run later.")

    df = df.sort_values("year")
    df = df[(df["year"]>=1900) & (df["year"]<=time.gmtime().tm_year)]

    # ---- Normalize categories [0..100] with sensible invert where “higher=worse” ----
    cats = {}

    # Planetary Health: combine temp anomaly (invert) + CO2 (invert)
    ph1 = norm_minmax(df["temp_anom"]) if "temp_anom" in df else pd.Series([50]*len(df), index=df.index)
    ph2 = norm_minmax(df["co2_mt"])    if "co2_mt"    in df else pd.Series([50]*len(df), index=df.index)
    cats["Planetary Health"] = (1 - ph1/100.0)*50 + (1 - ph2/100.0)*50  # invert both, average, keep 0..100

    # Economic Wellbeing: GDP per capita (higher better)
    cats["Economic Wellbeing"] = norm_minmax(df["gdp_pc"]) if "gdp_pc" in df else pd.Series([50]*len(df), index=df.index)

    # Public Health: Life expectancy (higher better)
    cats["Public Health"] = norm_minmax(df["life_exp"]) if "life_exp" in df else pd.Series([50]*len(df), index=df.index)

    # Global Peace & Conflict: battle deaths (higher worse → invert)
    if "battle_deaths" in df:
        b = norm_minmax(df["battle_deaths"])
        cats["Global Peace & Conflict"] = (1 - b/100.0) * 100.0
    else:
        cats["Global Peace & Conflict"] = pd.Series([50]*len(df), index=df.index)

    # Civic Freedom & Rights: V-Dem index (higher better)
    cats["Civic Freedom & Rights"] = norm_minmax(df["vdem"]) if "vdem" in df else pd.Series([50]*len(df), index=df.index)

    # Technological Progress: internet users % (higher better)
    cats["Technological Progress"] = norm_minmax(df["internet_share"]) if "internet_share" in df else pd.Series([50]*len(df), index=df.index)

    # Sentiment & Culture: placeholder
    cats["Sentiment & Culture"] = pd.Series([50]*len(df), index=df.index)

    # Entropy Index: energy intensity (higher intensity = worse → invert)
    if "energy_intensity" in df:
        e = norm_minmax(df["energy_intensity"])
        cats["Entropy Index"] = (1 - e/100.0) * 100.0
    else:
        cats["Entropy Index"] = pd.Series([50]*len(df), index=df.index)

    # ---- Compose GTI (equal weights placeholder; swap in your hybrid later) ----
    order = ["Planetary Health","Economic Wellbeing","Global Peace & Conflict","Public Health","Civic Freedom & Rights","Technological Progress","Sentiment & Culture","Entropy Index"]
    weights = {k: 1.0/len(order) for k in order}
    gti_score = sum(weights[k]*cats[k] for k in order)

    # ---- Output ----
    out = {
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "series": [{"year": int(y), "gti": float(v)} for y,v in zip(df["year"].values.tolist(), gti_score.values.tolist())],
        "by_category": {k: {int(y): float(v) for y,v in zip(df["year"].values.tolist(), cats[k].values.tolist())} for k in order},
        "sources_used": {k: (CANDIDATES[k] and "…"+CANDIDATES[k][0][-40:]) if v is None else v for k,v in used.items()},
        "note": "Historical backfill from public datasets; robust to missing sources; normalized by 5th–95th percentile ranges."
    }
    (DATA / "gti.json").write_text(json.dumps(out, indent=2))
    print(f"Wrote data/gti.json with {len(out['series'])} years.")
    print("Sources (first working url per series):")
    for k,v in used.items():
        print(f"  {k}: {v or 'none'}")

if __name__ == "__main__":
    main()
