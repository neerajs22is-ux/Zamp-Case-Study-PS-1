"""Root launcher for AP Digital Employee & AP Command Center.

Usage:
  python run.py               # Starts the PS-1 AP Digital Employee on http://127.0.0.1:8001 (Recommended, zero credentials)
  python run.py --enterprise  # Starts the Multi-Tenant Enterprise Command Center on http://127.0.0.1:8001
  python run.py --legacy      # Alias for PS-1 AP Digital Employee
  python run.py --test        # Runs verification test suite before starting server
"""

import sys
import uvicorn
import pytest

# Ensure utf-8 encoding resilience on Windows cp1252 consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main():
    if "--test" in sys.argv:
        print("\n=======================================================")
        print("[*] Running Pytest Verification Suite before launch...")
        print("=======================================================\n")
        exit_code = pytest.main(["tests/test_engine.py", "-v"])
        if exit_code != 0:
            print("\n[!] Tests failed. Halting server launch.")
            sys.exit(exit_code)
        print("\n[+] Verification tests passed!\n")

    if "--enterprise" in sys.argv:
        print("""
=============================================================================
   [AP COMMAND CENTER] - ENTERPRISE MULTI-TENANT ARCHITECTURE
   FastAPI application with PostgreSQL RLS, Supabase Auth, and React UI
=============================================================================
   * Command Center UI:     http://127.0.0.1:8001
   * API Docs (Swagger UI): http://127.0.0.1:8001/docs
   * System Health:         http://127.0.0.1:8001/api/v1/health
   * Invoices Inbox:        http://127.0.0.1:8001/api/v1/inbox
   * Operational Approvals: http://127.0.0.1:8001/api/v1/approvals
=============================================================================
        """)
        uvicorn.run("backend.main:app", host="127.0.0.1", port=8001, reload=False, log_level="info")
    else:
        print("""
=============================================================================
   [AI SOLUTIONS ASSOCIATE] - PS-1 AP DIGITAL EMPLOYEE
   Autonomous Accounts Payable (AP) Decision Engine & Live Execution Server
=============================================================================
   * Interactive UI:        http://127.0.0.1:8001
   * API Docs (Swagger UI): http://127.0.0.1:8001/docs
   * System Health:         http://127.0.0.1:8001/api/health
   * Test Scenarios:        http://127.0.0.1:8001/api/scenarios
   * Real-Time Stream:      http://127.0.0.1:8001/api/stream-scenario/HP-01-Happy-Path
   * Run History Dashboard: http://127.0.0.1:8001/api/runs
=============================================================================
        """)
        uvicorn.run("engine.server:app", host="127.0.0.1", port=8001, reload=False, log_level="info")


if __name__ == "__main__":
    main()
