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
