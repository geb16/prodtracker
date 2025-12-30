# dashboard/api_client.py

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

# Load workspace .env for local dev UX (optional)
try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")


# -------------------------------
# PC (SQL-backed)
# -------------------------------


def get_pc_metrics(last_minutes: int = 60) -> dict:
    r = requests.get(
        f"{API_BASE}/metrics/snr",
        params={"last_minutes": last_minutes},
        timeout=5,
    )
    r.raise_for_status()
    return r.json()


def get_pc_events(limit: int = 30) -> list[dict]:
    r = requests.get(
        f"{API_BASE}/events/recent",
        params={"limit": limit},
        timeout=5,
    )
    r.raise_for_status()
    return r.json()


# -------------------------------
# Phone (Redis-backed)
# -------------------------------


def get_phone_summary(device_id: str, minutes: int = 60) -> dict:
    r = requests.get(
        f"{API_BASE}/phone/summary",
        params={"device_id": device_id, "minutes": minutes},
        timeout=5,
    )
    r.raise_for_status()
    return r.json()


def trigger_phone_block(device_id: str, minutes: int, reason: str) -> dict:
    admin_token = os.getenv("DASHBOARD_ADMIN_TOKEN")
    if not admin_token:
        raise RuntimeError(
            "DASHBOARD_ADMIN_TOKEN must be set to trigger blocks from the dashboard. "
            "(Set the same value in both the API and dashboard environments.)"
        )

    r = requests.post(
        f"{API_BASE}/phone/block_now",
        json={
            "device_id": device_id,
            "duration_minutes": minutes,
            "reason": reason,
        },
        headers={"X-Admin-Token": admin_token},
        timeout=5,
    )
    r.raise_for_status()
    return r.json()


def pair_phone(device_id: str, name: str) -> dict:
    admin_token = os.getenv("DASHBOARD_ADMIN_TOKEN")
    if not admin_token:
        raise RuntimeError(
            "DASHBOARD_ADMIN_TOKEN must be set to pair phones from the dashboard. " "(Set the same value in both the API and dashboard environments.)"
        )

    r = requests.post(
        f"{API_BASE}/phone/pair_admin",
        json={"device_id": device_id, "name": name},
        headers={"X-Admin-Token": admin_token},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def send_test_heartbeat(device_id: str, secret: str, screen_on: bool, foreground_app: str | None) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    unsigned_payload = {
        "device_id": device_id,
        "timestamp": timestamp,
        "screen_on": bool(screen_on),
        "foreground_app": foreground_app,
    }
    payload_bytes = json.dumps(unsigned_payload, separators=(",", ":"), sort_keys=True, default=str).encode()
    signature = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

    payload = dict(unsigned_payload)
    payload["signature"] = signature

    r = requests.post(
        f"{API_BASE}/phone/heartbeat",
        json=payload,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()
