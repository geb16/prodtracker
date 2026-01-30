# ProdTracker

ProdTracker is a local-first productivity monitor that combines desktop activity
tracking, phone distraction detection, and a real-time dashboard. It is designed
to run on your workstation, record signal vs. noise events, and optionally block
known distracting domains via the system hosts file.

## What it does

- Tracks active window focus and classifies activity as signal or noise.
- Logs events and optional screenshots to a local SQLite database.
- Receives mobile "heartbeat" pings and detects distracting apps.
- Exposes metrics and event data through a FastAPI service.
- Provides a Streamlit dashboard for live monitoring and controls.

## Components

- Desktop monitor: active window sampling, noise detection, optional screenshots.
- API service (FastAPI): event storage, metrics, phone pairing, and block actions.
- Phone integration: HMAC-signed heartbeats stored in Redis and rate-limited.
- Dashboard (Streamlit): real-time stats, pairing UI, and manual block actions.
- Blocker: hosts-file based domain blocking with backup/restore.

## Data flow (high level)

1. The API starts and initializes the SQLite database.
2. A background thread monitors active windows and logs events.
3. Phone heartbeats are accepted, validated, and aggregated in Redis.
4. The dashboard reads metrics and recent events from the API.
5. Optional block actions update the hosts file and record block history.

## Requirements

- Windows/macOS/Linux with permissions to edit the hosts file.
- Python 3.10+ (uses modern type hints).
- Redis (password-protected) for phone heartbeat data.
- Optional: Streamlit dashboard and Prometheus/Grafana for metrics.

## Dependencies (pinned)

This project uses a pinned dependency list for reproducible installs. See:

- `requirements.txt`

Optional packages are included but can be removed if you do not need their
features (for example, `qrcode` for QR pairing or `plyer` for desktop alerts).

## Install

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Configuration

Create a `.env` in the project root with your secrets and local settings.
Example (use your own secrets, never commit real values):

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=change-me

# Required for phone pairing JWTs
PAIRING_JWT_SECRET=change-me

# Optional admin token used by the dashboard for pairing/blocking actions
DASHBOARD_ADMIN_TOKEN=change-me

# Used for CORS when the dashboard is accessed from another device
PC_IP=192.168.0.10

# Optional override for SQLite file location (defaults to ./prodtracker.db)
PRODTRACKER_DB=prodtracker.db

# Dashboard-only (optional)
API_BASE=http://127.0.0.1:8000
```

## Running locally

1. Start the API (spawns the background monitor):

```powershell
python src/cli.py start-api
```

Note: hosts-file blocking requires elevated permissions on most systems.

2. Start the dashboard:

```powershell
cd dashboard
streamlit run streamlit_app.py
```

3. Pair a phone:
- Open the dashboard sidebar and use the "Pair phone" controls.
- Copy the generated config (device_id + secret) to the mobile client.

## Quickstart (Windows services)

The simplest local setup is three terminals (Redis, API, dashboard). If you
already run Redis as a Windows service, skip step 1.

1. Start Redis:
   - Service install (example): start the Redis service from Services.
   - Portable binary (example): run `redis-server.exe`.
2. Start the API in an elevated terminal:

```powershell
python src/cli.py start-api
```

3. Start the dashboard:

```powershell
cd dashboard
streamlit run streamlit_app.py
```

Optional: launch all three from PowerShell (edit paths as needed):

```powershell
Start-Process powershell -ArgumentList "-NoProfile -Command redis-server"
Start-Process powershell -ArgumentList "-NoProfile -Command `\"python src/cli.py start-api`\""
Start-Process powershell -ArgumentList "-NoProfile -Command `\"cd dashboard; streamlit run streamlit_app.py`\""
```

## API endpoints (examples)

Base URL (default): `http://127.0.0.1:8000`

### Metrics and events (PC)

```powershell
curl "http://127.0.0.1:8000/metrics"
curl "http://127.0.0.1:8000/metrics/snr?last_minutes=60"
curl "http://127.0.0.1:8000/events/recent?limit=50"
```

### Manual block controls (hosts file)

```powershell
curl -X POST "http://127.0.0.1:8000/blocker/manual_block"
curl -X POST "http://127.0.0.1:8000/blocker/manual_unblock"
```

### Phone pairing (admin)

```powershell
curl -X POST "http://127.0.0.1:8000/phone/pair_admin" ^
  -H "Content-Type: application/json" ^
  -H "X-Admin-Token: <DASHBOARD_ADMIN_TOKEN>" ^
  -d "{\"device_id\":\"phone-001\",\"name\":\"Android Phone\"}"
```

### Phone pairing (JWT)

```powershell
curl -X POST "http://127.0.0.1:8000/phone/pair" ^
  -H "Content-Type: application/json" ^
  -d "{\"device_id\":\"phone-001\",\"name\":\"Android Phone\",\"token\":\"<PAIRING_JWT>\"}"
```

The pairing JWT must be signed with `PAIRING_JWT_SECRET` and include a
`device_id` claim that matches the request.

### Phone heartbeat (HMAC)

```powershell
curl -X POST "http://127.0.0.1:8000/phone/heartbeat" ^
  -H "Content-Type: application/json" ^
  -d "{\"device_id\":\"phone-001\",\"timestamp\":\"2026-01-30T12:00:00Z\",\"screen_on\":true,\"foreground_app\":\"youtube\",\"signature\":\"<HMAC_HEX>\"}"
```

`signature` is an HMAC-SHA256 hex digest of the canonical JSON payload
(sorted keys, compact separators) using the per-device secret.

### Phone block now (admin token or HMAC)

```powershell
curl -X POST "http://127.0.0.1:8000/phone/block_now" ^
  -H "Content-Type: application/json" ^
  -H "X-Admin-Token: <DASHBOARD_ADMIN_TOKEN>" ^
  -d "{\"device_id\":\"phone-001\",\"duration_minutes\":30,\"reason\":\"manual\"}"
```

### Phone summary

```powershell
curl "http://127.0.0.1:8000/phone/summary?device_id=phone-001&minutes=60"
```

## Project layout

- `src/prodtracker/api`: FastAPI endpoints for desktop + phone.
- `src/prodtracker/monitor`: active window tracking and screenshots.
- `src/prodtracker/blocker`: hosts-file block/unblock helpers.
- `src/prodtracker/db`: SQLite models and session setup.
- `dashboard`: Streamlit UI and API client.
- `android_phone_client`: mobile client (if enabled).

## Security and privacy notes

- Event logs and screenshots are stored locally in `prodtracker.db` and the
  `screenshots` directory. Treat them as sensitive.
- Keep `.env` out of version control and rotate secrets if exposed.
- Hosts-file changes are backed up to `~/.pguard_backups` before modifications.

## Troubleshooting

- Redis auth errors: ensure `REDIS_PASSWORD` is set and matches the server.
- CORS errors in the dashboard: set `PC_IP` to the machine running the API.
- Permission errors when blocking domains: run the API with admin privileges.
