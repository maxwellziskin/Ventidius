"""Scoring engine: rate a FareObservation and assign a decision."""

import logging
import sqlite3
from typing import Optional

from .config import AppConfig
from .history import get_route_history
from .models import FareObservation, ScoredDeal

logger = logging.getLogger(__name__)


def score_observation(
    obs: FareObservation,
    cfg: AppConfig,
    conn: sqlite3.Connection,
) -> ScoredDeal:
    """
    Score a FareObservation, returning a ScoredDeal.
    Scores are additive and all stored for audit purposes.
    """
    deal = ScoredDeal(fare_observation_id=obs.id)
    reasons: list[str] = []
    sc = cfg.scoring

    # ── Hard cap check ─────────────────────────────────────────────────────
    dest_cfg = cfg.destination_by_code(obs.destination_airport or "")
    hard_cap = dest_cfg.get("hard_cap_usd") if dest_cfg else None

    if obs.price_amount is None:
        deal.hard_cap_pass = False
        deal.decision = "ignore"
        deal.decision_reason_text = "No price extracted"
        return deal

    if hard_cap and obs.price_amount > hard_cap:
        deal.hard_cap_pass = False
        deal.decision = "ignore"
        deal.decision_reason_text = (
            f"Price ${obs.price_amount:.0f} exceeds hard cap ${hard_cap:.0f} for {obs.destination_airport}"
        )
        return deal

    deal.hard_cap_pass = True

    # ── Destination priority score ─────────────────────────────────────────
    priority_weight = dest_cfg.get("priority_weight", 1.0) if dest_cfg else 1.0
    deal.priority_score = priority_weight * 10
    reasons.append(f"priority×{priority_weight:.1f}")

    # ── Price score (how much below cap) ──────────────────────────────────
    if hard_cap:
        cap_distance = hard_cap - obs.price_amount
        # Normalize: 0 at cap, up to 30 points at 50%+ below cap
        deal.price_score = min(30.0, (cap_distance / hard_cap) * 60)
        pct_below_cap = (cap_distance / hard_cap) * 100
        reasons.append(f"${cap_distance:.0f} below {obs.destination_airport} cap ({pct_below_cap:.0f}%)")
    else:
        deal.price_score = 10.0  # neutral if no cap

    # ── Stop penalties ─────────────────────────────────────────────────────
    stops = obs.max_stops_normalized
    if stops == 0:
        bonus = float(sc.get("nonstop_bonus", 15))
        deal.stop_penalty = bonus  # stored as positive for nonstop
        reasons.append("nonstop (+bonus)")
    elif stops == 1:
        deal.stop_penalty = float(sc.get("one_stop_penalty", -5))
        reasons.append("1 stop (mild penalty)")
    elif stops is not None and stops >= 2:
        deal.stop_penalty = float(sc.get("two_plus_stop_penalty", -25))
        reasons.append(f"{stops} stops (major penalty)")
    # else: unknown stops, no adjustment

    # ── Self-transfer and airport-change penalties ─────────────────────────
    if obs.self_transfer_flag:
        deal.self_transfer_penalty = float(sc.get("self_transfer_penalty", -40))
        reasons.append("self-transfer (major penalty)")

    if obs.airport_change_flag:
        deal.airport_change_penalty = float(sc.get("airport_change_penalty", -30))
        reasons.append("airport change (major penalty)")

    # ── Schedule / trip-length penalty ────────────────────────────────────
    if obs.trip_length_bucket is None and obs.trip_nights is not None:
        deal.schedule_penalty += float(sc.get("ugly_schedule_penalty", -10))
        reasons.append(f"trip length {obs.trip_nights}n outside accepted buckets")
    if obs.booking_window_bucket is None and obs.days_until_departure is not None:
        # Outside allowed window (too soon or too far)
        if obs.days_until_departure < 21:
            deal.schedule_penalty += float(sc.get("near_booking_window_penalty", -5))
            reasons.append(f"very short notice ({obs.days_until_departure}d out)")

    # ── Historical discount score ─────────────────────────────────────────
    hist = get_route_history(
        conn,
        obs.origin_airport or "",
        obs.destination_airport or "",
        obs.trip_length_bucket,
        obs.booking_window_bucket,
    )
    h_cfg = cfg.history_cfg
    min_samples = h_cfg.get("min_samples_for_history", 5)

    if hist and hist.get("sample_count", 0) >= min_samples:
        median = hist["median_price"]
        if median and median > 0:
            discount_fraction = (median - obs.price_amount) / median
            meaningful = h_cfg.get("meaningful_discount_fraction", 0.20)
            exceptional = h_cfg.get("exceptional_deal_fraction", 0.30)

            if discount_fraction >= exceptional:
                deal.historical_discount_score = 25.0
                pct = discount_fraction * 100
                reasons.append(f"{pct:.0f}% below route median (exceptional)")
            elif discount_fraction >= meaningful:
                deal.historical_discount_score = 12.0
                pct = discount_fraction * 100
                reasons.append(f"{pct:.0f}% below route median (notable)")
            elif discount_fraction > 0:
                deal.historical_discount_score = 5.0
                reasons.append("slightly below route median")
            else:
                deal.historical_discount_score = 0.0
                pct = abs(discount_fraction) * 100
                reasons.append(f"{pct:.0f}% above route median")
        else:
            deal.historical_discount_score = None
    else:
        deal.historical_discount_score = None
        if hist:
            reasons.append(f"history: only {hist.get('sample_count', 0)} samples (skipping)")
        else:
            reasons.append("no route history yet")

    # ── Total score ────────────────────────────────────────────────────────
    deal.total_score = (
        deal.priority_score
        + deal.price_score
        + deal.stop_penalty
        + deal.self_transfer_penalty
        + deal.airport_change_penalty
        + deal.schedule_penalty
        + (deal.historical_discount_score or 0)
    )

    # ── Decision thresholds ────────────────────────────────────────────────
    book_now_thresh = float(sc.get("book_now_threshold", 75))
    deal_thresh = float(sc.get("deal_threshold", 55))
    watch_thresh = float(sc.get("watch_threshold", 30))

    if deal.total_score >= book_now_thresh:
        deal.decision = "book_now"
    elif deal.total_score >= deal_thresh:
        deal.decision = "deal"
    elif deal.total_score >= watch_thresh:
        deal.decision = "watch"
    else:
        deal.decision = "ignore"

    deal.decision_reason_text = "; ".join(reasons)
    logger.debug(
        "Scored obs_id=%s %s->%s $%.0f: score=%.1f decision=%s",
        obs.id,
        obs.origin_airport,
        obs.destination_airport,
        obs.price_amount,
        deal.total_score,
        deal.decision,
    )
    return deal


def save_scored_deal(conn: sqlite3.Connection, deal: ScoredDeal) -> int:
    cursor = conn.execute(
        """
        INSERT INTO scored_deals
            (fare_observation_id, hard_cap_pass, price_score, priority_score,
             schedule_penalty, stop_penalty, airport_change_penalty,
             self_transfer_penalty, historical_discount_score, total_score,
             decision, decision_reason_text, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            deal.fare_observation_id,
            int(deal.hard_cap_pass),
            deal.price_score,
            deal.priority_score,
            deal.schedule_penalty,
            deal.stop_penalty,
            deal.airport_change_penalty,
            deal.self_transfer_penalty,
            deal.historical_discount_score,
            deal.total_score,
            deal.decision,
            deal.decision_reason_text,
        ),
    )
    return cursor.lastrowid


def get_unscored_observations(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return fare observations that have no scored_deal record yet."""
    return conn.execute(
        """
        SELECT fo.* FROM fare_observations fo
        LEFT JOIN scored_deals sd ON sd.fare_observation_id = fo.id
        WHERE sd.id IS NULL
          AND fo.price_amount IS NOT NULL
          AND fo.origin_airport IS NOT NULL
          AND fo.destination_airport IS NOT NULL
        ORDER BY fo.created_at ASC
        """
    ).fetchall()
