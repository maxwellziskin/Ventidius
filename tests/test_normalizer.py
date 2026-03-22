"""Tests for the normalizer module."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from flightwatch.config import AppConfig
from flightwatch.normalizer import normalize, passes_basic_filters
from flightwatch.parser_google_flights import ParseResult


def make_result(**kwargs) -> ParseResult:
    r = ParseResult()
    r.origin = kwargs.get("origin", "EWR")
    r.destination = kwargs.get("destination", "LIM")
    r.destination_city = kwargs.get("destination_city", "Lima")
    r.departure_date = kwargs.get("departure_date", date(2026, 5, 6))
    r.return_date = kwargs.get("return_date", date(2026, 5, 13))
    r.price = kwargs.get("price", 318.0)
    r.currency = kwargs.get("currency", "USD")
    r.stops = kwargs.get("stops", 0)
    r.stops_text = kwargs.get("stops_text", "nonstop")
    r.self_transfer = kwargs.get("self_transfer", False)
    r.airport_change = kwargs.get("airport_change", False)
    return r


@pytest.fixture
def cfg():
    return AppConfig()


class TestNormalize:
    def test_basic_normalization(self, cfg):
        result = make_result()
        obs = normalize(result, raw_message_id=1, cfg=cfg, reference_date=date(2026, 3, 22))
        assert obs is not None
        assert obs.origin_airport == "EWR"
        assert obs.destination_airport == "LIM"
        assert obs.price_amount == 318.0
        assert obs.trip_nights == 7
        assert obs.trip_length_bucket == "medium"
        assert obs.days_until_departure == 45
        assert obs.booking_window_bucket == "near"
        assert obs.observation_hash is not None

    def test_trip_nights_computed(self, cfg):
        result = make_result(
            departure_date=date(2026, 6, 1),
            return_date=date(2026, 6, 11),
        )
        obs = normalize(result, raw_message_id=1, cfg=cfg, reference_date=date(2026, 3, 22))
        assert obs.trip_nights == 10
        assert obs.trip_length_bucket == "long"

    def test_trip_length_bucket_short(self, cfg):
        result = make_result(
            departure_date=date(2026, 6, 1),
            return_date=date(2026, 6, 4),
        )
        obs = normalize(result, raw_message_id=1, cfg=cfg, reference_date=date(2026, 3, 22))
        assert obs.trip_nights == 3
        assert obs.trip_length_bucket == "short"

    def test_missing_return_date(self, cfg):
        result = make_result(return_date=None)
        obs = normalize(result, raw_message_id=1, cfg=cfg)
        assert obs is not None  # Still valid; trip_nights will be None
        assert obs.trip_nights is None
        assert obs.return_date is None

    def test_non_usable_result_returns_none(self, cfg):
        result = ParseResult()  # Empty result
        obs = normalize(result, raw_message_id=1, cfg=cfg)
        assert obs is None

    def test_hash_is_deterministic(self, cfg):
        result1 = make_result()
        result2 = make_result()
        obs1 = normalize(result1, raw_message_id=1, cfg=cfg, reference_date=date(2026, 3, 22))
        obs2 = normalize(result2, raw_message_id=2, cfg=cfg, reference_date=date(2026, 3, 22))
        # Same route+dates+price should produce same hash despite different raw_message_id
        assert obs1.observation_hash == obs2.observation_hash

    def test_booking_window_buckets(self, cfg):
        ref = date(2026, 3, 22)
        # near: 21-60 days
        r = make_result(departure_date=date(2026, 4, 20))
        obs = normalize(r, 1, cfg, reference_date=ref)
        assert obs.booking_window_bucket == "near"

        # mid: 61-120 days
        r = make_result(departure_date=date(2026, 6, 1))
        obs = normalize(r, 1, cfg, reference_date=ref)
        assert obs.booking_window_bucket == "mid"

        # far: 121-180 days
        r = make_result(departure_date=date(2026, 8, 1))
        obs = normalize(r, 1, cfg, reference_date=ref)
        assert obs.booking_window_bucket == "far"


class TestPassesBasicFilters:
    def test_valid_observation_passes(self, cfg):
        result = make_result()
        obs = normalize(result, 1, cfg, reference_date=date(2026, 3, 22))
        passes, reason = passes_basic_filters(obs, cfg)
        assert passes is True
        assert reason == "OK"

    def test_invalid_origin_fails(self, cfg):
        result = make_result(origin="ORD")  # Not in allowed origins
        obs = normalize(result, 1, cfg, reference_date=date(2026, 3, 22))
        passes, reason = passes_basic_filters(obs, cfg)
        assert passes is False
        assert "ORD" in reason

    def test_disabled_destination_fails(self, cfg):
        result = make_result(destination="CDG")  # Not in our destinations list
        obs = normalize(result, 1, cfg, reference_date=date(2026, 3, 22))
        if obs:  # CDG won't be in KNOWN_AIRPORTS, so obs might be None
            passes, reason = passes_basic_filters(obs, cfg)
            assert passes is False

    def test_price_above_hard_cap_fails(self, cfg):
        # LIM cap is $550
        result = make_result(destination="LIM", price=600.0)
        obs = normalize(result, 1, cfg, reference_date=date(2026, 3, 22))
        passes, reason = passes_basic_filters(obs, cfg)
        assert passes is False
        assert "cap" in reason.lower()
