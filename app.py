#!/usr/bin/env python3
"""Web dashboard for Shetland fuel price tracking."""
import json
import os
from pathlib import Path

from flask import Flask, render_template_string

from db import get_conn, init_db

app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Shetland Fuel Prices</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }
        header {
            background: #1e293b;
            border-bottom: 1px solid #334155;
            padding: 1.5rem 2rem;
        }
        header h1 { font-size: 1.5rem; font-weight: 600; color: #f8fafc; }
        header p { color: #94a3b8; margin-top: 0.25rem; }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }

        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 0.75rem;
            padding: 1.25rem;
        }
        .card h3 { font-size: 0.875rem; color: #94a3b8; font-weight: 500; }
        .card .value { font-size: 1.75rem; font-weight: 700; color: #f8fafc; margin-top: 0.25rem; }
        .card .sub { font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }
        .card .premium { color: #f87171; font-weight: 600; }

        .chart-container {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 0.75rem;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        .chart-container h2 { font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; }

        table {
            width: 100%;
            border-collapse: collapse;
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 0.75rem;
            overflow: hidden;
        }
        th, td { padding: 0.75rem 1rem; text-align: left; }
        th {
            background: #0f172a;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #94a3b8;
            font-weight: 600;
        }
        td { border-top: 1px solid #1e293b; font-size: 0.9rem; }
        tr:nth-child(even) td { background: rgba(255,255,255,0.02); }

        .fuel-tag {
            display: inline-block;
            padding: 0.15rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .fuel-E10 { background: #065f46; color: #6ee7b7; }
        .fuel-B7_STANDARD { background: #1e3a5f; color: #7dd3fc; }
        .fuel-E5 { background: #713f12; color: #fde68a; }
        .fuel-SDV { background: #581c87; color: #d8b4fe; }
        .fuel-default { background: #334155; color: #e2e8f0; }

        .empty-state {
            text-align: center;
            padding: 4rem 2rem;
            color: #64748b;
        }
        .empty-state h2 { color: #94a3b8; margin-bottom: 1rem; }
        .empty-state code {
            background: #1e293b;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            display: inline-block;
            margin-top: 0.5rem;
        }
    </style>
</head>
<body>
    <header>
        <h1>Shetland Fuel Prices</h1>
        <p>Tracking fuel prices across Shetland filling stations — with UK national averages for context</p>
    </header>
    <div class="container">
    {% if not stations %}
        <div class="empty-state">
            <h2>No data yet</h2>
            <p>Run the price fetcher to start collecting data:</p>
            <code>python fetch_prices.py</code>
        </div>
    {% else %}
        <div class="cards">
            <div class="card">
                <h3>Stations Tracked</h3>
                <div class="value">{{ stations|length }}</div>
                <div class="sub">Shetland (ZE postcode)</div>
            </div>
            {% for fuel, stats in summary.items() %}
            <div class="card">
                <h3>{{ fuel }} — Shetland Avg</h3>
                <div class="value">{{ "%.1f"|format(stats.avg) }}p</div>
                <div class="sub">
                    {{ "%.1f"|format(stats.min) }}p – {{ "%.1f"|format(stats.max) }}p range
                    {% if stats.uk_avg %}
                    <br>UK avg: {{ "%.1f"|format(stats.uk_avg) }}p
                    (<span class="premium">+{{ "%.1f"|format(stats.avg - stats.uk_avg) }}p</span>)
                    {% endif %}
                </div>
            </div>
            {% endfor %}
            <div class="card">
                <h3>Price Records</h3>
                <div class="value">{{ total_records }}</div>
                <div class="sub">Since tracking began</div>
            </div>
        </div>

        <div class="chart-container">
            <h2>Shetland Price Tracking</h2>
            <div id="shetland-chart"></div>
        </div>

        <div class="chart-container" style="overflow-x: auto;">
            <h2>Latest Prices by Station</h2>
            <table>
                <thead>
                    <tr>
                        <th>Station</th>
                        <th>Brand</th>
                        <th>Postcode</th>
                        <th>Fuel</th>
                        <th>Price (p/litre)</th>
                        <th>vs UK Avg</th>
                        <th>Last Updated</th>
                    </tr>
                </thead>
                <tbody>
                {% for row in latest_prices %}
                    <tr>
                        <td>{{ row.name }}</td>
                        <td>{{ row.brand }}</td>
                        <td>{{ row.postcode }}</td>
                        <td><span class="fuel-tag fuel-{{ row.fuel_type if row.fuel_type in ['E10','B7_STANDARD','E5','SDV'] else 'default' }}">{{ row.fuel_type }}</span></td>
                        <td><strong>{{ "%.1f"|format(row.price_pence) }}</strong></td>
                        <td>
                            {% if row.fuel_type in uk_latest %}
                                {% set diff = row.price_pence - uk_latest[row.fuel_type] %}
                                <span class="premium">{{ "%+.1f"|format(diff) }}p</span>
                            {% else %}
                                —
                            {% endif %}
                        </td>
                        <td>{{ row.recorded_at[:10] }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        <div class="chart-container" style="overflow-x: auto;">
            <h2>Shetland Filling Stations</h2>
            <table>
                <thead>
                    <tr>
                        <th>Station</th>
                        <th>Brand</th>
                        <th>Postcode</th>
                        <th>Fuels Available</th>
                    </tr>
                </thead>
                <tbody>
                {% for s in station_fuels %}
                    <tr>
                        <td>{{ s.name }}</td>
                        <td>{{ s.brand }}</td>
                        <td>{{ s.postcode }}</td>
                        <td>
                            {% for ft in s.fuels %}
                            <span class="fuel-tag fuel-{{ ft if ft in ['E10','B7_STANDARD','E5','SDV'] else 'default' }}">{{ ft }}</span>
                            {% endfor %}
                        </td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>

    {% endif %}
    </div>

    {% if stations %}
    <script>
        // Shetland tracking chart
        const shetlandData = {{ shetland_chart_data|tojson }};
        const sTraces = [];
        const sColors = { 'E10': '#6ee7b7', 'B7_STANDARD': '#7dd3fc', 'E5': '#fde68a', 'SDV': '#d8b4fe' };
        for (const [key, series] of Object.entries(shetlandData)) {
            sTraces.push({
                x: series.x,
                y: series.y,
                name: 'Shetland ' + key,
                mode: 'lines+markers',
                line: { width: 2, color: sColors[key] || '#94a3b8' },
                marker: { size: 5 },
            });
        }
        // Overlay UK weekly averages for the same period (actual time series, not flat line)
        const ukOverlay = {{ uk_overlay|tojson }};
        const ukOverlayColors = { 'ULSP': '#6ee7b780', 'ULSD': '#7dd3fc80' };
        const ukOverlayLabels = { 'ULSP': 'UK Avg Petrol', 'ULSD': 'UK Avg Diesel' };
        for (const [key, series] of Object.entries(ukOverlay)) {
            sTraces.push({
                x: series.x,
                y: series.y,
                name: ukOverlayLabels[key] || key,
                mode: 'lines',
                line: { width: 1.5, dash: 'dash', color: ukOverlayColors[key] || '#94a3b880' },
            });
        }
        Plotly.newPlot('shetland-chart', sTraces, {
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            font: { color: '#94a3b8' },
            xaxis: { gridcolor: '#334155' },
            yaxis: { gridcolor: '#334155', title: 'Pence per litre' },
            legend: { orientation: 'h', y: -0.15 },
            margin: { t: 30, r: 20 },
            hovermode: 'x unified',
            shapes: [{
                type: 'line',
                x0: '2026-02-28', x1: '2026-02-28',
                y0: 0, y1: 1, yref: 'paper',
                line: { color: '#f87171', width: 2, dash: 'dot' },
            }],
            annotations: [{
                x: '2026-02-28', y: 1.05, yref: 'paper',
                text: 'Iran war begins (28 Feb)',
                showarrow: false,
                font: { color: '#f87171', size: 11 },
            }],
        }, { responsive: true });
    </script>
    {% endif %}
</body>
</html>
"""


@app.route("/")
def dashboard():
    init_db()
    conn = get_conn()

    stations = conn.execute("SELECT * FROM stations ORDER BY name").fetchall()

    # Latest price per station+fuel
    latest_prices = conn.execute("""
        SELECT s.name, s.brand, s.postcode, p.fuel_type, p.price_pence, p.recorded_at
        FROM prices p
        JOIN stations s ON s.node_id = p.node_id
        WHERE p.id IN (
            SELECT MAX(id) FROM prices GROUP BY node_id, fuel_type
        )
        ORDER BY s.name, p.fuel_type
    """).fetchall()

    # Latest UK averages (map Shetland fuel types to UK equivalents)
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

    # Summary stats
    summary = {}
    for row in latest_prices:
        ft = row["fuel_type"]
        if ft not in summary:
            summary[ft] = {"min": row["price_pence"], "max": row["price_pence"], "sum": 0, "count": 0, "uk_avg": uk_latest.get(ft)}
        summary[ft]["min"] = min(summary[ft]["min"], row["price_pence"])
        summary[ft]["max"] = max(summary[ft]["max"], row["price_pence"])
        summary[ft]["sum"] += row["price_pence"]
        summary[ft]["count"] += 1
    for ft in summary:
        summary[ft]["avg"] = summary[ft]["sum"] / summary[ft]["count"]

    total_records = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]

    # Station list with available fuels
    station_fuel_rows = conn.execute("""
        SELECT s.name, s.brand, s.postcode, p.fuel_type
        FROM stations s
        LEFT JOIN prices p ON p.node_id = s.node_id
        WHERE p.id IN (SELECT MAX(id) FROM prices GROUP BY node_id, fuel_type)
        GROUP BY s.node_id, p.fuel_type
        ORDER BY s.name, p.fuel_type
    """).fetchall()
    station_fuels_map = {}
    for row in station_fuel_rows:
        key = row["name"]
        if key not in station_fuels_map:
            station_fuels_map[key] = {"name": row["name"], "brand": row["brand"], "postcode": row["postcode"], "fuels": []}
        if row["fuel_type"]:
            station_fuels_map[key]["fuels"].append(row["fuel_type"])
    station_fuels = list(station_fuels_map.values())

    # Shetland chart data
    shetland_rows = conn.execute("""
        SELECT fuel_type, DATE(recorded_at) as day, AVG(price_pence) as avg_price
        FROM prices GROUP BY fuel_type, DATE(recorded_at) ORDER BY day
    """).fetchall()
    shetland_chart_data = {}
    for row in shetland_rows:
        key = row["fuel_type"]
        if key not in shetland_chart_data:
            shetland_chart_data[key] = {"x": [], "y": []}
        shetland_chart_data[key]["x"].append(row["day"])
        shetland_chart_data[key]["y"].append(round(row["avg_price"], 1))

    # UK national history chart data
    uk_rows = conn.execute("""
        SELECT fuel_type, date, price_pence FROM uk_weekly_prices ORDER BY date
    """).fetchall()
    uk_chart_data = {}
    for row in uk_rows:
        key = row["fuel_type"]
        if key not in uk_chart_data:
            uk_chart_data[key] = {"x": [], "y": []}
        uk_chart_data[key]["x"].append(row["date"])
        uk_chart_data[key]["y"].append(round(row["price_pence"], 1))

    # UK weekly data overlaid on Shetland chart (same date range)
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

    conn.close()

    return render_template_string(
        DASHBOARD_HTML,
        stations=stations,
        latest_prices=latest_prices,
        summary=summary,
        total_records=total_records,
        shetland_chart_data=shetland_chart_data,
        uk_chart_data=uk_chart_data,
        uk_latest=uk_latest,
        uk_overlay=uk_overlay,
        station_fuels=station_fuels,
    )


@app.route("/api/prices")
def api_prices():
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.name, s.postcode, p.fuel_type, p.price_pence, p.recorded_at
        FROM prices p JOIN stations s ON s.node_id = p.node_id
        ORDER BY p.recorded_at DESC LIMIT 500
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)
