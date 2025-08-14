#!/usr/bin/env python3
import re, io, json, datetime, urllib.request, time, traceback
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "data" / "live"
LIVE.mkdir(parents=True, exist_ok=True)
OUT = LIVE / "markets.json"

STOOQ_PAGE = "https://stooq.com/q/d/?s={sym}"
CSV_HREF_RE = re.compile(r'href="([^"]*?/q/d/l/\?s=[^"]+?)"')
SYMS = {"acwi":"acwi.us","vix":"vi.f","brent":"cb.f"}

def prev():
    if OUT.exists():
        try: return json.loads(OUT.read_text())
        except: pass
    return {}

def fetch_csv(symbol, tries=2, sleep=3):
    for i in range(tries):
        try:
            url = STOOQ_PAGE.format(sym=symbol)
            req = urllib.request.Request(url, headers={"User-Agent":"AnthroMeter/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                html = r.read().decode("utf-8", errors="replace")
            m = CSV_HREF_RE.search(html)
            if not m: raise RuntimeError("No CSV link")
            csv_url = m.group(1)
            if csv_url.startswith("//"): csv_url = "https:"+csv_url
            if csv_url.startswith("/"):  csv_url = "https://stooq.com"+csv_url
            req2 = urllib.request.Request(csv_url, headers={"User-Agent":"AnthroMeter/1.0"})
            with urllib.request.urlopen(req2, timeout=30) as r2:
                raw = r2.read().decode("utf-8", errors="replace")
            df = pd.read_csv(io.StringIO(raw))
            df["Date"] = pd.to_datetime(df["Date"])
            return df.sort_values("Date").reset_index(drop=True)
        except Exception:
            if i+1 == tries: raise
            time.sleep(sleep)

def pct_return(series, days):
    if len(series) <= days: return 0.0
    now = float(series.iloc[-1]); prev = float(series.iloc[-1-days])
    return (now/prev)-1.0 if prev else 0.0

def zscore(x, mean, std, clip=3.0):
    if std <= 0: return 0.0
    z=(x-mean)/std
    return max(-clip, min(clip, z))

def z_to_100(z, clip=3.0): return max(0.0, min(100.0, (z+clip)*(100.0/(2*clip))))
def vix_to_score(vix):
    v=max(10.0, min(40.0, vix))
    return 100.0 - (v - 10.0) * (90.0/30.0)

def main():
    out = {"updated": datetime.datetime.utcnow().isoformat()+"Z"}
    old = prev()
    try:
        # ACWI
        acwi = fetch_csv(SYMS["acwi"])
        ac = acwi["Close"]; ret30 = pct_return(ac, 30)
        r30_hist=[(float(ac.iloc[i])/float(ac.iloc[i-30]))-1.0 for i in range(30,len(ac))]
        if r30_hist:
            import statistics
            mean_r = statistics.fmean(r30_hist)
            std_r  = (sum((x-mean_r)**2 for x in r30_hist)/max(1,len(r30_hist)-1))**0.5
            acwi_score = z_to_100(zscore(ret30, mean_r, std_r, 3.0))
        else:
            acwi_score = 60.0
        acwi_obj = {"last": float(ac.iloc[-1]), "ret30": round(ret30,4), "score": round(acwi_score,2)}

        # VIX
        vix  = fetch_csv(SYMS["vix"]); vix_last = float(vix["Close"].iloc[-1])
        vix_obj = {"last": round(vix_last,3), "score": round(vix_to_score(vix_last),2)}

        # Brent
        br   = fetch_csv(SYMS["brent"]); bc = br["Close"]
        rets = bc.pct_change().dropna()
        if len(rets) >= 30:
            import pandas as pd
            vol30 = float(rets.tail(30).std())
            base_mean = float(rets.rolling(30).std().dropna().mean())
            base_std  = float(rets.rolling(30).std().dropna().std()) or (base_mean*0.5 if base_mean>0 else 1.0)
        else:
            vol30 = float(rets.std()) if not rets.empty else 0.0
            base_mean, base_std = (vol30, max(1e-6, vol30*0.5))
        stab = z_to_100(-zscore(vol30, base_mean, base_std, 3.0))
        brent_obj = {"last": float(bc.iloc[-1]), "vol30": round(vol30,4), "stability_score": round(stab,2)}

        econ = 0.50*acwi_obj["score"] + 0.25*vix_obj["score"] + 0.25*brent_obj["stability_score"]
        ent  = 0.60*vix_obj["score"]  + 0.40*brent_obj["stability_score"]

        out.update({
            "acwi": acwi_obj, "vix": vix_obj, "brent": brent_obj,
            "econ_score": round(econ,2), "entropy_score": round(ent,2)
        })
    except Exception:
        traceback.print_exc()
        # carry forward previous or neutral
        out.update({
            "acwi":  old.get("acwi",  {"last": None, "ret30": 0.0, "score": 60.0}),
            "vix":   old.get("vix",   {"last": None, "score": 60.0}),
            "brent": old.get("brent", {"last": None, "vol30": 0.0, "stability_score": 60.0}),
            "econ_score":  old.get("econ_score", 60.0),
            "entropy_score": old.get("entropy_score", 60.0)
        })

    OUT.write_text(json.dumps(out, indent=2))
    print("Markets updated:", out)

if __name__ == "__main__":
    main()
