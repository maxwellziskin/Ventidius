"""Tests for deduplication and alert suppression logic."""

import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from flightwatch.config import AppConfig
from flightwatch.db import bootstrap
from flightwatch.models import FareObservation, ScoredDeal
from flightwatch.notifier import should_suppress, _build_alert_key
from flightwatch.observation_store import insert_observation


@pytest.fixture
def cfg():
    return AppConfig()


@pytest.fixture
def db_conn(tmp_path):
    db_path = str(tmp_path / "test.sqlite")
    bootstrap(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def make_obs(price: float = 300.0, obs_id: int = 1) -> FareObservation:
    return FareObservation(
        id=obs_id,
        raw_message_id=1,
        origin_airport="EWR",
        destination_airport="LIM",
        destination_city="Lima",
        departure_date="2026-05-06",
        return_date="2026-05-13",
        trip_nights=7,
        trip_length_bucket="medium",
        days_until_departure=45,
        booking_window_bucket="near",
        price_amount=price,
        price_currency="USD",
        observation_hash=f"hash_{price}_{obs_id}",
    )


def insert_alert_log(conn, obs: FareObservation, deal_id: int, alert_key: str, days_ago: int = 0) -> None:
    """Insert a fake alert_log row (and prerequisite fare_observations row) for testing."""
    sent_at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Ensure the fare_observations row exists so the JOIN in should_suppress works
    existing = conn.execute("SELECT id FROM fare_observations WHERE id = ?", (obs.id,)).fetchone()
    if not existing:
        conn.execute(
            """
            INSERT INTO fare_observations
                (id, raw_message_id, source, origin_airport, destination_airport,
                 departure_date, return_date, price_amount, price_currency,
                 observation_hash, created_at)
            VALUES (?, 1, 'google_flights_email', ?, ?, ?, ?, ?, 'USD', ?, datetime('now'))
            """,
            (
                obs.id,
                obs.origin_airport,
                obs.destination_airport,
                obs.departure_date,
                obs.return_date,
                obs.price_amount,
                obs.observation_hash or f"testhash_{obs.id}",
            ),
        )

    conn.execute(
        """
        INSERT INTO alert_log
            (fare_observation_id, scored_deal_id, alert_channel, alert_type,
             alert_key, sent_success, sent_at, created_at)
        VALUES (?, ?, 'pushover', 'deal', ?, 1, ?, datetime('now'))
        """,
        (obs.id, deal_id, alert_key, sent_at),
    )
    conn.commit()


class TestObservationDedup:
    def test_duplicate_hash_not_inserted(self, db_conn):
        obs1 = make_obs(300.0, obs_id=None)
        obs1.observation_hash = "same_hash"
        obs2 = make_obs(300.0, obs_id=None)
        obs2.observation_hash = "same_hash"

        id1 = insert_observation(db_conn, obs1)
        id2 = insert_observation(db_conn, obs2)

        assert id1 is not None
        assert id2 is None  # Duplicate blocked

    def test_different_hash_both_inserted(self, db_conn):
        obs1 = make_obs(300.0, obs_id=None)
        obs1.observation_hash = "hash_a"
        obs2 = make_obs(310.0, obs_id=None)
        obs2.observation_hash = "hash_b"

        id1 = insert_observation(db_conn, obs1)
        id2 = insert_observation(db_conn, obs2)

        assert id1 is not None
        assert id2 is not None
        assert id1 != id2


class TestAlertSuppression:
    def test_no_prior_alert_not_suppressed(self, cfg, db_conn):
        obs = make_obs(300.0)
        alert_key = _build_alert_key(obs)
        suppress, reason = should_suppress(db_conn, alert_key, 300.0, cfg)
        assert suppress is False

    def test_recent_alert_same_price_suppressed(self, cfg, db_conn):
        obs = make_obs(300.0)
        alert_key = _build_alert_key(obs)

        # Insert a recent successful alert
        insert_alert_log(db_conn, obs, deal_id=1, alert_key=alert_key, days_ago=1)

        suppress, reason = should_suppress(db_conn, alert_key, 300.0, cfg)
        assert suppress is True
        assert "Suppressed" in reason

    def test_recent_alert_big_price_drop_not_suppressed(self, cfg, db_conn):
        obs = make_obs(300.0)
        alert_key = _build_alert_key(obs)

        # Previous alert at $300
        insert_alert_log(db_conn, obs, deal_id=1, alert_key=alert_key, days_ago=1)

        # Now price dropped to $200 (> $50 drop and > 10%)
        suppress, reason = should_suppress(db_conn, alert_key, 200.0, cfg)
        assert suppress is False
        assert "dropped" in reason

    def test_old_alert_not_suppressed(self, cfg, db_conn):
        obs = make_obs(300.0)
        alert_key = _build_alert_key(obs)

        # Insert alert from 10 days ago (beyond cooldown_days=7)
        insert_alert_log(db_conn, obs, deal_id=1, alert_key=alert_key, days_ago=10)

        suppress, reason = should_suppress(db_conn, alert_key, 300.0, cfg)
        assert suppress is False

    def test_alert_key_includes_dates(self):
        obs1 = make_obs()
        obs2 = FareObservation(
            id=2, raw_message_id=1,
            origin_airport="EWR", destination_airport="LIM",
            departure_date="2026-06-01", return_date="2026-06-08",
            price_amount=300.0, price_currency="USD",
        )
        key1 = _build_alert_key(obs1)
        key2 = _build_alert_key(obs2)
        # Different dates → different cluster keys
        assert key1 != key2
