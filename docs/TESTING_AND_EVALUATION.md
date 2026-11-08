# Testing & Evaluation Guide

This document details the test suites, evaluation corpora, benchmark procedures, and quality gates of the Autonomous Accounts Payable (AP) Command Center.

---

## 1. Automated Test Suite Architecture

The repository contains 484 automated test items executed via `pytest`. Current regression status: **441 passed, 43 skipped, 0 failed** in 37.49s (`python -m pytest tests/`).

> [!NOTE]
> **Evidence Classification Standard:** The 441 passing tests execute against isolated in-memory SQLite fixtures, local loopback sockets, and mocked ERP/LLM/Storage adapters. They prove mathematical precision, RLS policies, audit immutability, and safety guards. They are classified as **local regression/integration evidence**, not live hosted acceptance. Live hosted capabilities (live Supabase Auth, persistent PostgreSQL migration 013, live browser PDF upload, live Mantle extraction) remain unverified on the public deployment until P0 launch.

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
└── phase_e/                               # Phase E Acceptance & Security Hardening
    └── test_security_and_financial_controls.py # Dev session sandbox, JWT claims, dual control
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

## 4. End-to-End Browser Verification (Playwright)

Automated browser tests verify the complete frontend and backend workflow using headless Microsoft Edge (`msedge`):

```bash
python scratch/test_browser_acceptance.py
```

The script exercises:
1. Enterprise login screen and dev-session token acquisition.
2. Operational dashboard with real-time KPI metrics.
3. Invoice inbox table filtering.
4. 3-Pane Review Workspace on `APTC-001` with human sign-off (`APPROVE_AP_REVIEW`).
5. Unit rate variance inspection on `APTC-030` with query hold (`HOLD_PENDING_EVIDENCE`).
6. Degraded scan handling on `APTC-037` with fail-closed HITL review.
7. Quarantined document inspection on `APTC-038` in Connections view.

Full-resolution screenshots are captured in [`docs/images/browser_verification/`](./images/browser_verification/).
