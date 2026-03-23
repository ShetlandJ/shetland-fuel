#!/usr/bin/env python3
"""Fetch current Shetland fuel prices and store them in the database.

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
from config import SHETLAND_POSTCODE_PREFIX
from db import get_conn, init_db


def find_shetland_stations(stations):
    shetland = []
    for s in stations:
        postcode = s.get("location", {}).get("postcode", "")
        if postcode.upper().startswith(SHETLAND_POSTCODE_PREFIX):
            shetland.append(s)
    return shetland


def upsert_stations(conn, stations):
    for s in stations:
        loc = s.get("location", {})
        conn.execute(
            """INSERT INTO stations (node_id, brand, name, address, postcode, latitude, longitude)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(node_id) DO UPDATE SET
                   brand=excluded.brand, name=excluded.name,
                   address=excluded.address, postcode=excluded.postcode,
                   latitude=excluded.latitude, longitude=excluded.longitude
            """,
            (
                s["node_id"],
                s.get("brand_name", ""),
                s.get("trading_name", ""),
                ", ".join(filter(None, [loc.get("address_line_1", ""), loc.get("city", "")])),
                loc.get("postcode", ""),
                loc.get("latitude"),
                loc.get("longitude"),
            ),
        )
    conn.commit()


def store_prices(conn, shetland_ids, all_prices):
    count = 0
    for node_id in shetland_ids:
        fuels = all_prices.get(node_id, [])
        for fuel in fuels:
            price = fuel.get("price")
            if price is None:
                continue
            conn.execute(
                "INSERT INTO prices (node_id, fuel_type, price_pence, api_timestamp) VALUES (?, ?, ?, ?)",
                (node_id, fuel["fuel_type"], float(price), fuel.get("price_last_updated", "")),
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

    shetland = find_shetland_stations(all_stations)
    print(f"  Shetland stations: {len(shetland)}")

    if not shetland:
        print("No Shetland stations found.")
        sys.exit(0)

    conn = get_conn()
    upsert_stations(conn, shetland)

    shetland_ids = {s["node_id"] for s in shetland}

    print("Fetching fuel prices...")
    all_prices = client.get_all_fuel_prices()
    print(f"  Total stations with prices: {len(all_prices)}")

    count = store_prices(conn, shetland_ids, all_prices)
    print(f"  Stored {count} Shetland price records.")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
