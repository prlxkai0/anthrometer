#!/usr/bin/env python3
# Fetch daily ACWI (equities), VIX (volatility), and Brent (oil) from Stooq.
# No API key needed. Writes: data/live/markets.json
#
# Scoring (0-100, higher = better):
# - ACWI momentum (30d return vs its own history): higher = better
# - VIX level (inverse): lower = better
# - Brent 30d volatility (inverse): lower = better
#
# Outputs:
# {
#   "updated": "...Z",
#   "acwi": {"last": 123.45, "ret30": 0.042, "score": 66.7},
#   "vix":  {"last": 15.2,   "score": 82.0},
#   "brent":{"last": 66.1,  "vol30": 0.021, "stability_score": 74.3},
#   "econ_score": 68.1,
#   "entropy_score": 77.5
# }

import re, io, csv, math, json, datetime, urllib.request
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT  = ROOT / "data" / "live"
OUT.mkdir(parents=True, exist_ok=True)

# Stooq symbol pages with a "Download data in csv file" link.
# We'll fetch the HTML and extract the CSV href for robustness.
STOOQ_PAGE = "https://stooq.com/q/d/?s={sym}"

SYMS = {
    "acwi": "acwi.us",  # iShares MSCI ACWI ETF
    "vix":  "vi.f",     # S&P 500 VIX futures
    "brent":"cb.f"      # Brent crude futures
}

CSV_HREF_RE = re.compile(r'href="([^"]*?/q/d/l/\?s=[^"]+?)"')

def fetch_csv_for_symbol(symbol: str) -> pd.DataFrame:
    url = STOOQ_PAGE.format(sym=symbol)
    with urllib.request.urlopen(url, timeout=30) as r:
        html = r.read().decode("utf-8", errors="replace")
    m = CSV_HREF_RE.search(html)
    if not m:
        raise RuntimeError(f"No CSV link found on {url}")
    csv_url = m.group(1)
    if csv_url.startswith("//"):
        csv_url = "https:" + csv_url
    elif csv_url.startswith("/"):
        csv_url = "https://stooq.com" + csv_url

    with urllib.request.urlopen(csv_url, timeout=30) as r:
        raw = r.read().decode("utf-8", errors="replace")
    df = pd.read_csv(io.StringIO(raw))
    # Expected columns: Date,Open,High,Low,Close,Volume
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df

def pct_return(series: pd.Series, days: int) -> float:
    if len(series) <= days: return 0.0
    now = float(series.iloc[-1])
    prev = float(series.iloc[-1 - days])
    if prev == 0: return 0.0
    return (now / prev) - 1.0

def zscore(x: float, mean: float, std: float, clip: float = 3.0) -> float:
    if std <= 0: return 0.0
    z = (x - mean) / std
    return max(-clip, min(clip, z))

def z_to_0_100(z: float, clip: float = 3.0) -> float:
    # map z ∈ [-clip, clip] → [0,100], linearly
    return max(0.0, min(100.0, (z + clip) * (100.0 / (2 * clip))))

def vix_level_to_score(vix: float) -> float:
    # 10 → 100, 40 → 10 (linear, clipped)
    v = max(10.0, min(40.0, vix))
    return 100.0 - (v - 10.0) * (90.0 / 30.0)

def vol_to_score(vol: float, base_mean: float, base_std: float) -> float:
    # higher vol = worse → invert zscore mapping
    z = zscore(vol, base_mean, base_std, clip=3.0)   # -3..+3
    s = z_to_0_100(-z)  # invert: higher-than-baseline vol → lower score
    return s

def main():
    # --- ACWI ---
    acwi_df = fetch_csv_for_symbol(SYMS["acwi"])
    acwi_close = acwi_df["Close"]
    acwi_ret30 = pct_return(acwi_close, 30)
    # History of 30d returns for zscoring
    r30_hist = []
    for i in range(30, len(acwi_close)):
        r30_hist.append((float(acwi_close.iloc[i]) / float(acwi_close.iloc[i-30])) - 1.0)
    if r30_hist:
        mean_r = sum(r30_hist) / len(r30_hist)
        std_r  = (sum((x - mean_r)**2 for x in r30_hist) / max(1, len(r30_hist)-1))**0.5
        acwi_score = z_to_0_100(zscore(acwi_ret30, mean_r, std_r, 3.0))
    else:
        acwi_score = 50.0

    # --- VIX ---
    vix_df = fetch_csv_for_symbol(SYMS["vix"])
    vix_last = float(vix_df["Close"].iloc[-1])
    vix_score = vix_level_to_score(vix_last)

    # --- Brent ---
    brent_df = fetch_csv_for_symbol(SYMS["brent"])
    brent_close = brent_df["Close"]
    # 30d historical volatility (stdev of daily returns)
    brent_rets = brent_close.pct_change().dropna()
    vol30 = float(brent_rets.tail(30).std()) if len(brent_rets) >= 30 else float(brent_rets.std()) if not brent_rets.empty else 0.0
    # Baseline from long history
    base_mean = float(brent_rets.rolling(30).std().dropna().mean()) if len(brent_rets) >= 60 else float(brent_rets.std()) or 0.0
    base_std  = float(brent_rets.rolling(30).std().dropna().std())  if len(brent_rets) >= 90 else (base_mean * 0.5) if base_mean>0 else 1.0
    brent_stability = vol_to_score(vol30, base_mean, base_std)

    # --- Compose category/entropy ---
    econ_score = 0.50*acwi_score + 0.25*vix_score + 0.25*brent_stability
    entropy_score = 0.60*vix_score + 0.40*brent_stability  # higher score = more ordered (less entropy)

    out = {
        "updated": datetime.datetime.utcnow().isoformat() + "Z",
        "acwi": {
            "last": float(acwi_close.iloc[-1]),
            "ret30": round(acwi_ret30, 4),
            "score": round(acwi_score, 2)
        },
        "vix": {
            "last": round(vix_last, 3),
            "score": round(vix_score, 2)
        },
        "brent": {
            "last": float(brent_close.iloc[-1]),
            "vol30": round(vol30, 4),
            "stability_score": round(brent_stability, 2)
        },
        "econ_score": round(econ_score, 2),
        "entropy_score": round(entropy_score, 2)
    }
    (OUT / "markets.json").write_text(json.dumps(out, indent=2))
    print("Markets updated:", out)

if __name__ == "__main__":
    main()
