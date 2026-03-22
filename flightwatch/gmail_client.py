"""Gmail API client for fetching Google Flights alert emails."""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Only need read access to Gmail
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Heuristics to identify Google Flights price alert emails
GOOGLE_FLIGHTS_SENDERS = [
    "googleflights-noreply@google.com",
    "price-alerts@google.com",
    "noreply@google.com",
]

GOOGLE_FLIGHTS_SUBJECT_KEYWORDS = [
    "price alert",
    "fare alert",
    "flight deal",
    "prices dropped",
    "tracked flight",
    "flight prices",
    "price drop",
    "cheap flights",
]


def _build_service(credentials_path: str, client_secret_path: str):
    """Authenticate and return a Gmail API service object."""
    creds = None

    if Path(credentials_path).exists():
        creds = Credentials.from_authorized_user_file(credentials_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:
                logger.warning("Token refresh failed: %s. Re-authenticating.", exc)
                creds = None

        if not creds:
            if not Path(client_secret_path).exists():
                raise FileNotFoundError(
                    f"Gmail client secret not found at '{client_secret_path}'. "
                    "Download it from Google Cloud Console and place it there, "
                    "or set GMAIL_CLIENT_SECRET_PATH in .env."
                )
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(credentials_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


class GmailClient:
    def __init__(self, credentials_path: str, client_secret_path: str) -> None:
        self._service = _build_service(credentials_path, client_secret_path)

    def fetch_flight_alert_message_ids(
        self,
        max_results: int = 100,
        newer_than_days: int = 14,
    ) -> list[str]:
        """Return a list of message IDs likely to be Google Flights alerts."""
        query_parts = [
            f"newer_than:{newer_than_days}d",
            "(from:googleflights-noreply@google.com OR from:price-alerts@google.com "
            "OR (from:google.com subject:\"price alert\") "
            "OR subject:\"price alert\" OR subject:\"prices dropped\" "
            "OR subject:\"tracked flight\")",
        ]
        query = " ".join(query_parts)
        logger.debug("Gmail query: %s", query)

        try:
            results = (
                self._service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
        except HttpError as exc:
            logger.error("Gmail API error fetching message list: %s", exc)
            raise

        messages = results.get("messages", [])
        ids = [m["id"] for m in messages]
        logger.info("Gmail query returned %d candidate message IDs", len(ids))
        return ids

    def fetch_message(self, message_id: str) -> dict:
        """Fetch full message payload for a given message ID."""
        try:
            msg = (
                self._service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            return msg
        except HttpError as exc:
            logger.error("Gmail API error fetching message %s: %s", message_id, exc)
            raise

    @staticmethod
    def extract_sender(msg: dict) -> str:
        headers = msg.get("payload", {}).get("headers", [])
        for h in headers:
            if h["name"].lower() == "from":
                return h["value"]
        return ""

    @staticmethod
    def extract_subject(msg: dict) -> str:
        headers = msg.get("payload", {}).get("headers", [])
        for h in headers:
            if h["name"].lower() == "subject":
                return h["value"]
        return ""

    @staticmethod
    def extract_date_header(msg: dict) -> str:
        headers = msg.get("payload", {}).get("headers", [])
        for h in headers:
            if h["name"].lower() == "date":
                return h["value"]
        return ""

    @staticmethod
    def extract_body(msg: dict) -> tuple[Optional[str], Optional[str]]:
        """Return (html_body, plain_body) decoded from the message payload."""
        html_body = None
        plain_body = None

        def _decode(data: str) -> str:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

        def _walk(part: dict) -> None:
            nonlocal html_body, plain_body
            mime = part.get("mimeType", "")
            body_data = part.get("body", {}).get("data", "")

            if mime == "text/html" and body_data and html_body is None:
                html_body = _decode(body_data)
            elif mime == "text/plain" and body_data and plain_body is None:
                plain_body = _decode(body_data)

            for sub in part.get("parts", []):
                _walk(sub)

        payload = msg.get("payload", {})
        _walk(payload)
        return html_body, plain_body

    @staticmethod
    def internal_date_to_iso(internal_date_ms: str) -> str:
        """Convert Gmail internalDate (ms since epoch) to ISO datetime string."""
        import datetime
        ts = int(internal_date_ms) / 1000
        dt = datetime.datetime.utcfromtimestamp(ts)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def is_google_flights_email(self, sender: str, subject: str) -> bool:
        sender_lower = sender.lower()
        subject_lower = subject.lower()

        sender_match = any(s in sender_lower for s in GOOGLE_FLIGHTS_SENDERS)
        subject_match = any(k in subject_lower for k in GOOGLE_FLIGHTS_SUBJECT_KEYWORDS)

        return sender_match or subject_match
