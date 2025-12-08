# src/prodtracker/blocker/manual_unblock.py
from fastapi import APIRouter, HTTPException

from .backup_helper import backup_hosts, restore_latest_backup
from .hosts_blocker import block_domains, unblock_all

router = APIRouter()


@router.post("/manual_unblock")
def manual_unblock():
    try:
        backup_hosts()
        restore_latest_backup()
        unblock_all()
        return {"status": "success", "message": "All domains unblocked and hosts restored."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual_block")
def manual_block():
    try:
        backup_hosts()
        block_domains()
        return {"status": "success", "message": "Domains blocked manually."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
