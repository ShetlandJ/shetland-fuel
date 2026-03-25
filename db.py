import sqlite3

from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS stations (
            node_id TEXT PRIMARY KEY,
            brand TEXT,
            name TEXT,
            address TEXT,
            postcode TEXT,
            latitude REAL,
            longitude REAL,
            region TEXT
        );

        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            fuel_type TEXT NOT NULL,
            price_pence REAL NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            api_timestamp TEXT,
            FOREIGN KEY (node_id) REFERENCES stations(node_id)
        );

        CREATE INDEX IF NOT EXISTS idx_prices_node_fuel
            ON prices(node_id, fuel_type, recorded_at);

        CREATE TABLE IF NOT EXISTS uk_weekly_prices (
            date TEXT NOT NULL,
            fuel_type TEXT NOT NULL,
            price_pence REAL NOT NULL,
            duty_pence REAL,
            vat_pct REAL,
            PRIMARY KEY (date, fuel_type)
        );
    """)
    # Migration: add region column to existing databases
    try:
        conn.execute("ALTER TABLE stations ADD COLUMN region TEXT")
    except Exception:
        pass
    conn.execute("UPDATE stations SET region = 'shetland' WHERE region IS NULL")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialised.")
