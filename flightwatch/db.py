"""Database connection and schema management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS destinations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    city_name       TEXT NOT NULL,
    airport_code    TEXT NOT NULL UNIQUE,
    country         TEXT NOT NULL,
    region          TEXT NOT NULL,
    priority_weight REAL NOT NULL DEFAULT 1.0,
    hard_cap_usd    REAL,
    enabled         INTEGER NOT NULL DEFAULT 1,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS raw_messages (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_message_id    TEXT NOT NULL UNIQUE,
    gmail_thread_id     TEXT,
    sender              TEXT,
    subject             TEXT,
    snippet             TEXT,
    received_at         TEXT,
    raw_html            TEXT,
    raw_text            TEXT,
    parse_status        TEXT NOT NULL DEFAULT 'pending',
    parse_error         TEXT,
    processed_at        TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_raw_messages_parse_status ON raw_messages(parse_status);
CREATE INDEX IF NOT EXISTS idx_raw_messages_received_at ON raw_messages(received_at);

CREATE TABLE IF NOT EXISTS fare_observations (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_message_id          INTEGER REFERENCES raw_messages(id),
    source                  TEXT NOT NULL DEFAULT 'google_flights_email',
    origin_airport          TEXT,
    destination_airport     TEXT,
    destination_city        TEXT,
    departure_date          TEXT,
    return_date             TEXT,
    trip_nights             INTEGER,
    trip_length_bucket      TEXT,
    days_until_departure    INTEGER,
    booking_window_bucket   TEXT,
    price_amount            REAL,
    price_currency          TEXT NOT NULL DEFAULT 'USD',
    carrier_text            TEXT,
    stops_text              TEXT,
    max_stops_normalized    INTEGER,
    self_transfer_flag      INTEGER,
    airport_change_flag     INTEGER,
    deep_link               TEXT,
    observation_hash        TEXT UNIQUE,
    observed_at             TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_fare_obs_dest ON fare_observations(destination_airport);
CREATE INDEX IF NOT EXISTS idx_fare_obs_origin ON fare_observations(origin_airport);
CREATE INDEX IF NOT EXISTS idx_fare_obs_depart ON fare_observations(departure_date);
CREATE INDEX IF NOT EXISTS idx_fare_obs_hash ON fare_observations(observation_hash);

CREATE TABLE IF NOT EXISTS user_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name       TEXT NOT NULL UNIQUE,
    rule_type       TEXT NOT NULL,
    rule_payload_json TEXT NOT NULL,
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scored_deals (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    fare_observation_id         INTEGER NOT NULL REFERENCES fare_observations(id),
    hard_cap_pass               INTEGER NOT NULL DEFAULT 0,
    price_score                 REAL NOT NULL DEFAULT 0,
    priority_score              REAL NOT NULL DEFAULT 0,
    schedule_penalty            REAL NOT NULL DEFAULT 0,
    stop_penalty                REAL NOT NULL DEFAULT 0,
    airport_change_penalty      REAL NOT NULL DEFAULT 0,
    self_transfer_penalty       REAL NOT NULL DEFAULT 0,
    historical_discount_score   REAL,
    total_score                 REAL NOT NULL DEFAULT 0,
    decision                    TEXT NOT NULL DEFAULT 'ignore',
    decision_reason_text        TEXT,
    created_at                  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_scored_deals_obs ON scored_deals(fare_observation_id);
CREATE INDEX IF NOT EXISTS idx_scored_deals_decision ON scored_deals(decision);

CREATE TABLE IF NOT EXISTS alert_log (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    fare_observation_id     INTEGER REFERENCES fare_observations(id),
    scored_deal_id          INTEGER REFERENCES scored_deals(id),
    alert_channel           TEXT NOT NULL,
    alert_type              TEXT NOT NULL,
    alert_key               TEXT NOT NULL,
    sent_success            INTEGER NOT NULL DEFAULT 0,
    sent_response_text      TEXT,
    sent_at                 TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_alert_log_key ON alert_log(alert_key);
CREATE INDEX IF NOT EXISTS idx_alert_log_sent_at ON alert_log(sent_at);

CREATE TABLE IF NOT EXISTS route_history_summary (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    origin_airport          TEXT NOT NULL,
    destination_airport     TEXT NOT NULL,
    trip_length_bucket      TEXT NOT NULL,
    booking_window_bucket   TEXT NOT NULL,
    sample_count            INTEGER NOT NULL DEFAULT 0,
    min_price               REAL,
    median_price            REAL,
    p10_price               REAL,
    p25_price               REAL,
    last_computed_at        TEXT,
    UNIQUE(origin_airport, destination_airport, trip_length_bucket, booking_window_bucket)
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def bootstrap(db_path: str) -> None:
    """Create all tables if they don't exist."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


@contextmanager
def get_connection(db_path: str):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
