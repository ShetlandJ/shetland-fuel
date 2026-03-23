#!/usr/bin/env python3
"""Archive a full snapshot of all Shetland station prices as JSON.

Run alongside fetch_prices.py to keep both the database and raw JSON archives.
The JSON snapshots are useful for auditing and can be replayed into the DB.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

for line in (Path(__file__).parent / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from api_client import FuelFinderClient
from config import SHETLAND_POSTCODE_PREFIX

ARCHIVE_DIR = Path(__file__).parent / "archive"
ARCHIVE_DIR.mkdir(exist_ok=True)


def main():
    client = FuelFinderClient()

    # Fetch all stations, filter to Shetland
    all_stations = client.get_all_stations()
    shetland = [
        s for s in all_stations
        if s.get("location", {}).get("postcode", "").upper().startswith(SHETLAND_POSTCODE_PREFIX)
    ]
    shetland_ids = {s["node_id"] for s in shetland}

    # Fetch all prices
    all_prices = client.get_all_fuel_prices()

    # Build snapshot
    now = datetime.now(timezone.utc)
    snapshot = {
        "timestamp": now.isoformat(),
        "station_count": len(shetland),
        "stations": {},
    }

    for s in shetland:
        nid = s["node_id"]
        fuels = all_prices.get(nid, [])
        snapshot["stations"][nid] = {
            "name": s.get("trading_name", ""),
            "brand": s.get("brand_name", ""),
            "postcode": s.get("location", {}).get("postcode", ""),
            "prices": fuels,
        }

    # Save as dated JSON
    filename = now.strftime("%Y-%m-%dT%H%M%SZ") + ".json"
    out_path = ARCHIVE_DIR / filename
    out_path.write_text(json.dumps(snapshot, indent=2))
    print(f"Archived {len(shetland)} stations to {out_path}")


if __name__ == "__main__":
    main()
