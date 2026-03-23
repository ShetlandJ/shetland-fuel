#!/usr/bin/env python3
"""Build a static HTML version of the dashboard for GitHub Pages."""
from app import app, dashboard

with app.test_request_context():
    html = dashboard()

with open("docs/index.html", "w") as f:
    f.write(html)

print("Built docs/index.html")
