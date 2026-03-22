"""
Flightwatch main entrypoint.

Usage:
    python -m flightwatch.main [--dry-run] [--no-fetch]
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from .config import AppConfig
from .db import bootstrap, get_connection
from .gmail_client import GmailClient
from .message_store import (
    upsert_raw_message,
    mark_parse_success,
    mark_parse_failed,
    mark_parse_partial,
    get_pending_messages,
)
from .models import RawMessage
from .normalizer import normalize, passes_basic_filters
from .observation_store import insert_observation, row_to_observation
from .parser_google_flights import parse_email
from .scorer import score_observation, save_scored_deal, get_unscored_observations
from .notifier import send_notification
from .history import compute_route_history_summaries

logger = logging.getLogger(__name__)


def setup_logging(level: int = logging.INFO) -> None:
    from pathlib import Path
    import os

    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "flightwatch.log"

    fmt = "%(asctime)s %(levelname)-8s %(name)s %(message)s"
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    logging.basicConfig(level=level, format=fmt, handlers=handlers)


def seed_destinations(cfg: AppConfig, conn) -> None:
    """Insert or update destination records from config."""
    for d in cfg.destinations:
        existing = conn.execute(
            "SELECT id FROM destinations WHERE airport_code = ?", (d["airport_code"],)
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE destinations SET
                    city_name=?, country=?, region=?, priority_weight=?,
                    hard_cap_usd=?, enabled=?, notes=?, updated_at=datetime('now')
                WHERE airport_code=?
                """,
                (
                    d["city_name"], d["country"], d["region"],
                    d["priority_weight"], d.get("hard_cap_usd"),
                    int(d.get("enabled", True)), d.get("notes"),
                    d["airport_code"],
                ),
            )
        else:
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


def run(dry_run: bool = False, no_fetch: bool = False) -> dict:
    """
    Main pipeline. Returns a summary dict with counts.
    """
    start_time = time.time()
    now_str = datetime.now(timezone.utc).isoformat()
    logger.info("=" * 60)
    logger.info("Flightwatch run started at %s  dry_run=%s", now_str, dry_run)

    cfg = AppConfig()
    bootstrap(cfg.db_path)

    counts = {
        "messages_fetched": 0,
        "messages_stored": 0,
        "parse_success": 0,
        "parse_partial": 0,
        "parse_failed": 0,
        "observations_created": 0,
        "alerts_considered": 0,
        "alerts_sent": 0,
        "alerts_suppressed": 0,
    }

    with get_connection(cfg.db_path) as conn:
        seed_destinations(cfg, conn)

        # ── Step 1: Fetch Gmail messages ───────────────────────────────────
        if not no_fetch:
            try:
                gmail = GmailClient(cfg.gmail_credentials_path, cfg.gmail_client_secret_path)
                message_ids = gmail.fetch_flight_alert_message_ids()
                counts["messages_fetched"] = len(message_ids)
                logger.info("Fetched %d candidate message IDs from Gmail", len(message_ids))
            except Exception as exc:
                logger.error("Gmail fetch failed: %s", exc)
                message_ids = []
                counts["messages_fetched"] = 0
        else:
            logger.info("--no-fetch: skipping Gmail ingestion")
            message_ids = []

        # ── Step 2: Store raw messages ─────────────────────────────────────
        for msg_id in message_ids:
            try:
                raw_msg_data = gmail.fetch_message(msg_id)
                sender = gmail.extract_sender(raw_msg_data)
                subject = gmail.extract_subject(raw_msg_data)

                if not gmail.is_google_flights_email(sender, subject):
                    logger.debug("Skipping non-flights message %s: %s", msg_id, subject)
                    continue

                html_body, plain_body = gmail.extract_body(raw_msg_data)
                received_at = gmail.internal_date_to_iso(raw_msg_data.get("internalDate", "0"))

                raw_msg = RawMessage(
                    gmail_message_id=msg_id,
                    gmail_thread_id=raw_msg_data.get("threadId"),
                    sender=sender,
                    subject=subject,
                    snippet=raw_msg_data.get("snippet", "")[:500],
                    received_at=received_at,
                    raw_html=html_body,
                    raw_text=plain_body,
                )

                stored_id = upsert_raw_message(conn, raw_msg)
                if stored_id is not None:
                    counts["messages_stored"] += 1
            except Exception as exc:
                logger.error("Error storing message %s: %s", msg_id, exc)

        # ── Step 3: Parse pending messages ─────────────────────────────────
        pending = get_pending_messages(conn)
        logger.info("Parsing %d pending messages", len(pending))

        for raw_row in pending:
            raw_id = raw_row["id"]
            subject = raw_row["subject"] or ""
            try:
                result = parse_email(raw_row["raw_html"], raw_row["raw_text"], subject=subject)

                if not result.is_usable:
                    if result.warnings:
                        note = "; ".join(result.warnings)
                        mark_parse_partial(conn, raw_id, note)
                        counts["parse_partial"] += 1
                        logger.warning(
                            "Partial parse for msg_id=%s (%s): %s",
                            raw_row["gmail_message_id"], subject[:60], note,
                        )
                    else:
                        mark_parse_failed(conn, raw_id, "Could not extract route+price")
                        counts["parse_failed"] += 1
                    continue

                # ── Normalize ─────────────────────────────────────────────
                obs = normalize(result, raw_id, cfg)
                if obs is None:
                    mark_parse_partial(conn, raw_id, "Normalized to None (route/price missing)")
                    counts["parse_partial"] += 1
                    continue

                passes, reason = passes_basic_filters(obs, cfg)
                if not passes:
                    logger.info(
                        "Observation filtered out for msg_id=%s: %s",
                        raw_row["gmail_message_id"], reason,
                    )
                    mark_parse_success(conn, raw_id)  # Successfully parsed, just not relevant
                    counts["parse_success"] += 1
                    continue

                # ── Store observation ──────────────────────────────────────
                obs_id = insert_observation(conn, obs)
                if obs_id is None:
                    logger.debug("Duplicate observation for msg_id=%s; skipping", raw_row["gmail_message_id"])
                    mark_parse_success(conn, raw_id)
                    counts["parse_success"] += 1
                    continue

                obs.id = obs_id
                counts["observations_created"] += 1
                mark_parse_success(conn, raw_id)
                counts["parse_success"] += 1

            except Exception as exc:
                logger.exception(
                    "Unexpected error parsing msg_id=%s subject=%s: %s",
                    raw_row["gmail_message_id"], subject[:60], exc,
                )
                mark_parse_failed(conn, raw_id, str(exc)[:500])
                counts["parse_failed"] += 1

        # ── Step 4: Score unscored observations ────────────────────────────
        unscored = get_unscored_observations(conn)
        logger.info("Scoring %d unscored observations", len(unscored))

        for row in unscored:
            obs = row_to_observation(row)
            try:
                deal = score_observation(obs, cfg, conn)
                deal_id = save_scored_deal(conn, deal)
                deal.id = deal_id

                counts["alerts_considered"] += 1

                if deal.decision in ("deal", "book_now", "watch"):
                    logger.info(
                        "Scored obs_id=%d %s->%s $%.0f as %s (score=%.1f): %s",
                        obs.id or 0,
                        obs.origin_airport, obs.destination_airport,
                        obs.price_amount or 0,
                        deal.decision, deal.total_score,
                        deal.decision_reason_text,
                    )

                # ── Step 5: Send notifications ─────────────────────────────
                sent = send_notification(obs, deal, cfg, conn, dry_run=dry_run)
                if sent:
                    counts["alerts_sent"] += 1
                elif deal.decision in ("deal", "book_now"):
                    counts["alerts_suppressed"] += 1

            except Exception as exc:
                logger.exception("Error scoring obs_id=%s: %s", obs.id, exc)

        # ── Step 6: Update route history ───────────────────────────────────
        try:
            compute_route_history_summaries(conn)
        except Exception as exc:
            logger.error("History recompute failed: %s", exc)

    elapsed = time.time() - start_time
    logger.info(
        "Run complete in %.1fs | fetched=%d stored=%d parsed=%d partial=%d failed=%d "
        "obs=%d alerts_considered=%d sent=%d suppressed=%d",
        elapsed,
        counts["messages_fetched"],
        counts["messages_stored"],
        counts["parse_success"],
        counts["parse_partial"],
        counts["parse_failed"],
        counts["observations_created"],
        counts["alerts_considered"],
        counts["alerts_sent"],
        counts["alerts_suppressed"],
    )
    logger.info("=" * 60)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Flightwatch: Personal flight deal alert system")
    parser.add_argument("--dry-run", action="store_true", help="Parse and score but do not send notifications")
    parser.add_argument("--no-fetch", action="store_true", help="Skip Gmail fetch; process already-stored messages")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(log_level)

    try:
        counts = run(dry_run=args.dry_run, no_fetch=args.no_fetch)
        # Exit 0 on success, even if some parses failed
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
