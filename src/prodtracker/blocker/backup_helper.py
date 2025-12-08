# src/prodtracker/blocker/backup_helper.py
import shutil
from datetime import datetime

from .config import BACKUP_DIR, HOSTS_PATH

BACKUP_DIR.mkdir(exist_ok=True)


def backup_hosts():
    backup_path = BACKUP_DIR / f"hosts_{datetime.now():%Y%m%d_%H%M%S}.bak"
    shutil.copy(HOSTS_PATH, backup_path)
    return backup_path


def restore_latest_backup():
    backups = sorted(BACKUP_DIR.glob("hosts_*.bak"), reverse=True)
    if backups:
        shutil.copy(backups[0], HOSTS_PATH)
        return backups[0]
    return None
