"""Notification sender: Pushover and Telegram."""

import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

from .config import AppConfig
from .models import FareObservation, ScoredDeal, AlertRecord

logger = logging.getLogger(__name__)

PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _build_alert_key(obs: FareObservation) -> str:
    """
    A stable key representing a route/date cluster for deduplication.
    Ignores exact price so that re-alerts for same trip dates
    are caught as the same cluster.
    """
    parts = [
        obs.origin_airport or "",
        obs.destination_airport or "",
        obs.departure_date or "",
        obs.return_date or "",
    ]
    return "|".join(parts)


def _format_message(obs: FareObservation, deal: ScoredDeal) -> tuple[str, str]:
    """Return (title, body) for the notification."""
    label = deal.decision.upper().replace("_", " ")
    route = f"{obs.origin_airport} → {obs.destination_airport}"
    city = obs.destination_city or obs.destination_airport

    lines = [
        f"{label}",
        f"{route} ({city})",
    ]

    if obs.departure_date and obs.return_date:
        lines.append(f"{obs.departure_date} – {obs.return_date}")
    elif obs.departure_date:
        lines.append(f"Departs {obs.departure_date}")

    if obs.price_amount:
        lines.append(f"${obs.price_amount:.0f} RT ({obs.price_currency})")

    if obs.trip_nights:
        lines.append(f"{obs.trip_nights} nights")

    if obs.stops_text:
        lines.append(obs.stops_text.capitalize())

    if deal.decision_reason_text:
        lines.append("")
        lines.append(deal.decision_reason_text)

    if obs.deep_link:
        lines.append("")
        lines.append(obs.deep_link)

    lines.append(f"\nObs ID: {obs.id}")

    title = f"✈ {label}: {route} ${obs.price_amount:.0f}" if obs.price_amount else f"✈ {label}: {route}"
    body = "\n".join(lines)
    return title, body


def _send_pushover(token: str, user_key: str, title: str, body: str, priority: int = 0) -> tuple[bool, str]:
    try:
        resp = requests.post(
            PUSHOVER_API_URL,
            data={
                "token": token,
                "user": user_key,
                "title": title,
                "message": body,
                "priority": priority,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True, resp.text
    except requests.RequestException as exc:
        logger.error("Pushover send failed: %s", exc)
        return False, str(exc)


def _send_telegram(bot_token: str, chat_id: str, title: str, body: str) -> tuple[bool, str]:
    url = TELEGRAM_API_URL.format(token=bot_token)
    text = f"<b>{title}</b>\n\n{body}"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        resp.raise_for_status()
        return True, resp.text
    except requests.RequestException as exc:
        logger.error("Telegram send failed: %s", exc)
        return False, str(exc)


def should_suppress(
    conn: sqlite3.Connection,
    alert_key: str,
    current_price: float,
    cfg: AppConfig,
) -> tuple[bool, str]:
    """
    Return (suppress, reason) based on dedup/cooldown rules.
    """
    alerting = cfg.alerting
    cooldown_days = int(alerting.get("repeat_cooldown_days", 7))
    min_drop_usd = float(alerting.get("realert_min_drop_usd", 50))
    min_drop_frac = float(alerting.get("realert_min_drop_fraction", 0.10))

    cutoff = (datetime.now(timezone.utc) - timedelta(days=cooldown_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    recent = conn.execute(
        """
        SELECT al.sent_at, fo.price_amount
        FROM alert_log al
        JOIN fare_observations fo ON fo.id = al.fare_observation_id
        WHERE al.alert_key = ?
          AND al.sent_success = 1
          AND al.sent_at >= ?
        ORDER BY al.sent_at DESC
        LIMIT 1
        """,
        (alert_key, cutoff),
    ).fetchone()

    if not recent:
        return False, "No recent alert for this route/date cluster"

    prev_price = recent["price_amount"]
    if prev_price and prev_price > 0:
        abs_drop = prev_price - current_price
        frac_drop = abs_drop / prev_price
        threshold = min(min_drop_usd, prev_price * min_drop_frac)
        if abs_drop >= threshold:
            return False, f"Price dropped ${abs_drop:.0f} ({frac_drop*100:.0f}%) since last alert"

    return True, (
        f"Suppressed: alerted within {cooldown_days}d and price unchanged "
        f"(prev=${prev_price:.0f} now=${current_price:.0f})"
    )


def save_alert_log(
    conn: sqlite3.Connection,
    obs: FareObservation,
    deal: ScoredDeal,
    channel: str,
    alert_type: str,
    alert_key: str,
    success: bool,
    response_text: str,
) -> None:
    conn.execute(
        """
        INSERT INTO alert_log
            (fare_observation_id, scored_deal_id, alert_channel, alert_type,
             alert_key, sent_success, sent_response_text, sent_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        (obs.id, deal.id, channel, alert_type, alert_key, int(success), response_text[:2000]),
    )


def send_notification(
    obs: FareObservation,
    deal: ScoredDeal,
    cfg: AppConfig,
    conn: sqlite3.Connection,
    dry_run: bool = False,
) -> bool:
    """
    Decide whether to send a push notification and send it.
    Returns True if alert was sent (or would-be sent in dry_run).
    """
    push_on: list[str] = cfg.alerting.get("push_on", ["deal", "book_now"])

    if deal.decision not in push_on:
        logger.debug("Decision '%s' not in push_on list; skipping notification", deal.decision)
        return False

    alert_key = _build_alert_key(obs)
    suppress, suppress_reason = should_suppress(conn, alert_key, obs.price_amount or 0, cfg)

    if suppress:
        logger.info(
            "Alert suppressed for obs_id=%s key=%s: %s",
            obs.id, alert_key, suppress_reason,
        )
        save_alert_log(conn, obs, deal, cfg.notification_channel, "suppressed", alert_key, False, suppress_reason)
        return False

    title, body = _format_message(obs, deal)

    if dry_run:
        logger.info("[DRY RUN] Would send %s notification:\nTitle: %s\nBody:\n%s", cfg.notification_channel, title, body)
        save_alert_log(conn, obs, deal, cfg.notification_channel, "dry_run", alert_key, True, "dry_run")
        return True

    channel = cfg.notification_channel
    success = False
    response_text = ""
    priority = 1 if deal.decision == "book_now" else 0

    if channel == "pushover":
        if cfg.pushover_token and cfg.pushover_user_key:
            success, response_text = _send_pushover(
                cfg.pushover_token, cfg.pushover_user_key, title, body, priority=priority
            )
        else:
            logger.warning("Pushover tokens not configured; cannot send notification")
            response_text = "Pushover tokens not configured"
    elif channel == "telegram":
        if cfg.telegram_bot_token and cfg.telegram_chat_id:
            success, response_text = _send_telegram(
                cfg.telegram_bot_token, cfg.telegram_chat_id, title, body
            )
        else:
            logger.warning("Telegram tokens not configured; cannot send notification")
            response_text = "Telegram tokens not configured"
    else:
        logger.error("Unknown notification channel: %s", channel)
        response_text = f"Unknown channel: {channel}"

    save_alert_log(conn, obs, deal, channel, deal.decision, alert_key, success, response_text)

    if success:
        logger.info(
            "Notification sent for obs_id=%s %s->%s $%.0f decision=%s",
            obs.id, obs.origin_airport, obs.destination_airport, obs.price_amount or 0, deal.decision,
        )
    else:
        logger.warning(
            "Notification FAILED for obs_id=%s: %s",
            obs.id, response_text,
        )

    return success
