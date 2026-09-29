#!/usr/bin/env python3
"""Import GOV.UK weekly road fuel prices into the database."""
import csv
import io
from datetime import datetime

import requests

from db import get_conn, init_db

# The recent CSV is re-uploaded weekly under a new URL, so resolve it from the
# GOV.UK content API rather than hardcoding it.
CONTENT_API = "https://www.gov.uk/api/content/government/statistics/weekly-road-fuel-prices"
HISTORIC_URL = "https://assets.publishing.service.gov.uk/media/68a3326b32d2c63f869343a3/weekly_road_fuel_prices_2003_to_2017.csv"


def recent_csv_url():
    resp = requests.get(CONTENT_API)
    resp.raise_for_status()
    for att in resp.json()["details"]["attachments"]:
        title = att.get("title", "")
        if "CSV" in title and "2018" in title:
            return att["url"]
    raise RuntimeError("Recent weekly fuel prices CSV not found on GOV.UK")


def import_csv(conn, url):
    print(f"Downloading {url.split('/')[-1]}...")
    resp = requests.get(url)
    resp.raise_for_status()

    text = resp.text.lstrip("\ufeff")  # strip BOM
    reader = csv.reader(io.StringIO(text))
    header = next(reader)

    count = 0
    for row in reader:
        if not row or not row[0].strip():
            continue
        date_str = row[0].strip()
        try:
            date = datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            continue

        petrol = row[1].strip() if len(row) > 1 and row[1].strip() else None
        diesel = row[2].strip() if len(row) > 2 and row[2].strip() else None
        petrol_duty = row[3].strip() if len(row) > 3 and row[3].strip() else None
        diesel_duty = row[4].strip() if len(row) > 4 and row[4].strip() else None
        petrol_vat = row[5].strip() if len(row) > 5 and row[5].strip() else None
        diesel_vat = row[6].strip() if len(row) > 6 and row[6].strip() else None

        if petrol:
            conn.execute(
                "INSERT OR REPLACE INTO uk_weekly_prices (date, fuel_type, price_pence, duty_pence, vat_pct) VALUES (?, ?, ?, ?, ?)",
                (date, "ULSP", float(petrol), float(petrol_duty) if petrol_duty else None, float(petrol_vat) if petrol_vat else None),
            )
            count += 1
        if diesel:
            conn.execute(
                "INSERT OR REPLACE INTO uk_weekly_prices (date, fuel_type, price_pence, duty_pence, vat_pct) VALUES (?, ?, ?, ?, ?)",
                (date, "ULSD", float(diesel), float(diesel_duty) if diesel_duty else None, float(diesel_vat) if diesel_vat else None),
            )
            count += 1

    conn.commit()
    return count


def main():
    init_db()
    conn = get_conn()
    total = 0
    total += import_csv(conn, HISTORIC_URL)
    total += import_csv(conn, recent_csv_url())
    conn.close()
    print(f"Imported {total} records.")


if __name__ == "__main__":
    main()
