# Testing & Evaluation Guide

This document details the test suites, evaluation corpora, benchmark procedures, and quality gates of the Autonomous Accounts Payable (AP) Command Center.

---

## 1. Automated Test Suite Architecture

The repository contains 499 automated test items executed via `pytest`. Current regression status: **456 passed, 43 skipped, 0 failed** in 64.45s (`python -m pytest tests/`), plus **12 passed, 0 failed** in Node.js (`node --test frontend/src/tests/auth_lifecycle.test.mjs`). Total **468 passing tests**.

> [!NOTE]
> **Evidence Classification Standard:** The 456 passing Python tests and 12 passing Node.js tests execute against isolated fixtures, local loopback sockets, and mocked ERP/LLM/Storage adapters. They prove mathematical precision, RLS policies, audit immutability, differentiated 401 revocation handling, multi-tab session mechanics, and safety guards. They are classified as **local regression/integration evidence**, not live hosted acceptance. Live hosted capabilities (live Supabase Auth, persistent PostgreSQL migration 013, live browser PDF upload, live Mantle extraction) remain unverified on the public deployment until P0 staging launch.

```
tests/
├── phase_a/                               # Phase A Security & Architectural Invariants
│   ├── test_audit_immutability.py         # Database trigger immutability tests
│   ├── test_auth_and_rbac.py              # Role permissions & unauthenticated rejection
│   ├── test_config_invariants.py          # Production truth rules & config validation
│   ├── test_honest_states_and_no_fictional_data.py # Truthful zero states & health checks
│   └── test_storage_access_control.py     # Private bucket access & signed URL TTL
│
├── phase_b/                               # Phase B Enterprise Subsystems
│   ├── test_stage1_tenant_isolation.py    # Multi-tenant cross-org boundary tests
│   ├── test_stage2_gmail_oauth.py         # Google OAuth token encryption & refresh
│   ├── test_stage3_storage_security.py    # Supabase private storage signed URL policies
│   ├── test_stage4_sap_s4hana_mock.py     # OData ERP integration & cache TTL
│   ├── test_stage5_gmail_pubsub.py        # Webhook signature validation & History sync
│   └── test_stage7_cloudrun_deployment.py # Cloud Run container invariants & health probes
│
├── phase_d/                               # Phase D Modality & Pipeline Routing
│   ├── test_modality_classification.py    # Digital PDF vs raster scan pre-screening
│   └── test_grounding_verification.py     # Source page coordinate grounding
│
├── phase_e/                               # Phase E Acceptance & Security Hardening
│   └── test_security_and_financial_controls.py # Dev session sandbox, JWT claims, dual control
│
├── test_auth_and_session_lifecycle.py     # Unknown email rejection & dual-control anti-self-approval
└── test_bootstrap_eval_db.py              # Out-of-band evaluation database bootstrap invariants

frontend/src/tests/
└── auth_lifecycle.test.mjs                # Client OTP, token rotation, deduplication, error handling
```

---

## 2. Running Automated Tests

```bash
# Run the complete test suite
python -m pytest tests/ -v

# Run with fail-fast on first error
python -m pytest tests/ -x

# Run only Phase E security and financial control tests
python -m pytest tests/phase_e/ -v

# Run with test execution duration profiling
python -m pytest tests/ --durations=10
```

---

## 3. The 40-Document Indian AP Corpus

The evaluation corpus (`mixed_indian_ap_test_corpus_40_docs_v2.zip`) contains 40 distinct synthetic commercial documents representing real-world AP edge cases:

- **Clean Happy-Path Invoices (15 docs):** Correct 18% IGST / CGST+SGST, valid PO references, exact GRN and QC alignment.
- **Price & Rate Variances (6 docs):** Unit rates exceeding agreed PO contracts (e.g. ₹220 vs PO ₹185).
- **Quantity Variances (4 docs):** Billed quantities exceeding warehouse received quantities on GRNs.
- **Degraded Scans & Low Contrast (6 docs):** Raster scans with $\sigma < 10.0$ contrast, skewed text, and zero machine-readable characters.
- **Non-Payable Documents (5 docs):** Advance payment receipts, vendor account statements, proforma invoices, and delivery challans.
- **Malformed & Tampered Invoices (4 docs):** Inconsistent tax arithmetic, invalid state codes, and corrupted PDF streams.

### Benchmark Execution Procedure
To run the full 40-document Mantle evaluation:
```bash
python engine/evaluation_runner.py
```
Evaluation metrics are logged to `docs/project-history/full_40_evaluation_report.json`.

---

## 4. End-to-End Browser Verification & Evaluator Acceptance Walkthrough

The primary evaluation target is the flagship AP Command Center (`backend/` + `frontend/`). Evaluator testing and browser automation verify the end-to-end workflow:

```bash
# Run client auth lifecycle regression
node --test frontend/src/tests/auth_lifecycle.test.mjs

# Run automated browser verification (headless Edge/Chromium)
python scratch/test_browser_acceptance.py
```

### Complete Primary HR Acceptance Sequence:
1. **Authentication & Session Lifecycle:**
   - Evaluator navigates to the public portal in an incognito window.
   - Signs in using Email OTP (`POST /auth/v1/otp`, `create_user: false`). Unknown or unprovisioned emails are rejected with HTTP 403 Forbidden.
   - Enters 6-digit OTP to receive cryptographically signed session tokens. Token rotation via refresh tokens is verified on token expiration.
2. **Operational Dashboard & Inbox:**
   - Evaluator inspects live KPI metrics (ingested invoice volume, pending reviews, blocked exposure).
   - Filters inbox by status (`MATCH_CANDIDATE`, `FLAGGED_EXCEPTION`, `FLAGGED_HITL_REVIEW`, `QUARANTINE_NON_INVOICE`).
3. **Fresh PDF Ingestion & Real-Time Processing Checkpoints:**
   - Evaluator uploads a test multi-page invoice PDF to private Supabase Storage bucket 'invoices'.
   - Observes processing checkpoints via HTTP polling (`pollRun` querying `GET /api/v1/invoices/{id}/processing`) reading persisted PostgreSQL `AuditEvent` records across 5 pipeline stages: Classification, Entity Extraction, Grounding Tripwires, Procurement Cross-Reference, and Deterministic Policy Engine. (Note: Standalone engine uses SSE; flagship Command Center uses persisted checkpoints and API polling).
4. **3-Pane Review Workspace:**
   - Left: Source PDF rendering via private signed URL (900s TTL).
   - Center: Line item reconciliation, contracted PO references, and Indian GST tax math (CGST+SGST vs IGST with ₹20 rounding tolerance).
   - Right: Policy gate checks, grounding coordinates, and immutable audit history.
5. **Financial Governance & Approvals:**
   - **Single Approval (< ₹5,00,000 INR):** Evaluator reviews `APTC-001` (₹4,10,000 INR) and clicks 'Approve Invoice'. System immediately moves invoice to `APPROVED` and stages GL voucher.
   - **Strict Dual-Control (≥ ₹5,00,000 INR):** Evaluator reviews high-value invoices (`DUAL_APPROVAL_THRESHOLD_INR`). AP Lead grants Step 1 approval (`PENDING_SECOND_APPROVAL`). Controller grants Step 2 approval (`APPROVED`). The system strictly forbids the first approver from granting second approval (anti-self-approval protection).
6. **Exception Triage & Margin Protection:**
   - Evaluator reviews `APTC-030` (+8.8% unit rate spike exceeding 1.5% policy tolerance).
   - System flags variance exception, blocks payment, and recommends a ₹15/unit debit note. Evaluator places invoice on query hold (`HOLD_PENDING_EVIDENCE`).
7. **Immutable Audit Verification:**
   - Evaluator verifies audit trail entries backed by PostgreSQL `AuditEvent` rows with SHA-256 payload hashes and user attribution.

Full-resolution screenshots are captured in [`docs/images/browser_verification/`](./images/browser_verification/).
