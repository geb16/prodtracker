import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest

from prodtracker.api.phone import router as phone_router
from prodtracker.blocker.backup_helper import backup_hosts, restore_latest_backup
from prodtracker.blocker.manual_unblock import router as unblock_router
from prodtracker.db.models import Event
from prodtracker.db.session import SessionLocal, init_db
from prodtracker.monitor.noise_detector import background_monitor_and_block

load_dotenv()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    backup_hosts()
    threading.Thread(target=background_monitor_and_block, daemon=True).start()
    print("✅ ProdTracker background monitor started.")

    try:
        yield
    finally:
        restore_latest_backup()
        print("♻️ Hosts restored from latest backup on shutdown.")


app = FastAPI(title="ProdTracker API", version="1.0", lifespan=lifespan)

PC_IP = os.getenv("PC_IP")
# CORS: tightened for typical local dashboard use
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        f"http://{PC_IP}:8501",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(unblock_router, prefix="/blocker", tags=["Blocker"])
app.include_router(phone_router, prefix="/phone", tags=["Phone"])

# Prometheus / Grafana metrics
SNR_GAUGE = Gauge("prodtracker_snr", "Signal-to-noise ratio over recent events")


@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint (scraped by Prometheus; visualized in Grafana)."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# -------------------------------
# Metrics & recent events endpoints
# -------------------------------
@app.get("/metrics/snr")
def snr(last_minutes: int = 60):
    db = SessionLocal()
    since = datetime.utcnow() - timedelta(minutes=last_minutes)
    evs = db.query(Event).filter(Event.timestamp >= since).all()
    db.close()

    if not evs:
        SNR_GAUGE.set(0.0)
        return {"snr": None, "signal": 0, "noise": 0, "count": 0}

    signal = sum(bool(e.productive) for e in evs)
    noise = sum(not bool(e.productive) for e in evs)
    snr_value = (signal / (signal + noise)) if (signal + noise) else 0.0
    SNR_GAUGE.set(snr_value)

    return {"snr": snr_value, "signal": signal, "noise": noise, "count": len(evs)}


@app.get("/events/recent")
def recent(limit: int = 50):
    db = SessionLocal()
    events = db.query(Event).order_by(Event.timestamp.desc()).limit(limit).all()
    db.close()

    return [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat(),
            "etype": e.event_type,
            "title": e.window_title,
            "app": e.app_name,
            "prod": e.productive,
            "screenshot": e.screenshot_path,
        }
        for e in events
    ]
