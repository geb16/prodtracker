"""Phone device integration API routes.

Uses:
- Redis for heartbeat windows and rate limiting
- HMAC-SHA256 for heartbeat integrity
- JWT for secure device pairing
- Prometheus metrics for observability
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Annotated, Dict, Iterator, List, Optional

import jwt
import redis
from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from jwt import InvalidTokenError
from prometheus_client import Counter
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.prodtracker.blocker.hosts_blocker import block_domains, unblock_all
from src.prodtracker.db.models import BlockRecord, Device, Event
from src.prodtracker.db.session import SessionLocal

load_dotenv()

# Optional scheduler (gracefully degraded if missing)
try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:  # pragma: no cover - environment fallback

    class BackgroundScheduler:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

        def start(self) -> None:
            pass

        def add_job(self, *args, **kwargs):
            return None


logger = logging.getLogger(__name__)

router = APIRouter()
sched = BackgroundScheduler()
sched.start()

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

if not REDIS_PASSWORD:
    raise RuntimeError("REDIS_PASSWORD environment variable must be set for authenticated Redis.")

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
    socket_timeout=5,
    health_check_interval=30,
)

# Optional: fail fast if auth is wrong
try:
    redis_client.ping()
    logger.info("✅ Connected to Redis at %s:%s db=%s", REDIS_HOST, REDIS_PORT, REDIS_DB)
except Exception as e:
    logger.error("❌ Redis connection failed: %r", e)
    raise


PAIRING_JWT_SECRET = os.getenv("PAIRING_JWT_SECRET")
if not PAIRING_JWT_SECRET:
    raise RuntimeError("PAIRING_JWT_SECRET environment variable must be set for secure pairing JWTs.")

PAIRING_JWT_ALG = "HS256"

DISTRACTING_KEYWORDS: List[str] = [
    "youtube",
    "tiktok",
    "shorts",
    "instagram",
    "reddit",
    "facebook",
    "netflix",
    "hulu",
    "disneyplus",
    "twitter",
    "x",
    "linkedin",
    "discord",
    "instagram",
]
DISTRACTION_THRESHOLD: int = 3
HEARTBEAT_WINDOW_SECONDS: int = 60 * 5

BLOCK_DOMAINS_DEFAULT: List[str] = [
    "youtube.com",
    "m.youtube.com",
    "tiktok.com",
    "www.reddit.com",
    "x.com",
    "twitter.com",
    "www.instagram.com",
    "instagram.com",
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "www.linkedin.com",
    "linkedin.com",
    "netflix.com",
    "www.netflix.com",
    "www.hulu.com",
    "hulu.com",
    "www.disneyplus.com",
    "disneyplus.com",
]

# Heartbeat rate limiting (per device)
HEARTBEAT_RATE_LIMIT: int = 60  # max requests
HEARTBEAT_RATE_WINDOW_SECONDS: int = 60  # per this many seconds

# Prometheus metrics
HEARTBEAT_TOTAL = Counter(
    "prodtracker_heartbeat_total",
    "Total number of heartbeats received",
    ["device_id"],
)
BLOCK_APPLIED_TOTAL = Counter(
    "prodtracker_block_applied_total",
    "Total number of mobile distraction blocks applied",
)


# -------------------------------------------------------------------
# DB dependency
# -------------------------------------------------------------------
def get_db() -> Iterator[Session]:
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------------------------------------------------
# Crypto helpers
# -------------------------------------------------------------------
def verify_hmac(secret: str, body: bytes, signature_hex: str) -> bool:
    """Verify HMAC-SHA256 signature of request body."""
    mac = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, signature_hex)


def enforce_heartbeat_rate_limit(device_id: str) -> None:
    """
    Simple Redis sliding window rate limit:
    - key: rl:hb:{device_id}
    - limit: HEARTBEAT_RATE_LIMIT per HEARTBEAT_RATE_WINDOW_SECONDS
    """
    key = f"rl:hb:{device_id}"
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, HEARTBEAT_RATE_WINDOW_SECONDS)
    if count > HEARTBEAT_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many heartbeats; slow down.",
        )


def store_heartbeat_in_redis(hb: "Heartbeat") -> None:
    """
    Store heartbeat in a Redis sorted set:
    - key: hb:{device_id}
    - score: timestamp
    - member: JSON payload
    Older entries beyond HEARTBEAT_WINDOW_SECONDS are pruned.
    """
    key = f"hb:{hb.device_id}"
    ts = hb.timestamp.timestamp() if isinstance(hb.timestamp, datetime) else datetime.utcnow().timestamp()
    entry = {
        "ts": ts,
        "screen_on": bool(hb.screen_on),
        "foreground_app": (hb.foreground_app or "").lower(),
    }
    cutoff_ts = datetime.utcnow().timestamp() - HEARTBEAT_WINDOW_SECONDS

    pipe = redis_client.pipeline()
    pipe.zadd(key, {json.dumps(entry): ts})
    pipe.zremrangebyscore(key, 0, cutoff_ts)
    pipe.expire(key, HEARTBEAT_WINDOW_SECONDS * 2)
    pipe.execute()


def load_recent_heartbeats(device_id: str) -> List[Dict[str, object]]:
    """Load recent heartbeats for a device from Redis within the configured window."""
    key = f"hb:{device_id}"
    cutoff_ts = datetime.utcnow().timestamp() - HEARTBEAT_WINDOW_SECONDS
    raw_entries = redis_client.zrangebyscore(key, cutoff_ts, "+inf")
    return [json.loads(e) for e in raw_entries]


# -------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------
class PairRequest(BaseModel):
    device_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    token: str = Field(..., min_length=1, description="JWT pairing token")


class PairResponse(BaseModel):
    status: str
    secret: str


class Heartbeat(BaseModel):
    device_id: str
    timestamp: datetime
    screen_on: bool
    foreground_app: Optional[str] = None
    signature: Optional[str] = Field(default=None, description="Hex HMAC of payload")


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
@router.post("/pair", response_model=PairResponse, status_code=status.HTTP_200_OK)
def pair(req: PairRequest, db: Annotated[Session, Depends(get_db)]) -> PairResponse:
    """
    Pair a device and issue a per-device secret.

    The pairing token is a JWT signed with PAIRING_JWT_SECRET.
    It must contain a `device_id` claim that matches the request.
    """
    try:
        payload = jwt.decode(req.token, PAIRING_JWT_SECRET, algorithms=[PAIRING_JWT_ALG])
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid pairing token")

    if payload.get("device_id") != req.device_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="token/device mismatch")

    import secrets

    secret = secrets.token_hex(32)
    device = db.query(Device).filter(Device.device_id == req.device_id).first()

    if device:
        device.name = req.name
        device.paired = True
        device.secret = secret
    else:
        device = Device(device_id=req.device_id, name=req.name, paired=True, secret=secret)
        db.add(device)

    db.commit()
    logger.info("Paired device %s", req.device_id)
    return PairResponse(status="paired", secret=secret)


@router.post("/heartbeat", status_code=status.HTTP_200_OK)
def heartbeat(
    hb: Heartbeat,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Authenticated heartbeat endpoint.

    - Requires device to be paired.
    - Requires valid HMAC signature of payload (per-device secret).
    - Enforces rate limiting per device ID via Redis.
    - Stores recent heartbeat samples in Redis.
    - Schedules asynchronous evaluation of distraction vs productivity.
    """
    try:
        # 1️⃣ Rate limit
        enforce_heartbeat_rate_limit(hb.device_id)

        # 2️⃣ Device validation
        device = db.query(Device).filter(Device.device_id == hb.device_id).first()
        if not device or not getattr(device, "paired", False):
            raise HTTPException(status_code=403, detail="device not paired")

        if not device.secret:
            raise HTTPException(status_code=500, detail="device secret missing")

        # 3️⃣ ✅ Canonical payload (MATCHES CLIENT EXACTLY)
        timestamp_str = hb.timestamp.isoformat() if hasattr(hb.timestamp, "isoformat") else str(hb.timestamp)

        unsigned_payload = {
            "device_id": hb.device_id,
            "timestamp": timestamp_str,
            "screen_on": hb.screen_on,
            "foreground_app": hb.foreground_app,
        }

        payload_bytes = json.dumps(unsigned_payload, separators=(",", ":"), sort_keys=True, default=str).encode()

        # 4️⃣ ✅ HMAC verification
        if not hb.signature:
            raise HTTPException(status_code=403, detail="missing signature")

        if not verify_hmac(device.secret, payload_bytes, hb.signature):
            raise HTTPException(status_code=403, detail="invalid signature")

        # 5️⃣ DB update (safe)
        from datetime import timezone

        device.last_seen = datetime.now(timezone.utc)
        db.commit()

        # 6️⃣ Redis (safe)
        try:
            store_heartbeat_in_redis(hb)
        except Exception as e:
            print("⚠️ Redis error:", e)

        # 7️⃣ Metrics (safe)
        try:
            HEARTBEAT_TOTAL.labels(device_id=hb.device_id).inc()
        except Exception as e:
            print("⚠️ Metrics error:", e)

        # 8️⃣ Background evaluation
        background_tasks.add_task(evaluate_device_state, hb.device_id)

        return {"ok": True}

    except HTTPException:
        raise

    except Exception as e:
        print("🔥 HEARTBEAT CRASH:", repr(e))
        raise HTTPException(status_code=500, detail="heartbeat processing failed")


# -------------------------------------------------------------------
# Summary endpoint
# -------------------------------------------------------------------


@router.get("/summary")
def phone_pc_summary(
    device_id: str,
    minutes: int = 60,
    db: Annotated[Session, Depends(get_db)] = None,
):
    entries = load_recent_heartbeats(device_id)

    now_ts = datetime.utcnow().timestamp()
    cutoff_ts = now_ts - minutes * 60
    entries = [e for e in entries if float(e.get("ts", 0)) >= cutoff_ts]

    phone_total = len(entries)
    phone_screen_on = sum(1 for e in entries if e.get("screen_on"))
    phone_distract = sum(1 for e in entries if any(kw in (str(e.get("foreground_app")) or "") for kw in DISTRACTING_KEYWORDS))

    since = datetime.utcnow() - timedelta(minutes=minutes)
    pc_events = db.query(Event).filter(Event.timestamp >= since).order_by(Event.timestamp.asc()).all()
    pc_signal = sum(1 for e in pc_events if bool(e.productive))
    pc_noise = sum(1 for e in pc_events if not bool(e.productive))
    pc_total = pc_signal + pc_noise
    pc_snr = (pc_signal / pc_total) if pc_total else None

    return {
        "device_id": device_id,
        "window_minutes": minutes,
        "phone": {
            "total": phone_total,
            "screen_on": phone_screen_on,
            "distract": phone_distract,
            "series": entries,
        },
        "pc": {
            "signal": pc_signal,
            "noise": pc_noise,
            "snr": pc_snr,
        },
    }


# -------------------------------------------------------------------
# Policy evaluation and scheduled unblock
# -------------------------------------------------------------------
def evaluate_device_state(device_id: str) -> None:
    """
    Evaluate mobile distraction vs PC productivity and enforce blocking policy.
    Uses:
    - Redis heartbeat window for mobile activity
    - DB `Event` rows for PC activity
    - `BlockRecord` + hosts blocker to enforce policy
    """
    entries = load_recent_heartbeats(device_id)
    distract_count = sum(1 for e in entries if any(kw in (str(e.get("foreground_app")) or "") for kw in DISTRACTING_KEYWORDS))
    screen_on_count = sum(1 for e in entries if bool(e.get("screen_on")))

    db = SessionLocal()
    try:
        two_min = datetime.utcnow() - timedelta(minutes=2)
        recent_pc = db.query(Event).filter(Event.timestamp >= two_min).order_by(Event.timestamp.desc()).limit(20).all()
        pc_prod_count = sum(1 for e in recent_pc if getattr(e, "productive", False))
        pc_total = max(1, len(recent_pc))
        pc_is_productive = (pc_prod_count / pc_total) >= 0.7

        if pc_is_productive and distract_count >= DISTRACTION_THRESHOLD and screen_on_count >= 2:
            reason = f"mobile-distract:{device_id}"
            expires_at = datetime.combine(datetime.utcnow().date(), datetime.max.time())
            domains = BLOCK_DOMAINS_DEFAULT

            br = BlockRecord(
                created_at=datetime.utcnow(),
                expires_at=expires_at,
                domains=json.dumps(domains),
                active=True,
                reason=reason,
            )
            db.add(br)
            db.commit()
            logger.warning(
                "Applying domain block for device %s; record id=%s",
                device_id,
                getattr(br, "id", None),
            )

            BLOCK_APPLIED_TOTAL.inc()

            try:
                block_domains(domains)
            except Exception as exc:  # pragma: no cover
                logger.error("Block apply failed: %s", exc)

            try:
                sched.add_job(
                    func=scheduled_unblock,
                    trigger="date",
                    run_date=expires_at,
                    args=[getattr(br, "id", 0)],
                    id=f"unblock-{getattr(br, 'id', 0)}",
                )
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to schedule unblock: %s", exc)

            try:
                from src.prodtracker.agent_alerts import alert_user_now

                alert_user_now(
                    title="Focus alert",
                    message="Phone active on distracting apps — blocking until end of day.",
                )
            except Exception:
                # Alert is optional
                pass
    except Exception as exc:
        logger.exception("evaluate_device_state failed: %s", exc)
    finally:
        db.close()


def scheduled_unblock(block_record_id: int) -> None:
    """Scheduled task: deactivate block record and remove hosts block."""
    db = SessionLocal()
    try:
        rec = db.get(BlockRecord, block_record_id)
        if not rec or not rec.active:
            return
        try:
            unblock_all()
        except Exception as exc:  # pragma: no cover
            logger.error("Unblock failed: %s", exc)
        rec.active = False
        db.commit()
    except Exception as exc:
        logger.exception("scheduled_unblock failed: %s", exc)
    finally:
        db.close()
