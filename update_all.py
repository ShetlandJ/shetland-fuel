#!/usr/bin/env python3
"""Full update pipeline: pull archive, fetch live prices, import UK weekly, build static site."""
import csv
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent

# Build set of all tracked postcode prefixes
from config import get_region, REGIONS
_ALL_PREFIXES = []
for cfg in REGIONS.values():
    _ALL_PREFIXES.extend(cfg["postcode_prefixes"])


def pull_archive():
    """Clone fuelfinder-archive and extract records for tracked regions."""
    print("=== Pulling fuelfinder-archive ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = f"{tmpdir}/fuelfinder-archive.git"
        subprocess.run(
            ["git", "clone", "--bare", "https://github.com/matthewgall/fuelfinder-archive.git", repo_path],
            check=True,
        )
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "--format=%H %aI", "--", "data.csv"],
            capture_output=True, text=True, check=True,
        )
        commits = []
        for line in result.stdout.strip().split("\n"):
            sha, date = line.split(" ", 1)
            commits.append((sha, date))
        print(f"  Processing {len(commits)} commits...")

        records = []
        for sha, commit_date in commits:
            blob = subprocess.run(
                ["git", "-C", repo_path, "show", f"{sha}:data.csv"],
                capture_output=True, text=True,
            )
            if blob.returncode != 0:
                continue
            reader = csv.DictReader(io.StringIO(blob.stdout))
            for row in reader:
                postcode = row.get("forecourts.location.postcode", "")
                if not any(postcode.startswith(p) for p in _ALL_PREFIXES):
                    continue
                records.append({
                    "commit_date": commit_date,
                    "node_id": row["forecourts.node_id"],
                    "name": row["forecourts.trading_name"],
                    "brand": row["forecourts.brand_name"],
                    "postcode": postcode,
                    "E5": row.get("forecourts.fuel_price.E5", ""),
                    "E10": row.get("forecourts.fuel_price.E10", ""),
                    "B7S": row.get("forecourts.fuel_price.B7S", ""),
                    "update_ts": row.get("forecourt_update_timestamp", ""),
                })

        records.sort(key=lambda r: r["commit_date"], reverse=True)
        out_path = ROOT / "shetland_history_raw.json"
        with open(out_path, "w") as f:
            json.dump(records, f, indent=2)
        print(f"  Extracted {len(records)} records across all regions")


def import_history():
    print("=== Importing history ===")
    subprocess.run([sys.executable, str(ROOT / "import_history.py")], check=True)


def import_uk_weekly():
    print("=== Importing UK weekly averages ===")
    subprocess.run([sys.executable, str(ROOT / "import_uk_weekly.py")], check=True)


def build_static():
    print("=== Building static site ===")
    subprocess.run([sys.executable, str(ROOT / "build_static.py")], check=True)


def main():
    pull_archive()
    import_history()
    import_uk_weekly()
    build_static()
    print("\n=== All done ===")


if __name__ == "__main__":
    main()
