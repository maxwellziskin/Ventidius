"""Tests for the scoring engine."""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from flightwatch.config import AppConfig
from flightwatch.db import bootstrap
from flightwatch.models import FareObservation
from flightwatch.scorer import score_observation


def make_obs(**kwargs) -> FareObservation:
    defaults = {
        "id": 1,
        "raw_message_id": 1,
        "origin_airport": "EWR",
        "destination_airport": "LIM",
        "destination_city": "Lima",
        "departure_date": "2026-05-06",
        "return_date": "2026-05-13",
        "trip_nights": 7,
        "trip_length_bucket": "medium",
        "days_until_departure": 45,
        "booking_window_bucket": "near",
        "price_amount": 300.0,
        "price_currency": "USD",
        "max_stops_normalized": 0,
        "self_transfer_flag": False,
        "airport_change_flag": False,
    }
    defaults.update(kwargs)
    return FareObservation(**defaults)


@pytest.fixture
def cfg():
    """Return an AppConfig with test settings."""
    return AppConfig()


@pytest.fixture
def db_conn(tmp_path):
    """In-memory SQLite connection with schema bootstrapped."""
    db_path = str(tmp_path / "test.sqlite")
    bootstrap(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


class TestHardCapFiltering:
    def test_above_cap_ignored(self, cfg, db_conn):
        # LIM cap is $550; price $600 should be ignored
        obs = make_obs(destination_airport="LIM", price_amount=600.0)
        deal = score_observation(obs, cfg, db_conn)
        assert deal.decision == "ignore"
        assert deal.hard_cap_pass is False

    def test_below_cap_passes(self, cfg, db_conn):
        obs = make_obs(destination_airport="LIM", price_amount=300.0)
        deal = score_observation(obs, cfg, db_conn)
        assert deal.hard_cap_pass is True
        assert deal.decision != "ignore"

    def test_no_price_ignored(self, cfg, db_conn):
        obs = make_obs(price_amount=None)
        deal = score_observation(obs, cfg, db_conn)
        assert deal.decision == "ignore"


class TestStopScoring:
    def test_nonstop_gets_bonus(self, cfg, db_conn):
        obs_nonstop = make_obs(max_stops_normalized=0)
        obs_one_stop = make_obs(max_stops_normalized=1)
        deal_nonstop = score_observation(obs_nonstop, cfg, db_conn)
        deal_one_stop = score_observation(obs_one_stop, cfg, db_conn)
        # Nonstop should score higher
        assert deal_nonstop.total_score > deal_one_stop.total_score

    def test_self_transfer_penalized(self, cfg, db_conn):
        obs_clean = make_obs(self_transfer_flag=False)
        obs_st = make_obs(self_transfer_flag=True)
        deal_clean = score_observation(obs_clean, cfg, db_conn)
        deal_st = score_observation(obs_st, cfg, db_conn)
        assert deal_clean.total_score > deal_st.total_score
        assert deal_st.self_transfer_penalty < 0

    def test_airport_change_penalized(self, cfg, db_conn):
        obs_clean = make_obs(airport_change_flag=False)
        obs_ac = make_obs(airport_change_flag=True)
        deal_clean = score_observation(obs_clean, cfg, db_conn)
        deal_ac = score_observation(obs_ac, cfg, db_conn)
        assert deal_clean.total_score > deal_ac.total_score


class TestDecisionThresholds:
    def test_low_score_is_ignore(self, cfg, db_conn):
        # Very expensive nonstop flight well below cap but self-transfer + airport change
        obs = make_obs(
            price_amount=530.0,  # Close to cap
            self_transfer_flag=True,
            airport_change_flag=True,
            max_stops_normalized=2,
        )
        deal = score_observation(obs, cfg, db_conn)
        # Heavy penalties should push to ignore or watch
        assert deal.decision in ("ignore", "watch")

    def test_great_deal_is_deal(self, cfg, db_conn):
        # Well below cap, nonstop, priority destination
        obs = make_obs(
            destination_airport="LIM",
            price_amount=200.0,  # Hard cap 550, so $350 below = ~64% below cap
            max_stops_normalized=0,
        )
        deal = score_observation(obs, cfg, db_conn)
        assert deal.decision in ("deal", "book_now")

    def test_decision_reason_text_present(self, cfg, db_conn):
        obs = make_obs()
        deal = score_observation(obs, cfg, db_conn)
        assert deal.decision_reason_text is not None
        assert len(deal.decision_reason_text) > 0


class TestPriorityWeight:
    def test_higher_priority_boosts_score(self, cfg, db_conn):
        # OAX has priority_weight=1.3, MEX has 1.2, GDL has 0.9
        obs_high = make_obs(destination_airport="OAX", destination_city="Oaxaca", price_amount=300.0)
        obs_low = make_obs(destination_airport="GDL", destination_city="Guadalajara", price_amount=300.0)
        deal_high = score_observation(obs_high, cfg, db_conn)
        deal_low = score_observation(obs_low, cfg, db_conn)
        assert deal_high.total_score > deal_low.total_score


class TestIntegration:
    def test_full_pipeline_sample_email(self, cfg, db_conn):
        """Simulate parsing sample email to scored deal."""
        from flightwatch.parser_google_flights import parse_email
        from flightwatch.normalizer import normalize

        html = (Path(__file__).parent / "fixtures" / "sample_flights_email.html").read_text()
        result = parse_email(html, None, subject="Price alert: EWR to LIM")
        assert result.is_usable

        obs = normalize(result, raw_message_id=1, cfg=cfg)
        assert obs is not None
        obs.id = 1

        deal = score_observation(obs, cfg, db_conn)
        assert deal.hard_cap_pass is True
        assert deal.decision in ("watch", "deal", "book_now")
        assert "LIM" in (deal.decision_reason_text or "")
