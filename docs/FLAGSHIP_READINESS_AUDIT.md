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

## 3. Prioritized Remediation Roadmap

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

## 4. Concrete Acceptance Criteria for Deployment Readiness

Before declaring the flagship AP Command Center ready for live evaluation, all of the following criteria must be met:

1. **Database Schema:** `alembic current` confirms revision `013_revoke_access_tokens` on the persistent database.
2. **Session Verification:** `GET /api/v1/dashboard/metrics` and `GET /api/v1/inbox` return `HTTP 200` with valid metrics when called with an authentic evaluator JWT.
3. **Container Boot:** `backend.main:app` starts up in `APP_ENV=production` without raising `ConfigurationError` (requires `STORAGE_BUCKET_NAME`).
4. **Safe Evaluator Access:** An evaluator visiting the planned primary public URL can authenticate into `org_sme_eval` via a tenant-fenced demo auth flow, view the 4 golden scenarios, inspect 3-pane evidence, and execute approvals without exposing development credentials.
5. **Launcher Truth:** `python run.py` launches the Flagship AP Command Center by default; `python run.py --sandbox` launches the standalone rules sandbox.
6. **Bounded Deterministic Safeguards:** All matching, tax math, and approval decisions are strictly governed by deterministic rules; degraded scans route fail-closed to `FLAGGED_HITL_REVIEW` with verified grounding boundaries.
