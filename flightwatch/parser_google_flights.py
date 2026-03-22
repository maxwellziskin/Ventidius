"""Parser for Google Flights price-alert emails.

Tries HTML first, falls back to plain text. Uses multiple regex patterns
so partial extractions survive format changes.
"""

import hashlib
import logging
import re
from datetime import datetime, date
from typing import Optional

from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

# ── Airport / city lookup  ──────────────────────────────────────────────────
# Expand as needed; used to validate extracted codes and map city names
KNOWN_AIRPORTS: dict[str, str] = {
    # Origins
    "EWR": "Newark",
    "LGA": "LaGuardia",
    "JFK": "John F. Kennedy",
    # Mexico
    "MEX": "Mexico City",
    "CUN": "Cancun",
    "OAX": "Oaxaca",
    "PVR": "Puerto Vallarta",
    "GDL": "Guadalajara",
    "MTY": "Monterrey",
    "SJD": "Los Cabos",
    "ZIH": "Ixtapa/Zihuatanejo",
    "MZT": "Mazatlan",
    # South America
    "BOG": "Bogota",
    "MDE": "Medellin",
    "CTG": "Cartagena",
    "LIM": "Lima",
    "CUZ": "Cusco",
    "EZE": "Buenos Aires",
    "AEP": "Buenos Aires",
    "SCL": "Santiago",
    "GIG": "Rio de Janeiro",
    "GRU": "Sao Paulo",
    "UIO": "Quito",
    "GYE": "Guayaquil",
    "MVD": "Montevideo",
    "ASU": "Asuncion",
    "VVI": "Santa Cruz",
    "LPB": "La Paz",
    "CCS": "Caracas",
    "PMV": "Porlamar",
}

CITY_TO_AIRPORT: dict[str, str] = {v.lower(): k for k, v in KNOWN_AIRPORTS.items()}

# Regex patterns ─────────────────────────────────────────────────────────────
# Airport code: 3 uppercase letters surrounded by word boundaries or parens
RE_AIRPORT_CODE = re.compile(r"\b([A-Z]{3})\b")

# Price patterns: $NNN or $N,NNN or USD NNN
RE_PRICE = re.compile(
    r"(?:USD\s*|US\$\s*|\$\s*)(\d{1,4}(?:,\d{3})?(?:\.\d{1,2})?)(?!\d)", re.IGNORECASE
)

# Date patterns (various formats)
_DATE_PATTERNS = [
    r"\b(\w{3}\s+\d{1,2}(?:,\s+\d{4})?)\b",          # Jan 5 or Jan 5, 2025
    r"\b(\d{1,2}\s+\w{3}(?:\s+\d{4})?)\b",            # 5 Jan or 5 Jan 2025
    r"\b(\d{4}-\d{2}-\d{2})\b",                        # ISO date
    r"\b(\w+\s+\d{1,2}–\d{1,2},\s+\d{4})\b",          # March 5–12, 2025
]
RE_DATES = [re.compile(p, re.IGNORECASE) for p in _DATE_PATTERNS]

# Route arrow patterns: EWR → LIM, EWR -> LIM, EWR–LIM, EWR to LIM
RE_ROUTE = re.compile(
    r"\b([A-Z]{3})\s*(?:→|->|–|to)\s*([A-Z]{3})\b", re.IGNORECASE
)

# Stop indicators
RE_NONSTOP = re.compile(r"nonstop|non-stop|direct", re.IGNORECASE)
RE_ONE_STOP = re.compile(r"\b1\s*stop\b|one\s*stop", re.IGNORECASE)
RE_TWO_STOP = re.compile(r"\b2\s*stops?\b|two\s*stops?", re.IGNORECASE)

# Self-transfer indicators
RE_SELF_TRANSFER = re.compile(r"self.?transfer|self.?connect|book separately", re.IGNORECASE)
RE_AIRPORT_CHANGE = re.compile(
    r"change\s+airport|different\s+airport|airport\s+change|terminal\s+change", re.IGNORECASE
)

# Deep link
RE_DEEP_LINK = re.compile(r"https?://(?:www\.)?(?:google\.com/flights|flights\.google\.com)[^\s\"'<>]+")


def _clean_text(text: str) -> str:
    """Normalize whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # Remove script/style tags
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator=" ")


def _extract_airport_codes(text: str) -> list[str]:
    candidates = RE_AIRPORT_CODE.findall(text)
    return [c for c in candidates if c in KNOWN_AIRPORTS]


def _extract_route(text: str) -> tuple[Optional[str], Optional[str]]:
    """Try to extract (origin, destination) from route arrow patterns."""
    for m in RE_ROUTE.finditer(text):
        orig = m.group(1).upper()
        dest = m.group(2).upper()
        if orig in KNOWN_AIRPORTS and dest in KNOWN_AIRPORTS:
            return orig, dest
    return None, None


def _extract_price(text: str) -> Optional[float]:
    matches = RE_PRICE.findall(text)
    prices = []
    for raw in matches:
        try:
            prices.append(float(raw.replace(",", "")))
        except ValueError:
            pass
    if not prices:
        return None
    # Heuristic: the lowest plausible airfare (not taxes alone, not absurdly high)
    plausible = [p for p in prices if 50 <= p <= 5000]
    return min(plausible) if plausible else None


def _parse_date(text: str) -> Optional[date]:
    """Try to parse a date string into a date object."""
    try:
        return dateutil_parser.parse(text, default=datetime(datetime.now().year, 1, 1)).date()
    except (ValueError, OverflowError):
        return None


def _extract_dates_from_text(text: str) -> list[date]:
    found: list[date] = []
    for pattern in RE_DATES:
        for m in pattern.finditer(text):
            d = _parse_date(m.group(1))
            if d and d not in found:
                found.append(d)
    # Keep only future or near-future dates
    today = date.today()
    found = [d for d in found if d >= today]
    found.sort()
    return found


def _normalize_stops(text: str) -> Optional[int]:
    if RE_NONSTOP.search(text):
        return 0
    if RE_ONE_STOP.search(text):
        return 1
    if RE_TWO_STOP.search(text):
        return 2
    return None


def _extract_deep_link(html: str) -> Optional[str]:
    m = RE_DEEP_LINK.search(html)
    return m.group(0) if m else None


def _extract_deep_link_from_soup(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "google.com/flights" in href or "flights.google.com" in href:
            return href
    return None


# ── Main parse function ──────────────────────────────────────────────────────

class ParseResult:
    """Result of parsing one email. Can be partial."""

    def __init__(self) -> None:
        self.origin: Optional[str] = None
        self.destination: Optional[str] = None
        self.destination_city: Optional[str] = None
        self.departure_date: Optional[date] = None
        self.return_date: Optional[date] = None
        self.price: Optional[float] = None
        self.currency: str = "USD"
        self.carrier: Optional[str] = None
        self.stops: Optional[int] = None
        self.stops_text: Optional[str] = None
        self.self_transfer: Optional[bool] = None
        self.airport_change: Optional[bool] = None
        self.deep_link: Optional[str] = None
        self.warnings: list[str] = []

    @property
    def is_usable(self) -> bool:
        """True if we have at minimum route + price."""
        return bool(self.origin and self.destination and self.price)

    def __repr__(self) -> str:
        return (
            f"ParseResult({self.origin}->{self.destination} "
            f"dep={self.departure_date} ret={self.return_date} "
            f"${self.price} stops={self.stops})"
        )


def parse_email(raw_html: Optional[str], raw_text: Optional[str], subject: str = "") -> ParseResult:
    """
    Attempt to parse a Google Flights alert email.
    Returns a ParseResult (possibly partial). Never raises.
    """
    result = ParseResult()

    # Build working text from best available source
    if raw_html:
        text = _clean_text(_html_to_text(raw_html))
    elif raw_text:
        text = _clean_text(raw_text)
    else:
        text = subject

    full_text = f"{subject} {text}"

    # ── Route extraction ───────────────────────────────────────────────────
    origin, dest = _extract_route(full_text)
    if origin:
        result.origin = origin
        result.destination = dest
        result.destination_city = KNOWN_AIRPORTS.get(dest, dest)
    else:
        # Fallback: extract individual airport codes and guess
        codes = _extract_airport_codes(full_text)
        if len(codes) >= 2:
            result.warnings.append(f"Route arrow not found; guessing from codes: {codes}")
            # Assume first known origin, next as dest
            from_codes = [c for c in codes if c in ("EWR", "LGA", "JFK")]
            dest_codes = [c for c in codes if c not in ("EWR", "LGA", "JFK")]
            if from_codes and dest_codes:
                result.origin = from_codes[0]
                result.destination = dest_codes[0]
                result.destination_city = KNOWN_AIRPORTS.get(result.destination, result.destination)

    # ── Price extraction ───────────────────────────────────────────────────
    result.price = _extract_price(full_text)
    if not result.price:
        result.warnings.append("Could not extract price")

    # ── Date extraction ────────────────────────────────────────────────────
    dates = _extract_dates_from_text(full_text)
    if len(dates) >= 2:
        result.departure_date = dates[0]
        result.return_date = dates[1]
    elif len(dates) == 1:
        result.departure_date = dates[0]
        result.warnings.append("Only one date found; return date missing")

    # ── Stops ─────────────────────────────────────────────────────────────
    result.stops = _normalize_stops(full_text)
    # Build stops_text for storage
    if RE_NONSTOP.search(full_text):
        result.stops_text = "nonstop"
    elif RE_ONE_STOP.search(full_text):
        result.stops_text = "1 stop"
    elif RE_TWO_STOP.search(full_text):
        result.stops_text = "2 stops"

    # ── Special flags ──────────────────────────────────────────────────────
    result.self_transfer = bool(RE_SELF_TRANSFER.search(full_text))
    result.airport_change = bool(RE_AIRPORT_CHANGE.search(full_text))

    # ── Deep link ─────────────────────────────────────────────────────────
    if raw_html:
        result.deep_link = _extract_deep_link_from_soup(raw_html) or _extract_deep_link(raw_html)

    return result


def build_observation_hash(
    origin: Optional[str],
    destination: Optional[str],
    departure_date: Optional[str],
    return_date: Optional[str],
    price: Optional[float],
    source: str = "google_flights_email",
) -> str:
    """Deterministic hash for deduplication."""
    parts = [
        str(origin or ""),
        str(destination or ""),
        str(departure_date or ""),
        str(return_date or ""),
        str(round(price or 0)),
        source,
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
