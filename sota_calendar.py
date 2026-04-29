#!/usr/bin/env python3
"""
SOTA Calendar Integration
Queries the SOTA Alerts API, finds W7M activations and watched activator
alerts, and syncs them to a shared Google Calendar via a service account.
Meant to be run every 15 minutes via cron or a systemd timer.
"""

import json
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ─── Configuration ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
SERVICE_ACCOUNT_FILE = BASE_DIR / "service_account.json"
ACTIVATORS_FILE      = BASE_DIR / "activators.json"
PROCESSED_FILE       = BASE_DIR / "processed_alerts.json"
LOG_FILE             = BASE_DIR / "sota_calendar.log"

CALENDAR_ID        = "ba91ce3870fbaf183101b5f110b3148d521cd6df57b2ae3a83f5cd143c16cf7b@group.calendar.google.com"
TARGET_ASSOCIATION = "W7M"
LOCAL_TZ           = ZoneInfo("America/Denver")  # Montana — auto handles MDT/MST
ALERT_WINDOW_DAYS  = 274                          # ~9 months
SOTA_API_URL       = "https://api2.sota.org.uk/api/alerts"
SCOPES             = ["https://www.googleapis.com/auth/calendar"]
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ─── Data helpers ─────────────────────────────────────────────────────────────

def load_activators() -> set:
    """Return the set of uppercase callsigns to watch outside W7M."""
    if not ACTIVATORS_FILE.exists():
        log.warning(f"{ACTIVATORS_FILE} not found — no activators being watched.")
        return set()
    with open(ACTIVATORS_FILE) as f:
        data = json.load(f)
    return {c.upper() for c in data.get("callsigns", [])}


def load_processed() -> dict:
    if not PROCESSED_FILE.exists():
        return {}
    with open(PROCESSED_FILE) as f:
        return json.load(f)


def save_processed(processed: dict) -> None:
    with open(PROCESSED_FILE, "w") as f:
        json.dump(processed, f, indent=2)


def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def fetch_alerts() -> list:
    try:
        resp = requests.get(SOTA_API_URL, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            log.error("Unexpected response format from SOTA API")
            return []
        return data
    except Exception as e:
        log.error(f"Failed to fetch SOTA alerts: {e}")
        return []


def parse_summit_name(summit_details: str) -> str:
    """'Mount Jumbo, 1453m, 1 pt'  →  'Mount Jumbo'"""
    return summit_details.split(",")[0].strip()


def normalize_callsign(callsign: str) -> str:
    """Strip portable suffix: KK7SDH/P → KK7SDH, JH0ROI/0 → JH0ROI."""
    return re.sub(r"/[A-Z0-9]+$", "", callsign.upper())


def parse_utc(date_str: str) -> datetime:
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ─── Calendar event builder ───────────────────────────────────────────────────

def build_event_body(alert: dict, is_watch: bool) -> dict:
    assoc        = alert["associationCode"]
    summit_local = alert["summitCode"]        # e.g. "LM-175"
    full_summit  = f"{assoc}/{summit_local}"  # e.g. "W7M/LM-175"
    details      = alert["summitDetails"]     # e.g. "Mount Jumbo, 1453m, 1 pt"
    summit_name  = parse_summit_name(details)
    callsign     = alert["activatingCallsign"]
    frequencies  = alert.get("frequency", "")
    comments     = alert.get("comments", "")

    if is_watch:
        title = f"[WATCH] {full_summit} ({callsign}) - {summit_name}"
    else:
        # Drop the redundant "W7M/" from the title for local alerts
        title = f"{summit_local} ({callsign}) - {summit_name}"

    start_utc   = parse_utc(alert["dateActivated"])
    end_utc     = start_utc + timedelta(hours=1)
    start_local = start_utc.astimezone(LOCAL_TZ)
    tz_abbr     = start_local.strftime("%Z")  # "MDT" or "MST"

    local_time_str = start_local.strftime(f"%Y-%m-%d %H:%M {tz_abbr}")
    utc_time_str   = start_utc.strftime("%Y-%m-%d %H:%M UTC")
    sotlas_url     = f"https://sotl.as/summits/{full_summit}"

    description = (
        f"SOTA Activation Alert\n\n"
        f"Summit: {full_summit}\n"
        f"Details: {details}\n"
        f"Activator: {callsign}\n"
        f"SOTLAS: {sotlas_url}\n\n"
        f"Local Time: {local_time_str}\n"
        f"UTC Time: {utc_time_str}\n"
        f"Frequency: {frequencies}\n"
        f"Comments: {comments}\n"
        f"W7M - SOTA Alerts"
    )

    return {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_utc.isoformat(), "timeZone": "America/Denver"},
        "end":   {"dateTime": end_utc.isoformat(),   "timeZone": "America/Denver"},
        "reminders": {"useDefault": False},
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def process_alerts() -> None:
    log.info("=== SOTA Calendar sync started ===")
    watched   = load_activators()
    processed = load_processed()
    alerts    = fetch_alerts()

    if not alerts:
        log.warning("No alerts returned from API — aborting.")
        return

    now     = datetime.now(timezone.utc)
    cutoff  = now + timedelta(days=ALERT_WINDOW_DAYS)
    service = get_calendar_service()
    changes = 0
    seen_ids = set()

    for alert in alerts:
        alert_id = str(alert["id"])

        try:
            activation_dt = parse_utc(alert["dateActivated"])
        except (ValueError, KeyError) as e:
            log.warning(f"Skipping alert {alert_id} — bad date: {e}")
            continue

        # Only process future alerts within the 9-month window
        if activation_dt < now or activation_dt > cutoff:
            continue

        assoc    = alert["associationCode"]
        callsign = alert["activatingCallsign"].upper()
        base_cs  = normalize_callsign(callsign)

        is_w7m    = (assoc == TARGET_ASSOCIATION)
        is_watched = (callsign in watched or base_cs in watched)

        if not is_w7m and not is_watched:
            continue

        # Watched activators inside W7M get normal W7M treatment (no [WATCH])
        is_watch = is_watched and not is_w7m

        seen_ids.add(alert_id)
        timestamp = alert.get("timeStamp", "")
        record    = processed.get(alert_id)

        # Skip if we already handled this exact version of the alert
        if record and record.get("timeStamp") == timestamp:
            continue

        event_body = build_event_body(alert, is_watch=is_watch)

        try:
            if record and record.get("gcal_event_id"):
                # Alert was edited — update the existing calendar event
                gcal_id = record["gcal_event_id"]
                service.events().update(
                    calendarId=CALENDAR_ID,
                    eventId=gcal_id,
                    body=event_body,
                ).execute()
                log.info(f"Updated  [{alert_id}] {event_body['summary']}")
            else:
                # New alert — create a calendar event
                created = service.events().insert(
                    calendarId=CALENDAR_ID,
                    body=event_body,
                ).execute()
                gcal_id = created["id"]
                log.info(f"Created  [{alert_id}] {event_body['summary']}")

            processed[alert_id] = {
                "gcal_event_id": gcal_id,
                "timeStamp": timestamp,
                "summary": event_body["summary"],
            }
            changes += 1

        except HttpError as e:
            log.error(f"Calendar API error for alert {alert_id}: {e}")

    # Prune records for alerts that are no longer in the API feed
    for k in [k for k in processed if k not in seen_ids]:
        del processed[k]

    save_processed(processed)
    log.info(f"=== Done. {changes} event(s) created/updated. ===")


if __name__ == "__main__":
    process_alerts()
