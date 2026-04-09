#!/usr/bin/env python3
"""Web dashboard for Shetland & Orkney fuel price tracking."""
import json
import os
from pathlib import Path
from urllib.parse import quote

from flask import Flask, render_template_string

from config import REGIONS
from db import get_conn, init_db

app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Northern Isles Fuel Prices</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    {% set fuel_labels = {'E10': 'Petrol (E10)', 'E5': 'Premium Petrol (E5)', 'B7_STANDARD': 'Diesel (B7)', 'SDV': 'SDV'} %}
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

        .tabs {
            display: flex;
            gap: 0.5rem;
            margin-bottom: 2rem;
        }
        .tab-btn {
            background: #1e293b;
            color: #94a3b8;
            border: 1px solid #334155;
            padding: 0.6rem 1.25rem;
            border-radius: 0.5rem;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            transition: all 0.15s;
        }
        .tab-btn:hover { background: #334155; color: #e2e8f0; }
        .tab-btn.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        .cards {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
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

        .dl-btn {
            background: #334155; color: #e2e8f0; border: 1px solid #475569;
            padding: 0.4rem 0.8rem; border-radius: 0.375rem; cursor: pointer;
            font-size: 0.8rem; margin-left: 0.5rem;
        }
        .dl-btn:hover { background: #475569; }

        .empty-state {
            text-align: center;
            padding: 4rem 2rem;
            color: #64748b;
        }
        .station-link {
            color: #60a5fa;
            text-decoration: none;
            font-weight: 500;
        }
        .station-link:hover { text-decoration: underline; color: #93bbfc; }

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
        <h1>Northern Isles Fuel Prices</h1>
        <p>Tracking fuel prices across Shetland &amp; Orkney filling stations — with UK national averages for context</p>
    </header>
    <div class="container">
    {% if not has_data %}
        <div class="empty-state">
            <h2>No data yet</h2>
            <p>Run the price fetcher to start collecting data:</p>
            <code>python fetch_prices.py</code>
        </div>
    {% else %}
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('shetland', this)">Shetland</button>
            <button class="tab-btn" onclick="switchTab('orkney', this)">Orkney</button>
            <button class="tab-btn" onclick="switchTab('comparison', this)">Comparison</button>
        </div>

        {# ===== MACRO: region dashboard ===== #}
        {% macro region_tab(data, region_key, region_label, chart_id) %}
        {% if data.stations %}
        {% if data.price_windows.get('today') %}
        {% set today = data.price_windows['today'] %}
        <div class="cards">
            {% for fuel, stats in today.fuels.items() %}
            <div class="card">
                <h3>{{ fuel_labels.get(fuel, fuel) }} — Today</h3>
                <div class="value">{{ "%.1f"|format(stats.avg) }}p</div>
                <div class="sub">
                    {{ stats.n }} stations
                    {% if data.summary.get(fuel, {}).get('uk_avg') %}
                    <br>UK avg: {{ "%.1f"|format(data.summary[fuel].uk_avg) }}p
                    (<span class="premium">+{{ "%.1f"|format(stats.avg - data.summary[fuel].uk_avg) }}p</span>)
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
        <div class="cards">
            {% for fuel in today.fuels.keys() %}
            <div class="card">
                <h3>{{ fuel_labels.get(fuel, fuel) }} — Change</h3>
                <div class="sub" style="font-size: 0.95rem; line-height: 1.8;">
                    {% for wlabel, wkey in [("7d", "7d"), ("14d", "14d"), ("30d", "30d")] %}
                    {% if data.price_windows.get(wkey, {}).get('fuels', {}).get(fuel) %}
                    {% set prev = data.price_windows[wkey].fuels[fuel] %}
                    {% set diff = today.fuels[fuel].avg - prev.avg %}
                    <span style="display: inline-block; min-width: 3.5em;">{{ wlabel }}:</span>
                    <span class="{{ 'premium' if diff > 0 else '' }}" style="font-weight: 600;">{{ "%+.1f"|format(diff) }}p</span>
                    <span style="color: #64748b;">({{ "%.1f"|format(prev.avg) }}p → {{ "%.1f"|format(today.fuels[fuel].avg) }}p)</span><br>
                    {% endif %}
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if data.price_windows.get('today') and region_key == 'shetland' %}
        {% set today_excl = data.price_windows['today'].fuels_excl %}
        <div class="cards">
            {% for fuel, stats in today_excl.items() %}
            <div class="card">
                <h3>{{ fuel_labels.get(fuel, fuel) }} — Excl. Skerries</h3>
                <div class="value">{{ "%.1f"|format(stats.avg) }}p</div>
                <div class="sub">{{ stats.n }} stations
                    {% if fuel in data.price_windows['today'].fuels %} (all: {{ "%.1f"|format(data.price_windows['today'].fuels[fuel].avg) }}p){% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if data.conflict_change %}
        <div class="cards">
            {% for fuel, chg in data.conflict_change.items() %}
            <div class="card">
                <h3>{{ fuel_labels.get(fuel, fuel) }} — Since Iran Conflict</h3>
                <div class="value"><span class="premium">{{ "%+.1f"|format(chg.diff) }}p ({{ "%+.1f"|format(chg.pct) }}%)</span></div>
                <div class="sub">
                    {{ "%.1f"|format(chg.before) }}p → {{ "%.1f"|format(chg.after) }}p since 28 Feb
                    {% if chg.uk_diff is defined %}
                    <br>UK avg: {{ "%+.1f"|format(chg.uk_diff) }}p ({{ "%+.1f"|format(chg.uk_pct) }}%)
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="chart-container">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h2 style="margin-bottom: 0;">{{ region_label }} Price Tracking</h2>
                <div style="display: flex; align-items: center; gap: 1rem;">
                    {% if region_key == 'shetland' %}
                    <label style="display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; color: #94a3b8; cursor: pointer;">
                        <input type="checkbox" id="excl-skerries-{{ region_key }}" onchange="toggleSkerries('{{ region_key }}', '{{ chart_id }}', this.checked)">
                        Exclude Skerries
                    </label>
                    {% endif %}
                    <button class="dl-btn" onclick="downloadCSV('{{ region_key }}')">Download CSV</button>
                    <button class="dl-btn" onclick="downloadJSON('{{ region_key }}')">Download JSON</button>
                </div>
            </div>
            <div id="{{ chart_id }}"></div>
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
                {% for row in data.latest_prices %}
                    <tr>
                        <td><a href="station/{{ row.node_id }}{{ station_suffix }}" class="station-link">{{ row.name }}</a></td>
                        <td>{{ row.brand }}</td>
                        <td>{{ row.postcode }}</td>
                        <td><span class="fuel-tag fuel-{{ row.fuel_type if row.fuel_type in ['E10','B7_STANDARD','E5','SDV'] else 'default' }}">{{ fuel_labels.get(row.fuel_type, row.fuel_type) }}</span></td>
                        <td><strong>{{ "%.1f"|format(row.price_pence) }}</strong></td>
                        <td>
                            {% if row.fuel_type in uk_latest %}
                                {% set diff = row.price_pence - uk_latest[row.fuel_type] %}
                                <span class="premium">{{ "%+.1f"|format(diff) }}p</span>
                            {% else %}
                                —
                            {% endif %}
                        </td>
                        <td>{{ row.api_timestamp[:10] if row.api_timestamp else row.recorded_at[:10] }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        <div class="chart-container" style="overflow-x: auto;">
            <h2>{{ region_label }} Filling Stations</h2>
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
                {% for s in data.station_fuels %}
                    <tr>
                        <td><a href="station/{{ s.node_id }}{{ station_suffix }}" class="station-link">{{ s.name }}</a></td>
                        <td>{{ s.brand }}</td>
                        <td>{{ s.postcode }}</td>
                        <td>
                            {% for ft in s.fuels %}
                            <span class="fuel-tag fuel-{{ ft if ft in ['E10','B7_STANDARD','E5','SDV'] else 'default' }}">{{ fuel_labels.get(ft, ft) }}</span>
                            {% endfor %}
                        </td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <div class="empty-state">
            <h2>No {{ region_label }} data yet</h2>
            <p>{{ region_label }} station data will appear after the next data fetch.</p>
        </div>
        {% endif %}
        {% endmacro %}

        {# ===== TAB CONTENT ===== #}
        <div id="tab-shetland" class="tab-content active">
            {{ region_tab(regions.shetland, 'shetland', 'Shetland', 'shetland-chart') }}
        </div>
        <div id="tab-orkney" class="tab-content">
            {{ region_tab(regions.orkney, 'orkney', 'Orkney', 'orkney-chart') }}
        </div>
        <div id="tab-comparison" class="tab-content">
            <div class="cards">
                {% for fuel in comparison_fuels %}
                <div class="card">
                    <h3>{{ fuel_labels.get(fuel, fuel) }} — Comparison</h3>
                    <div class="value">
                        {% if fuel in regions.shetland.summary and fuel in regions.orkney.summary %}
                        {{ "%.1f"|format(regions.shetland.summary[fuel].avg) }}p vs {{ "%.1f"|format(regions.orkney.summary[fuel].avg) }}p
                        {% elif fuel in regions.shetland.summary %}
                        {{ "%.1f"|format(regions.shetland.summary[fuel].avg) }}p vs —
                        {% elif fuel in regions.orkney.summary %}
                        — vs {{ "%.1f"|format(regions.orkney.summary[fuel].avg) }}p
                        {% endif %}
                    </div>
                    <div class="sub">Shetland vs Orkney</div>
                </div>
                {% endfor %}
            </div>
            <div class="cards">
                {% for fuel in comparison_fuels %}
                {% if fuel in regions.shetland.summary_excl_outliers %}
                <div class="card">
                    <h3>{{ fuel_labels.get(fuel, fuel) }} — Excl. Skerries</h3>
                    <div class="value">
                        {% if fuel in regions.orkney.summary %}
                        {{ "%.1f"|format(regions.shetland.summary_excl_outliers[fuel].avg) }}p vs {{ "%.1f"|format(regions.orkney.summary[fuel].avg) }}p
                        {% else %}
                        {{ "%.1f"|format(regions.shetland.summary_excl_outliers[fuel].avg) }}p vs —
                        {% endif %}
                    </div>
                    <div class="sub">Shetland (excl. Skerries) vs Orkney</div>
                </div>
                {% endif %}
                {% endfor %}
            </div>
            <div class="chart-container">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <h2 style="margin-bottom: 0;">Shetland vs Orkney</h2>
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <label style="display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; color: #94a3b8; cursor: pointer;">
                            <input type="checkbox" id="excl-skerries-comparison" onchange="toggleComparisonSkerries(this.checked)">
                            Exclude Skerries
                        </label>
                        <button class="dl-btn" onclick="downloadCSV('comparison')">Download CSV</button>
                        <button class="dl-btn" onclick="downloadJSON('comparison')">Download JSON</button>
                    </div>
                </div>
                <div id="comparison-chart"></div>
            </div>
        </div>
    {% endif %}
    </div>

    {% if has_data %}
    <script>
        const fuelLabels = { 'E10': 'Petrol (E10)', 'E5': 'Premium Petrol (E5)', 'B7_STANDARD': 'Diesel (B7)', 'SDV': 'SDV' };
        const fuelColors = { 'E10': '#6ee7b7', 'B7_STANDARD': '#7dd3fc', 'E5': '#fde68a', 'SDV': '#d8b4fe' };
        const ukOverlayColors = { 'ULSP': '#6ee7b780', 'ULSD': '#7dd3fc80' };
        const ukOverlayLabels = { 'ULSP': 'UK Avg Petrol', 'ULSD': 'UK Avg Diesel' };

        const chartLayout = {
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
        };

        // Region chart data from server
        const regionData = {
            shetland: {{ regions.shetland.chart_data|tojson }},
            orkney: {{ regions.orkney.chart_data|tojson }},
        };
        const regionDataExcl = {
            shetland: {{ regions.shetland.chart_data_excl_outliers|tojson }},
            orkney: {{ regions.orkney.chart_data_excl_outliers|tojson }},
        };
        const regionChartIds = { shetland: 'shetland-chart', orkney: 'orkney-chart' };
        const ukOverlay = {{ uk_overlay|tojson }};

        function buildRegionTraces(data, label) {
            const traces = [];
            for (const [key, series] of Object.entries(data)) {
                traces.push({
                    x: series.x, y: series.y,
                    name: label + ' ' + (fuelLabels[key] || key),
                    mode: 'lines+markers',
                    line: { width: 2, color: fuelColors[key] || '#94a3b8' },
                    marker: { size: 5 },
                });
            }
            return traces;
        }

        function buildUkTraces() {
            const traces = [];
            for (const [key, series] of Object.entries(ukOverlay)) {
                traces.push({
                    x: series.x, y: series.y,
                    name: ukOverlayLabels[key] || key,
                    mode: 'lines',
                    line: { width: 1.5, dash: 'dash', color: ukOverlayColors[key] || '#94a3b880' },
                });
            }
            return traces;
        }

        const regionLabels = { shetland: 'Shetland', orkney: 'Orkney' };

        function renderRegionChart(regionKey, chartId, exclSkerries) {
            const data = exclSkerries ? regionDataExcl[regionKey] : regionData[regionKey];
            const label = regionLabels[regionKey];
            Plotly.newPlot(chartId,
                [...buildRegionTraces(data, label), ...buildUkTraces()],
                chartLayout, { responsive: true }
            );
        }

        function toggleSkerries(regionKey, chartId, excluded) {
            renderRegionChart(regionKey, chartId, excluded);
        }

        // Render Shetland chart
        renderRegionChart('shetland', 'shetland-chart', false);

        // Render Orkney chart
        renderRegionChart('orkney', 'orkney-chart', false);

        function buildCompTraces(exclSkerries) {
            const shetData = exclSkerries ? regionDataExcl.shetland : regionData.shetland;
            const orkData = regionData.orkney;
            const traces = [];
            const fuels = new Set([...Object.keys(shetData), ...Object.keys(orkData)]);
            for (const fuel of fuels) {
                const color = fuelColors[fuel] || '#94a3b8';
                const label = fuelLabels[fuel] || fuel;
                if (shetData[fuel]) {
                    traces.push({
                        x: shetData[fuel].x, y: shetData[fuel].y,
                        name: 'Shetland ' + label,
                        legendgroup: fuel,
                        mode: 'lines+markers',
                        line: { width: 2.5, color: color },
                        marker: { size: 5, symbol: 'circle' },
                    });
                }
                if (orkData[fuel]) {
                    traces.push({
                        x: orkData[fuel].x, y: orkData[fuel].y,
                        name: 'Orkney ' + label,
                        legendgroup: fuel,
                        mode: 'lines+markers',
                        line: { width: 2.5, dash: 'dash', color: color },
                        marker: { size: 5, symbol: 'diamond' },
                    });
                }
            }
            return traces;
        }

        function toggleComparisonSkerries(excluded) {
            Plotly.newPlot('comparison-chart', buildCompTraces(excluded), chartLayout, { responsive: true });
        }

        Plotly.newPlot('comparison-chart', buildCompTraces(false), chartLayout, { responsive: true });

        // Tab switching
        function switchTab(tab, btn) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById('tab-' + tab).classList.add('active');
            btn.classList.add('active');
            // Plotly needs resize when shown from hidden
            Plotly.Plots.resize(tab + '-chart');
        }

        // Download helpers
        function getActiveData(region) {
            if (region === 'comparison') {
                return { shetland: regionData.shetland, orkney: regionData.orkney, uk_weekly: ukOverlay };
            }
            return { [region]: regionData[region], uk_weekly: ukOverlay };
        }

        function downloadJSON(region) {
            const data = getActiveData(region);
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = region + '_fuel_prices.json';
            a.click();
        }

        function downloadCSV(region) {
            const allDates = new Set();
            const series = {};
            const sources = region === 'comparison'
                ? [['Shetland', regionData.shetland], ['Orkney', regionData.orkney]]
                : [[region.charAt(0).toUpperCase() + region.slice(1), regionData[region]]];
            for (const [label, data] of sources) {
                for (const [key, s] of Object.entries(data)) {
                    series[label + ' ' + (fuelLabels[key] || key)] = Object.fromEntries(s.x.map((d, i) => [d, s.y[i]]));
                    s.x.forEach(d => allDates.add(d));
                }
            }
            for (const [key, s] of Object.entries(ukOverlay)) {
                series[ukOverlayLabels[key] || key] = Object.fromEntries(s.x.map((d, i) => [d, s.y[i]]));
                s.x.forEach(d => allDates.add(d));
            }
            const dates = [...allDates].sort();
            const cols = Object.keys(series);
            let csv = 'Date,' + cols.join(',') + String.fromCharCode(10);
            for (const d of dates) {
                csv += d + ',' + cols.map(c => series[c][d] ?? '').join(',') + String.fromCharCode(10);
            }
            const blob = new Blob([csv], { type: 'text/csv' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = region + '_fuel_prices.csv';
            a.click();
        }
    </script>
    {% endif %}
</body>
</html>
"""

STATION_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ station.name }} — Northern Isles Fuel Prices</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    {% set fuel_labels = {'E10': 'Petrol (E10)', 'E5': 'Premium Petrol (E5)', 'B7_STANDARD': 'Diesel (B7)', 'SDV': 'SDV'} %}
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

        .back-link {
            color: #60a5fa;
            text-decoration: none;
            font-size: 0.9rem;
            display: inline-block;
            margin-bottom: 1.5rem;
        }
        .back-link:hover { text-decoration: underline; }

        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
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

        .change-up { color: #f87171; }
        .change-down { color: #6ee7b7; }
        .change-none { color: #94a3b8; }
    </style>
</head>
<body>
    <header>
        <h1>{{ station.name }}</h1>
        <p>{{ station.brand }} — {{ station.address }}, {{ station.postcode }}</p>
    </header>
    <div class="container">
        <a href="{{ base_path }}" class="back-link">&#8592; Back to dashboard</a>

        <div class="cards">
            {% for fuel in latest_prices %}
            <div class="card">
                <h3>{{ fuel_labels.get(fuel.fuel_type, fuel.fuel_type) }}</h3>
                <div class="value">{{ "%.1f"|format(fuel.price_pence) }}p</div>
                <div class="sub">Last updated {{ fuel.api_timestamp[:10] if fuel.api_timestamp else fuel.recorded_at[:10] }}</div>
            </div>
            {% endfor %}
        </div>

        <div class="chart-container">
            <h2>Price History</h2>
            <div id="station-chart"></div>
        </div>

        <div class="chart-container" style="overflow-x: auto;">
            <h2>All Recorded Prices</h2>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Fuel</th>
                        <th>Price (p/litre)</th>
                        <th>Change</th>
                    </tr>
                </thead>
                <tbody>
                {% for row in price_history %}
                    <tr>
                        <td>{{ row.date }}</td>
                        <td><span class="fuel-tag fuel-{{ row.fuel_type if row.fuel_type in ['E10','B7_STANDARD','E5','SDV'] else 'default' }}">{{ fuel_labels.get(row.fuel_type, row.fuel_type) }}</span></td>
                        <td><strong>{{ "%.1f"|format(row.price_pence) }}</strong></td>
                        <td>
                            {% if row.change is not none %}
                                <span class="{{ 'change-up' if row.change > 0 else ('change-down' if row.change < 0 else 'change-none') }}">
                                    {{ "%+.1f"|format(row.change) }}p
                                </span>
                            {% else %}
                                —
                            {% endif %}
                        </td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const fuelLabels = { 'E10': 'Petrol (E10)', 'E5': 'Premium Petrol (E5)', 'B7_STANDARD': 'Diesel (B7)', 'SDV': 'SDV' };
        const fuelColors = { 'E10': '#6ee7b7', 'B7_STANDARD': '#7dd3fc', 'E5': '#fde68a', 'SDV': '#d8b4fe' };

        const chartData = {{ chart_data|tojson }};
        const traces = [];
        for (const [key, series] of Object.entries(chartData)) {
            traces.push({
                x: series.x, y: series.y,
                name: fuelLabels[key] || key,
                mode: 'lines+markers',
                line: { width: 2, color: fuelColors[key] || '#94a3b8' },
                marker: { size: 5 },
            });
        }

        Plotly.newPlot('station-chart', traces, {
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
</body>
</html>
"""


def get_region_data(conn, region, uk_latest):
    """Query all dashboard data for a single region."""
    stations = conn.execute(
        "SELECT * FROM stations WHERE region = ? ORDER BY name", (region,)
    ).fetchall()

    latest_prices = conn.execute("""
        SELECT s.node_id, s.name, s.brand, s.postcode, p.fuel_type, p.price_pence, p.recorded_at, p.api_timestamp
        FROM prices p
        JOIN stations s ON s.node_id = p.node_id
        WHERE s.region = ? AND p.id = (
            SELECT p2.id FROM prices p2
            WHERE p2.node_id = p.node_id AND p2.fuel_type = p.fuel_type
            ORDER BY p2.recorded_at DESC
            LIMIT 1
        )
        ORDER BY s.name, p.fuel_type
    """, (region,)).fetchall()

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

    # Time-windowed averages (today vs 7d/14d/30d ago)
    from datetime import datetime, timedelta
    outlier_names = {"Skerries Co-operative Society"}

    max_date_row = conn.execute("""
        SELECT MAX(DATE(p.recorded_at)) FROM prices p
        JOIN stations s ON s.node_id = p.node_id WHERE s.region = ?
    """, (region,)).fetchone()
    max_date = max_date_row[0] if max_date_row else None

    price_windows = {}
    if max_date:
        for label, days_ago in [("today", 0), ("7d", 7), ("14d", 14), ("30d", 30)]:
            target = (datetime.strptime(max_date, "%Y-%m-%d") - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            row = conn.execute("""
                SELECT DATE(p.recorded_at) as day FROM prices p
                JOIN stations s ON s.node_id = p.node_id
                WHERE s.region = ? AND DATE(p.recorded_at) <= ?
                ORDER BY DATE(p.recorded_at) DESC LIMIT 1
            """, (region, target)).fetchone()
            if not row:
                continue
            actual_date = row["day"]
            avgs = conn.execute("""
                SELECT p.fuel_type, AVG(p.price_pence) as avg_price, COUNT(*) as n
                FROM prices p JOIN stations s ON s.node_id = p.node_id
                WHERE s.region = ? AND DATE(p.recorded_at) = ?
                GROUP BY p.fuel_type
            """, (region, actual_date)).fetchall()
            avgs_excl = conn.execute("""
                SELECT p.fuel_type, AVG(p.price_pence) as avg_price, COUNT(*) as n
                FROM prices p JOIN stations s ON s.node_id = p.node_id
                WHERE s.region = ? AND DATE(p.recorded_at) = ? AND s.name NOT IN ({})
                GROUP BY p.fuel_type
            """.format(",".join("?" for _ in outlier_names)), (region, actual_date, *outlier_names)).fetchall()
            price_windows[label] = {
                "date": actual_date,
                "fuels": {r["fuel_type"]: {"avg": r["avg_price"], "n": r["n"]} for r in avgs},
                "fuels_excl": {r["fuel_type"]: {"avg": r["avg_price"], "n": r["n"]} for r in avgs_excl},
            }

    # Conflict change
    conflict_date = "2026-02-28"
    pre_conflict = conn.execute("""
        SELECT p.fuel_type, AVG(p.price_pence) as avg_price
        FROM prices p JOIN stations s ON s.node_id = p.node_id
        WHERE s.region = ? AND DATE(p.recorded_at) = (
            SELECT MAX(DATE(p2.recorded_at)) FROM prices p2
            JOIN stations s2 ON s2.node_id = p2.node_id
            WHERE s2.region = ? AND DATE(p2.recorded_at) <= ?
        )
        GROUP BY p.fuel_type
    """, (region, region, conflict_date)).fetchall()
    post_conflict = conn.execute("""
        SELECT p.fuel_type, AVG(p.price_pence) as avg_price
        FROM prices p JOIN stations s ON s.node_id = p.node_id
        WHERE s.region = ? AND DATE(p.recorded_at) = (
            SELECT MAX(DATE(p2.recorded_at)) FROM prices p2
            JOIN stations s2 ON s2.node_id = p2.node_id
            WHERE s2.region = ?
        )
        GROUP BY p.fuel_type
    """, (region, region)).fetchall()

    pre_map = {r["fuel_type"]: r["avg_price"] for r in pre_conflict}
    post_map = {r["fuel_type"]: r["avg_price"] for r in post_conflict}

    uk_fuel_map = {"E10": "ULSP", "E5": "ULSP", "B7_STANDARD": "ULSD"}
    uk_pre = conn.execute("""
        SELECT fuel_type, price_pence FROM uk_weekly_prices
        WHERE date = (SELECT MAX(date) FROM uk_weekly_prices WHERE date <= ?)
    """, (conflict_date,)).fetchall()
    uk_post = conn.execute("""
        SELECT fuel_type, price_pence FROM uk_weekly_prices
        WHERE date = (SELECT MAX(date) FROM uk_weekly_prices)
    """).fetchall()
    uk_pre_map = {r["fuel_type"]: r["price_pence"] for r in uk_pre}
    uk_post_map = {r["fuel_type"]: r["price_pence"] for r in uk_post}

    conflict_change = {}
    for ft in pre_map:
        if ft in post_map:
            before, after = pre_map[ft], post_map[ft]
            entry = {"before": before, "after": after, "diff": after - before, "pct": ((after - before) / before) * 100}
            uk_ft = uk_fuel_map.get(ft)
            if uk_ft and uk_ft in uk_pre_map and uk_ft in uk_post_map:
                uk_before, uk_after = uk_pre_map[uk_ft], uk_post_map[uk_ft]
                entry["uk_diff"] = uk_after - uk_before
                entry["uk_pct"] = ((uk_after - uk_before) / uk_before) * 100
            conflict_change[ft] = entry

    # Station fuels
    station_fuel_rows = conn.execute("""
        SELECT s.node_id, s.name, s.brand, s.postcode, p.fuel_type
        FROM stations s
        LEFT JOIN prices p ON p.node_id = s.node_id
        WHERE s.region = ? AND p.id = (
            SELECT p2.id FROM prices p2
            WHERE p2.node_id = p.node_id AND p2.fuel_type = p.fuel_type
            ORDER BY p2.recorded_at DESC
            LIMIT 1
        )
        GROUP BY s.node_id, p.fuel_type
        ORDER BY s.name, p.fuel_type
    """, (region,)).fetchall()
    station_fuels_map = {}
    for row in station_fuel_rows:
        key = row["name"]
        if key not in station_fuels_map:
            station_fuels_map[key] = {"node_id": row["node_id"], "name": row["name"], "brand": row["brand"], "postcode": row["postcode"], "fuels": []}
        if row["fuel_type"]:
            station_fuels_map[key]["fuels"].append(row["fuel_type"])
    station_fuels = list(station_fuels_map.values())

    # Chart data
    chart_rows = conn.execute("""
        SELECT p.fuel_type, DATE(p.recorded_at) as day, AVG(p.price_pence) as avg_price
        FROM prices p JOIN stations s ON s.node_id = p.node_id
        WHERE s.region = ?
        GROUP BY p.fuel_type, DATE(p.recorded_at) ORDER BY day
    """, (region,)).fetchall()
    chart_data = {}
    for row in chart_rows:
        key = row["fuel_type"]
        if key not in chart_data:
            chart_data[key] = {"x": [], "y": []}
        chart_data[key]["x"].append(row["day"])
        chart_data[key]["y"].append(round(row["avg_price"], 1))

    # Chart data excluding outliers (Skerries)
    chart_rows_excl = conn.execute("""
        SELECT p.fuel_type, DATE(p.recorded_at) as day, AVG(p.price_pence) as avg_price
        FROM prices p JOIN stations s ON s.node_id = p.node_id
        WHERE s.region = ? AND s.name NOT IN ({})
        GROUP BY p.fuel_type, DATE(p.recorded_at) ORDER BY day
    """.format(",".join("?" for _ in outlier_names)), (region, *outlier_names)).fetchall()
    chart_data_excl_outliers = {}
    for row in chart_rows_excl:
        key = row["fuel_type"]
        if key not in chart_data_excl_outliers:
            chart_data_excl_outliers[key] = {"x": [], "y": []}
        chart_data_excl_outliers[key]["x"].append(row["day"])
        chart_data_excl_outliers[key]["y"].append(round(row["avg_price"], 1))

    return {
        "stations": stations,
        "latest_prices": latest_prices,
        "summary": summary,
        "price_windows": price_windows,
        "conflict_change": conflict_change,
        "station_fuels": station_fuels,
        "chart_data": chart_data,
        "chart_data_excl_outliers": chart_data_excl_outliers,
    }


@app.route("/")
def dashboard(station_suffix=""):
    init_db()
    conn = get_conn()

    # UK latest averages (shared across regions)
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

    # Per-region data
    regions_data = {}
    for region_key in REGIONS:
        regions_data[region_key] = get_region_data(conn, region_key, uk_latest)

    has_data = any(r["stations"] for r in regions_data.values())

    # Comparison fuel types (union of both regions)
    comparison_fuels = sorted(set(
        list(regions_data.get("shetland", {}).get("summary", {}).keys()) +
        list(regions_data.get("orkney", {}).get("summary", {}).keys())
    ))

    # UK overlay (shared)
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

    # Wrap in a namespace-like dict for template access
    class RegionNS:
        def __init__(self, data):
            self.__dict__.update(data)

    regions_ns = type('Regions', (), {k: RegionNS(v) for k, v in regions_data.items()})()

    return render_template_string(
        DASHBOARD_HTML,
        has_data=has_data,
        regions=regions_ns,
        comparison_fuels=comparison_fuels,
        uk_latest=uk_latest,
        uk_overlay=uk_overlay,
        station_suffix=station_suffix,
    )


@app.route("/station/<node_id>")
def station_view(node_id, base_path=None):
    init_db()
    conn = get_conn()

    station = conn.execute(
        "SELECT * FROM stations WHERE node_id = ?", (node_id,)
    ).fetchone()
    if not station:
        conn.close()
        return "Station not found", 404

    # Latest price per fuel type
    latest_prices = conn.execute("""
        SELECT fuel_type, price_pence, recorded_at, api_timestamp
        FROM prices WHERE node_id = ? AND id IN (
            SELECT MAX(id) FROM prices WHERE node_id = ?
            GROUP BY fuel_type
        )
        ORDER BY fuel_type
    """, (node_id, node_id)).fetchall()

    # Daily prices for chart (one point per day per fuel)
    chart_rows = conn.execute("""
        SELECT fuel_type, DATE(recorded_at) as day, AVG(price_pence) as avg_price
        FROM prices WHERE node_id = ?
        GROUP BY fuel_type, DATE(recorded_at) ORDER BY day
    """, (node_id,)).fetchall()
    chart_data = {}
    for row in chart_rows:
        key = row["fuel_type"]
        if key not in chart_data:
            chart_data[key] = {"x": [], "y": []}
        chart_data[key]["x"].append(row["day"])
        chart_data[key]["y"].append(round(row["avg_price"], 1))

    # Full price history (one row per date per fuel, with day-over-day change)
    history_rows = conn.execute("""
        SELECT fuel_type, DATE(recorded_at) as date, AVG(price_pence) as price_pence
        FROM prices WHERE node_id = ?
        GROUP BY fuel_type, DATE(recorded_at)
        ORDER BY DATE(recorded_at) DESC, fuel_type
    """, (node_id,)).fetchall()

    # Compute day-over-day changes
    prev_price = {}
    history_with_change = []
    # Process in chronological order to compute changes, then reverse for display
    sorted_rows = list(reversed(history_rows))
    for row in sorted_rows:
        key = row["fuel_type"]
        change = None
        if key in prev_price:
            change = round(row["price_pence"] - prev_price[key], 1)
        prev_price[key] = row["price_pence"]
        history_with_change.append({
            "date": row["date"],
            "fuel_type": row["fuel_type"],
            "price_pence": row["price_pence"],
            "change": change,
        })
    history_with_change.reverse()

    conn.close()

    if base_path is None:
        base_path = "/"

    return render_template_string(
        STATION_HTML,
        station=station,
        latest_prices=latest_prices,
        chart_data=chart_data,
        price_history=history_with_change,
        base_path=base_path,
    )


@app.route("/api/prices")
def api_prices():
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.name, s.postcode, s.region, p.fuel_type, p.price_pence, p.recorded_at
        FROM prices p JOIN stations s ON s.node_id = p.node_id
        ORDER BY p.recorded_at DESC LIMIT 500
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)
