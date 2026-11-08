# Flagship AP Command Center: Readiness & Verification Audit

**Audit Date:** 8 November 2026  
**Auditor:** Neeraj Shivkumar  
**Target Repository Snapshot:** Git commit `a6ee383` (Branch: `master`)  
**Audit Purpose:** Independent, evidence-based verification of flagship readiness, deployment configuration, and evaluator access prior to implementation.  

---

## 1. Audit Scope & Methodology

This audit inspects the current repository snapshot across Python source code, database migration scripts, container specifications, frontend TypeScript components, and committed inspection evidence.

### Verification Classification Standards:
- **`[CONFIRMED]`**: Verified directly by inspecting current working code, active runtime configuration, or reproducible command output.
- **`[HISTORICALLY VERIFIED]`**: Verified against committed historical test runs, provider transcripts, or JSON logs from a specific historical date; environment may no longer be active.
- **`[REPORTED BUT NOT REPRODUCED]`**: A claim or issue described in earlier documentation or tickets that was not reproduced in the current snapshot.
- **`[INFERRED]`**: Deductions based on source code analysis where live execution was barred or out of scope.
- **`[NOT VERIFIED]`**: External third-party services or infrastructure not directly accessible in this local sandbox.

---

## 2. Verification of the 10 Specific Repository Findings

### Finding 1: November 6 Provider-Backed Acceptance Report
- **Status:** **`[HISTORICALLY VERIFIED]`**
- **Evidence:** [`docs/inspection-evidence/provider-full-20261106/summary.json`](inspection-evidence/provider-full-20261106/summary.json) lines 1–41.
- **Finding Analysis:** The committed report documents an acceptance run on 6 November 2026 that processed 5 test cases using 4 live AWS Bedrock Mantle calls (Qwen-235B) with 3,343 total tokens ($0.004128 USD). However, line 40 explicitly notes: `"cloud_cleanup": "Supabase deleted; IAM user/key/policy deleted; main and retention-probe Mantle projects archived"`. 
- **Readiness Implication:** This report confirms that the hybrid model pipeline historically executed against real cloud APIs. It does **not** prove current public deployment, browser-based UI acceptance, or post-migration-013 readiness on the current persistent database.

---

### Finding 2: `render.yaml` Omits Production-Required `STORAGE_BUCKET_NAME`
- **Status:** **`[CONFIRMED]`**
- **Evidence:** [`render.yaml`](../render.yaml#L64-L67) vs [`backend/core/config.py`](../backend/core/config.py#L210-L214).
- **Finding Analysis:** In `backend/core/config.py` (lines 210–214), production startup validation strictly enforces:
  ```python
  if not self.STORAGE_BUCKET_NAME:
      raise ConfigurationError(
          f"Production violation: STORAGE_BUCKET_NAME is required in '{self.APP_ENV.value}'. "
          f"Local disk fallback is strictly barred in production."
      )
  ```
  `render.yaml` defines `APP_ENV: production` and sets `SUPABASE_STORAGE_BUCKET: invoices`, but **omits `STORAGE_BUCKET_NAME`**.
- **Readiness Implication:** A fresh deployment to Render using `render.yaml` will crash immediately on boot with a fatal `ConfigurationError`.

---

### Finding 3: Target Database Missing Migration 013 (`revoked_access_tokens`)
- **Status:** **`[CONFIRMED]`** (Environment Observation: 8 November 2026)
- **Evidence:** Database query and Alembic version check against persistent Supabase PostgreSQL (`aws-0-ap-south-1.pooler.supabase.com:6543/postgres`) recorded on 8 November 2026.
- **Finding Analysis:**
  1. Executing `python -m alembic current` against the persistent Supabase instance on 8 November 2026 reported revision `010_identity_memberships`.
  2. Migrations `011_require_assigned_roles.py`, `012_invitation_utc_expiry.py`, and `013_revoke_access_tokens.py` exist in [`backend/migrations/versions/`](../backend/migrations/versions/) but were not applied to this persistent database.
  3. In [`backend/core/auth.py`](../backend/core/auth.py#L550-L553), every authenticated API request verifies token revocation:
     ```python
     token_hash = hashlib.sha256(credentials.credentials.encode("utf-8")).hexdigest()
     try:
         revoked = db.get(RevokedAccessToken, token_hash)
     except Exception as exc:
         logger.error("Session verification store unavailable (%s)", type(exc).__name__)
         raise HTTPException(status_code=503, detail="Session verification is unavailable.") from exc
     ```
  4. Querying `RevokedAccessToken` on that date produced: `ProgrammingError: relation "revoked_access_tokens" does not exist`.
  5. *Infrastructure & Environment Distinction:* This persistent Supabase database is distinct from the ephemeral acceptance database used during the 6 November acceptance run (which was torn down per `cloud_cleanup`). Furthermore, this is an environment-specific observation from 8 November 2026; live migration application is pending explicit preflight validation and authorization under Milestone P0.1.
- **Readiness Implication:** Every authenticated endpoint (`/api/v1/dashboard/metrics`, `/api/v1/inbox`, `/api/v1/approvals`) returns **HTTP 503 Service Unavailable** until migrations 011–013 are verified and safely applied.

---

### Finding 4: `engine/sme_eval_setup.py` Checks Nonexistent `settings.ENVIRONMENT`
- **Status:** **`[CONFIRMED]`**
- **Evidence:** [`engine/sme_eval_setup.py`](../engine/sme_eval_setup.py#L532) lines 532, 585, 642, and 690.
- **Finding Analysis:** The script attempts to guard against running in production using:
  ```python
  if getattr(settings, "ENVIRONMENT", "development") == "production":
      raise RuntimeError("CRITICAL SAFETY VIOLATION: Seeding synthetic evaluation fixtures is strictly prohibited in production!")
  ```
  However, in `backend/core/config.py`, the setting is named **`APP_ENV`** (`settings.APP_ENV`, an `AppEnv` enum). `hasattr(settings, "ENVIRONMENT")` evaluates to `False`. The fallback `"development"` is always returned.
- **Readiness Implication:** The safety guard is completely ineffective; running the script in a production environment where `APP_ENV=production` would proceed without raising the intended safety error.

---

### Finding 5: Public `dev-session` Access Intentionally Prohibited
- **Status:** **`[CONFIRMED]`**
- **Evidence:** [`backend/api/v1/auth.py`](../backend/api/v1/auth.py#L112-L126).
- **Finding Analysis:** `dev-session` enforces three consecutive security gates:
  1. `if not settings.ENABLE_DEV_SESSION: raise HTTPException(403)`
  2. `if settings.APP_ENV not in (AppEnv.DEVELOPMENT, AppEnv.TEST): raise HTTPException(403)`
  3. `is_local = client_host in ("127.0.0.1", "localhost", "::1", "testclient"); if not is_local: raise HTTPException(403)`
- **Readiness Implication:** This defense-in-depth design is **correct and must not be weakened** by removing loopback checks or exposing unauthenticated token minting to the open internet. To support hosted evaluator access safely, a dedicated, tenant-fenced demo authentication route scoped exclusively to `org_sme_eval` must be designed.

---

### Finding 6: `/api/v1/system/reset-demo` Disabled in Production/Staging
- **Status:** **`[CONFIRMED]`**
- **Evidence:** [`backend/api/v1/system.py`](../backend/api/v1/system.py#L39-L40).
- **Finding Analysis:** Line 39 explicitly raises:
  ```python
  if settings.APP_ENV in (AppEnv.PRODUCTION, AppEnv.STAGING):
      raise HTTPException(status_code=403, detail="Demo reset is disabled in production and staging.")
  ```
- **Readiness Implication:** When deployed with `APP_ENV=production`, the UI's "Reset Workspace Demo Data" button returns HTTP 403. An evaluator cannot re-seed the workspace without a controlled demo reset policy for `org_sme_eval`.

---

### Finding 7: Flagship Persisted Processing Run View
- **Status:** **`[CONFIRMED]`**
- **Evidence:** [`frontend/src/components/InvoiceRunView.tsx`](../frontend/src/components/InvoiceRunView.tsx#L40) and [`backend/core/processing_events.py`](../backend/core/processing_events.py#L46-L75).
- **Finding Analysis:** The frontend component `InvoiceRunView.tsx` requests `GET /api/v1/invoices/{id}/processing`. The endpoint calls `processing_snapshot()`, which queries real `AuditEvent` records with `action IN ('PIPELINE_STAGE', 'DOCUMENT_UPLOADED', 'GMAIL_INVOICE_INGESTED')` and `processing_version = 1`.
- **Readiness Implication:** The run view is genuine and backed by actual PostgreSQL audit log rows, not synthetic client-side timers.

---

### Finding 8: Normal Hybrid Extraction Modality & Palmyra Vision Boundary
- **Status:** **`[CONFIRMED]`**
- **Evidence:** [`engine/hybrid_extractor.py`](../engine/hybrid_extractor.py#L180-L215) and [`engine/palmyra_benchmark_runner.py`](../engine/palmyra_benchmark_runner.py).
- **Finding Analysis:**
  1. In `engine/hybrid_extractor.py`, if a document has fewer than 20 characters of extractable text, it is classified as `DocumentType.SCANNED_IMAGE` and immediately returned as `FLAGGED_HITL_REVIEW`. It does **not** invoke `PalmyraVisionAdapter`.
  2. Palmyra Vision was implemented and evaluated in a separate benchmark script (`engine/palmyra_benchmark_runner.py`), where it was determined to lack bounding box provenance and was feature-flagged OFF in production.
- **Readiness Implication:** The active production pipeline fail-safes degraded scans to human review. Documentation must accurately describe this boundary rather than implying that live Palmyra vision models are actively parsing production scans.

---

### Finding 9: Conflicting Test Counts Across Documentation
- **Status:** **`[CONFIRMED]`**
- **Evidence:** Discrepant metrics across historical documentation files:
  - `PROJECT_STATUS.md`: Mentions 244 tests (Phase E) and 393 passed.
  - Historical evidence files: `baseline_tests.txt` (244), `broad.txt` (335), `final_tests.txt` (396 -> 404).
  - Current pytest output: **404 passed, 43 skipped, 0 failed** in 37.09s (`pytest tests/`).
- **Readiness Implication:** The documentation reflects historical milestones rather than deliberate contradictions, but creating an authoritative, unified test ledger eliminates any perception of discrepancy.

---

### Finding 10: Dockerfile Runs Flagship While `run.py` Runs Standalone Engine
- **Status:** **`[CONFIRMED]`**
- **Evidence:** [`Dockerfile`](../Dockerfile#L74) line 74 vs [`run.py`](../run.py#L60) line 60.
- **Finding Analysis:**
  - `Dockerfile` executes: `CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080", ...]`
  - `run.py` executes: `uvicorn.run("engine.server:app", host="127.0.0.1", port=8001, ...)`
- **Readiness Implication:** This creates severe product confusion. A developer running Docker gets the flagship AP Command Center, while an evaluator running `python run.py` gets the standalone regex mock.

---

### Finding 11: Rejection of Shared Bearer-Token Links & Selection of Real Evaluator Auth
- **Status:** **`[CONFIRMED & REMEDIATED]`**
- **Evidence:** [`frontend/src/components/AuthScreen.tsx`](../frontend/src/components/AuthScreen.tsx), [`frontend/src/utils/oauth.ts`](../frontend/src/utils/oauth.ts), and [`frontend/src/api/client.ts`](../frontend/src/api/client.ts).
- **Finding Analysis:**
  1. Distributing pre-minted bearer tokens via URLs (`https://app/#access_token=...`) is an anti-pattern:
     - **Client-Side Mechanics Clarification:** URL fragments (`#...`) are processed purely by the client browser DOM and are never transmitted across the network in HTTP request headers to the server.
     - However, placing bearer tokens in URL fragments remains an unsafe credential distribution mechanism:
       - Fragment-bearing URLs persist in browser navigation history, bookmarks, and clipboard logs.
       - URL links are easily forwarded, leaked via chat logs, or exposed to shoulder-surfing.
       - Distributing a shared token destroys non-repudiation: all evaluator actions (approvals, exception overrides, audit logs) collapse into a single synthetic identity.
       - Pre-minted tokens expire (typically 1 hour), causing evaluator lockouts, while long-lived tokens create indefinite replay vulnerabilities without revocation capability.
  2. Evaluator Authentication Architecture Implemented:
     - **Primary: Supabase Auth Passwordless Email OTP.**
       - Frontend sends OTP via Supabase Auth REST API (`POST /auth/v1/otp`) with `create_user: false`. This guarantees that unauthorized visitors cannot register arbitrary unprovisioned accounts in the identity provider.
       - Evaluator enters the 6-digit code received via email; the frontend verifies it via `POST /auth/v1/verify` (type `email`) to receive an authentic, cryptographically signed Supabase session (`access_token` and `refresh_token`).
       - Server-side membership resolution (`resolve_server_side_membership`) verifies that the email is pre-provisioned in `users` and assigned to `org_sme_eval`. Unknown or unassigned emails are barred with HTTP 403.
     - **Session Lifecycle & Differentiated 401 Handling:**
       - The API client (`frontend/src/api/client.ts`) distinguishes between normal token expiration and explicit session revocation.
       - **Session Revocation Safeguard:** If an HTTP 401 error contains details indicating token revocation (`Session token has been revoked`, `deactivated`, `older than the recovery security cutoff`), the client **strictly refuses to refresh the token**. It immediately purges `localStorage` session state (`clearSession()`) and terminates the session. This guarantees that backend token revocation cannot be circumvented by obtaining a new access token from Supabase GoTrue.
       - **Token Rotation & Multi-Tab Synchronization:** For standard expired tokens, the client deduplicates in-flight refresh requests into a single promise, coordinates across browser tabs via timestamp storage mutex (`ap_command_center_refresh_lock`), and calls Supabase GoTrue `POST /auth/v1/token?grant_type=refresh_token`.
       - **Sanitized Session Parsing:** `getAuthToken()` and `getRefreshToken()` strictly validate values, rejecting `'undefined'`, `'null'`, and whitespace strings.
       - **Dual-Termination Logout:** Logout invokes Supabase Auth `POST /auth/v1/logout?scope=global` (invalidating provider refresh sessions) and backend `POST /api/v1/auth/logout` (recording the access token hash in `revoked_access_tokens`) before clearing local storage.
     - **Secondary: Google OAuth.** Available for evaluators using corporate Google accounts where Google provider is enabled.
     - **Local Only: Dev-Session Quick Login.** Restricted strictly to loopback IP (`127.0.0.1`, `localhost`) when `APP_ENV=development`. Barred on public hosts.
- **Readiness Implication:** Evaluator access is authentic, individual, standards-compliant, and does not rely on shared credentials or URL token shortcuts.

---

### Finding 12: Elimination of Vulnerable Session Markers in Database Seeding Guard
- **Status:** **`[CONFIRMED & REMEDIATED]`**
- **Evidence:** [`engine/sme_eval_setup.py`](../engine/sme_eval_setup.py) and [`backend/core/config.py`](../backend/core/config.py).
- **Finding Analysis:**
  1. Previous implementations checked `db.info["is_isolated_test_db"]` and `current_setting('app.is_isolated_test_db')`. Both are application-controlled flags that can be executed on any connection.
  2. Multi-tenant checks (`Organisation.id != 'org_sme_eval'`) are masked by Row-Level Security (RLS) policies and return 0 on empty databases.
  3. If `APP_ENV=development` was set locally while `DATABASE_URL` accidentally targeted persistent production cloud databases, synthetic seeding could corrupt production records.
- **Remediation Implemented:**
  - Mandatory inspection of underlying database connection URL and engine dialect.
  - Non-bypassable Cloud Host Disallow Blocklist (`supabase.co`, `supabase.com`, `pooler.supabase.com`, `rds.amazonaws.com`, `render.com`, `neon.tech`, `elephantsql.com`, `aivencloud.com`, `timescale.com`, `cloudsql`).
  - Networked non-loopback databases strictly require `IS_DISPOSABLE_TEST_DATABASE=True` and a valid 16+ character `DEMO_SEEDING_AUTHORIZATION_KEY`.
  - Zero database credentials or secrets are logged or included in exceptions.

---

### Finding 13: Out-of-Band Evaluation Database Bootstrap Architecture
- **Status:** **`[CONFIRMED & IMPLEMENTED]`**
- **Evidence:** [`engine/bootstrap_eval_db.py`](../engine/bootstrap_eval_db.py) and [`tests/test_bootstrap_eval_db.py`](../tests/test_bootstrap_eval_db.py).
- **Finding Analysis:**
  1. A critical architectural tension existed: the runtime container running in production mode (`APP_ENV=production`) strictly disallows synthetic seeding and blocks all cloud hostnames to prevent data contamination.
  2. However, hosted evaluator acceptance requires an isolated cloud database instance pre-loaded with baseline procurement fixtures (vendors, POs, GRNs, QC inspection records).
  3. Attempting to seed via runtime web endpoints (`/api/v1/system/reset-demo`) would violate zero-trust production posture.
- **Remediation Implemented & Hardened:**
  - Implemented a dedicated administrative out-of-band CLI tool: `python -m engine.bootstrap_eval_db`.
  - Multi-factor safety gates enforced before any SQL write:
    1. **Explicit CLI Flag:** Requires `--confirm-isolated-eval-database`.
    2. **Secret Exposure Safeguards:** Secret key is read from environment variable `EVAL_BOOTSTRAP_SECRET_KEY` (minimum 32 characters). CLI emits a security warning if passed as a command argument to prevent leakage in process tables or shell history.
    3. **Explicit Database Identity & Production Blacklist:** Inspects `SELECT current_database()` and matches against `--expected-db-name`. Known default production identifiers (`"production"`, `"prod"`, `"main"`, `"live"`) are blocked unless explicitly confirmed.
    4. **RLS Bypass Privilege Check:** Executes `SET LOCAL row_security = OFF;` to confirm connection has privileges to bypass Row-Level Security; fails closed if restricted privileges could hide foreign customer records.
    5. **Zero Foreign Organizations & Users:** Verifies target contains zero organizations other than `org_sme_eval` and zero non-evaluation users.
    6. **Alembic Migration Gate:** Confirms target schema revision is at `013_revoke_access_tokens`.
    7. **Dry-Run Mode:** Supports `--dry-run` (or `--verify-only`) to run all inspection gates in read-only mode without modifying data.
- **Limitation Notice:** Local mock verification proves code logic correctness but does not independently establish cloud physical isolation. An out-of-band operator preflight check against the targeted Supabase project ref remains mandatory prior to staging evaluation.

---

## 3. Test Evidence Classifications & Unverified Hosted Runtime Matrix

### A. Classification of Test Evidence
- **Local Unit & Mocked Integration Suite:** **456 passed, 43 skipped, 0 failed** in 64.45s (`python -m pytest`, 499 collected), plus **12 passed, 0 failed** in Node.js (`node --test frontend/src/tests/auth_lifecycle.test.mjs`). Total **468 passing tests**.
  - These tests execute against isolated in-memory SQLite fixtures, local loopback connections, and mocked third-party adapters (Mantle LLM, Supabase Storage, Gmail API, SAP ERP).
  - They provide high confidence in deterministic rule math, RLS policies, audit immutability, schema consistency, and safety guards.
  - **They do NOT constitute live external-service verification.**
- **Historical Provider-Backed Acceptance Report:** Documented 6 November 2026 (`docs/inspection-evidence/provider-full-20261106/`).
  - Proves historical execution of 5 scenarios using 4 live AWS Bedrock Mantle calls (Qwen-235B) with 3,343 tokens ($0.004128 USD).
  - Cloud resources were cleaned up immediately following that test run (`"cloud_cleanup": "Supabase deleted; IAM user/key/policy deleted"`).

### B. Unverified Hosted Capabilities Matrix
The following runtime capabilities remain unverified until public cloud deployment:
| Capability | Current State | Verification Requirement for Public Launch |
| :--- | :--- | :--- |
| **1. Live Supabase Auth Sign-In** | Code implemented; unverified against live hosted IdP | External browser completes Email OTP verification and receives authentic JWT |
| **2. Current PostgreSQL Migration 013** | Target persistent DB at rev `010`; isolated rehearsals unapplied | Live DB migrated to revision `013` with `revoked_access_tokens` queryable |
| **3. Fresh PDF Browser Ingestion** | Local tests pass with mock/file upload | Evaluator uploads multi-page PDF directly through hosted web UI |
| **4. Current Provider-Backed Extraction** | Historical run on Nov 6; not verified on current instance | Document processed via active AWS Bedrock Mantle endpoint |
| **5. Durable Decision Persistence** | In-memory/SQLite pass; persistent DB unverified | Approved invoice, audit events, and ledger records persist across container restart |
| **6. Hosted Document Previews** | Signed URL generation tested; bucket permissions unverified | PDF renders in browser via authenticated Supabase Storage signed URL |
| **7. End-to-End HR Acceptance** | Local tests pass | External evaluator navigates inbox, reviews 3-pane matching, and signs off |

---

## 4. The Shortest Safe Path to Deployment Acceptance

```
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 1. Preflight Verification                                              │
  │    Validate render.yaml env vars (DATABASE_URL, SUPABASE_URL,          │
  │    STORAGE_BUCKET_NAME, MANTLE_API_KEY). APP_ENV=production.           │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 2. Dedicated Demo Database Strategy                                    │
  │    Ensure database target is an isolated evaluation instance or clone. │
  │    Strictly avoid multi-tenant production or unbacked shared instances.│
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 3. Migration Rehearsal (011 -> 012 -> 013)                             │
  │    Rehearse migrations on an isolated backup/clone per                 │
  │    docs/MIGRATION_READINESS_PROCEDURE.md. Verify revoked_access_tokens.│
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 4. Identity & Role Provisioning                                        │
  │    Configure Supabase Auth Email OTP provider. Provision HR evaluator  │
  │    identity in auth.users and map to org_sme_eval with role AP_LEAD.   │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 5. Synthetic PO/GRN/QC Baseline Initialization                         │
  │    Seed golden reference vendors, POs, GRNs, and QC approvals for the  │
  │    5 scenarios using authorized initialization script.                 │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 6. Storage & Mantle Connectivity Checks                                │
  │    Verify Supabase private bucket 'invoices' exists and accepts writes.│
  │    Perform test ping against AWS Bedrock Mantle API endpoint.          │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 7. Single-Container Build & Deployment                                 │
  │    Deploy multi-stage Dockerfile to Render Free / Cloud Run.           │
  │    Verify container healthcheck probe passes at /api/v1/liveness.      │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 8. Fresh-Browser Evaluator Acceptance                                  │
  │    Open incognito browser at public URL, sign in via Email OTP,        │
  │    upload sample invoice, verify 3-way match, and approve invoice.     │
  └────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Prioritized Remediation Roadmap

```
  ┌───────────────────────────────────────────────────────────────┐
  │                           PHASE P0                            │
  │     Flagship Production Readiness & Public Cloud Launch       │
  │  1. Safe DB migration & authenticated API functionality (013) │
  │  2. Production configuration correctness (STORAGE_BUCKET_NAME)│
  │  3. Safe evaluator auth & tenant fencing (org_sme_eval)       │
  │  4. Real PDF ingestion to decision execution                  │
  │  5. Primary public flagship deployment (Cloud Run / Render)   │
  │  6. Browser-based happy-path & edge-case acceptance tests     │
  └───────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
  ┌───────────────────────────────────────────────────────────────┐
  │                           PHASE P1                            │
  │               Evaluator Experience & Polish                   │
  │  • Reconcile README & PROJECT_STATUS test counts (404/43)     │
  │  • Seed & verify org_sme_eval golden scenarios & repeatable   │
  │    demo reset design                                          │
  │  • Prepare 5-minute video recording walkthrough & shotlist    │
  │  • Clarify Palmyra Vision / degraded scan modality boundary   │
  └───────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
  ┌───────────────────────────────────────────────────────────────┐
  │                           PHASE P2                            │
  │                Auxiliary Tooling & Enhancements               │
  │  • Standalone sandbox secondary deployment (--sandbox)        │
  │  • Secondary UI density polish & nonessential shortcuts       │
  └───────────────────────────────────────────────────────────────┘
```

---

## 6. Concrete Acceptance Criteria for Deployment Readiness

Before declaring the flagship AP Command Center ready for live evaluation, all of the following criteria must be met:

1. **Database Schema:** `alembic current` confirms revision `013_revoke_access_tokens` on the persistent database.
2. **Session Verification:** `GET /api/v1/dashboard/metrics` and `GET /api/v1/inbox` return `HTTP 200` with valid metrics when called with an authentic evaluator JWT.
3. **Container Boot:** `backend.main:app` starts up in `APP_ENV=production` without raising `ConfigurationError` (requires `STORAGE_BUCKET_NAME`).
4. **Safe Evaluator Access:** An evaluator visiting the planned primary public URL can authenticate into `org_sme_eval` via a tenant-fenced demo auth flow, view the 4 golden scenarios, inspect 3-pane evidence, and execute approvals without exposing development credentials.
5. **Launcher Truth:** `python run.py` launches the Flagship AP Command Center by default; `python run.py --sandbox` launches the standalone rules sandbox.
6. **Bounded Deterministic Safeguards:** All matching, tax math, and approval decisions are strictly governed by deterministic rules; degraded scans route fail-closed to `FLAGGED_HITL_REVIEW` with verified grounding boundaries.


---

## 7. Planned Primary HR Browser Acceptance Walkthrough (Staging Procedure)

> [!NOTE]
> **Walkthrough Scope & Status:** This document describes the planned acceptance procedure for external HR/evaluators testing the hosted AP Command Center once deployed to staging. It is **not** a report of a completed browser acceptance test. Pre-seeded golden scenarios (`APTC-001` through `APTC-038`) in `org_sme_eval` demonstrate baseline reference states; genuine acceptance requires uploading fresh invoice documents.

```
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 1. Evaluator Authentication & Session Management                       │
  │    - Visit the primary public staging URL in a fresh incognito window. │
  │    - Enter deliverable evaluator email (e.g. evaluator.zamp@gmail.com; │
  │      note: email identity must be provisioned in auth.users at staging)│
  │    - Frontend calls POST /auth/v1/otp (create_user: false).            │
  │    - Enter 6-digit OTP received via email -> Receive JWT session.      │
  │    - Server verifies user membership in org_sme_eval (AP_LEAD role).   │
  │    - If access token expires, client performs automatic refresh token   │
  │      rotation; if session is revoked, client immediately terminates.   │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 2. Fresh Multi-Page PDF Ingestion & Persisted Checkpoints              │
  │    - Evaluator clicks 'Upload Invoice' and selects a test invoice PDF. │
  │    - File is uploaded to private Supabase bucket 'invoices'.           │
  │    - Document is ingested with SHA-256 cryptographic payload hash.     │
  │    - Flagship streams progress via HTTP polling (pollRun query to      │
  │      GET /api/v1/invoices/{id}/processing), reading persisted          │
  │      PostgreSQL AuditEvent checkpoints:                                │
  │      • Stage 1: Classification & Optical Contrast Pre-screening.       │
  │      • Stage 2: Structured Entity Extraction (AWS Bedrock Mantle).     │
  │      • Stage 3: Mathematical Grounding Tripwires (bounding boxes).     │
  │      • Stage 4: Procurement Cross-Reference (Vendor, PO, GRN, QC).     │
  │      • Stage 5: Deterministic Policy Engine (7 Match Gates).           │
  │    (Note: The standalone engine uses SSE; the flagship uses persisted  │
  │     checkpoints and API polling).                                      │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 3. 3-Pane Reconciliation Workspace Inspection                          │
  │    - Left Pane: High-fidelity rendered PDF document via authenticated  │
  │      Supabase Storage signed URL (900s TTL).                           │
  │    - Middle Pane: Extracted Line Items, Contracted PO Reference, and   │
  │      Indian GST Math (CGST+SGST vs IGST within ₹20 tolerance).         │
  │    - Right Pane: The 7 Deterministic Matching Gates:                   │
  │      1. Active Vendor Master / GSTIN Registration                      │
  │      2. Purchase Order Authorization (Valid status, currency, supplier)│
  │      3. Goods Receipt Note (GRN) Receipt Confirmed                     │
  │      4. Quality Control (QC) Inspection Accepted                       │
  │      5. GST Arithmetic Reconciled (Subtotal+Tax==Total within ₹20.00,  │
  │         Line Total==Qty*Rate within ₹0.01; ungrounded lines block)     │
  │      6. PO Price & Quantity Tolerances (±1.50% rate, 0.00% over-qty,   │
  │         cumulative line drawdown, and total remaining PO balance)      │
  │      7. Duplicate Invoice Check (Vendor GSTIN + normalized invoice no) │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 4. Financial Governance & Approvals Execution                          │
  │                                                                        │
  │  • Single Approval Flow (Invoice Amount < ₹5,00,000 INR):              │
  │    - Example: APTC-001 (Amount: ₹4,10,000 INR, clean 3-way match).     │
  │    - AP Lead reviews evidence and clicks 'Approve Invoice'.            │
  │    - Transition: stage -> INTERNAL_APPROVAL_COMPLETE,                  │
  │                  decision -> MANUALLY_APPROVED.                        │
  │    - Immutable AuditEvent is permanently committed to PostgreSQL.      │
  │    - (Note: ERP GL voucher export is an offline/batch capability;      │
  │       no live GL vouchers table mutation occurs in the database).      │
  │                                                                        │
  │  • Strict Dual-Control Flow (Invoice Amount ≥ ₹5,00,000 INR):          │
  │    - Example: High-value commercial invoice exceeding threshold.       │
  │    - Step 1: AP Lead signs off -> stage: ACTION_REQUIRED,              │
  │              workflow_substatus: PENDING_SECOND_APPROVAL.              │
  │    - Step 2: Controller signs off -> stage: INTERNAL_APPROVAL_COMPLETE,│
  │              decision: MANUALLY_APPROVED.                              │
  │    - Anti-Self-Approval Enforcement: System strictly prohibits the     │
  │      first approver from granting second approval (HTTP 403 Forbidden).│
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 5. Exception Triage & Margin Protection (APTC-030)                     │
  │    - Evaluator inspects APTC-030 (unit rate ₹185.00 vs PO ₹170.00).    │
  │    - System flags +8.8% rate spike exceeding ±1.50% policy tolerance.  │
  │    - Payment is blocked; system generates recommended debit note for   │
  │      the ₹15/unit variance.                                            │
  │    - Evaluator can place on hold (HOLD_PENDING_EVIDENCE) or reject.    │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ 6. Audit Trail & Immutability Verification                             │
  │    - Evaluator inspects the immutable Audit Trail ledger.              │
  │    - Verifies append-only integrity protected by PostgreSQL database-  │
  │      level triggers (prevent_audit_events_mutation) and ORM listeners, │
  │      with actor attribution, before/after states, and UTC timestamps.  │
  └────────────────────────────────────────────────────────────────────────┘
```
