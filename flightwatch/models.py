"""Lightweight dataclasses for core domain objects."""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class RawMessage:
    gmail_message_id: str
    gmail_thread_id: Optional[str]
    sender: str
    subject: str
    snippet: str
    received_at: str          # ISO datetime string
    raw_html: Optional[str]
    raw_text: Optional[str]
    parse_status: str = "pending"
    parse_error: Optional[str] = None
    processed_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class FareObservation:
    raw_message_id: Optional[int]
    source: str = "google_flights_email"
    origin_airport: Optional[str] = None
    destination_airport: Optional[str] = None
    destination_city: Optional[str] = None
    departure_date: Optional[str] = None     # ISO date string
    return_date: Optional[str] = None        # ISO date string
    trip_nights: Optional[int] = None
    trip_length_bucket: Optional[str] = None
    days_until_departure: Optional[int] = None
    booking_window_bucket: Optional[str] = None
    price_amount: Optional[float] = None
    price_currency: str = "USD"
    carrier_text: Optional[str] = None
    stops_text: Optional[str] = None
    max_stops_normalized: Optional[int] = None
    self_transfer_flag: Optional[bool] = None
    airport_change_flag: Optional[bool] = None
    deep_link: Optional[str] = None
    observation_hash: Optional[str] = None
    observed_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class ScoredDeal:
    fare_observation_id: int
    hard_cap_pass: bool = False
    price_score: float = 0.0
    priority_score: float = 0.0
    schedule_penalty: float = 0.0
    stop_penalty: float = 0.0
    airport_change_penalty: float = 0.0
    self_transfer_penalty: float = 0.0
    historical_discount_score: Optional[float] = None
    total_score: float = 0.0
    decision: str = "ignore"
    decision_reason_text: Optional[str] = None
    id: Optional[int] = None


@dataclass
class AlertRecord:
    fare_observation_id: int
    scored_deal_id: int
    alert_channel: str
    alert_type: str
    alert_key: str
    sent_success: bool = False
    sent_response_text: Optional[str] = None
    sent_at: Optional[str] = None
    id: Optional[int] = None
