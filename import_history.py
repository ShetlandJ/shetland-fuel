#!/usr/bin/env python3
"""Import historical prices from the fuelfinder-archive git repo."""
import json
from datetime import datetime

from config import get_region, normalise_price
from db import get_conn, init_db


def main():
    init_db()
    conn = get_conn()

    with open("shetland_history_raw.json") as f:
        records = json.load(f)

    # Deduplicate: keep one record per (date, node_id, fuel_type)
    seen = set()
    count = 0

    for r in records:
        date = r["commit_date"][:10]  # YYYY-MM-DD
        node_id = r["node_id"]
        name = r["name"]
        brand = r["brand"]
        postcode = r["postcode"]
        region = get_region(postcode) or "unknown"

        # Upsert station
        conn.execute(
            """INSERT INTO stations (node_id, brand, name, address, postcode, region)
               VALUES (?, ?, ?, '', ?, ?)
               ON CONFLICT(node_id) DO UPDATE SET
                   brand=excluded.brand, name=excluded.name, postcode=excluded.postcode,
                   region=excluded.region""",
            (node_id, brand, name, postcode, region),
        )

        # Insert prices for each fuel type
        for fuel_code, fuel_type in [("E5", "E5"), ("E10", "E10"), ("B7S", "B7_STANDARD")]:
            val = r.get(fuel_code, "")
            if not val:
                continue
            price = normalise_price(float(val))
            # Skip obviously bad data (early commits had prices in pounds not pence)
            if price < 10:
                continue

            key = (date, node_id, fuel_type)
            if key in seen:
                continue
            seen.add(key)

            recorded_at = f"{date}T12:00:00Z"
            # Skip if we already have a record for this station/fuel/date
            existing = conn.execute(
                "SELECT 1 FROM prices WHERE node_id = ? AND fuel_type = ? AND DATE(recorded_at) = ?",
                (node_id, fuel_type, date),
            ).fetchone()
            if existing:
                continue

            conn.execute(
                "INSERT INTO prices (node_id, fuel_type, price_pence, recorded_at, api_timestamp) VALUES (?, ?, ?, ?, ?)",
                (node_id, fuel_type, price, recorded_at, r.get("update_ts", "")),
            )
            count += 1

    conn.commit()
    conn.close()
    print(f"Imported {count} historical price records.")


if __name__ == "__main__":
    main()
