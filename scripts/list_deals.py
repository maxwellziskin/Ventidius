#!/usr/bin/env python3
"""
List recent deals from the database.

Usage:
    python scripts/list_deals.py
    python scripts/list_deals.py --decision deal
    python scripts/list_deals.py --days 30
    python scripts/list_deals.py --export deals.csv
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flightwatch.config import AppConfig
from flightwatch.db import get_connection


def main() -> None:
    parser = argparse.ArgumentParser(description="List recent deals")
    parser.add_argument("--decision", choices=["watch", "deal", "book_now", "all"], default="all")
    parser.add_argument("--days", type=int, default=7, help="Look back N days")
    parser.add_argument("--export", type=str, help="Export to CSV file")
    args = parser.parse_args()

    cfg = AppConfig()

    decision_filter = "" if args.decision == "all" else f"AND sd.decision = '{args.decision}'"

    query = f"""
        SELECT
            fo.id AS obs_id,
            fo.origin_airport,
            fo.destination_airport,
            fo.destination_city,
            fo.departure_date,
            fo.return_date,
            fo.trip_nights,
            fo.price_amount,
            fo.stops_text,
            sd.decision,
            sd.total_score,
            sd.decision_reason_text,
            sd.created_at AS scored_at
        FROM fare_observations fo
        JOIN scored_deals sd ON sd.fare_observation_id = fo.id
        WHERE sd.created_at >= datetime('now', '-{args.days} days')
          {decision_filter}
        ORDER BY sd.total_score DESC, sd.created_at DESC
    """

    with get_connection(cfg.db_path) as conn:
        rows = conn.execute(query).fetchall()

    if not rows:
        print("No deals found.")
        sys.exit(0)

    if args.export:
        with open(args.export, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows([dict(r) for r in rows])
        print(f"Exported {len(rows)} rows to {args.export}")
        return

    print(f"{'obs_id':<8} {'route':<12} {'depart':<12} {'return':<12} {'$':<7} {'stops':<10} {'decision':<10} {'score':<6}")
    print("-" * 90)
    for r in rows:
        route = f"{r['origin_airport']}->{r['destination_airport']}"
        print(
            f"{r['obs_id']:<8} {route:<12} {r['departure_date'] or '?':<12} "
            f"{r['return_date'] or '?':<12} "
            f"${r['price_amount'] or 0:<6.0f} {r['stops_text'] or '?':<10} "
            f"{r['decision']:<10} {r['total_score']:<6.1f}"
        )
        if r["decision_reason_text"]:
            print(f"         {r['decision_reason_text']}")


if __name__ == "__main__":
    main()
