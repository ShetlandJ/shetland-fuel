#!/usr/bin/env python3
"""Build a static HTML version of the dashboard for GitHub Pages."""
import os

from flask import render_template_string

from app import app, DASHBOARD_HTML, station_view
from db import get_conn, init_db
from config import REGIONS

init_db()

# Build main dashboard with .html suffix for static links
with app.test_request_context():
    conn = get_conn()

    uk_latest_row = conn.execute("""
        SELECT fuel_type, price_pence FROM uk_weekly_prices
        WHERE date = (SELECT MAX(date) FROM uk_weekly_prices)
    """).fetchall()
    uk_latest = {}
    for row in uk_latest_row:
        if row["fuel_type"] == "ULSP":
            uk_latest["E10"] = row["price_pence"]
            uk_latest["E5"] = row["price_pence"]
        elif row["fuel_type"] == "ULSD":
            uk_latest["B7_STANDARD"] = row["price_pence"]

    from app import get_region_data
    regions_data = {}
    for region_key in REGIONS:
        regions_data[region_key] = get_region_data(conn, region_key, uk_latest)

    has_data = any(r["stations"] for r in regions_data.values())

    comparison_fuels = sorted(set(
        list(regions_data.get("shetland", {}).get("summary", {}).keys()) +
        list(regions_data.get("orkney", {}).get("summary", {}).keys())
    ))

    min_date = conn.execute("SELECT MIN(DATE(recorded_at)) FROM prices").fetchone()[0] or "2026-01-01"
    uk_overlay_rows = conn.execute("""
        SELECT fuel_type, date, price_pence FROM uk_weekly_prices
        WHERE date >= ? ORDER BY date
    """, (min_date,)).fetchall()
    uk_overlay = {}
    for row in uk_overlay_rows:
        key = row["fuel_type"]
        if key not in uk_overlay:
            uk_overlay[key] = {"x": [], "y": []}
        uk_overlay[key]["x"].append(row["date"])
        uk_overlay[key]["y"].append(round(row["price_pence"], 1))

    class RegionNS:
        def __init__(self, data):
            self.__dict__.update(data)

    regions_ns = type('Regions', (), {k: RegionNS(v) for k, v in regions_data.items()})()

    html = render_template_string(
        DASHBOARD_HTML,
        has_data=has_data,
        regions=regions_ns,
        comparison_fuels=comparison_fuels,
        uk_latest=uk_latest,
        uk_overlay=uk_overlay,
        station_suffix=".html",
    )

    conn.close()

with open("docs/index.html", "w") as f:
    f.write(html)

print("Built docs/index.html")

# Build individual station pages
conn = get_conn()
stations = conn.execute("SELECT node_id, name FROM stations ORDER BY name").fetchall()
conn.close()

os.makedirs("docs/station", exist_ok=True)

for s in stations:
    node_id = s["node_id"]
    with app.test_request_context(f"/station/{node_id}"):
        html = station_view(node_id, base_path="../index.html")
    path = f"docs/station/{node_id}.html"
    with open(path, "w") as f:
        f.write(html)

print(f"Built {len(stations)} station pages in docs/station/")
