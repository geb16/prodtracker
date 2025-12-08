# src/prodtracker/blocker/hosts_blocker.py
from .config import HOSTS_PATH, BLOCK_LIST, BLOCK_MARK

def block_domains(domains=BLOCK_LIST):
    with open(HOSTS_PATH, "a") as f:
        for d in domains:
            f.write(f"127.0.0.1 {d} {BLOCK_MARK}\n")

def unblock_all():
    lines = []
    with open(HOSTS_PATH, "r") as f:
        for line in f:
            if BLOCK_MARK not in line:
                lines.append(line)
    with open(HOSTS_PATH, "w") as f:
        f.writelines(lines)
