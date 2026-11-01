"""Production Launcher for AP Command Center.

Starts the production FastAPI application mounted with the compiled React SPA.
Binds to 0.0.0.0 and dynamically respects Cloud Run $PORT (default 8080 or configured APP_PORT).
"""

import os
import sys
from dotenv import load_dotenv

# Explicitly load .env file from project root
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path)

import uvicorn
from backend.core.config import settings

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main():
    host = os.environ.get("APP_HOST", settings.APP_HOST)
    port = int(os.environ.get("PORT", str(settings.APP_PORT)))

    print(f"""
=============================================================================
   AUTONOMOUS AP COMMAND CENTER — PRODUCTION RUNTIME
=============================================================================
   * Application UI:        http://{host}:{port}
   * API Health & Status:   http://{host}:{port}/api/v1/health
   * OpenAPI Specification: http://{host}:{port}/docs
   * Environment:           {settings.APP_ENV.value}
=============================================================================
    """)
    uvicorn.run("backend.main:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
