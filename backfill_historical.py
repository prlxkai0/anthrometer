#!/usr/bin/env python3
# backfill_historical.py — Build annual GTI from public datasets (OWID, UCDP).
# Writes: data/gti.json (full series, 1900→present where available)
import io, json, time, pathlib
from urllib.request import urlopen, Request
import pandas as pd
import numpy as np

DATA = pathlib.Path("data")
DATA.mkdir(exist_ok=True)

def fetch_csv(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=60) as r:
        raw = r.read()
    try:
        return pd.read_csv(io.BytesIO(raw))
    except Exception:
        return pd.read_csv(io.BytesIO(raw), sep="\t")

def norm_minmax(s, lo=None, hi=None, invert=False):
    ss = pd.Series(s, dtype="float64")
    if lo is None: lo = np.nanpercentile(ss.dropna(), 5)
    if hi is None: hi = np.nanpercentile(ss.dropna(), 95)
    rng = (hi - lo) if (hi is not None and lo is not None and hi>lo) else 1.0
    x = (ss - lo) / rng
    x = x.clip(lower=0, upper=1)
    if invert: x = 1 - x
    return (x * 100.0)

def safe_merge(left, right, on="year"):
    return pd.merge(left, right, on=on, how="outer")

def main():
    # ---- Sources (OWID/UCDP endpoints) ----
    urls = {
        "co2":      "https://ourworldindata.org/grapher/co2.csv",  # country/year emissions (Mt). We'll global-sum per year.
        "temp":     "https://ourworldindata.org/grapher/temperature-anomaly.csv",  # global anomaly by year
        "gdp_pc":   "https://ourworldindata.org/grapher/gdp-per-capita-maddison-2020.csv",
        "lifeexp":  "https://ourworldindata.org/grapher/life-expectancy.csv",
        "vdem":     "https://ourworldindata.org/grapher/vdem_libdem.csv",
        "internet": "https://ourworldindata.org/grapher/share-of-individuals-using-the-internet.csv",
        "energyint":"https://ourworldindata.org/grapher/energy-intensity.csv",  # energy per GDP
        "battle":   "https://ourworldindata.org/grapher/battle-deaths-from-external-and-internal-conflicts-per-100-000.csv",
    }

    # ---- Load + shape each series into global-year form ----
    # CO2: sum across countries per year (Mt) -> proxy of atmospheric pressure (directional)
    co2 = fetch_csv(urls["co2"])
    if "Entity" in co2.columns and "Year" in co2.columns and "CO2" in co2.columns:
        co2g = co2.groupby("Year", as_index=False)["CO2"].sum()
        co2g.rename(columns={"Year":"year","CO2":"co2_mt"}, inplace=True)
    else:
        co2g = pd.DataFrame(columns=["year","co2_mt"])

    temp = fetch_csv(urls["temp"])
    if "Year" in temp.columns and "World" in temp.columns:
        tempg = temp[["Year","World"]].rename(columns={"Year":"year","World":"temp_anom"})
    else:
        # grapher variants often have ["Entity","Year","temperature-anomaly"]
        cols = [c.lower() for c in temp.columns]
        temp.columns = cols
        if "year" in cols and "temperature-anomaly" in cols and "entity" in cols:
            tempg = temp[temp["entity"].str.lower().eq("world")][["year","temperature-anomaly"]].rename(columns={"temperature-anomaly":"temp_anom"})
        else:
            tempg = pd.DataFrame(columns=["year","temp_anom"])

    gdp = fetch_csv(urls["gdp_pc"])
    if "Entity" in gdp.columns and "Year" in gdp.columns:
        gdpw = gdp[gdp["Entity"]=="World"][["Year", gdp.columns[-1]]].rename(columns={"Year":"year", gdp.columns[-1]:"gdp_pc"})
    else:
        gdpw = pd.DataFrame(columns=["year","gdp_pc"])

    life = fetch_csv(urls["lifeexp"])
    if "Entity" in life.columns and "Year" in life.columns:
        lifew = life[life["Entity"]=="World"][["Year", life.columns[-1]]].rename(columns={"Year":"year", life.columns[-1]:"life_exp"})
    else:
        lifew = pd.DataFrame(columns=["year","life_exp"])

    vdem = fetch_csv(urls["vdem"])
    if "Entity" in vdem.columns and "Year" in vdem.columns:
        vd = vdem[vdem["Entity"]=="World"][["Year", vdem.columns[-1]]].rename(columns={"Year":"year", vdem.columns[-1]:"vdem"})
    else:
        vd = pd.DataFrame(columns=["year","vdem"])

    net = fetch_csv(urls["internet"])
    if "Entity" in net.columns and "Year" in net.columns:
        netw = net[net["Entity"]=="World"][["Year", net.columns[-1]]].rename(columns={"Year":"year", net.columns[-1]:"internet_share"})
    else:
        netw = pd.DataFrame(columns=["year","internet_share"])

    eint = fetch_csv(urls["energyint"])
    if "Entity" in eint.columns and "Year" in eint.columns:
        eintw = eint[eint["Entity"]=="World"][["Year", eint.columns[-1]]].rename(columns={"Year":"year", eint.columns[-1]:"energy_intensity"})
    else:
        eintw = pd.DataFrame(columns=["year","energy_intensity"])

    battle = fetch_csv(urls["battle"])
    if "Entity" in battle.columns and "Year" in battle.columns:
        batw = battle[battle["Entity"]=="World"][["Year", battle.columns[-1]]].rename(columns={"Year":"year", battle.columns[-1]:"battle_deaths_per100k"})
    else:
        batw = pd.DataFrame(columns=["year","battle_deaths_per100k"])

    # ---- Join on year ----
    df = None
    for piece in [co2g, tempg, gdpw, lifew, vd, netw, eintw, batw]:
        df = piece if df is None else safe_merge(df, piece, on="year")
    if df is None or df.empty:
        raise SystemExit("No historical series could be fetched — please retry later.")

    df = df.sort_values("year")
    # Restrict to 1900→present
    df = df[(df["year"]>=1900) & (df["year"]<=time.gmtime().tm_year)]

    # ---- Normalize per category to [0..100] (directionally correct) ----
    cats = {}

    # Planetary Health: combine temp anomaly (bad ↑) and (optionally CO2 total ↑ bad)
    # Use anomaly as primary; CO2 as secondary (50/50 simple)
    if "temp_anom" in df and df["temp_anom"].notna().any():
        ph1 = norm_minmax(df["temp_anom"], invert=True)  # higher anomaly = worse → invert
    else:
        ph1 = pd.Series([50]*len(df), index=df.index)
    if "co2_mt" in df and df["co2_mt"].notna().any():
        ph2 = norm_minmax(df["co2_mt"], invert=True)     # more emissions = worse → invert
    else:
        ph2 = pd.Series([50]*len(df), index=df.index)
    cats["Planetary Health"] = (0.5*ph1 + 0.5*ph2)

    # Economic Wellbeing: GDP per cap (higher better)
    if "gdp_pc" in df and df["gdp_pc"].notna().any():
        cats["Economic Wellbeing"] = norm_minmax(df["gdp_pc"], invert=False)
    else:
        cats["Economic Wellbeing"] = pd.Series([50]*len(df), index=df.index)

    # Public Health: Life expectancy (higher better)
    if "life_exp" in df and df["life_exp"].notna().any():
        cats["Public Health"] = norm_minmax(df["life_exp"], invert=False)
    else:
        cats["Public Health"] = pd.Series([50]*len(df), index=df.index)

    # Global Peace & Conflict: battle deaths per 100k (higher worse → invert)
    if "battle_deaths_per100k" in df and df["battle_deaths_per100k"].notna().any():
        cats["Global Peace & Conflict"] = norm_minmax(df["battle_deaths_per100k"], invert=True)
    else:
        cats["Global Peace & Conflict"] = pd.Series([50]*len(df), index=df.index)

    # Civic Freedom & Rights: V-Dem liberal democracy index (higher better)
    if "vdem" in df and df["vdem"].notna().any():
        cats["Civic Freedom & Rights"] = norm_minmax(df["vdem"], invert=False)
    else:
        cats["Civic Freedom & Rights"] = pd.Series([50]*len(df), index=df.index)

    # Technological Progress: internet users % (higher better)
    if "internet_share" in df and df["internet_share"].notna().any():
        cats["Technological Progress"] = norm_minmax(df["internet_share"], invert=False)
    else:
        cats["Technological Progress"] = pd.Series([50]*len(df), index=df.index)

    # Sentiment & Culture: placeholder neutral (can be replaced later)
    cats["Sentiment & Culture"] = pd.Series([50]*len(df), index=df.index)

    # Entropy Index: energy intensity (higher intensity = worse → invert)
    if "energy_intensity" in df and df["energy_intensity"].notna().any():
        cats["Entropy Index"] = norm_minmax(df["energy_intensity"], invert=True)
    else:
        cats["Entropy Index"] = pd.Series([50]*len(df), index=df.index)

    # ---- Compose GTI (Weighted Hybrid placeholder) ----
    # Start with balanced equal weights; you can swap to your approved weights later.
    order = ["Planetary Health","Economic Wellbeing","Global Peace & Conflict","Public Health","Civic Freedom & Rights","Technological Progress","Sentiment & Culture","Entropy Index"]
    weights = {k: 1.0/len(order) for k in order}
    gti_score = sum(weights[k]*cats[k] for k in order)

    # ---- Build output ----
    out = {
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "series": [{"year": int(y), "gti": float(v)} for y,v in zip(df["year"].values.tolist(), gti_score.values.tolist())],
        "by_category": {k: {int(y): float(v) for y,v in zip(df["year"].values.tolist(), cats[k].values.tolist())} for k in order},
        "note": "Historical backfill from public datasets; normalized per-series by 5th–95th percentile range."
    }
    (DATA / "gti.json").write_text(json.dumps(out, indent=2))
    print("Wrote data/gti.json with", len(out["series"]), "years.")

if __name__ == "__main__":
    main()
