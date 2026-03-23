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

# Shetland postcodes all start with ZE
SHETLAND_POSTCODE_PREFIX = "ZE"
