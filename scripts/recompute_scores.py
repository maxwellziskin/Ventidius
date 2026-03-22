#!/usr/bin/env python3
"""
Recompute scores for all or specific fare observations.

Usage:
    python scripts/recompute_scores.py              # all unscored
    python scripts/recompute_scores.py --all        # clear and recompute all
    python scripts/recompute_scores.py --obs-id 42
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flightwatch.config import AppConfig
from flightwatch.db import get_connection
from flightwatch.history import compute_route_history_summaries
from flightwatch.observation_store import row_to_observation
from flightwatch.scorer import score_observation, save_scored_deal, get_unscored_observations

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute fare scores")
    parser.add_argument("--all", action="store_true", help="Delete all scores and recompute")
    parser.add_argument("--obs-id", type=int, help="Score a specific observation id")
    parser.add_argument("--dry-run", action="store_true", help="Print scores without saving")
    args = parser.parse_args()

    cfg = AppConfig()

    with get_connection(cfg.db_path) as conn:
        # First refresh history
        compute_route_history_summaries(conn)

        if args.all:
            print("Deleting all scored_deals records...")
            conn.execute("DELETE FROM scored_deals")

        if args.obs_id:
            rows = conn.execute(
                "SELECT * FROM fare_observations WHERE id = ?", (args.obs_id,)
            ).fetchall()
        else:
            rows = get_unscored_observations(conn)

        if not rows:
            print("Nothing to score.")
            sys.exit(0)

        print(f"Scoring {len(rows)} observation(s)...")
        counts = {"ignore": 0, "watch": 0, "deal": 0, "book_now": 0}

        for row in rows:
            obs = row_to_observation(row)
            deal = score_observation(obs, cfg, conn)
            counts[deal.decision] = counts.get(deal.decision, 0) + 1

            print(
                f"  obs_id={obs.id} {obs.origin_airport}->{obs.destination_airport} "
                f"${obs.price_amount:.0f} → {deal.decision.upper()} (score={deal.total_score:.1f})"
            )
            print(f"    {deal.decision_reason_text}")

            if not args.dry_run:
                deal_id = save_scored_deal(conn, deal)
                deal.id = deal_id

        print(f"\nDone. ignore={counts['ignore']} watch={counts['watch']} deal={counts['deal']} book_now={counts['book_now']}")


if __name__ == "__main__":
    main()
