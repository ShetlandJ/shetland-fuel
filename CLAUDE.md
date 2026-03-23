# Shetland Fuel Price Tracker

## What this is
A Python app that tracks fuel prices across all 12 Shetland filling stations using the UK Government's Fuel Finder API. Stores price history in SQLite and serves a Flask dashboard with Plotly charts.

## Architecture
- **Flask app** (`app.py`) — dashboard on port 5001, single-page with Plotly charts and station table
- **API client** (`api_client.py`) — OAuth2 client-credentials flow against `https://www.fuel-finder.service.gov.uk`
- **SQLite database** (`prices.db`) — tables: `stations`, `prices`, `uk_weekly_prices`
- **No frontend build step** — HTML is a template string inside `app.py`, Plotly loaded from CDN

## Key files
| File | Purpose |
|---|---|
| `app.py` | Flask dashboard (port 5001) |
| `api_client.py` | Fuel Finder API client with OAuth token management |
| `fetch_prices.py` | Fetches current Shetland prices → SQLite. Run on a schedule |
| `archive_snapshot.py` | Saves full JSON snapshot to `archive/` directory |
| `import_history.py` | One-time import from `matthewgall/fuelfinder-archive` git history |
| `import_uk_weekly.py` | Imports GOV.UK weekly national fuel price averages (2003–2026) |
| `config.py` | Loads `.env`, sets API credentials and DB path |
| `db.py` | SQLite schema and connection helper |

## API details
- **Base URL:** `https://www.fuel-finder.service.gov.uk`
- **Auth:** `POST /api/v1/oauth/generate_access_token` with `client_id` + `client_secret` → returns `{"data": {"access_token": "...", "refresh_token": "..."}}`
- **Stations:** `GET /api/v1/pfs?batch-number=N` — returns list of 500 stations per batch, 404 when exhausted
- **Prices:** `GET /api/v1/pfs/fuel-prices?batch-number=N` — same pagination, each item has `fuel_prices` array with `fuel_type`, `price`, `price_last_updated`
- **Rate limits:** 120 req/min, 10,000 req/day
- **Credentials in `.env`** (gitignored)

## Shetland filtering
All 12 Shetland stations have postcodes starting with `ZE`. None are major chains — all independent operators. The fetcher iterates all ~15 batches (~7,400 stations) to find the 12 ZE-postcode ones.

## Historical data sources
- **Station-level (Feb 16 – present):** Extracted from git history of `github.com/matthewgall/fuelfinder-archive` which commits `data.csv` ~twice daily. Run `import_history.py` to reimport.
- **UK national averages (2003–2026):** Weekly GOV.UK CSV. Run `import_uk_weekly.py` to reimport.
- **No official historical API exists** — the Fuel Finder API only serves current snapshots.

## Running
```bash
pip install -r requirements.txt
python3 fetch_prices.py   # fetch current prices
python3 app.py            # start dashboard on :5001
```

## Fuel type codes
| Code | Meaning |
|---|---|
| E10 | Standard unleaded petrol (10% ethanol) |
| E5 | Premium/super unleaded (5% ethanol) |
| B7_STANDARD / B7S | Standard diesel (7% biodiesel) |
| ULSP | UK national average unleaded (in `uk_weekly_prices`) |
| ULSD | UK national average diesel (in `uk_weekly_prices`) |

## Dashboard chart
The Shetland Price Tracking chart overlays UK weekly averages (dashed) against Shetland daily averages (solid) with an annotation marking the start of the Iran war (28 Feb 2026) which triggered the current price spike.
