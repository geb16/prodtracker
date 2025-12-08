# src/prodtracker/blocker/config.py

import platform
from pathlib import Path

SYSTEM = platform.system()
HOSTS_PATH = Path("/etc/hosts") if SYSTEM != "Windows" else Path(r"C:\Windows\System32\drivers\etc\hosts")
BACKUP_DIR = Path.home() / ".pguard_backups"
BACKUP_DIR.mkdir(exist_ok=True)

BLOCK_LIST = ["youtube.com", "tiktok.com", "instagram.com"]
BLOCK_MARK = "# PGUARD_BLOCK"
