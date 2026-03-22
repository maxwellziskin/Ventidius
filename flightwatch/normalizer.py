"""Normalize parsed fare data into canonical FareObservation objects."""

import logging
from datetime import date, datetime, timezone
from typing import Optional

from .config import AppConfig
from .models import FareObservation
from .parser_google_flights import ParseResult, build_observation_hash, KNOWN_AIRPORTS

logger = logging.getLogger(__name__)


def normalize(
    parse_result: ParseResult,
    raw_message_id: int,
    cfg: AppConfig,
    reference_date: Optional[date] = None,
) -> Optional[FareObservation]:
    """
    Convert a ParseResult into a FareObservation.
    Returns None if the result is not usable (missing route or price).
    """
    if not parse_result.is_usable:
        logger.debug(
            "ParseResult not usable (origin=%s dest=%s price=%s)",
            parse_result.origin,
            parse_result.destination,
            parse_result.price,
        )
        return None

    today = reference_date or date.today()

    # ── Canonical airport codes ────────────────────────────────────────────
    origin = (parse_result.origin or "").upper()
    destination = (parse_result.destination or "").upper()

    # ── Trip nights ────────────────────────────────────────────────────────
    trip_nights: Optional[int] = None
    if parse_result.departure_date and parse_result.return_date:
        delta = parse_result.return_date - parse_result.departure_date
        if delta.days > 0:
            trip_nights = delta.days

    trip_length_bucket = cfg.trip_length_bucket(trip_nights) if trip_nights else None

    # ── Days until departure ───────────────────────────────────────────────
    days_until_departure: Optional[int] = None
    if parse_result.departure_date:
        delta = parse_result.departure_date - today
        days_until_departure = max(delta.days, 0)

    booking_window_bucket = (
        cfg.booking_window_bucket(days_until_departure) if days_until_departure is not None else None
    )

    # ── Destination city ───────────────────────────────────────────────────
    destination_city = parse_result.destination_city or KNOWN_AIRPORTS.get(destination, destination)

    # ── Observation hash ───────────────────────────────────────────────────
    dep_str = parse_result.departure_date.isoformat() if parse_result.departure_date else None
    ret_str = parse_result.return_date.isoformat() if parse_result.return_date else None
    obs_hash = build_observation_hash(origin, destination, dep_str, ret_str, parse_result.price)

    obs = FareObservation(
        raw_message_id=raw_message_id,
        source="google_flights_email",
        origin_airport=origin,
        destination_airport=destination,
        destination_city=destination_city,
        departure_date=dep_str,
        return_date=ret_str,
        trip_nights=trip_nights,
        trip_length_bucket=trip_length_bucket,
        days_until_departure=days_until_departure,
        booking_window_bucket=booking_window_bucket,
        price_amount=parse_result.price,
        price_currency=parse_result.currency,
        carrier_text=parse_result.carrier,
        stops_text=parse_result.stops_text,
        max_stops_normalized=parse_result.stops,
        self_transfer_flag=parse_result.self_transfer,
        airport_change_flag=parse_result.airport_change,
        deep_link=parse_result.deep_link,
        observation_hash=obs_hash,
        observed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    return obs


def passes_basic_filters(obs: FareObservation, cfg: AppConfig) -> tuple[bool, str]:
    """
    Return (passes, reason) based on hard filters before scoring.
    """
    if obs.origin_airport not in cfg.origins:
        return False, f"Origin {obs.origin_airport} not in configured origins {cfg.origins}"

    enabled_codes = cfg.destination_airport_codes()
    if obs.destination_airport not in enabled_codes:
        return False, f"Destination {obs.destination_airport} not in enabled destinations"

    dest_cfg = cfg.destination_by_code(obs.destination_airport)
    if dest_cfg and dest_cfg.get("hard_cap_usd") and obs.price_amount:
        if obs.price_amount > dest_cfg["hard_cap_usd"]:
            return False, (
                f"Price ${obs.price_amount:.0f} exceeds hard cap "
                f"${dest_cfg['hard_cap_usd']:.0f} for {obs.destination_airport}"
            )

    if obs.max_stops_normalized is not None and obs.max_stops_normalized > cfg.max_stops:
        return False, (
            f"Stops {obs.max_stops_normalized} exceeds max_stops {cfg.max_stops}"
        )

    return True, "OK"
