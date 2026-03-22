"""Historical route baseline computation and retrieval."""

import logging
import sqlite3
import statistics
from typing import Optional

logger = logging.getLogger(__name__)


def get_route_history(
    conn: sqlite3.Connection,
    origin: str,
    destination: str,
    trip_length_bucket: Optional[str],
    booking_window_bucket: Optional[str],
    window_days: int = 90,
) -> Optional[dict]:
    """
    Retrieve pre-computed summary stats for a route template.
    Returns None if not enough data.
    """
    row = conn.execute(
        """
        SELECT * FROM route_history_summary
        WHERE origin_airport = ?
          AND destination_airport = ?
          AND trip_length_bucket = ?
          AND booking_window_bucket = ?
        """,
        (origin, destination, trip_length_bucket or "", booking_window_bucket or ""),
    ).fetchone()

    if not row:
        return None

    return dict(row)


def compute_route_history_summaries(conn: sqlite3.Connection, window_days: int = 90) -> int:
    """
    Recompute route_history_summary for all observed route templates.
    Returns the number of routes updated.
    """
    routes = conn.execute(
        """
        SELECT DISTINCT
            origin_airport,
            destination_airport,
            trip_length_bucket,
            booking_window_bucket
        FROM fare_observations
        WHERE origin_airport IS NOT NULL
          AND destination_airport IS NOT NULL
          AND price_amount IS NOT NULL
          AND trip_length_bucket IS NOT NULL
          AND booking_window_bucket IS NOT NULL
        """
    ).fetchall()

    updated = 0
    for r in routes:
        origin = r["origin_airport"]
        dest = r["destination_airport"]
        tlb = r["trip_length_bucket"]
        bwb = r["booking_window_bucket"]

        prices_rows = conn.execute(
            f"""
            SELECT price_amount FROM fare_observations
            WHERE origin_airport = ?
              AND destination_airport = ?
              AND trip_length_bucket = ?
              AND booking_window_bucket = ?
              AND price_amount IS NOT NULL
              AND created_at >= datetime('now', '-{window_days} days')
            ORDER BY price_amount ASC
            """,
            (origin, dest, tlb, bwb),
        ).fetchall()

        prices = [row["price_amount"] for row in prices_rows]
        n = len(prices)
        if n == 0:
            continue

        sorted_prices = sorted(prices)
        min_p = sorted_prices[0]
        median_p = statistics.median(sorted_prices)
        p10_p = sorted_prices[max(0, int(n * 0.10))]
        p25_p = sorted_prices[max(0, int(n * 0.25))]

        conn.execute(
            """
            INSERT INTO route_history_summary
                (origin_airport, destination_airport, trip_length_bucket, booking_window_bucket,
                 sample_count, min_price, median_price, p10_price, p25_price, last_computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(origin_airport, destination_airport, trip_length_bucket, booking_window_bucket)
            DO UPDATE SET
                sample_count = excluded.sample_count,
                min_price = excluded.min_price,
                median_price = excluded.median_price,
                p10_price = excluded.p10_price,
                p25_price = excluded.p25_price,
                last_computed_at = excluded.last_computed_at
            """,
            (origin, dest, tlb, bwb, n, min_p, median_p, p10_p, p25_p),
        )
        updated += 1
        logger.debug(
            "History updated %s->%s (%s/%s): n=%d median=$%.0f",
            origin, dest, tlb, bwb, n, median_p,
        )

    conn.commit()
    logger.info("Route history summaries recomputed for %d route templates", updated)
    return updated
