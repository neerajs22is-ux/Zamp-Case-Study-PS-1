"""Unified Launcher for Zamp PS-1 AP Command Center.

One authoritative processing engine. Two user experiences:
1. Flagship AP Command Center (Primary enterprise multi-tenant application)
2. AP Command Center Sandbox (Simplified interactive demonstration)

Usage:
  python run.py             # Starts unified server defaulting to Flagship AP Command Center on http://127.0.0.1:8001
  python run.py --sandbox   # Starts unified server with focus on the Sandbox Experience (http://127.0.0.1:8001/sandbox)
  python run.py --test      # Runs verification test suite before launch
"""

import sys
import uvicorn

# Ensure utf-8 encoding resilience on Windows cp1252 consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main():
    if "--test" in sys.argv:
        import pytest
        print("\n=======================================================")
        print("[*] Running Verification Suite before launch...")
        print("=======================================================\n")
        exit_code = pytest.main(["tests/test_sandbox_flagship_parity.py", "-v"])
        if exit_code != 0:
            print("\n[!] Tests failed. Halting server launch.")
            sys.exit(exit_code)
        print("\n[+] Verification tests passed!\n")

    is_sandbox_focus = "--sandbox" in sys.argv or "--legacy" in sys.argv

    if is_sandbox_focus:
        print("""
=============================================================================
   [ZAMP AP COMMAND CENTER] - SANDBOX DEMONSTRATION EXPERIENCE
   Powered by the Single Authoritative Processing Engine (Decimal INR + Mantle)
=============================================================================
   * Sandbox Experience:     http://127.0.0.1:8001/sandbox
   * Flagship Command Center:http://127.0.0.1:8001/today
   * API Documentation:      http://127.0.0.1:8001/docs
   * System Health:          http://127.0.0.1:8001/api/v1/health
   * Sandbox Runs & Metrics: http://127.0.0.1:8001/api/v1/sandbox/runs
=============================================================================
   One Engine. Two Experiences.
   - Upload any invoice PDF or select one of 6 genuine scenario fixtures.
   - Watch Bedrock Mantle extraction, GST verification, and 7 policy gates.
=============================================================================
        """)
    else:
        print("""
=============================================================================
   [ZAMP AP COMMAND CENTER] - FLAGSHIP ENTERPRISE EXPERIENCE (PRIMARY)
   Autonomous Accounts Payable Ingestion, Matching, and Decision Engine
=============================================================================
   * Flagship Command Center:http://127.0.0.1:8001/
   * Invoices Inbox:         http://127.0.0.1:8001/invoices
   * Approvals Queue:        http://127.0.0.1:8001/approvals
   * Sandbox Experience:     http://127.0.0.1:8001/sandbox
   * API Documentation:      http://127.0.0.1:8001/docs
   * System Health:          http://127.0.0.1:8001/api/v1/health
=============================================================================
   One Engine. Two Experiences.
   - Enterprise Multi-Tenant RLS + Supabase Auth + Dual-Control Governance.
   - Authoritative 7-Gate Matching with Decimal INR & Indian GST validation.
=============================================================================
        """)

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8001, reload=False, log_level="info")


if __name__ == "__main__":
    main()
