"""Health and Readiness Subsystem Check Endpoints.

Enforces:
1. Truthful reporting of live subsystem status.
2. In production, returns HTTP 503 if mandatory database or storage dependencies are missing or unready.
3. No secret leakage.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict
from fastapi import APIRouter, Response, status

from backend.core.auth import check_idp_health
from backend.core.config import AppEnv, settings
from backend.core.database import check_db_health
from backend.core.storage import storage_adapter

router = APIRouter(tags=["Health & Diagnostics"])


@router.get("/liveness")
def liveness() -> Dict[str, Any]:
    """Basic process liveness check."""
    return {
        "status": "ALIVE",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "app_env": settings.APP_ENV.value,
    }


@router.get("/health")
def health(response: Response) -> Dict[str, Any]:
    """Comprehensive health check across all operational pillars."""
    db_status = check_db_health()
    storage_status = storage_adapter.check_health()
    idp_status = check_idp_health()

    gmail_status = {
        "status": "CONFIGURED_UNVERIFIED" if settings.is_gmail_configured() else "NOT_CONFIGURED",
        "mailbox": settings.GMAIL_TARGET_MAILBOX if settings.is_gmail_configured() else None,
        "readiness": settings.is_gmail_configured(),
        "message": "Gmail credentials configured; mailbox authorization is verified separately." if settings.is_gmail_configured() else "Gmail ingestion credentials not configured.",
    }

    erp_status = {
        "status": "CONFIGURED_UNVERIFIED" if settings.is_erp_configured() else "NOT_CONFIGURED",
        "company_code": settings.SAP_COMPANY_CODE if settings.is_erp_configured() else None,
        "endpoint": settings.SAP_API_BASE_URL if settings.is_erp_configured() else None,
        "readiness": settings.is_erp_configured(),
        "message": "SAP settings configured; live synchronization is not implemented." if settings.is_erp_configured() else "SAP S/4HANA ERP API not configured.",
    }

    is_production_like = settings.APP_ENV in (AppEnv.PRODUCTION, AppEnv.STAGING)
    is_ready = db_status["readiness"] and storage_status["readiness"] and idp_status["readiness"]

    if is_production_like and not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "app_name": settings.APP_NAME,
        "app_env": settings.APP_ENV.value,
        "overall_status": "READY" if is_ready else ("SETUP_REQUIRED" if not is_production_like else "BLOCKED"),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "subsystems": {
            "database": db_status,
            "object_storage": storage_status,
            "identity_provider": idp_status,
            "gmail_ingestion": gmail_status,
            "sap_erp": erp_status,
        },
    }
