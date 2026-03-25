import os
from pathlib import Path

# Load .env if present
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

BASE_URL = "https://www.fuel-finder.service.gov.uk"
CLIENT_ID = os.environ["FUEL_FINDER_CLIENT_ID"]
CLIENT_SECRET = os.environ["FUEL_FINDER_CLIENT_SECRET"]
DB_PATH = os.path.join(os.path.dirname(__file__), "prices.db")

# Regions we track
REGIONS = {
    "shetland": {"label": "Shetland", "postcode_prefixes": ["ZE"]},
    "orkney": {"label": "Orkney", "postcode_prefixes": ["KW15", "KW16", "KW17"]},
}


def normalise_price(price):
    """Fix prices with a missing decimal point (4-digit values like 1599 → 159.9)."""
    if 1000 <= price <= 9999:
        return price / 10
    return price


def get_region(postcode):
    """Return region key for a postcode, or None if not tracked."""
    postcode = postcode.upper()
    for region_key, cfg in REGIONS.items():
        for prefix in cfg["postcode_prefixes"]:
            if postcode.startswith(prefix):
                return region_key
    return None
