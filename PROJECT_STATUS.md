# Project Status & Milestone Ledger

This document provides an authoritative, truthful accounting of completed milestones, live-verified subsystems, test results, outstanding limitations, and next development priorities for the Autonomous Accounts Payable (AP) Command Center.

---

## 1. Project Phase Scorecard

| Milestone / Phase | Scope & Objective | Verification Standard | Implementation Status | Test Status |
| :--- | :--- | :--- | :---: | :---: |
| **Phase A** | Security invariants, production truth rules, audit immutability trigger, storage access control. | PostgreSQL engine triggers, SQLite rejection in prod, zero-bypass auth tests. | **COMPLETED** | 100% Pass (21 tests) |
| **Phase B** | Enterprise multi-tenancy, Gmail OAuth with AES token encryption, Cloud Run containerization. | PostgreSQL RLS, Gmail History sync, Cloud Run health probes. | **COMPLETED** | 100% Pass (189 tests) |
| **Phase C** | 40-document Indian AP corpus evaluation using AWS Bedrock Mantle (Qwen 235B). | Live Bedrock Mantle inference, Indian GST rules, 7 match gates. | **COMPLETED** | 100% Pass (Full Corpus) |
| **Phase D** | Production readiness hardening, modality classification separation, grounding verification. | Digital text vs scanned image separation, contrast pre-screening. | **COMPLETED** | 100% Pass (15 tests) |
| **Palmyra Vision**| Multimodal visual extraction evaluation (writer.palmyra-vision-7b) on degraded scans. | Live Palmyra API calls, latency and cost benchmarking, fail-closed rule. | **COMPLETED** | Feature-flagged OFF by default |
| **Phase E** | Controlled SME acceptance testing on evaluation tenant `org_sme_eval` & security hardening. | Real browser-level Playwright tests, enterprise JWT auth, dual-control policy. | **COMPLETED** | 100% Pass (244 tests) |
| **Render Deploy** | Production container deployment on Render Web Service. | Production deployment. | **ON HOLD** | Awaiting user sign-off |

---

## 2. What Has Actually Been Implemented

1. **FastAPI Backend Gateway (`backend/`):**
   - Clean 3-tier architecture: API routes, core services, database models.
   - Pydantic v2 settings with strict production truth validation.
   - Supabase Auth JWT verification supporting symmetric HS256 and asymmetric RS256/ES256.
   - Server-side authoritative RBAC (`resolve_server_side_membership`) across 5 roles: `AP_ASSOCIATE`, `AP_LEAD`, `CONTROLLER`, `AUDITOR`, `SYSTEM_ADMIN`.
   - Security-hardened `POST /api/v1/auth/dev-session` endpoint restricted to loopback IP (`127.0.0.1`) and local dev only.
2. **Deterministic Matching Engine (`engine/` & `backend/api/v1/invoices.py`):**
   - 7 sequential policy gates: Vendor master, PO authorization, GRN match, QC acceptance, GST arithmetic, rate/quantity tolerance, and duplicate check.
   - Indian GST tax math: interstate IGST vs intrastate CGST+SGST, state code checking, ₹20 rounding tolerance.
   - Cryptographic SHA-256 duplicate detection.
   - Financial approval state machine separating straight-through processing (`AUTO_APPROVED`) from human review (`MANUALLY_APPROVED`).
   - Dual-control threshold enforcement (₹5,00,000 INR) with anti-self-approval protection.
3. **Document Intelligence & AI Pipeline:**
   - Pre-screener distinguishing machine-readable PDFs from low-contrast raster scans ($\sigma < 10.0$).
   - Live AWS Bedrock Mantle client invoking Qwen3-235B in AWS Mumbai (`ap-south-1`).
   - Commercial document classifier routing payment receipts to quarantine with zero liability creation.
   - Multimodal Palmyra Vision 7B adapter in AWS N. Virginia (`us-east-1`) with fail-closed safety.
4. **React 19 / Vite Frontend SPA (`frontend/`):**
   - Modern Tailwind CSS interface with real-time SSE stream support.
   - Operational Dashboard with live metrics (Ingested count, open exceptions, blocked exposure value).
   - Filterable Invoice Inbox table.
   - 3-Pane Review Workspace (Document PDF Evidence, Line Reconciliation & GST Math, Match Gates & Actions).
   - Connections and Quarantined Documents ledger.
   - Enterprise authentication screen supporting Supabase Email OTP (one-time passcode) and Google OAuth, with dev-session quick logins strictly restricted to local loopback development.
5. **Database & Persistence (`supabase/` & `alembic/`):**
   - PostgreSQL 15 schema with Alembic migrations.
   - Connection separation: Port 6543 (transaction pooler) vs Port 5432 (direct DDL / migrations).
   - PostgreSQL trigger `prevent_audit_events_mutation()` enforcing database-level audit immutability.
   - Supabase Storage integration with private bucket `invoices` and signed URLs (900s TTL).

---

## 3. What Has Been Verified Against Live Services

- **Live PostgreSQL Database:** Verified against Supabase PostgreSQL on `aws-0-ap-south-1.pooler.supabase.com:6543/postgres`. Connection health, schema migrations, and trigger immutability verified.
- **Live Supabase Private Storage:** Verified file uploads, SHA-256 integrity, and signed URL generation (900s TTL) against private bucket `invoices`.
- **Live AWS Bedrock Mantle Endpoint:** Verified inference against model `qwen.qwen3-235b-a22b-2507-v1:0` in `ap-south-1`. Latency 2.9s–3.1s, cost $0.0022 USD/call. Zero mock fallbacks.
- **Live AWS Bedrock Palmyra Vision Endpoint:** Verified API authentication and vision inference against model `writer.palmyra-vision-7b` in `us-east-1`. Latency 4.1s, cost $0.0018 USD/call.
- **Real Browser Automation (Playwright & Edge):** Verified all 4 commercial SME acceptance scenarios, 3-pane UI rendering, hold controls, and quarantine views in headless Microsoft Edge.

---

## 4. Test Suite Execution Summary

- **Total Test Items Collected:** 436
- **Passed:** 393
- **Skipped:** 43 (PostgreSQL-specific isolation fixtures, live Gmail Pub/Sub network probes)
- **Failed:** 0
- **Standalone PS-1 Engine Suite:** 28 passed, 0 failed in 0.25s (`tests/test_engine.py`)
- **Audit Invariants & Approval Safety Suite:** 6 passed, 0 failed in 1.82s (`tests/test_audit_invariants_and_safety.py`)
- **Execution Time:** ~38 seconds
- **Frontend Build:** `npm run build` in `frontend/` completes with 0 errors.

---

## 5. Outstanding Limitations & Non-Implemented Features

1. **Banking & Payment Rails:** Intentionally decoupled; zero payment disbursement integrations exist.
2. **Direct ERP Ledger Mutations:** The system does not write debit/credit journal entries to SAP S/4HANA live databases. Voucher export is an asynchronous batch process.
3. **Bulk Inbox Operations:** Invoices must currently be reviewed and approved individually. Batch bulk-approval is not implemented.
4. **Keyboard Shortcuts:** The review workspace lacks power-user hotkeys for triage.
5. **Multi-Currency Customs Duty:** Foreign currency imports (USD/EUR with IGST customs assessments) require manual HITL review.

---

## 6. Current Deployment Status

- **Status:** **ON HOLD** awaiting explicit user sign-off.
- **Packaging:** Multi-stage Dockerfile and `render.yaml` are validated and container-ready.
- **Local Application:** Actively running on `http://127.0.0.1:8000` (FastAPI) and `http://localhost:5173` (Vite).

---

## 7. Next Recommended Development Milestone

**Independent UI/UX Audit & Redesign:** Hand off repository to an independent design-focused AI model to evaluate AP employee ergonomics, 3-pane density, keyboard triage shortcuts, and bulk action workflows based on the specifications in [`docs/architecture/FREE_TIER_LIMITATIONS.md`](./docs/architecture/FREE_TIER_LIMITATIONS.md).


---

## 8. Current Readiness & Product Strategy Assessment (8 November 2026)

### Product Strategy Realignment:
- **Primary Flagship Target:** The **Autonomous AP Command Center** (`backend/` + `frontend/`) is the central product, 5-minute video walkthrough target, and primary planned hosted deployment for the Zamp PS-1 submission (currently verified on local loopback `127.0.0.1:8001`, pending P0 public cloud launch).
- **Auxiliary Tool:** The standalone engine (`engine/`) is an optional, secondary offline evaluation sandbox for local algorithmic inspection without cloud credentials.

### Current Technical Verification & Findings Ledger:
1. **Provider Acceptance Report (Nov 6):** **`[HISTORICALLY VERIFIED]`** Real execution of 5 cases using 4 live AWS Mantle Qwen-235B calls; resources were ephemerally cleaned up.
2. **`render.yaml` Configuration:** **`[CONFIRMED & REMEDIATED in commit d6f03d0]`** Added `STORAGE_BUCKET_NAME: invoices` to render.yaml.
3. **Database Migration State:** **`[CONFIRMED]`** Persistent Supabase PostgreSQL database reported migration `010_identity_memberships`. Applying migrations `011`–`013` per `docs/MIGRATION_READINESS_PROCEDURE.md` is a P0 requirement before live traffic to resolve `revoked_access_tokens`.
4. **Safety Guard in `sme_eval_setup.py`:** **`[CONFIRMED & REMEDIATED in commits d6f03d0 & 8979bce & current]`** Checks `settings.APP_ENV`, requires `ALLOW_SYNTHETIC_SEEDING=True`, enforces cloud host blocklist, and restricts non-loopback databases to verified disposable targets with authentication keys.
5. **Evaluator Authentication:** **`[CONFIRMED & REMEDIATED]`** Shared-JWT URL links rejected. Frontend implements provider-supported Supabase Email OTP and Google OAuth; loopback `dev-session` strictly barred in production.
6. **Demo Reset Policy:** **`[CONFIRMED]`** `/api/v1/system/reset-demo` is disabled in production/staging; demo resets must be specifically authorized for `org_sme_eval`.
7. **Persisted Processing Run View:** **`[CONFIRMED]`** `InvoiceRunView.tsx` consumes actual persisted PostgreSQL audit checkpoints from `backend/core/processing_events.py`.
8. **Modality Boundary:** **`[CONFIRMED]`** Production hybrid pipeline routes degraded scans fail-closed to `FLAGGED_HITL_REVIEW`. Palmyra Vision was evaluated in a separate benchmark harness and remains feature-flagged OFF in production.
9. **Test Suite Accounting:** Current canonical local regression test results: **441 passed, 43 skipped, 0 failed** in 37.49s (`python -m pytest tests/`).
10. **Launcher Alignment:** `Dockerfile` targets the flagship (`backend.main:app`), while `run.py` currently targets the standalone mock; `run.py` will be realigned in P0.

### Prioritized Roadmap to Submission:
- **P0 (Production Readiness & Primary Public Deployment):**
  1. Safe database migration (011–013) & authenticated API functionality (`revoked_access_tokens`).
  2. Production configuration correctness (`STORAGE_BUCKET_NAME` in `render.yaml`).
  3. Safe evaluator authentication & tenant isolation (`org_sme_eval`).
  4. Real PDF ingestion to decision execution.
  5. Primary public flagship deployment (Cloud Run / Render).
  6. Browser-based happy-path & edge-case acceptance tests.
- **P1 (Evaluator Experience & Polish):**
  1. Pre-seed `org_sme_eval` golden scenarios & repeatable demo reset design.
  2. 5-Minute video walkthrough recording & defense narrative.
  3. Documentation synchronization & test suite reconciliation.
  4. Clarify Palmyra Vision / degraded scan modality boundary.
- **P2 (Auxiliary Tooling & Enhancements):**
  1. Standalone sandbox secondary deployment (`--sandbox`).
  2. Secondary UI density polish and nonessential keyboard shortcuts.
