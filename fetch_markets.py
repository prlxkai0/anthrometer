#!/usr/bin/env python3
import io, json, datetime, urllib.request, time, traceback
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "data" / "live"
LIVE.mkdir(parents=True, exist_ok=True)
OUT = LIVE / "markets.json"

CSV = "https://stooq.com/q/d/l/?s={sym}&i=d"  # direct CSV endpoint (daily)

# Primary + fallbacks
ACWI_SYMS = ["acwi.us", "vt.us", "spy.us"]
VIX_SYMS  = ["^vix", "vix"]
BRENT_SYMS= ["brent", "cb.f", "cl.f"]  # last resort: crude WTI if Brent missing

UA = {"User-Agent":"AnthroMeter/1.0 (+github actions)"}

def fetch_df(symbol, tries=2, sleep=3):
    url = CSV.format(sym=symbol)
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode("utf-8", errors="replace")
            df = pd.read_csv(io.StringIO(raw))
            if "Close" not in df.columns:
                raise RuntimeError(f"CSV for {symbol} missing Close")
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.sort_values("Date").reset_index(drop=True)
            if len(df) < 10: raise RuntimeError(f"Too few rows for {symbol}")
            return df
        except Exception:
            if i+1 == tries: raise
            time.sleep(sleep)

def first_good_df(symbols):
    last_err = None
    for s in symbols:
        try:
            return s, fetch_df(s)
        except Exception as e:
            last_err = e
            continue
    if last_err: raise last_err
    raise RuntimeError("No working symbol")

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
    try:
        # ACWI proxy
        ac_sym, ac = first_good_df(ACWI_SYMS)
        ac_close = ac["Close"]
        ret30 = pct_return(ac_close, 30)
        r30_hist=[(float(ac_close.iloc[i])/float(ac_close.iloc[i-30]))-1.0 for i in range(30,len(ac_close))]
        if r30_hist:
            import statistics
            mean_r = statistics.fmean(r30_hist)
            std_r  = (sum((x-mean_r)**2 for x in r30_hist)/max(1,len(r30_hist)-1))**0.5
            ac_score = z_to_100(zscore(ret30, mean_r, std_r, 3.0))
        else:
            ac_score = 60.0
        ac_obj = {"symbol": ac_sym, "last": float(ac_close.iloc[-1]), "ret30": round(ret30,4), "score": round(ac_score,2)}

        # VIX
        vix_sym, vix = first_good_df(VIX_SYMS)
        vix_last = float(vix["Close"].iloc[-1])
        vix_obj = {"symbol": vix_sym, "last": round(vix_last,2), "score": round(vix_to_score(vix_last),2)}

        # Brent (or fallback)
        br_sym, br = first_good_df(BRENT_SYMS)
        br_close = br["Close"]
        rets = br_close.pct_change().dropna()
        if len(rets) >= 30:
            vol30 = float(rets.tail(30).std())
            base_mean = float(rets.rolling(30).std().dropna().mean())
            base_std  = float(rets.rolling(30).std().dropna().std()) or (base_mean*0.5 if base_mean>0 else 1.0)
        else:
            vol30 = float(rets.std()) if not rets.empty else 0.0
            base_mean, base_std = (vol30, max(1e-6, vol30*0.5))
        stab = z_to_100(-zscore(vol30, base_mean, base_std, 3.0))
        br_obj = {"symbol": br_sym, "last": float(br_close.iloc[-1]), "vol30": round(vol30,4), "stability_score": round(stab,2)}

        econ = 0.50*ac_obj["score"] + 0.25*vix_obj["score"] + 0.25*br_obj["stability_score"]
        ent  = 0.60*vix_obj["score"]  + 0.40*br_obj["stability_score"]

        out.update({
            "acwi": ac_obj, "vix": vix_obj, "brent": br_obj,
            "econ_score": round(econ,2), "entropy_score": round(ent,2)
        })
    except Exception:
        traceback.print_exc()
        # leave out fields to allow updater to carry forward; it will coalesce with previous status

    OUT.write_text(json.dumps(out, indent=2))
    print("Markets updated:", out)

if __name__ == "__main__":
    main()
