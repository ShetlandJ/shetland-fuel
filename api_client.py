import time

import requests

from config import BASE_URL, CLIENT_ID, CLIENT_SECRET


class FuelFinderClient:
    def __init__(self):
        self._access_token = None
        self._refresh_token = None
        self._token_expiry = 0

    def _authenticate(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/oauth/generate_access_token",
            json={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        )
        resp.raise_for_status()
        body = resp.json()
        data = body["data"] if "data" in body else body
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        self._token_expiry = time.time() + data.get("expires_in", 3600) - 60

    def _refresh(self):
        resp = requests.post(
            f"{BASE_URL}/api/v1/oauth/regenerate_access_token",
            json={"client_id": CLIENT_ID, "refresh_token": self._refresh_token},
        )
        resp.raise_for_status()
        body = resp.json()
        data = body["data"] if "data" in body else body
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._token_expiry = time.time() + data.get("expires_in", 3600) - 60

    def _ensure_token(self):
        if self._access_token and time.time() < self._token_expiry:
            return
        if self._refresh_token:
            try:
                self._refresh()
                return
            except requests.RequestException:
                pass
        self._authenticate()

    def _get(self, path, params=None):
        self._ensure_token()
        resp = requests.get(
            f"{BASE_URL}{path}",
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Accept": "application/json",
            },
            params=params,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        return resp.json()

    def get_all_stations(self):
        """Fetch all stations across all batches (returns flat list)."""
        stations = []
        batch = 1
        while True:
            data = self._get("/api/v1/pfs", params={"batch-number": batch})
            items = data if isinstance(data, list) else data.get("data", [])
            if not items:
                break
            stations.extend(items)
            batch += 1
        return stations

    def get_all_fuel_prices(self):
        """Fetch all fuel prices, keyed by node_id."""
        prices = {}
        batch = 1
        while True:
            data = self._get("/api/v1/pfs/fuel-prices", params={"batch-number": batch})
            items = data if isinstance(data, list) else data.get("data", [])
            if not items:
                break
            for item in items:
                node_id = item.get("node_id", "")
                if node_id:
                    prices[node_id] = item.get("fuel_prices", [])
            batch += 1
        return prices
