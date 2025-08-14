#!/usr/bin/env python3
import re, io, csv, json, datetime, urllib.request, traceback
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT  = ROOT / "data" / "live"
OUT.mkdir(parents=True, exist_ok=True)

STOOQ_PAGE = "https://stooq.com/q/d/?s={sym}"
CSV_HREF_RE = re.compile(r'href="([^"]*?/q/d/l/\?s=[^"]+?)"')
SYMS = {"acwi":"acwi.us","vix":"vi.f","brent":"cb.f"}

def fetch_csv_df(symbol: str):
    url = STOOQ_PAGE.format(sym=symbol)
    with urllib.request.urlopen(url, timeout=30) as r:
        html = r.read().decode("utf-8", errors="replace")
    m = CSV_HREF_RE.search(html)
    if not m: raise RuntimeError(f"No CSV link on {url}")
    csv_url = m.group(1)
    if csv_url.startswith("//"): csv_url = "https:" + csv_url
    if csv_url.startswith("/"):  csv_url = "https://stooq.com" + csv_url
    with urllib.request.urlopen(csv_url, timeout=30) as r:
        raw = r.read().decode("utf-8", errors="replace")
    import pandas as pd
    df = pd.read_csv(io.StringIO(raw))
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)

def pct_return(series, days):
    if len(series) <= days: return 0.0
    now = float(series.iloc[-1]); prev = float(series.iloc[-1-days])
    return (now/prev) - 1.0 if prev else 0.0

def zscore(x, mean, std, clip=3.0):
    if std <= 0: return 0.0
    z = (x-mean)/std
    return max(-clip, min(clip, z))

def z_to_100(z, clip=3.0): return max(0.0, min(100.0, (z+clip)*(100.0/(2*clip))))
def vix_to_score(vix): 
    v = max(10.0, min(40.0, vix))
    return 100.0 - (v - 10.0) * (90.0/30.0)

def main():
    out = {
        "updated": datetime.datetime.utcnow().isoformat()+"Z",
        "acwi": {"last": None, "ret30": 0.0, "score": 60.0},
        "vix":  {"last": None, "score": 60.0},
        "brent":{"last": None, "vol30": 0.0, "stability_score": 60.0},
        "econ_score": 60.0,
        "entropy_score": 60.0
    }
    try:
        # ACWI
        acwi_df = fetch_csv_df(SYMS["acwi"])
        close = acwi_df["Close"]
        ret30 = pct_return(close, 30)
        # zscore of 30d returns over history
        r30_hist = []
        for i in range(30, len(close)):
            r30_hist.append((float(close.iloc[i])/float(close.iloc[i-30]))-1.0)
        if r30_hist:
            import statistics, math
            mean_r = sum(r30_hist)/len(r30_hist)
            std_r  = (sum((x-mean_r)**2 for x in r30_hist)/max(1,len(r30_hist)-1))**0.5
            acwi_score = z_to_100(zscore(ret30, mean_r, std_r, 3.0))
        else:
            acwi_score = 60.0
        out["acwi"] = {"last": float(close.iloc[-1]), "ret30": round(ret30,4), "score": round(acwi_score,2)}

        # VIX
        vix_df = fetch_csv_df(SYMS["vix"])
        vix_last = float(vix_df["Close"].iloc[-1])
        out["vix"] = {"last": round(vix_last,3), "score": round(vix_to_score(vix_last),2)}

        # Brent
        brent_df = fetch_csv_df(SYMS["brent"])
        bclose = brent_df["Close"]
        rets = bclose.pct_change().dropna()
        if len(rets) >= 30:
            vol30 = float(rets.tail(30).std())
            base_mean = float(rets.rolling(30).std().dropna().mean())
            base_std  = float(rets.rolling(30).std().dropna().std()) or (base_mean*0.5 if base_mean>0 else 1.0)
        else:
            vol30 = float(rets.std()) if not rets.empty else 0.0
            base_mean, base_std = (vol30, max(1e-6, vol30*0.5))
        # higher vol -> worse, invert
        import math
        from math import isfinite
        z = zscore(vol30, base_mean, base_std, 3.0)
        stability = z_to_100(-z)
        out["brent"] = {"last": float(bclose.iloc[-1]), "vol30": round(vol30,4), "stability_score": round(stability,2)}

        # Compose
        econ = 0.50*out["acwi"]["score"] + 0.25*out["vix"]["score"] + 0.25*out["brent"]["stability_score"]
        ent  = 0.60*out["vix"]["score"]  + 0.40*out["brent"]["stability_score"]
        out["econ_score"] = round(econ,2)
        out["entropy_score"] = round(ent,2)

    except Exception:
        traceback.print_exc()
        # keep neutral defaults

    (OUT/"markets.json").write_text(json.dumps(out, indent=2))
    print("Markets updated:", out)

if __name__ == "__main__":
    main()
