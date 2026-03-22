# Flightwatch

Personal flight-deal alert system. Monitors Google Flights price-alert emails for cheap round-trip fares from EWR, LGA, and JFK to destinations in Mexico and South America. Sends push notifications only for high-signal deals.

## How it works

```
cron (every 30 min)
  → scripts/run_flightwatch.sh
    → python -m flightwatch.main
      → Gmail API: fetch Google Flights alert emails
      → Parser: extract route, dates, price, stops
      → Normalizer: canonical form, trip/booking buckets
      → Scorer: rules + historical baselines → decision
      → Notifier: push alert (Pushover or Telegram) if deal qualifies
      → SQLite: full audit trail of every decision
```

**No booking. No paid fare APIs. Near-zero recurring cost.**

---

## Quick setup

### 1. Clone and create virtualenv

```bash
git clone <repo>
cd Ventidius
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use existing)
3. Enable the **Gmail API**
4. Create **OAuth 2.0 credentials** → Desktop app
5. Download the JSON and save as `client_secret.json` in the repo root
6. Run bootstrap (this will trigger OAuth flow in your browser on first run):
   ```bash
   python scripts/bootstrap_db.py
   ```

### 3. Configure notifications

**Pushover** (recommended):
1. Create account at [pushover.net](https://pushover.net)
2. Note your **User Key**
3. Create an application → note the **API Token**

**Telegram** (alternative):
1. Message [@BotFather](https://t.me/botfather) → `/newbot`
2. Note the bot token
3. Get your chat ID: message your bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates`

### 4. Set up .env

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 5. Configure destinations and rules

Edit `config/destinations.yaml` to adjust:
- `hard_cap_usd`: your max price for each destination
- `priority_weight`: higher = preferred destination
- `enabled`: set `false` to pause a destination

Edit `config/settings.yaml` to adjust:
- Scoring bonuses/penalties
- Alert thresholds
- Notification cooldown rules

### 6. Dry run

```bash
python -m flightwatch.main --dry-run
```

This processes any stored messages and prints what notifications *would* be sent, without actually sending them.

### 7. Install cron

```bash
crontab -e
```

Add (every 30 minutes):
```
*/30 * * * * /home/user/Ventidius/scripts/run_flightwatch.sh >> /home/user/Ventidius/logs/cron.log 2>&1
```

### 8. Test notification

```bash
# Send a test Pushover notification
python -c "
import requests, os
from dotenv import load_dotenv
load_dotenv()
requests.post('https://api.pushover.net/1/messages.json', data={
  'token': os.getenv('PUSHOVER_API_TOKEN'),
  'user': os.getenv('PUSHOVER_USER_KEY'),
  'title': 'Flightwatch test',
  'message': 'Setup working!'
})
"
```

---

## CLI reference

| Command | Description |
|---------|-------------|
| `python -m flightwatch.main` | Full pipeline run |
| `python -m flightwatch.main --dry-run` | Parse + score without sending notifications |
| `python -m flightwatch.main --no-fetch` | Process stored messages only (skip Gmail) |
| `python -m flightwatch.main --verbose` | Debug-level logging |
| `python scripts/bootstrap_db.py` | Create schema + seed destinations |
| `python scripts/reparse_messages.py --all-failed` | Retry all failed/partial parses |
| `python scripts/reparse_messages.py --message-id 42` | Reparse specific DB row |
| `python scripts/reparse_messages.py --gmail-id <id>` | Reparse by Gmail message ID |
| `python scripts/reparse_messages.py --all` | Reparse everything |
| `python scripts/recompute_scores.py` | Score unscored observations |
| `python scripts/recompute_scores.py --all` | Recompute all scores |
| `python scripts/list_deals.py` | List recent deals |
| `python scripts/list_deals.py --decision deal --days 30` | Filter by decision and timeframe |
| `python scripts/list_deals.py --export deals.csv` | Export to CSV |

---

## Scoring explained

Every fare observation is scored 0-100+:

| Component | Effect |
|-----------|--------|
| Destination priority weight | +10 x weight |
| Price below hard cap | +0 to +30 (proportional) |
| Nonstop | +15 bonus |
| 1 stop | -5 |
| 2+ stops | -25 |
| Self-transfer | -40 |
| Airport change | -30 |
| Outside booking/trip-length window | -5 to -10 |
| Historical discount (20%+ below median) | +12 |
| Historical discount (30%+ below median) | +25 |

**Decision thresholds** (configurable in `settings.yaml`):

| Score | Decision | Push notification |
|-------|----------|-------------------|
| < 30 | ignore | No |
| 30-54 | watch | No (logged only) |
| 55-74 | deal | Yes |
| 75+ | book_now | Yes (high priority) |

---

## Google Flights email setup

1. Search for a route on [Google Flights](https://flights.google.com)
2. Click **Track prices** (the bell icon)
3. Sign in with the Google account whose Gmail you configured
4. Google will email you when prices change

The system processes these emails automatically.

---

## Project structure

```
flightwatch/           Python package
  config.py            Config loader
  db.py                SQLite schema + connection
  models.py            Domain dataclasses
  gmail_client.py      Gmail API client
  message_store.py     Raw message persistence
  parser_google_flights.py  Email parser
  normalizer.py        Canonical form + filters
  observation_store.py Fare observation persistence
  scorer.py            Scoring + decision engine
  notifier.py          Push notification sender
  history.py           Route baseline computation
  main.py              Entrypoint + pipeline orchestration

scripts/
  run_flightwatch.sh   Cron-safe bash wrapper
  bootstrap_db.py      Schema creation + destination seeding
  reparse_messages.py  Replay stored emails through parser
  recompute_scores.py  Re-score stored observations
  list_deals.py        Browse + export deals

config/
  destinations.yaml    Tracked destinations with caps
  settings.yaml        Scoring rules + alerting config

data/
  flightwatch.sqlite   (gitignored)

logs/
  flightwatch.log      (gitignored)

tests/
  test_parser.py
  test_scorer.py
  test_normalizer.py
  test_dedup.py
  fixtures/            Sample emails for testing
```

---

## Running tests

```bash
pytest tests/ -v
pytest tests/ --cov=flightwatch --cov-report=term-missing
```

---

## Failure recovery

- **Parser failures**: raw email kept in DB with `parse_status='failed'`. Fix parser then: `python scripts/reparse_messages.py --all-failed`
- **Gmail auth failure**: delete `token_gmail.json` and re-run to trigger fresh OAuth
- **Notification failure**: logged in `alert_log` table; pipeline continues
- **Duplicate runs**: bash wrapper uses `flock` to prevent overlapping cron runs
