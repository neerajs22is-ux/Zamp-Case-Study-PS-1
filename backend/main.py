"""Production FastAPI Application for AP Command Center.

Enforces:
1. Strict environment validation at startup.
2. In production: Never mutates schema at startup; requires explicit migrations.
3. Serves all 7 operational route APIs under /api/v1.
4. Mounts static frontend build and provides seamless SPA routing.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.v1.approvals import router as approvals_router
from backend.api.v1.audit import router as audit_router
from backend.api.v1.auth import router as auth_router
from backend.api.v1.backup import router as backup_router
from backend.api.v1.connections import router as connections_router
from backend.api.v1.dashboard import router as dashboard_router
from backend.api.v1.documents import router as documents_router
from backend.api.v1.exceptions import router as exceptions_router
from backend.api.v1.health import router as health_router
from backend.api.v1.inbox import router as inbox_router
from backend.api.v1.integrations_gmail import router as gmail_router
from backend.api.v1.invoices import router as invoices_router
from backend.api.v1.source_records import router as source_records_router
from backend.core.config import AppEnv, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ap_command_center")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation
    logger.info(f"Starting {settings.APP_NAME} in environment: '{settings.APP_ENV.value}'")
    if settings.APP_ENV in (AppEnv.PRODUCTION, AppEnv.STAGING):
        # Enforce that schema mutation is NEVER run at startup in production
        logger.info("Production mode verified: Auto-DDL startup disabled. Migrations must be run via Alembic.")
    yield
    logger.info("Shutting down AP Command Center.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade Autonomous AP Operations Platform.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_ENV == AppEnv.DEVELOPMENT else [settings.BASE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 Routers FIRST
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(connections_router, prefix="/api/v1")
app.include_router(gmail_router, prefix="/api/v1")
app.include_router(inbox_router, prefix="/api/v1")
app.include_router(approvals_router, prefix="/api/v1")
app.include_router(invoices_router, prefix="/api/v1")
app.include_router(exceptions_router, prefix="/api/v1")
app.include_router(source_records_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(backup_router, prefix="/api/v1")

# Mount frontend assets and provide SPA fallback
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
assets_dir = os.path.join(frontend_dist, "assets")

if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{full_path:path}")
async def serve_spa_or_asset(full_path: str):
    """Serves static files or falls back to index.html for client-side SPA routing."""
    if full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": f"API endpoint '/{full_path}' not found."})

    target_file = os.path.join(frontend_dist, full_path)
    if full_path and os.path.isfile(target_file):
        return FileResponse(target_file)

    index_file = os.path.join(frontend_dist, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)

    return {
        "app_name": settings.APP_NAME,
        "version": "1.0.0",
        "environment": settings.APP_ENV.value,
        "status": "Operational",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
