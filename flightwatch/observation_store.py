"""Store and retrieve FareObservation records."""

import logging
import sqlite3
from typing import Optional

from .models import FareObservation

logger = logging.getLogger(__name__)


def insert_observation(conn: sqlite3.Connection, obs: FareObservation) -> Optional[int]:
    """
    Insert a FareObservation. Returns new row id or None if hash already exists.
    """
    if obs.observation_hash:
        existing = conn.execute(
            "SELECT id FROM fare_observations WHERE observation_hash = ?",
            (obs.observation_hash,),
        ).fetchone()
        if existing:
            logger.debug("Observation with hash %s already exists (id=%d)", obs.observation_hash, existing["id"])
            return None

    cursor = conn.execute(
        """
        INSERT INTO fare_observations
            (raw_message_id, source, origin_airport, destination_airport, destination_city,
             departure_date, return_date, trip_nights, trip_length_bucket,
             days_until_departure, booking_window_bucket,
             price_amount, price_currency, carrier_text, stops_text,
             max_stops_normalized, self_transfer_flag, airport_change_flag,
             deep_link, observation_hash, observed_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            obs.raw_message_id,
            obs.source,
            obs.origin_airport,
            obs.destination_airport,
            obs.destination_city,
            obs.departure_date,
            obs.return_date,
            obs.trip_nights,
            obs.trip_length_bucket,
            obs.days_until_departure,
            obs.booking_window_bucket,
            obs.price_amount,
            obs.price_currency,
            obs.carrier_text,
            obs.stops_text,
            obs.max_stops_normalized,
            int(obs.self_transfer_flag) if obs.self_transfer_flag is not None else None,
            int(obs.airport_change_flag) if obs.airport_change_flag is not None else None,
            obs.deep_link,
            obs.observation_hash,
            obs.observed_at,
        ),
    )
    row_id = cursor.lastrowid
    logger.debug(
        "Inserted observation id=%d %s->%s $%.0f",
        row_id,
        obs.origin_airport,
        obs.destination_airport,
        obs.price_amount or 0,
    )
    return row_id


def get_observation_by_id(conn: sqlite3.Connection, obs_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM fare_observations WHERE id = ?", (obs_id,)).fetchone()


def row_to_observation(row: sqlite3.Row) -> FareObservation:
    return FareObservation(
        id=row["id"],
        raw_message_id=row["raw_message_id"],
        source=row["source"],
        origin_airport=row["origin_airport"],
        destination_airport=row["destination_airport"],
        destination_city=row["destination_city"],
        departure_date=row["departure_date"],
        return_date=row["return_date"],
        trip_nights=row["trip_nights"],
        trip_length_bucket=row["trip_length_bucket"],
        days_until_departure=row["days_until_departure"],
        booking_window_bucket=row["booking_window_bucket"],
        price_amount=row["price_amount"],
        price_currency=row["price_currency"],
        carrier_text=row["carrier_text"],
        stops_text=row["stops_text"],
        max_stops_normalized=row["max_stops_normalized"],
        self_transfer_flag=bool(row["self_transfer_flag"]) if row["self_transfer_flag"] is not None else None,
        airport_change_flag=bool(row["airport_change_flag"]) if row["airport_change_flag"] is not None else None,
        deep_link=row["deep_link"],
        observation_hash=row["observation_hash"],
        observed_at=row["observed_at"],
    )
