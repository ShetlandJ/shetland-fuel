#!/usr/bin/env python3
"""Fetch current fuel prices for tracked regions and store them in the database.

Run this on a schedule (e.g. every 30 minutes) to build up price history.
"""
import os
import sys
from pathlib import Path

# Load .env
for line in (Path(__file__).parent / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from api_client import FuelFinderClient
from config import get_region, normalise_price
from db import get_conn, init_db


def classify_stations(stations):
    """Group stations by tracked region. Returns {region: [station, ...]}."""
    by_region = {}
    for s in stations:
        postcode = s.get("location", {}).get("postcode", "")
        region = get_region(postcode)
        if region:
            by_region.setdefault(region, []).append(s)
    return by_region


def upsert_stations(conn, stations, region):
    for s in stations:
        loc = s.get("location", {})
        conn.execute(
            """INSERT INTO stations (node_id, brand, name, address, postcode, latitude, longitude, region)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(node_id) DO UPDATE SET
                   brand=excluded.brand, name=excluded.name,
                   address=excluded.address, postcode=excluded.postcode,
                   latitude=excluded.latitude, longitude=excluded.longitude,
                   region=excluded.region
            """,
            (
                s["node_id"],
                s.get("brand_name", ""),
                s.get("trading_name", ""),
                ", ".join(filter(None, [loc.get("address_line_1", ""), loc.get("city", "")])),
                loc.get("postcode", ""),
                loc.get("latitude"),
                loc.get("longitude"),
                region,
            ),
        )
    conn.commit()


def store_prices(conn, node_ids, all_prices):
    count = 0
    for node_id in node_ids:
        fuels = all_prices.get(node_id, [])
        for fuel in fuels:
            price = fuel.get("price")
            if price is None:
                continue
            conn.execute(
                "INSERT INTO prices (node_id, fuel_type, price_pence, api_timestamp) VALUES (?, ?, ?, ?)",
                (node_id, fuel["fuel_type"], normalise_price(float(price)), fuel.get("price_last_updated", "")),
            )
            count += 1
    conn.commit()
    return count


def main():
    init_db()
    client = FuelFinderClient()

    print("Fetching stations...")
    all_stations = client.get_all_stations()
    print(f"  Total stations: {len(all_stations)}")

    by_region = classify_stations(all_stations)
    for region, stations in by_region.items():
        print(f"  {region.title()} stations: {len(stations)}")

    if not by_region:
        print("No tracked stations found.")
        sys.exit(0)

    conn = get_conn()
    all_node_ids = set()
    for region, stations in by_region.items():
        upsert_stations(conn, stations, region)
        all_node_ids.update(s["node_id"] for s in stations)

    print("Fetching fuel prices...")
    all_prices = client.get_all_fuel_prices()
    print(f"  Total stations with prices: {len(all_prices)}")

    count = store_prices(conn, all_node_ids, all_prices)
    print(f"  Stored {count} price records.")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
