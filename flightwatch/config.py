"""Configuration loader for Flightwatch."""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_settings() -> dict[str, Any]:
    return _load_yaml(CONFIG_DIR / "settings.yaml")


def load_destinations() -> list[dict[str, Any]]:
    data = _load_yaml(CONFIG_DIR / "destinations.yaml")
    return data.get("destinations", [])


# ── Secrets from environment ────────────────────────────────────────────────

def get_env(key: str, required: bool = True) -> str | None:
    val = os.getenv(key)
    if required and not val:
        raise EnvironmentError(f"Required environment variable '{key}' is not set. Check your .env file.")
    return val


class AppConfig:
    """Central config object; built once and passed around."""

    def __init__(self) -> None:
        self.settings = load_settings()
        self.destinations = load_destinations()

        # Gmail
        self.gmail_credentials_path: str = get_env("GMAIL_CREDENTIALS_PATH", required=False) or str(
            ROOT_DIR / "token_gmail.json"
        )
        self.gmail_client_secret_path: str = get_env("GMAIL_CLIENT_SECRET_PATH", required=False) or str(
            ROOT_DIR / "client_secret.json"
        )

        # Notification
        self.notification_channel: str = (
            os.getenv("NOTIFICATION_CHANNEL") or self.settings.get("notification_channel", "pushover")
        )
        self.pushover_token: str | None = os.getenv("PUSHOVER_API_TOKEN")
        self.pushover_user_key: str | None = os.getenv("PUSHOVER_USER_KEY")
        self.telegram_bot_token: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID")

        # Database
        db_path = os.getenv("FLIGHTWATCH_DB_PATH") or str(DATA_DIR / "flightwatch.sqlite")
        self.db_path: str = db_path

        # Derived settings shortcuts
        s = self.settings
        self.origins: list[str] = s.get("origins", ["EWR", "LGA", "JFK"])
        self.max_stops: int = s.get("max_stops", 1)
        self.scoring: dict[str, Any] = s.get("scoring", {})
        self.alerting: dict[str, Any] = s.get("alerting", {})
        self.history_cfg: dict[str, Any] = s.get("history", {})
        self.trip_length_buckets: dict[str, Any] = s.get("trip_length_buckets", {})
        self.booking_window_buckets: dict[str, Any] = s.get("booking_window_buckets", {})

    def destination_airport_codes(self) -> set[str]:
        return {d["airport_code"] for d in self.destinations if d.get("enabled", True)}

    def destination_by_code(self, code: str) -> dict[str, Any] | None:
        for d in self.destinations:
            if d["airport_code"].upper() == code.upper():
                return d
        return None

    def trip_length_bucket(self, nights: int) -> str | None:
        for name, bounds in self.trip_length_buckets.items():
            if bounds["min"] <= nights <= bounds["max"]:
                return name
        return None

    def booking_window_bucket(self, days_out: int) -> str | None:
        for name, bounds in self.booking_window_buckets.items():
            if bounds["min"] <= days_out <= bounds["max"]:
                return name
        return None
