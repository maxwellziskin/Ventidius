#!/usr/bin/env bash
# run_flightwatch.sh — Cron-safe wrapper for the Flightwatch Python app.
#
# Usage (manual):
#   ./scripts/run_flightwatch.sh [--dry-run] [--no-fetch]
#
# Cron example (every 30 minutes):
#   */30 * * * * /home/user/Ventidius/scripts/run_flightwatch.sh >> /home/user/Ventidius/logs/cron.log 2>&1

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${APP_DIR}/.venv"
ENV_FILE="${APP_DIR}/.env"
LOG_DIR="${APP_DIR}/logs"
LOCK_FILE="/tmp/flightwatch.lock"
LOG_FILE="${LOG_DIR}/flightwatch.log"

# ── Ensure log directory exists ───────────────────────────────────────────────
mkdir -p "$LOG_DIR"

# ── Change to app directory ───────────────────────────────────────────────────
cd "$APP_DIR"

# ── Activate virtualenv ───────────────────────────────────────────────────────
if [[ -f "${VENV_DIR}/bin/activate" ]]; then
    source "${VENV_DIR}/bin/activate"
else
    echo "[flightwatch] ERROR: virtualenv not found at ${VENV_DIR}" >&2
    echo "[flightwatch] Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi

# ── Load .env if present ──────────────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
else
    echo "[flightwatch] WARNING: .env not found at ${ENV_FILE}. Using environment variables." >&2
fi

# ── Prevent overlapping runs using flock ──────────────────────────────────────
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "[flightwatch] Another instance is running (lock held by ${LOCK_FILE}). Exiting." >&2
    exit 0
fi

# ── Run the Python application ────────────────────────────────────────────────
echo "[flightwatch] Starting run at $(date -u +%Y-%m-%dT%H:%M:%SZ)"

EXIT_CODE=0
python -m flightwatch.main "$@" 2>&1 | tee -a "$LOG_FILE" || EXIT_CODE=$?

echo "[flightwatch] Run finished at $(date -u +%Y-%m-%dT%H:%M:%SZ) with exit code ${EXIT_CODE}"

# Release lock automatically when script exits
exit "$EXIT_CODE"
