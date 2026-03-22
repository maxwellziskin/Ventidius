#!/usr/bin/env python3
"""
Reparse stored raw messages.

Usage:
    python scripts/reparse_messages.py --all-failed
    python scripts/reparse_messages.py --message-id 42
    python scripts/reparse_messages.py --gmail-id 18abc123def456
    python scripts/reparse_messages.py --all
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flightwatch.config import AppConfig
from flightwatch.db import get_connection
from flightwatch.message_store import (
    get_failed_messages,
    get_message_by_id,
    get_message_by_gmail_id,
    mark_parse_success,
    mark_parse_failed,
    mark_parse_partial,
    reset_message_for_reparse,
)
from flightwatch.normalizer import normalize, passes_basic_filters
from flightwatch.observation_store import insert_observation
from flightwatch.parser_google_flights import parse_email

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def reparse_row(row, cfg, conn, dry_run: bool = False) -> str:
    """Reparse a single raw_message row. Returns outcome string."""
    raw_id = row["id"]
    gmail_id = row["gmail_message_id"]
    subject = row["subject"] or ""

    reset_message_for_reparse(conn, raw_id)

    result = parse_email(row["raw_html"], row["raw_text"], subject=subject)

    if not result.is_usable:
        note = "; ".join(result.warnings) or "Could not extract route+price"
        mark_parse_partial(conn, raw_id, note)
        return f"PARTIAL [{gmail_id}] {subject[:60]}: {note}"

    obs = normalize(result, raw_id, cfg)
    if obs is None:
        mark_parse_partial(conn, raw_id, "Normalized to None")
        return f"PARTIAL [{gmail_id}] normalize returned None"

    passes, reason = passes_basic_filters(obs, cfg)
    if not passes:
        mark_parse_success(conn, raw_id)
        return f"FILTERED [{gmail_id}] {reason}"

    if dry_run:
        mark_parse_success(conn, raw_id)
        return f"DRY_RUN [{gmail_id}] Would insert: {obs}"

    obs_id = insert_observation(conn, obs)
    mark_parse_success(conn, raw_id)
    if obs_id:
        return f"OK [{gmail_id}] obs_id={obs_id} {obs.origin_airport}->{obs.destination_airport} ${obs.price_amount}"
    else:
        return f"DUP [{gmail_id}] duplicate observation (hash already exists)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Reparse stored raw messages")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all-failed", action="store_true", help="Reparse all failed/partial messages")
    group.add_argument("--all", action="store_true", help="Reparse ALL stored messages")
    group.add_argument("--message-id", type=int, help="Reparse by database row id")
    group.add_argument("--gmail-id", type=str, help="Reparse by Gmail message ID")
    parser.add_argument("--dry-run", action="store_true", help="Parse but do not insert observations")
    args = parser.parse_args()

    cfg = AppConfig()

    with get_connection(cfg.db_path) as conn:
        if args.all_failed:
            rows = get_failed_messages(conn)
        elif args.all:
            rows = conn.execute("SELECT * FROM raw_messages ORDER BY received_at ASC").fetchall()
        elif args.message_id:
            row = get_message_by_id(conn, args.message_id)
            rows = [row] if row else []
        elif args.gmail_id:
            row = get_message_by_gmail_id(conn, args.gmail_id)
            rows = [row] if row else []
        else:
            rows = []

        if not rows:
            print("No messages found matching criteria.")
            sys.exit(0)

        print(f"Reparsing {len(rows)} message(s)...")
        results = {"ok": 0, "partial": 0, "filtered": 0, "dup": 0, "dry_run": 0}

        for row in rows:
            try:
                outcome = reparse_row(row, cfg, conn, dry_run=args.dry_run)
                print(outcome)
                tag = outcome.split("[")[0].strip().lower()
                if tag in results:
                    results[tag] += 1
                else:
                    results["ok"] += 1
            except Exception as exc:
                print(f"ERROR [{row['gmail_message_id']}]: {exc}")

        print(f"\nDone. {results}")


if __name__ == "__main__":
    main()
