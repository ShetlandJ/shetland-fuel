#!/usr/bin/env python3
"""Build a static HTML version of the dashboard for GitHub Pages."""
import os

from app import app, dashboard, station_view
from db import get_conn, init_db

init_db()

with app.test_request_context():
    html = dashboard(station_suffix=".html")

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
