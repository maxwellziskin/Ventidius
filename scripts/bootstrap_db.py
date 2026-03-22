#!/usr/bin/env python3
"""Bootstrap the Flightwatch SQLite database and seed destinations."""

import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from flightwatch.config import AppConfig
from flightwatch.db import bootstrap, get_connection


def main() -> None:
    cfg = AppConfig()
    print(f"Bootstrapping database at: {cfg.db_path}")
    bootstrap(cfg.db_path)
    print("Schema created.")

    with get_connection(cfg.db_path) as conn:
        # Seed destinations
        seeded = 0
        for d in cfg.destinations:
            existing = conn.execute(
                "SELECT id FROM destinations WHERE airport_code = ?", (d["airport_code"],)
            ).fetchone()
            if not existing:
                conn.execute(
                    """
                    INSERT INTO destinations
                        (city_name, airport_code, country, region, priority_weight, hard_cap_usd, enabled, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        d["city_name"], d["airport_code"], d["country"], d["region"],
                        d["priority_weight"], d.get("hard_cap_usd"),
                        int(d.get("enabled", True)), d.get("notes"),
                    ),
                )
                seeded += 1
        print(f"Seeded {seeded} new destination(s).")

        # Verify
        rows = conn.execute("SELECT airport_code, city_name, enabled FROM destinations ORDER BY region, country").fetchall()
        print(f"\nDestinations in DB ({len(rows)} total):")
        for r in rows:
            status = "✓" if r["enabled"] else "✗"
            print(f"  {status} {r['airport_code']}  {r['city_name']}")

    print("\nDatabase bootstrap complete.")


if __name__ == "__main__":
    main()
