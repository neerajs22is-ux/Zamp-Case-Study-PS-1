"""Root launcher for Zamp PS-1 Invoice Processing Digital Employee.

Usage:
  python run.py          # Starts the FastAPI local server on http://127.0.0.1:8000
  python run.py --test   # Runs the pytest suite first, then starts the server
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

    print("""
=============================================================================
   [ZAMP AI SOLUTIONS ANALYST] - PS-1 DIGITAL AP EMPLOYEE
   Pace Autonomous Workflow Engine & Live Execution Server
=============================================================================
   * Interactive UI:        http://127.0.0.1:8000
   * API Docs (Swagger UI): http://127.0.0.1:8000/docs
   * System Health:         http://127.0.0.1:8000/api/health
   * Test Scenarios:        http://127.0.0.1:8000/api/scenarios
   * Real-Time Stream:      http://127.0.0.1:8000/api/stream-scenario/HP-01-Happy-Path
   * Run History Dashboard: http://127.0.0.1:8000/api/runs
=============================================================================
    """)

    uvicorn.run("engine.server:app", host="127.0.0.1", port=8000, reload=False, log_level="info")


if __name__ == "__main__":
    main()
