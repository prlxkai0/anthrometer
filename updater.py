#!/usr/bin/env python3
# updater.py — assemble status.json (safe if live feeds missing)
import json, time, pathlib

DATA_DIR = pathlib.Path("data")
LIVE_DIR = DATA_DIR / "live"
STATUS   = DATA_DIR / "status.json"

def read_json(p, default=None):
    try:
        return json.loads(pathlib.Path(p).read_text())
    except Exception:
        return default

def main():
    DATA_DIR.mkdir(exist_ok=True)
    LIVE_DIR.mkdir(parents=True, exist_ok=True)

    planetary = read_json(LIVE_DIR / "planetary.json", default={})
    sentiment = read_json(LIVE_DIR / "sentiment.json", default={})
    markets   = read_json(LIVE_DIR / "markets.json",   default={})
    food      = read_json(LIVE_DIR / "food.json",      default={})
    conflict  = read_json(LIVE_DIR / "conflict.json",  default={})
    foodacc   = read_json(LIVE_DIR / "foodaccess.json",default={})
    employ    = read_json(LIVE_DIR / "employment.json",default={})
    gti       = read_json(DATA_DIR / "gti.json",       default=None)

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    gti_last = None; gti_avg30 = None
    if gti and isinstance(gti.get("series"), list) and gti["series"]:
        try:
            gti_last = float(gti["series"][-1]["gti"])
        except Exception:
            pass
        try:
            vals = [float(x["gti"]) for x in gti["series"][-30:]]
            if vals: gti_avg30 = sum(vals)/len(vals)
        except Exception:
            pass

    status = {
        "updated_iso": now,
        "gti_last": round(gti_last, 2) if gti_last is not None else None,
        "gti_30d_avg": round(gti_avg30, 2) if gti_avg30 is not None else None,

        "planetary": {
            "co2_ppm":        (planetary or {}).get("co2_ppm"),
            "gistemp_anom_c": (planetary or {}).get("gistemp_anom_c"),
            "delta_ppm":      (planetary or {}).get("delta_ppm"),
            "delta_anom":     (planetary or {}).get("delta_anom"),
        },
        "food": {
            "fpi_last": (food or {}).get("fpi_last"),
            "fpi_mom":  (food or {}).get("fpi_mom"),
            "fpi_yoy":  (food or {}).get("fpi_yoy"),
        },
        "sentiment": {
            "avg_tone_30d": (sentiment or {}).get("avg_tone_30d"),
            "delta_tone":   (sentiment or {}).get("delta_tone"),
        },
        "conflict": {
            "last_val":   (conflict or {}).get("last_val"),
            "avg_last30": (conflict or {}).get("avg_last30"),
            "avg_prev30": (conflict or {}).get("avg_prev30"),
            "delta_30":   (conflict or {}).get("delta_30"),
        },
        "markets": {
            "acwi_last":   (markets or {}).get("acwi_last"),
            "acwi_ret30":  (markets or {}).get("acwi_ret30"),
            "vix":         (markets or {}).get("vix"),
            "brent_last":  (markets or {}).get("brent_last"),
            "brent_vol30": (markets or {}).get("brent_vol30"),
            "econ_score":  (markets or {}).get("econ_score"),
            "entropy_score": (markets or {}).get("entropy_score"),
        },
        "food_access": {
            "undernourished_pct": (foodacc or {}).get("undernourished_pct"),
            "delta_pct":          (foodacc or {}).get("delta_pct"),
        },
        "employment": {
            "unemployment_rate": (employ or {}).get("unemployment_rate"),
            "delta_pct":         (employ or {}).get("delta_pct"),
        },
        "note": "Status composed from live inputs; nulls indicate missing feed this run."
    }

    STATUS.write_text(json.dumps(status, indent=2))
    print("Wrote", STATUS)

if __name__ == "__main__":
    main()
