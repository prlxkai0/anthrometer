#!/usr/bin/env python3
# fetch_conflict.py — GDELT Timelines (30d "conflict/violence" volume proxy). No API key.
# Writes: data/live/conflict.json
import json, os, sys, time, pathlib, urllib.parse
from urllib.request import urlopen, Request

OUT = pathlib.Path("data/live/conflict.json")
OUT.parent.mkdir(parents=True, exist_ok=True)

# We query multiple related themes to stabilize the signal, then combine.
QUERIES = [
    'theme:VIOLENCE',
    'theme:CONFLICT',
    'theme:PROTEST',
    'theme:ARREST'
]
BASE = "https://api.gdeltproject.org/api/v2/timeline/timeline"

def fetch_series(query: str, timespan="60d", smooth=7):
    # We request 60d so we can compute last-30 vs prior-30 deltas
    params = {
        "query": query,
        "mode": "timelinevol",
        "format": "json",
        "timespan": timespan,
        "timelinesmooth": str(smooth),
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8", errors="ignore"))
    # The JSON usually has: {"timeline":[{"value":"...","date":"YYYYMMDD"...}, ...]} under various keys.
    # We attempt to find numeric series by scanning values.
    series = []
    def collect(node):
        if isinstance(node, dict):
            for k,v in node.items():
                if k.lower()=="timeline" and isinstance(v, list):
                    # Extract numeric "value" keys
                    for row in v:
                        try:
                            val = float(row.get("value"))
                            series.append((row.get("date"), val))
                        except Exception:
                            pass
                else:
                    collect(v)
        elif isinstance(node, list):
            for item in node:
                collect(item)
    collect(data)
    # Deduplicate by date, average if duplicates
    if not series: return []
    by_date = {}
    for d,v in series:
        if d is None: continue
        by_date.setdefault(d, []).append(v)
    out = sorted([(d, sum(vs)/len(vs)) for d,vs in by_date.items()], key=lambda x:x[0])
    return out

def mean(vals):
    return sum(vals)/len(vals) if vals else 0.0

def main():
    updated_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # Fetch and combine multiple theme series
    buckets = []
    for q in QUERIES:
        try:
            s = fetch_series(q)
            if s:
                buckets.append(s)
        except Exception:
            continue

    # Align by date and average across queries
    combined = []
    if buckets:
        # Build date index
        dates = sorted({d for s in buckets for (d,_) in s})
        date_to_vals = {d:[] for d in dates}
        for s in buckets:
            dd = dict(s)
            for d in dates:
                if d in dd:
                    date_to_vals[d].append(dd[d])
        for d in dates:
            vals = date_to_vals[d]
            if vals:
                combined.append((d, mean(vals)))

    # Compute last value and 30d averages vs prior 30d
    last_val = None
    avg_last30 = None
    avg_prev30 = None
    delta_30 = None

    if combined:
        vals = [v for _,v in combined]
        if vals:
            last_val = float(vals[-1])
        # Assume roughly daily cadence; take last 30 and prior 30
        if len(vals) >= 60:
            avg_last30 = mean(vals[-30:])
            avg_prev30 = mean(vals[-60:-30])
            delta_30 = avg_last30 - avg_prev30
        elif len(vals) >= 30:
            avg_last30 = mean(vals[-30:])
            avg_prev30 = mean(vals[:-30]) if len(vals) > 30 else None
            delta_30 = (avg_last30 - avg_prev30) if (avg_prev30 is not None) else None

    data = {
        "updated_iso": updated_iso,
        "last_val": round(last_val, 2) if last_val is not None else None,
        "avg_last30": round(avg_last30, 2) if avg_last30 is not None else None,
        "avg_prev30": round(avg_prev30, 2) if avg_prev30 is not None else None,
        "delta_30": round(delta_30, 2) if delta_30 is not None else None,
        "note": "GDELT Timelines combined: VIOLENCE, CONFLICT, PROTEST, ARREST (7‑day smooth, 60d window)."
    }

    # Preserve previous file on total failure
    if all(v is None for v in [last_val, avg_last30]):
        if OUT.exists():
            try:
                cached = json.loads(OUT.read_text())
                cached["note"] = "Using cached conflict.json (fetch failed)."
                OUT.write_text(json.dumps(cached, indent=2))
                print("conflict.json: cached")
                return
            except Exception:
                pass

    OUT.write_text(json.dumps(data, indent=2))
    print("conflict.json:", json.dumps(data)[:200] + ("..." if len(json.dumps(data))>200 else ""))

if __name__ == "__main__":
    main()
