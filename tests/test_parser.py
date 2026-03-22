"""Tests for the Google Flights email parser."""

import sys
from pathlib import Path
from datetime import date

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from flightwatch.parser_google_flights import (
    parse_email,
    build_observation_hash,
    _extract_price,
    _extract_route,
    _normalize_stops,
    _extract_dates_from_text,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


class TestPriceExtraction:
    def test_simple_dollar(self):
        assert _extract_price("round trip from $318") == 318.0

    def test_with_comma(self):
        assert _extract_price("only $1,299 RT") == 1299.0

    def test_usd_prefix(self):
        assert _extract_price("USD 450 round trip") == 450.0

    def test_no_price(self):
        assert _extract_price("no price here") is None

    def test_picks_lowest_plausible(self):
        # $45 is below the 50-floor so gets filtered; $389 is the lowest plausible price
        assert _extract_price("taxes $45 total $389 fare") == 389.0

    def test_ignores_implausibly_low(self):
        assert _extract_price("save $5 on your $12 flight") is None  # both < 50

    def test_ignores_implausibly_high(self):
        # $12000 — regex matches only up to 4 digits before a non-digit, so $1200 would be matched,
        # but 12000 as a whole exceeds 5000 and is outside plausible range.
        # The regex (?!\d) prevents partial matching: $12000 matches nothing (5 digits, blocked).
        assert _extract_price("charter for $12000") is None  # 5-digit blocked by (?!\d)


class TestRouteExtraction:
    def test_arrow_unicode(self):
        o, d = _extract_route("EWR → LIM round trip")
        assert o == "EWR"
        assert d == "LIM"

    def test_arrow_ascii(self):
        o, d = _extract_route("JFK -> BOG nonstop")
        assert o == "JFK"
        assert d == "BOG"

    def test_dash(self):
        o, d = _extract_route("LGA–MEX fare alert")
        assert o == "LGA"
        assert d == "MEX"

    def test_unknown_airport(self):
        # ZZZ is not in KNOWN_AIRPORTS
        o, d = _extract_route("EWR → ZZZ")
        assert o is None
        assert d is None

    def test_no_route(self):
        o, d = _extract_route("flight prices have changed")
        assert o is None
        assert d is None


class TestStopsNormalization:
    def test_nonstop(self):
        assert _normalize_stops("nonstop flight available") == 0

    def test_non_hyphen_stop(self):
        assert _normalize_stops("non-stop service") == 0

    def test_one_stop(self):
        assert _normalize_stops("1 stop in Bogota") == 1

    def test_two_stops(self):
        assert _normalize_stops("2 stops via MIA and BOG") == 2

    def test_unknown(self):
        assert _normalize_stops("great fare available") is None


class TestDateExtraction:
    def test_standard_dates(self):
        text = "Departs May 6, 2026 Returns May 13, 2026"
        dates = _extract_dates_from_text(text)
        assert len(dates) == 2
        assert dates[0] == date(2026, 5, 6)
        assert dates[1] == date(2026, 5, 13)

    def test_iso_dates(self):
        text = "2026-06-01 to 2026-06-08"
        dates = _extract_dates_from_text(text)
        assert date(2026, 6, 1) in dates
        assert date(2026, 6, 8) in dates

    def test_past_dates_excluded(self):
        text = "Jan 1, 2020 through Jan 8, 2020"
        dates = _extract_dates_from_text(text)
        # Past dates should be filtered out
        assert all(d >= date.today() for d in dates)


class TestFullParseHTML:
    def test_sample_email(self):
        html = load_fixture("sample_flights_email.html")
        result = parse_email(html, None, subject="Price alert: EWR to LIM")

        assert result.is_usable
        assert result.origin == "EWR"
        assert result.destination == "LIM"
        assert result.price == 318.0
        assert result.stops == 0  # nonstop
        assert result.departure_date == date(2026, 5, 6)
        assert result.return_date == date(2026, 5, 13)
        assert result.deep_link is not None
        assert "google.com/flights" in result.deep_link

    def test_partial_email(self):
        html = load_fixture("sample_flights_email_partial.html")
        result = parse_email(html, None, subject="Flight prices dropped JFK BOG")

        # Should extract price at minimum
        assert result.price == 249.0

    def test_plain_text_fallback(self):
        plain = "Price alert EWR → LIM $299 nonstop May 20, 2026 return May 27, 2026"
        result = parse_email(None, plain, subject="")
        assert result.is_usable
        assert result.origin == "EWR"
        assert result.destination == "LIM"
        assert result.price == 299.0
        assert result.stops == 0

    def test_empty_email(self):
        result = parse_email(None, None, subject="")
        assert not result.is_usable

    def test_no_crash_on_malformed_html(self):
        result = parse_email("<html><body><<<broken>>></body>", None, subject="")
        # Should not raise; result may be non-usable but won't crash
        assert result is not None


class TestObservationHash:
    def test_deterministic(self):
        h1 = build_observation_hash("EWR", "LIM", "2026-05-06", "2026-05-13", 318.0)
        h2 = build_observation_hash("EWR", "LIM", "2026-05-06", "2026-05-13", 318.0)
        assert h1 == h2

    def test_different_price_differs(self):
        h1 = build_observation_hash("EWR", "LIM", "2026-05-06", "2026-05-13", 318.0)
        h2 = build_observation_hash("EWR", "LIM", "2026-05-06", "2026-05-13", 319.0)
        assert h1 != h2

    def test_different_route_differs(self):
        h1 = build_observation_hash("EWR", "LIM", "2026-05-06", "2026-05-13", 318.0)
        h2 = build_observation_hash("JFK", "LIM", "2026-05-06", "2026-05-13", 318.0)
        assert h1 != h2

    def test_length(self):
        h = build_observation_hash("EWR", "LIM", "2026-05-06", "2026-05-13", 318.0)
        assert len(h) == 32
