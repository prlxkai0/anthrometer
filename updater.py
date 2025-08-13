#!/usr/bin/env python3
import json, os, random, datetime

MIN_FLOOR = 100.0

DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'gti.json')

with open(DATA_PATH) as f:
    blob = json.load(f)

series = blob['series']
last = series[-1]['gti']

# Placeholder 'daily' tick: gentle random drift
nudge = random.uniform(-3, 3)
new_val = max(last + nudge, MIN_FLOOR)  # never below soft floor
series[-1]['gti'] = round(new_val, 2)

blob['updated'] = datetime.datetime.utcnow().isoformat() + 'Z'

with open(DATA_PATH, 'w') as f:
    json.dump(blob, f, indent=2)

print('Updated:', blob['updated'], 'Last GTI:', series[-1]['gti'])
