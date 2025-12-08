# dashboard/api_client.py

import os
import requests

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
    r = requests.post(
        f"{API_BASE}/phone/block_now",
        json={
            "device_id": device_id,
            "minutes": minutes,
            "reason": reason,
        },
        timeout=5,
    )
    r.raise_for_status()
    return r.json()
