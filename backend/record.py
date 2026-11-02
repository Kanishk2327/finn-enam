"""Run locally while NSE works: python -m backend.record
Saves the last 7 days of REAL filings so a blocked host still shows real (labelled) data."""
import json, os
from . import announcements

items, src = announcements.fetch(168)
assert src == "live", "NSE fetch failed, nothing recorded"
path = os.path.join(os.path.dirname(__file__), "snapshot_announcements.json")
json.dump(items, open(path, "w"))
print(f"recorded {len(items)} filings -> {path}")
