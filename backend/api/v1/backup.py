"""System Backup and Recovery API Endpoints (Phase B Stage 6).

Enforces:
1. Role-based access control (SYSTEM_ADMIN and CONTROLLER only for mutations).
2. Truthful inspection of backup archive repository (NOT_CONFIGURED if empty).
3. On-demand manual operator backup execution.
4. Transparent scheduling disclosure (manual execution, NOT_CONFIGURED background scheduler).
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.core.auth import (
    AuthenticatedUser, UserRole, require_role, verify_platform_operator
)
from backend.core.backup import (
    create_backup_archive, inspect_backup_status, BackupError
)
from backend.core.database import get_db
from backend.core.storage import storage_adapter

router = APIRouter(prefix="/system/backup", tags=["System & Disaster Recovery"])
logger = logging.getLogger("ap_command_center.backup.api")


@router.get("/status")
def get_backup_status(
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER, UserRole.AUDITOR])
    ),
) -> Dict[str, Any]:
    """Returns the current operational status of system backups and archive inventory."""
    verify_platform_operator(current_user)
    return inspect_backup_status()


@router.post("/trigger")
def trigger_backup(
    prune: bool = Query(default=True, description="Prune archives exceeding retention policy"),
    current_user: AuthenticatedUser = Depends(
        require_role([UserRole.SYSTEM_ADMIN, UserRole.CONTROLLER])
    ),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Triggers an operator-initiated encrypted backup of database and storage objects."""
    verify_platform_operator(current_user)
    try:
        result = create_backup_archive(
            session=db,
            storage_adapter=storage_adapter,
            prune=prune,
        )
        return {
            "status": "COMPLETED",
            "completion_status": result["completion_status"],
            "backup_id": result["backup_id"],
            "archive_path": result["archive_path"],
            "archive_size_bytes": result["archive_size_bytes"],
            "summary": result["summary"],
            "pruned_backups_count": len(result.get("pruned_backups", [])),
        }
    except BackupError as exc:
        logger.warning("Backup execution failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Backup execution failed. Check operator logs and backup status.",
        )
    except Exception as exc:
        logger.error("Unexpected backup execution failure (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Backup execution failed. Check operator logs and backup status.",
        )
