# AP Command Center — Implementation Notes & Phase A Acceptance Scorecard

**Author:** AP Engineering Team  
**Execution Timestamp:** 2026-10-31  
**Scope:** Phase A Foundation (Binding Engineering Contract)  
**Governing Standard:** Production Truth Rules (Zero Invented Data, Real Integrations or BLOCKED, Immutable Audit)

---

## 1. Architecture & Core Components Delivered

Phase A establishes the binding production foundation for the Autonomous Accounts Payable Command Center without any synthetic business data, fictional suppliers, or simulated integration progress.

### Backend Architecture
- **Framework:** Python 3.12, FastAPI, Pydantic v2 strict schemas, SQLAlchemy 2.0 ORM.
- **Relational Storage:** PostgreSQL architecture managed exclusively via Alembic migrations (`001_initial_schema.py`). Production & Staging strictly reject SQLite or in-memory databases via settings validators.
- **Audit Immutability:** Multi-tiered defense-in-depth:
  1. Database-level trigger (`trg_audit_events_immutable`) on `audit_events` raising an exception on any UPDATE or DELETE statement.
  2. Database permissions structure (`REVOKE UPDATE, DELETE ON TABLE audit_events FROM ap_app_user;`).
  3. SQLAlchemy ORM event listeners intercepting `before_update` and `before_delete` on `AuditEvent`.
- **Identity & RBAC:** Server-side OIDC/SAML integration structure enforcing 6 distinct operational roles (`AP_ASSOCIATE`, `AP_LEAD`, `CONTROLLER`, `CATEGORY_MANAGER`, `AUDITOR`, `SYSTEM_ADMIN`). Returns HTTP 401 for unauthenticated requests and HTTP 403 for unauthorized actions. No user-switcher or client-side bypass.
- **Object Storage Adapter:** Private encrypted object storage adapter (`s3` / `gcs`) with KMS encryption and presigned URL access. Strictly blocks fallback to unencrypted local disk in production.

### Frontend Operational UI
- **Stack:** React 19, TypeScript, Vite, Tailwind CSS v4, Lucide icons.
- **Design Standard:** Calm, dense finance-operations design; neutral canvas (`#090d16`), subtle borders, monospace tabular numbers, Indian rupee grouping (`en-IN`), 8pt grid, WCAG AA contrast.
- **Routes Delivered (All 7 Required Views):**
  1. `/dashboard`: Persisted invoice metrics, decision counts, and exposure totals computed from live DB queries. Returns `status: "unavailable"` when DB is unconfigured, and `0` only when a live DB query returns zero rows.
  2. `/connections`: Verified status cards for Identity, Gmail, SAP ERP, and Encrypted Storage. Authenticated PDF upload intake with SHA-256 verification and quarantine table.
  3. `/inbox`: Server-paginated invoice ledger with filters for stage and decision. Truthful empty state.
  4. `/invoices/:id`: Three modular panes: (1) Document & Extracted Field evidence, (2) 5-way line reconciliation and net payable waterfall, (3) Decision gates, dual-control chain, and append-only audit timeline.
  5. `/exceptions`: Priority queue sorted primarily by legally verified MSME statutory deadline, then exposure amount.
  6. `/source-records`: Read-only SAP S/4HANA snapshots (Vendors, POs, GRNs, QC).
  7. `/audit`: Append-only audit events table with query filters and audited CSV compliance export.

---

## 2. Phase A Acceptance Scorecard

| # | Acceptance Criterion | Required Evidence | Verification Result | Status |
|---|---|---|---|:---:|
| 1 | **Fresh start has no invented business data** | Database tables are unseeded; API returns 0 rows; zero sample/mock vendors or invoices exist. | `test_fresh_database_has_zero_invented_data` verified empty ledger and 0 records. | **PASS** |
| 2 | **Schema only via migrations** | Database schema created strictly via Alembic (`001_initial_schema.py`); startup does not execute unmanaged DDL. | Alembic migration generated pristine DDL for all 25 tables and trigger functions. | **PASS** |
| 3 | **Production rejects SQLite / in-memory / seed mode / local auth bypass** | Settings validator raises `ConfigurationError` when `APP_ENV=production` and `DATABASE_URL` is SQLite or local auth bypass is enabled. | `test_config_invariants.py` proved production rejects SQLite, in-memory DBs, and auth bypass. | **PASS** |
| 4 | **Protected routes/APIs reject unauthenticated users** | Protected API requests without a valid Bearer token return HTTP 401 Unauthorized. | `test_unauthenticated_request_rejected_on_protected_routes` confirmed 401 across all protected routes. | **PASS** |
| 5 | **Every mutation checks server-side identity & role** | Mutation endpoints verify authenticated role against RBAC matrix; unauthorized roles receive HTTP 403 Forbidden. | `test_auditor_role_barred_from_executing_mutations` proved auditors cannot execute actions (HTTP 403). | **PASS** |
| 6 | **DB rejects audit UPDATE/DELETE and tests prove it** | Database trigger and ORM listeners raise an exception upon any attempted modification or deletion of `audit_events`. | `test_audit_immutability.py` proved both raw SQL and ORM update/delete fail and roll back. | **PASS** |
| 7 | **Private storage access control** | S3 adapter rejects unconfigured access; no local-disk production fallback; presigned time-bounded URLs. | `test_storage_access_control.py` proved missing credentials raise StorageNotConfiguredError and reject fallback. | **PASS** |
| 8 | **All 7 routes display honest empty/setup states** | Frontend routes (`/dashboard`, `/connections`, `/inbox`, `/invoices/:id`, `/exceptions`, `/source-records`, `/audit`) show truthful empty/setup states without fake placeholders. | Verified in Vite build and live HTTP 200 route checks. | **PASS** |
| 9 | **Dashboard has no fabricated counts, activity, or zeroes** | Metrics endpoint returns `status: "unavailable"` when inputs are incomplete; returns zero only when a live DB query returns zero rows. | `test_dashboard_metrics_computes_exact_live_zeros` verified live query behavior. | **PASS** |
| 10 | **Missing dependencies reported without secret disclosure** | Connections and Health endpoints report missing credentials with required environment variable names; zero secret values, keys, or passwords logged or serialized. | `test_redacted_dict_masks_secrets` and `test_health_check_reports_truthful_subsystem_readiness` passed. | **PASS** |

---

## 3. Test Execution Summary

### Phase A Automated Verification Suite (`tests/phase_a/`)
Command: `python -m pytest tests/phase_a/ -v`
```
tests/phase_a/test_audit_immutability.py::test_audit_event_insertion PASSED
tests/phase_a/test_audit_immutability.py::test_audit_event_update_rejected_by_orm_and_db PASSED
tests/phase_a/test_audit_immutability.py::test_audit_event_delete_rejected_by_orm_and_db PASSED
tests/phase_a/test_auth_and_rbac.py::test_unauthenticated_request_rejected_on_protected_routes PASSED
tests/phase_a/test_auth_and_rbac.py::test_authenticated_user_access_succeeds PASSED
tests/phase_a/test_auth_and_rbac.py::test_auditor_role_barred_from_executing_mutations PASSED
tests/phase_a/test_auth_and_rbac.py::test_dual_control_rejects_self_approval PASSED
tests/phase_a/test_config_invariants.py::test_production_rejects_missing_database_url PASSED
tests/phase_a/test_config_invariants.py::test_production_rejects_sqlite PASSED
tests/phase_a/test_config_invariants.py::test_staging_rejects_in_memory_db PASSED
tests/phase_a/test_config_invariants.py::test_production_rejects_local_auth_bypass PASSED
tests/phase_a/test_config_invariants.py::test_production_rejects_missing_storage_bucket PASSED
tests/phase_a/test_config_invariants.py::test_redacted_dict_masks_secrets PASSED
tests/phase_a/test_honest_states_and_no_fictional_data.py::test_fresh_database_has_zero_invented_data PASSED
tests/phase_a/test_honest_states_and_no_fictional_data.py::test_dashboard_metrics_computes_exact_live_zeros PASSED
tests/phase_a/test_honest_states_and_no_fictional_data.py::test_health_check_reports_truthful_subsystem_readiness PASSED
tests/phase_a/test_honest_states_and_no_fictional_data.py::test_upload_rejects_non_pdf_file PASSED
tests/phase_a/test_honest_states_and_no_fictional_data.py::test_upload_rejects_corrupted_pdf_header PASSED
tests/phase_a/test_storage_access_control.py::test_production_storage_rejects_unconfigured_credentials PASSED
tests/phase_a/test_storage_access_control.py::test_storage_adapter_no_local_disk_production_fallback PASSED
tests/phase_a/test_storage_access_control.py::test_in_memory_test_adapter_signed_urls PASSED

======================= 21 passed in 0.21s =======================
```

### Preserved Legacy Verification Suite
Command: `python -m pytest tests/test_api.py tests/test_engine.py tests/test_hardening.py`
```
======================== 31 passed in 3.47s ========================
```
**Total Passing Automated Tests:** 52 tests with 0 failures.

### Frontend Production Build
Command: `cd frontend; npm run build`
```
vite v8.3.5 building client environment for production...
✓ 2054 modules transformed.
dist/index.html                   0.45 kB │ gzip:  0.29 kB
dist/assets/index-4hkhn-Dl.css   29.89 kB │ gzip:  5.96 kB
dist/assets/index-DRYmBskK.js   291.35 kB │ gzip: 83.91 kB
✓ built in 593ms
```

---

## 4. Operational Classification: Implemented vs Operational vs Blocked

- **IMPLEMENTED & TESTED (Code complete & verified by automated tests):**
  - Database schema & Alembic migration system (25 tables, constraints, indexes).
  - Database-enforced and ORM-enforced append-only immutability for audit events.
  - Server-side RBAC and Bearer token authentication engine.
  - Dual-control approval state machine for high-value invoices.
  - Private encrypted object storage adapter interface with time-bounded presigned URLs.
  - All 7 operational route APIs under `/api/v1/`.
  - Health check endpoint inspecting all 5 operational subsystems.
  - Production invariant validator rejecting SQLite, in-memory DBs, and local-auth bypass in production/staging.

- **OPERATIONAL (Currently running and serving live):**
  - FastAPI server actively listening on `http://127.0.0.1:8000` / `http://localhost:8000`.
  - Compiled React SPA mounted and serving truthful setup/empty states with SPA fallback routing.
  - Live diagnostics endpoint returning JSON at `/api/v1/health`.
  - OpenAPI Swagger documentation at `/docs`.

- **BLOCKED (Requires customer credentials, infrastructure, or policy sign-off):**
  - PostgreSQL live instance connection string (`DATABASE_URL`).
  - Enterprise OIDC / Google Workspace credentials (`OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_ISSUER_URL`).
  - Private encrypted S3 bucket & AWS IAM credentials (`STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).
  - Google Cloud Project with `gmail.readonly` scope and authorized mailbox (`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`).
  - SAP S/4HANA OData read-only API endpoint and service account credentials (`SAP_API_BASE_URL`, `SAP_CLIENT_ID`, `SAP_COMPANY_CODE`).
  - Authoritative GSTN and Udyam API access for external statutory verification.
  - Written finance & tax sign-off on MSMED Act deemed acceptance rules, Section 16 interest compounding method, and Income-tax Act, 2025 commencement interpretation.

---

## 5. Phase B — Stage 1: Relational Tenant Isolation & PostgreSQL RLS

### Delivered Components
1. **Relational Tenant Isolation (`002_tenant_isolation_and_rls.py`):**
   - Added `org_id` column to all 17 child entities.
   - Converted single-column foreign keys to composite foreign keys `(org_id, parent_id)`.
   - Isolated business identifiers (PO numbers, GRN numbers, vendor codes, idempotency keys) per tenant with `UNIQUE (org_id, <identifier>)`.
   - Implemented soft-deletion for documents (`is_deleted`, `deleted_at`, `deleted_by_user_id`).
2. **PostgreSQL RLS Implementation (Migration 002):**
   - RLS enabled on all 25 tables (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY;`).
   - RLS forced for table owners (`ALTER TABLE ... FORCE ROW LEVEL SECURITY;`).
   - Tenant isolation policy created `AS PERMISSIVE` for role `ap_app_user`:
     `org_id::text = NULLIF(TRIM(current_setting('app.current_org_id', true)), '')`.
   - Security audit confirmed: zero cleartext passwords in migration files.
3. **Transaction-Local Tenant Context:**
   - `set_tenant_context(session, org_id)` invokes `SELECT set_config('app.current_org_id', :org_id, true)` with `is_local=true`.
   - Pool check-in hook resets tenant context (`RESET ALL`).

---

## 6. Phase B — Stage 2: Authentication & User Provisioning

### Delivered Components
1. **Supabase Auth Cryptographic JWT Verification (`backend/core/auth.py`):**
   - Supports Supabase Auth tokens signed with `SUPABASE_JWT_SECRET` (or `SECRET_KEY` in test mode).
   - Strict verification of signature, issuer (`SUPABASE_ISSUER`), audience (`SUPABASE_AUDIENCE`), expiry (`exp`), and required subject/email claims (`sub`, `email`).
   - Unsigned or unverified tokens are rejected with HTTP 401 Unauthorized.
2. **Server-Side Membership Resolution & RLS Bootstrap:**
   - Server resolves user identity and active organisation memberships from the database *before* setting tenant context.
   - Solves chicken-and-egg bootstrap problem using `resolve_user_memberships(auth_user_id, email)` PostgreSQL `SECURITY DEFINER` function (owned by `postgres`, granted to `ap_app_user`) or un-scoped lookup before tenant context binding.
   - Returns unprovisioned profile if user is authenticated in Supabase but lacks active organisation membership.
3. **Strict Invitation-Only Provisioning (`backend/api/v1/auth.py`):**
   - Only authorised administrators (`SYSTEM_ADMIN`, `CONTROLLER`, `AP_LEAD`) can issue invitations.
   - Privilege escalation barred: only `SYSTEM_ADMIN` can issue invitations for the `SYSTEM_ADMIN` role.
   - Single-use, cryptographically unpredictable 32-byte tokens (`secrets.token_urlsafe(32)`) stored as SHA-256 hashes with 7-day expiration.
   - Strict email identity matching: authenticated email MUST match the invitation recipient email.
   - Atomic redemption provisions `User` and `RoleAssignment`, updates status to `ACCEPTED`, logs immutable `AuditEvent`, and invalidates token.
4. **Access Request Workflow (`backend/api/v1/auth.py`):**
   - Uninvited employees can submit access requests (`POST /api/v1/auth/access-requests`).
   - Never grants automatic membership: records status `PENDING`.
   - Administrators review and approve/reject (`POST /api/v1/auth/access-requests/{id}/review`).
   - Duplicate pending requests rejected (HTTP 400).
5. **Anti-Self-Promotion & Revocation Enforcement:**
   - Users cannot modify their own role (`PATCH /api/v1/auth/users/{id}/role` rejects self-modification with HTTP 400).
   - Users cannot deactivate their own active account (`POST /api/v1/auth/users/{id}/deactivate` rejects self-deactivation with HTTP 400).
   - Deactivated users (`is_active=False`) fail closed on all subsequent tenant-scoped operations (HTTP 403).
6. **Frontend UI Implementation (React 19 + TypeScript):**
   - `AuthScreen.tsx`: Complete coverage of all 10 required UI states:
     1. Sign in with Google (Supabase Auth trigger).
     2. Authentication loading state (spinner / claim resolution).
     3. Authentication failure state (clear error notification).
     4. User authenticated, invitation pending (single-use token input).
     5. User authenticated, invitation expired (expired banner, prompt to request access).
     6. User authenticated, unprovisioned (Request Access form).
     7. User authenticated, access request pending (status banner).
     8. User authenticated, access request denied (rejection reason).
     9. User authenticated, active membership (full dashboard & application access).
     10. Logout state (terminates session, clears local storage).
   - `AccessManagementPage.tsx`: Dedicated admin portal for issuing invitations and reviewing employee access requests.

---

## 7. Stage 2 Acceptance Test Scorecard (`tests/phase_b/test_stage2_auth_provisioning.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 1 | `test_01_valid_supabase_jwt_accepted` | Valid Supabase JWT with signature, issuer, audience, and active membership succeeds (HTTP 200). | Verified `/auth/me` returns active profile with role and org. | **PASS** |
| 2 | `test_02_invalid_jwt_signature_rejected` | Untrusted signature rejected cryptographically (HTTP 401). | Verified rejection with "signature verification failed". | **PASS** |
| 3 | `test_03_expired_token_rejected` | Token with `exp` in the past rejected (HTTP 401). | Verified rejection with "expired". | **PASS** |
| 4 | `test_04_wrong_jwt_issuer_rejected` | Token with mismatched issuer claim rejected (HTTP 401). | Verified rejection with "claims validation failed". | **PASS** |
| 5 | `test_05_wrong_audience_rejected` | Token with mismatched audience claim rejected (HTTP 401). | Verified rejection with "claims validation failed". | **PASS** |
| 6 | `test_06_uninvited_user_denied_tenant_access` | Authenticated employee without membership denied tenant access (HTTP 403). | Verified `/auth/me` returns UNPROVISIONED, `/inbox` returns 403. | **PASS** |
| 7 | `test_07_valid_invitation_accepted` | Single-use invitation redeemed, creates User & RoleAssignment, invalidates token. | Verified active membership activated; reuse rejected (HTTP 400). | **PASS** |
| 8 | `test_08_invitation_email_mismatch_rejected` | Redeeming token with different signed-in email rejected (HTTP 400). | Verified rejection with "Email mismatch". | **PASS** |
| 9 | `test_09_expired_invitation_rejected` | Redeeming expired token rejected (HTTP 400), status marked EXPIRED. | Verified rejection and status transition to EXPIRED. | **PASS** |
| 10 | `test_10_request_access_does_not_create_active_membership` | Access request records PENDING, never grants automatic membership. | Verified `/inbox` remains 403; duplicates rejected (HTTP 400). | **PASS** |
| 11 | `test_11_only_authorized_administrators_can_approve_access_requests` | Non-admin review rejected (403); Admin approval creates active membership. | Verified applicant granted membership and accesses inbox (200). | **PASS** |
| 12 | `test_12_user_cannot_modify_their_own_role` | Anti-self-promotion prevents self-role changes and self-deactivation. | Verified HTTP 400 on self-role change and self-deactivation. | **PASS** |
| 13 | `test_13_cross_tenant_membership_selection_rejected` | Header `X-Tenant-ID` for non-member organisation rejected (HTTP 403). | Verified rejection with "not an active member of organisation". | **PASS** |
| 14 | `test_14_membership_revocation_takes_effect` | Deactivated membership (`is_active=False`) immediately fails closed. | Verified member denied subsequent access (HTTP 403). | **PASS** |
| 15 | `test_15_tenant_context_established_only_after_membership_validation` | Tenant context established strictly after membership is confirmed. | Verified `app.current_org_id` is None for unprovisioned users. | **PASS** |
| 16 | `test_16_existing_rbac_and_audit_immutability_preserved` | Auditor read-only preserved; audit events immutable against UPDATE/DELETE. | Verified auditor barred from mutations; audit changes raise errors. | **PASS** |

### Complete Regression Test Suite Summary (Post Stage 2)
- **Phase A Test Suite:** 21 PASSED, 0 FAILED.
- **Stage 1 & Stage 1.1 Test Suite:** 13 PASSED, 9 SKIPPED (live PostgreSQL RLS), 0 FAILED.
- **Stage 2 Test Suite:** 16 PASSED, 0 FAILED.
- **Legacy Engine & API Tests:** 31 PASSED, 0 FAILED.
- **Total:** **81 PASSED, 9 SKIPPED, 0 FAILED** (4.24s).
- **Frontend Production Build:** Passed cleanly (0 TypeScript errors, 434ms).

---

## 8. Stage 3: Supabase Storage & Document Ingestion Implementation

### 1. Architecture & Security Invariants Delivered
- **Storage Provider:** Supabase Storage private bucket (`invoices`) via official REST API with service role authentication.
- **Zero Local Disk Fallback:** In production and staging, local disk fallback is strictly barred. Storage missing credentials triggers explicit `StorageNotConfiguredError` and returns truthful `NOT_CONFIGURED` or `BLOCKED` health states.
- **Tenant Isolation Path Structure:** Documents are saved to `org_{org_id}/invoices/{document_id}/{filename}` where `org_id` is strictly extracted from the verified authenticated user session.
- **MIME & Byte Header Validation:** Checks for `application/pdf` and validates the magic byte signature `b"%PDF-"`. Non-PDF files or header corruptions are rejected with `HTTP 400 Bad Request`.
- **File Size Enforcement:** Respects the 50 MB Supabase Free limit via `settings.MAX_UPLOAD_FILE_SIZE_BYTES`. Files exceeding 50 MB are rejected with `HTTP 400 Bad Request`.
- **Cryptographic SHA-256 Hashing:** Calculated over the raw byte stream prior to storage upload and persisted in `Document.sha256_hash`.
- **Tenant Duplicate Detection:** Queries active tenant documents with matching `sha256_hash` within the same organisation (`org_id`). Duplicates return `HTTP 409 Conflict` with `status: "DUPLICATE_DETECTED"`.
- **Compensating Rollback:** Distributed write without 2PC: if the database transaction fails after saving to storage, an automatic compensating cleanup immediately invokes `storage_adapter.delete_file(storage_key)` to prevent untracked orphaned files.
- **Presigned URLs with Capped TTL:** Generates time-bounded presigned URLs capped at a maximum TTL of 300 seconds (`STORAGE_SIGNED_URL_EXPIRY_SECONDS = 300`).
- **Verified Download Streaming:** Downloads stream bytes from private storage after verifying calculated SHA-256 against `Document.sha256_hash`. Mismatches raise `HTTP 500` and log critical security alerts.
- **Cross-Tenant Access Denial:** All document access endpoints (`GET /{id}`, `GET /{id}/signed-url`, `GET /{id}/download`, `GET /{id}/preview`, `DELETE /{id}`, `POST /{id}/purge`) strictly verify `doc.org_id == current_user.org_id`. Cross-tenant attempts return `HTTP 403 Forbidden`.
- **Soft Deletion vs Permanent Purge Lifecycle:**
  - Soft delete (`DELETE /documents/{id}`) marks `is_deleted = True`, sets `deleted_at`, records `deleted_by_user_id`, preserves the physical file in storage, and appends an immutable `DOCUMENT_SOFT_DELETED` audit event.
  - Permanent purge (`POST /documents/{id}/purge`) is protected by dual-control authorization and statutory retention checks. Requires two distinct authorized approvers (`CONTROLLER` or `SYSTEM_ADMIN`). Returns honest `BLOCKED` responses if purge policy is disabled or document is within statutory retention period (`DOCUMENT_RETENTION_DAYS = 2920`). Deleting the physical file and DB document strictly preserves all audit history.
- **Frontend Operational UI:** `ConnectionsPage.tsx` implements honest upload states (`Validating`, `Uploading`, `Processing`, `Ready`, `Duplicate detected`, `Access denied`, `Failed`) and provides a live tenant document catalog with presigned URL preview, verified download, and soft-delete actions.

---

## 9. Stage 3 Acceptance Test Scorecard (`tests/phase_b/test_stage3_storage_ingestion.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 1 | `test_01_valid_pdf_upload_succeeds_and_creates_records` | Valid PDF upload succeeds, stores tenant-scoped file, records DB rows (`Document`, `Invoice`, `IngestionJob`, `AuditEvent`). | Verified HTTP 200, status QUEUED, and exact DB row creation. | **PASS** |
| 2 | `test_02_invalid_mime_type_rejected` | Non-PDF file extension/MIME rejected with HTTP 400. | Verified HTTP 400 with "Only PDF documents are supported". | **PASS** |
| 3 | `test_03_invalid_pdf_magic_byte_rejected` | PDF extension with corrupt header (missing `%PDF-`) rejected with HTTP 400. | Verified HTTP 400 with "Invalid PDF header signature". | **PASS** |
| 4 | `test_04_file_size_limit_enforcement` | Upload exceeding size limit (50 MB) rejected with HTTP 400. | Verified HTTP 400 with "exceeds maximum permitted size". | **PASS** |
| 5 | `test_05_sha256_calculation_and_persistence_verified` | SHA-256 hash computed accurately and matches original bytes in DB. | Verified cryptographic hash matches bytes. | **PASS** |
| 6 | `test_06_duplicate_detection_within_tenant` | Identical upload within tenant returns DUPLICATE_DETECTED (HTTP 409). | Verified HTTP 409 Conflict with status DUPLICATE_DETECTED. | **PASS** |
| 7 | `test_07_tenant_scoped_object_path_generation` | Path conforms to `org_{org_id}/invoices/{document_id}/{filename}` without path traversal. | Verified deterministic path construction and directory sanitation. | **PASS** |
| 8 | `test_08_cross_tenant_download_rejection` | Download of Tenant A document by Tenant B user rejected with HTTP 403. | Verified HTTP 403 Forbidden on cross-tenant download attempt. | **PASS** |
| 9 | `test_09_cross_tenant_signed_url_rejection` | Presigned URL generation for Tenant A document by Tenant B user rejected with HTTP 403. | Verified HTTP 403 Forbidden on cross-tenant signed URL attempt. | **PASS** |
| 10 | `test_10_failed_upload_handling` | Object storage connection failure fails cleanly with HTTP 503 without corrupting DB. | Verified HTTP 503 and zero dangling DB rows. | **PASS** |
| 11 | `test_11_database_failure_triggers_compensating_cleanup` | Database commit failure after file upload triggers compensating `delete_file` call. | Verified orphaned object deleted from storage adapter. | **PASS** |
| 12 | `test_12_soft_deletion_preserves_physical_file` | Soft delete sets `is_deleted=True` while physical file in storage is preserved. | Verified `is_deleted=True` and physical storage bytes intact. | **PASS** |
| 13 | `test_13_audit_event_generation_on_upload_soft_delete_and_purge` | Audit events generated for upload, soft delete, and dual-control permanent purge. | Verified immutable audit trail, dual approvers, and honest BLOCKED responses. | **PASS** |
| 14 | `test_14_storage_health_check_accuracy` | Storage adapter health check accurately distinguishes NOT_CONFIGURED, CONNECTED, DEGRADED, and BLOCKED. | Verified health status codes across all mock scenarios. | **PASS** |
| 15 | `test_15_live_supabase_integration_truthful_state` | Unconfigured storage reports NOT_CONFIGURED truthfully without simulation. | Verified no synthetic connected state when credentials absent. | **PASS** |

---

## 10. Stage 4: Gmail OAuth & Mailbox Ingestion Implementation

### 1. Architecture & Security Invariants Delivered
- **Dedicated Gmail Test Mailbox Architecture:** Avoids personal mailbox access; designed for a dedicated test project and AP mailbox (`test-ap-inbox@...`).
- **Three-Legged OAuth 2.0 Flow:** Initiated via `/api/v1/integrations/gmail/authorize` with state verification and minimum privileged scope: `https://www.googleapis.com/auth/gmail.readonly`.
- **Server-Side Refresh Token Encryption:** Symmetric AES-256 Fernet cipher (`encrypt_refresh_token`, `decrypt_refresh_token`). Refresh tokens are never persisted in plaintext and are masked in logging and serialized outputs.
- **Dedicated Mailbox Sync Pipeline:** Ingests genuine RFC-822 messages matching `has:attachment filename:pdf`. Downloads attachments, checks `%PDF-` magic bytes, enforces $\le 50$ MB file limit, and calculates SHA-256.
- **Tenant Path Isolation:** Attachments saved to `org_{org_id}/invoices/{document_id}/{filename}` in Supabase Storage.
- **Tenant Duplicate Detection:** Ingestion skips duplicate attachments within the same organisation based on SHA-256 hash.
- **Corrupt File Quarantine:** Corrupted headers or non-PDF attachments are quarantined in `QuarantinedDocument` with `quarantine_reason="MALFORMED_PDF"`.
- **Truthful Compliance Disclosure:** Status endpoint discloses CASA Tier 2 assessment requirement pending production authorization.

---

## 11. Stage 4 Acceptance Test Scorecard (`tests/phase_b/test_stage4_gmail_ingestion.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 1 | `test_01_token_encryption_and_decryption` | Fernet AES-256 encrypts refresh token; ciphertext hides plaintext; roundtrip decrypts accurately. | Verified encryption and decryption roundtrip. | **PASS** |
| 2 | `test_02_oauth_state_generation_and_tamper_detection` | HMAC-signed state prevents tampering and enforces 15-minute expiration. | Verified tamper rejection and expiration checks. | **PASS** |
| 3 | `test_03_oauth_authorization_url_generation` | Generates canonical Google OAuth URL with `gmail.readonly` scope; rejects unauthorized roles. | Verified URL parameters and role enforcement (HTTP 403). | **PASS** |
| 4 | `test_04_oauth_callback_stores_encrypted_token_and_emits_audit` | OAuth callback exchanges code, encrypts refresh token, updates `GmailAccount`, and emits `GMAIL_MAILBOX_CONNECTED` audit event. | Verified encrypted token persistence and audit record. | **PASS** |
| 5 | `test_05_mailbox_ingestion_downloads_valid_pdf_and_stores_in_supabase` | Mailbox sync downloads genuine PDF attachment, persists to storage, creates `Document`, `Invoice`, `IngestionJob`, and `AuditEvent`. | Verified end-to-end ingestion pipeline. | **PASS** |
| 6 | `test_06_corrupt_attachment_is_quarantined` | Non-PDF attachment header quarantined in `QuarantinedDocument` with `MALFORMED_PDF`. | Verified quarantine entry without document creation. | **PASS** |
| 7 | `test_07_duplicate_attachment_detection_skips_ingestion` | Existing SHA-256 within tenant skipped with `duplicates_skipped` increment. | Verified duplicate detection and idempotency. | **PASS** |
| 8 | `test_08_unconfigured_gmail_reports_truthful_status` | Missing credentials return `status: "NOT_CONFIGURED"`, `readiness: False`, and `HTTP 503` on authorize. | Verified truthful status without simulation. | **PASS** |
| 9 | `test_09_mailbox_disconnect_revokes_token_and_emits_audit` | Disconnect revokes account status, clears encrypted token, and emits `GMAIL_MAILBOX_DISCONNECTED` audit event. | Verified revocation and audit trail. | **PASS** |
| 10 | `test_10_casa_compliance_metadata_disclosure` | Status endpoint discloses `gmail.readonly` scope and pending CASA Tier 2 assessment. | Verified compliance metadata in status payload. | **PASS** |

---

## 12. Stage 4.1 & Stage 5: Gmail Ingestion Hardening and Pub/Sub Event Processing

### 1. Stage 4.1 Targeted Corrections Delivered
- **Fernet Specification Rectification:** Formally documented encryption as 128-bit AES in CBC mode with PKCS7 padding and HMAC-SHA256 authentication per RFC / cryptography.io Fernet specifications. Cryptography keys are strictly server-side injected (`GMAIL_ENCRYPTION_KEY`) and masked in all logs and outputs.
- **Atomic Single-Use State Nonce:** Replaced stateless signed strings with database-backed `OAuthStateNonce` table. Generates cryptographically secure 24-byte nonces with 10-minute expiry and session binding. Replaying or tampering with state nonces is immediately rejected with HTTP 400.
- **Reconnect Token Preservation:** Re-authenticating a connected mailbox preserves the existing encrypted refresh token if Google omits the refresh token on subsequent authorizations. Revoked refresh tokens transition connection status to `EXPIRED`.
- **Recursive MIME Attachment Traversal:** Supports complex MIME tree structures, extracting multiple attachments per email. Seamlessly handles both small inline attachments (`body.data`) and large attachments requiring external `messages.attachments.get` API calls (`body.attachmentId`).
- **Truthful Compliance Disclosure:** Status endpoint reports `PRODUCTION_GOOGLE_VERIFICATION_PENDING`. Clarifies that test project credentials are used for development, and CASA Tier 2 assessment plus Google OAuth verification remain required prior to commercial multi-tenant rollout.
- **Permanent Purge Governance:** Permanent purge remains strictly disabled (`ENABLE_PERMANENT_PURGE = False`) with statutory retention protection (`DOCUMENT_RETENTION_DAYS = 2920`) and dual-control approval requirements.

### 2. Stage 5 Architecture & Pub/Sub Event Processing Delivered
- **Mailbox Watch Registration (`users.watch`):** Implemented `register_gmail_watch` establishing push notifications to Google Cloud Pub/Sub topic `projects/.../topics/...` with inbox label filtering.
- **Pub/Sub Push Webhook Endpoint (`POST /api/v1/integrations/gmail/pubsub/push`):**
  - Authenticates incoming requests via Google-signed OIDC Bearer tokens.
  - Verifies token issuer (`https://accounts.google.com`), audience (`PUBSUB_VERIFICATION_AUDIENCE`), and service account email (`PUBSUB_SERVICE_ACCOUNT_EMAIL`).
  - Rejects unauthenticated, expired, or audience-mismatched requests with HTTP 401/400.
  - Immediately acknowledges valid notifications (HTTP 200) to prevent Pub/Sub delivery retries.
  - Zero sensitive payload exposure: Pub/Sub messages contain only `emailAddress` and `historyId`.
- **Durable Notification Persistence (`PubSubEvent`):**
  - Stores `pubsub_message_id`, `publish_time`, `mailbox_address`, `history_id`, `subscription`, and `payload_json` with status `RECEIVED` *before* initiating processing.
  - Idempotent deduplication: duplicate `messageId` values return HTTP 200 `DUPLICATE` without re-running ingestion.
- **History Synchronization (`users.history.list`):**
  - Incremental sync retrieves only messages added since the last stored `historyId`.
  - Atomically advances `account.last_history_id` upon successful processing.
  - Automatic 404 Resynchronization Fallback: If `history.list` returns HTTP 404 (`HistoryExpiredError`), the system logs the event, executes a full mailbox synchronization (`sync_gmail_mailbox`), and resets the watermark.
- **48-Hour Watch Renewal & 6-Hour Reconciliation:**
  - `renew_expiring_watches`: Scheduled background task renews watches nearing expiration (> 48 hours old).
  - `reconcile_all_active_mailboxes`: Periodic 6-hour audit compares mailbox state against processed invoices to catch any missed push notifications.

---

## 13. Stage 5 Acceptance Test Scorecard (`tests/phase_b/test_stage5_gmail_pubsub.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 1 | `test_01_gmail_watch_registration` | `setup_mailbox_watch` establishes watch and records `watch_status="ACTIVE"`, `historyId`, and expiration. | Verified watch registration and DB columns updated. | **PASS** |
| 2 | `test_02_valid_pubsub_push_accepted` | Valid Pub/Sub push notification with valid OIDC token acknowledged (HTTP 200) and processed. | Verified HTTP 200 and `PubSubEvent` status `COMPLETED`. | **PASS** |
| 3 | `test_03_missing_or_invalid_oidc_token_rejected` | Missing or forged OIDC token rejected with HTTP 401 Unauthorized. | Verified rejection on missing header and invalid signature. | **PASS** |
| 4 | `test_04_mismatched_audience_rejected` | Push notification with mismatched audience rejected with HTTP 400 Bad Request. | Verified rejection on incorrect audience claim. | **PASS** |
| 5 | `test_05_malformed_pubsub_payload_rejected` | Malformed payload (missing message, invalid base64, missing fields) rejected with HTTP 400. | Verified clean HTTP 400 rejection without crashing server. | **PASS** |
| 6 | `test_06_durable_persistence_before_processing` | Notification persisted to `PubSubEvent` with status `RECEIVED` before processing begins. | Verified durable DB record exists even when sync crashes. | **PASS** |
| 7 | `test_07_duplicate_notification_idempotent` | Duplicate Pub/Sub `messageId` acknowledged (HTTP 200 `DUPLICATE`) without duplicate invoice ingestion. | Verified idempotency and zero duplicate sync calls. | **PASS** |
| 8 | `test_08_history_sync_ingests_attachments` | `history.list` detects new messages, extracts PDF attachments, and stores invoices. | Verified 2 invoices ingested and watermark advanced. | **PASS** |
| 9 | `test_09_history_sync_failure_allows_retry` | History sync failure records status `FAILED` without advancing watermark, enabling safe retry. | Verified watermark preservation and successful retry. | **PASS** |
| 10 | `test_10_expired_history_id_triggers_fallback_reconciliation` | Expired `historyId` (HTTP 404) triggers full mailbox sync fallback and advances watermark. | Verified `fallback_full_sync=True` and watermark reset. | **PASS** |
| 11 | `test_11_watch_renewal_extends_expiration` | Watches older than 48 hours renewed; watches under 48 hours skipped to prevent spamming. | Verified renewal timing and expiration extension. | **PASS** |
| 12 | `test_12_revoked_mailbox_authorization_detected` | Revoked refresh token detected during watch setup or sync; transitions status to `EXPIRED`. | Verified `oauth_status="EXPIRED"` on token refresh 400. | **PASS** |
| 13 | `test_13_periodic_reconciliation_catches_missed_messages` | 6-hour periodic reconciliation reconciles overdue mailboxes and reports metrics. | Verified reconciliation audit and metrics reporting. | **PASS** |
| 14 | `test_14_tenant_isolation_pubsub_notifications` | Push notification for Mailbox A cannot ingest into Tenant B; unmapped mailboxes rejected. | Verified strict tenant isolation and `UNKNOWN_MAILBOX` handling. | **PASS** |
| 15 | `test_stage41_oauth_state_nonce_single_use_and_replay_rejection` | Stage 4.1: State nonces consumed atomically; replay attacks rejected with HTTP 400. | Verified single-use consumption and replay rejection. | **PASS** |
| 16 | `test_stage41_reconnect_preserves_existing_refresh_token` | Stage 4.1: Reconnecting mailbox preserves existing refresh token when Google omits it. | Verified refresh token retained and status `AUTHORIZED`. | **PASS** |
| 17 | `test_stage41_multi_attachment_and_mixed_inline_extraction` | Stage 4.1: Traverses complex MIME structures, extracting both inline and external attachments. | Verified inline `body.data` and `attachmentId` extraction. | **PASS** |
| 18 | `test_live_gmail_pubsub_pipeline` | Live Google Cloud Pub/Sub verification against real Google test mailbox. | Gracefully skipped when `LIVE_GMAIL_TESTS != 1`. | **SKIP** |

---

---

## 14. Stage 5.1: Pub/Sub Reliability Verification

### 1. Architectural Safeguards Delivered
- **Per-Mailbox Distributed Concurrency Lease:** Added `sync_lock_token` and `sync_lock_expires_at` columns to `gmail_accounts` (Alembic migration `006_stage51_mailbox_lock`). Implemented `mailbox_sync_lease` context manager providing atomic DB-backed lease acquisition. Concurrent notifications for the same mailbox safely detect lock contention and defer processing (`CONCURRENT_DEFERRED`) without corrupting mailbox history or watermarks.
- **Idempotency for Overlapping History:** Different Pub/Sub message IDs covering overlapping Gmail history do not create duplicate invoices, documents, or audit events due to tenant-isolated SHA-256 content deduplication (`Document.sha256_hash`).
- **Strictly Monotonic Watermark Invariant:** History watermarks (`account.last_history_id`) can only advance (`is_history_id_greater`). Notifications delivered out of order or referencing older history IDs are safely acknowledged (`OUT_OF_ORDER_SKIPPED`) without regressing the stored watermark.
- **Premature Advancement Prevention on Failure:** If message details or attachments fail to download during a sync run, the watermark is NOT advanced, allowing clean subsequent retry without data loss.
- **Partial Failure Retry Safety:** If a batch partially ingests before a failure, subsequent retries detect already-ingested attachments by SHA-256 and process remaining items without duplicating previously created records.
- **Durable Acknowledgement Hardening:** Enforced that the `PubSubEvent` database transaction must be committed before returning HTTP 200/204. If database persistence raises an error, `PubSubPersistenceError` is triggered, raising HTTP 500 (`Durable acknowledgement failed`), ensuring Google Cloud Pub/Sub retries delivery.
- **Scheduling Status Truthful Disclosure:** Updated `/api/v1/integrations/gmail/status` to explicitly document that 48-hour watch renewal and 6-hour reconciliation functions are implemented, but external automated triggers (Cloud Scheduler) are `NOT_CONFIGURED` until Cloud Run deployment preparation. No unapproved worker frameworks were introduced.

---

## 15. Stage 5.1 Acceptance Test Scorecard (`tests/phase_b/test_stage51_reliability.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 1 | `test_01_concurrent_notifications_mailbox_locking` | Concurrent notifications for the same mailbox acquire per-mailbox lease; contention defers cleanly (`CONCURRENT_DEFERRED`). | Verified lock contention detection and zero watermark corruption. | **PASS** |
| 2 | `test_02_overlapping_history_does_not_duplicate_invoices_or_audits` | Different Pub/Sub messages covering overlapping history skip duplicate SHA-256 files; zero duplicate invoices or audit events. | Verified `duplicates_skipped=1` and exact invoice count. | **PASS** |
| 3 | `test_03_strictly_monotonic_watermark_never_regresses` | Out-of-order notification with older `historyId` does not regress stored watermark (`OUT_OF_ORDER_SKIPPED`). | Verified stored watermark remains strictly unchanged. | **PASS** |
| 4 | `test_04_failed_processing_does_not_advance_watermark` | History sync failure records status `FAILED` without advancing watermark, enabling clean subsequent retry. | Verified unadvanced watermark and clean retry. | **PASS** |
| 5 | `test_05_out_of_order_notifications_handled_safely` | Delayed notification arriving after a newer notification is acknowledged without regressing watermark. | Verified safe acknowledgement and watermark preservation. | **PASS** |
| 6 | `test_06_partial_failure_retry_does_not_duplicate_records` | Retry after partial batch failure skips already-ingested item and ingests pending item without duplicates. | Verified 2 distinct invoices, 1 duplicate skipped, zero duplicate records. | **PASS** |
| 7 | `test_07_durable_acknowledgement_fails_on_db_commit_error` | If database commit fails during `PubSubEvent` persistence, webhook refuses HTTP 200/204 and returns HTTP 500. | Verified HTTP 500 error and refusal of acknowledgement. | **PASS** |
| 8 | `test_08_scheduling_status_reports_not_configured_for_external_triggers` | Status endpoint reports `NOT_CONFIGURED` for automated external triggers (Cloud Scheduler). | Verified truthful scheduling disclosure in status payload. | **PASS** |

---

### Complete Regression Test Suite Summary (Post Stage 5.1)
- **Phase A Test Suite:** 21 PASSED, 0 FAILED.
- **Stage 1 & Stage 1.1 Test Suite:** 13 PASSED, 9 SKIPPED (live PostgreSQL RLS), 0 FAILED.
- **Stage 2 Test Suite:** 16 PASSED, 0 FAILED.
- **Stage 3 Test Suite:** 15 PASSED, 0 FAILED.
- **Stage 4 Test Suite:** 10 PASSED, 0 FAILED.
- **Stage 5 Test Suite:** 17 PASSED, 1 SKIPPED (live GCP Pub/Sub), 0 FAILED.
- **Stage 5.1 Test Suite:** 8 PASSED, 0 FAILED.
- **Legacy Engine & API Tests:** 31 PASSED, 0 FAILED.
- **Total Test Suite:** **131 PASSED, 10 SKIPPED, 0 FAILED** (7.18s).
- **Frontend Production Build:** Passed cleanly (0 TypeScript errors, 477ms).

---

## 16. Stage 5.2: Recovery of Persisted but Unfinished Pub/Sub Events

### 1. Problem Addressed
In Stage 5/5.1, incoming Pub/Sub notifications were durably committed with status `RECEIVED` before synchronisation began. However, if a crash occurred during message fetching or if an event ended in `FAILED` or `CONCURRENT_DEFERRED` status, redelivery of the same Pub/Sub message ID would previously be short-circuited as a duplicate (`status == "DUPLICATE"`), leaving unfinished events permanently abandoned.

### 2. Architectural Recovery Mechanisms Delivered
- **Event Status Discrimination on Redelivery:**
  - Existing events with status `COMPLETED` or `OUT_OF_ORDER_SKIPPED` are acknowledged as `DUPLICATE` without re-running history synchronisation.
  - Existing events with status `RECEIVED`, `FAILED`, or `CONCURRENT_DEFERRED` are actively reclaimed for processing.
- **Retry Tracking & Timestamps:**
  - Added `retry_count` (Integer, default 0) and `last_attempted_at` (DateTime, UTC) to `gmail_pubsub_events` (Alembic migration `007_stage52_pubsub_recovery.py`).
  - Every retry incremented `retry_count` and updates `last_attempted_at`.
- **Per-Mailbox Lease Reclamation:**
  - Implemented `clean_expired_mailbox_locks(db)`: expired locks (`sync_lock_expires_at < now`) are safely cleared, preventing zombie leases from blocking subsequent event processing.
- **On-Demand Recovery Routine (`reclaim_unfinished_pubsub_events`):**
  - Scans `gmail_pubsub_events` for any events in `RECEIVED`, `FAILED`, or `CONCURRENT_DEFERRED` older than a configurable threshold (default 60 seconds).
  - Processes each event safely under the mailbox concurrency lease, respecting watermark monotonicity.
  - Automatically embedded in `reconcile_all_active_mailboxes` to clean expired locks and recover unfinished events during regular 6-hour maintenance.
- **Exposed API Endpoint:**
  - `POST /api/v1/integrations/gmail/pubsub/reclaim` allows authorized operators (`SYSTEM_ADMIN`, `CONTROLLER`) to trigger on-demand reclamation.
- **Watermark & Ingestion Invariants Preserved:**
  - If a reclaimed event's `historyId` is $\le$ the mailbox's current `last_history_id`, the event is safely marked `COMPLETED` or `OUT_OF_ORDER_SKIPPED` without duplicate fetching, because newer history syncs already advanced past that point.
  - Document deduplication via SHA-256 prevents duplicate invoices or audit entries if an event had partially ingested before failing.
- **Truthful Scheduling Disclosure:**
  - Updated `/api/v1/integrations/gmail/status` `scheduling.pubsub_recovery`:
    - `processing_mode: "SYNCHRONOUS_IN_WEBHOOK_WITH_ON_DEMAND_RECOVERY"`
    - `status: "NOT_CONFIGURED"`
    - Discloses that automated background worker scheduler is not configured until Cloud Run deployment preparation.

---

## 17. Stage 5.2 Acceptance Test Scorecard (`tests/phase_b/test_stage52_event_recovery.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 1 | `test_01_crash_after_persistence_leaves_event_in_received_status` | Crash after durable persistence leaves event in `RECEIVED` status with `retry_count=0`. | Verified persistence and initial status preservation. | **PASS** |
| 2 | `test_02_redelivery_of_received_event_reclaims_and_processes` | Redelivery of an event in `RECEIVED` status reclaims and processes it, incrementing retry count. | Verified event transitions `RECEIVED` -> `COMPLETED`, `retry_count=1`. | **PASS** |
| 3 | `test_03_retry_of_failed_events_reclaims_and_succeeds` | Retry of `FAILED` event reclaims and processes it, clearing previous error message. | Verified event transitions `FAILED` -> `COMPLETED`, `error_message=None`. | **PASS** |
| 4 | `test_04_recovery_of_concurrent_deferred_events` | Recovery of `CONCURRENT_DEFERRED` events processes them once lease is available. | Verified deferred event successfully reclaimed and completed. | **PASS** |
| 5 | `test_05_duplicate_completed_events_acknowledged_without_reprocessing` | Redelivery of `COMPLETED` event acknowledged as `DUPLICATE` without invoking Gmail API. | Verified zero re-sync calls and prompt duplicate acknowledgement. | **PASS** |
| 6 | `test_06_expired_processing_lease_recovery` | Expired processing lease (`sync_lock_expires_at < now`) is safely cleared and recovered. | Verified stale lease cleared and new lock acquired. | **PASS** |
| 7 | `test_07_no_duplicate_invoice_or_audit_creation_on_reclaim` | Reclaiming unfinished event skips already-ingested attachments via SHA-256 without duplicate records. | Verified exactly 1 invoice and 1 audit event retained. | **PASS** |
| 8 | `test_08_reclaim_endpoint_and_scheduling_status_disclosure` | Reclaim endpoint responds correctly and status documents synchronous execution & `NOT_CONFIGURED` scheduler. | Verified HTTP 200 and truthful scheduling disclosure. | **PASS** |

---

### Complete Regression Test Suite Summary (Post Stage 5.2)
- **Phase A Test Suite:** 21 PASSED, 0 FAILED.
- **Stage 1 & Stage 1.1 Test Suite:** 13 PASSED, 9 SKIPPED (live PostgreSQL RLS), 0 FAILED.
- **Stage 2 Test Suite:** 16 PASSED, 0 FAILED.
- **Stage 3 Test Suite:** 15 PASSED, 0 FAILED.
- **Stage 4 Test Suite:** 10 PASSED, 0 FAILED.
- **Stage 5 Test Suite:** 17 PASSED, 1 SKIPPED (live GCP Pub/Sub), 0 FAILED.
- **Stage 5.1 Test Suite:** 8 PASSED, 0 FAILED.
- **Stage 5.2 Test Suite:** 8 PASSED, 0 FAILED.
- **Legacy Engine & API Tests:** 31 PASSED, 0 FAILED.
- **Total Test Suite:** **139 PASSED, 10 SKIPPED, 0 FAILED** (7.22s).
- **Frontend Production Build:** Passed cleanly (0 TypeScript errors, 506ms).

---

## 18. Stage 6: Supabase Backup and Recovery Architecture

### 1. Architectural Safeguards Delivered
- **Zero-AWS, Low-Cost Operator Architecture:** Uses standard Supabase PostgreSQL and private Supabase Storage (`invoices` bucket) on Supabase Free plan. Zero AWS S3 or paid third-party backup dependencies.
- **Authenticated Encryption Container:** Backup archives are compressed as `.tar.gz` and encrypted using Fernet (128-bit AES in CBC mode with PKCS7 padding and HMAC-SHA256 authenticated encryption) via Python `cryptography`. Keys are generated via `generate_backup_encryption_key()` and stored outside the repository. Plaintext credentials, passwords, and service role keys are strictly excluded from archives.
- **Database Dump Completeness:**
  - `roles.sql`: Custom application roles (`ap_app_user`), schema grants, and explicit revoke of update/delete on `audit_events`.
  - `schema.sql`: Schema metadata and Alembic head revision tracking.
  - `data.sql`: Foreign-key topologically ordered data dump with `session_replication_role = replica;` to bypass audit immutability triggers during restore.
  - `metadata.json`: Table row counts and Alembic version.
- **Supabase CLI Dump Reality Documented:** By default, `supabase db dump` excludes platform schemas (`auth`, `storage`, `extensions`, `realtime`, etc.) and does not export custom roles without `--role-only`. Documented the mandatory 3-part export procedure in `OPERATIONS_RUNBOOK.md`.
- **Supabase Auth Recovery Limitations:** Free tier does not support automated cross-project password migration. Users are primarily Google OAuth users; `auth_summary.json` captures user IDs, emails, roles, and org assignments so operators can pre-provision users in fresh projects via Supabase Auth Admin API (`create_user`).
- **Physical Supabase Storage Backup:** Traverses pagination in private `invoices` bucket, downloads raw PDF bytes, and verifies SHA-256 against `Document.sha256_hash` records.
- **Comprehensive Manifest & Strict Failure Invariant:** Per-document manifest (`manifest.json`) records ID, org ID, bucket, storage path, filename, size, content type, SHA-256, and verification status (`VERIFIED`, `CORRUPTED`, `MISSING_FROM_STORAGE`, `UNINDEXED_STORAGE_OBJECT`). If any file is missing or corrupted, the backup is strictly marked `completion_status = "FAILED"`.
- **Destructive Restore Guardrail:** Restoration requires explicit `--confirm-restore` flag and targets clean disposable environments. Verifies restored SHA-256 hashes, document-to-invoice references, tenant isolation, and audit event preservation.
- **Operator CLI Scripts & API Endpoints:** Delivered `python -m backend.scripts.backup` and `python -m backend.scripts.restore`, plus `GET /api/v1/system/backup/status` and `POST /api/v1/system/backup/trigger`.
- **Truthful Scheduling Disclosure:** Status endpoint documents `execution_mode: "OPERATOR_MANUAL"` and `background_scheduler: "NOT_CONFIGURED"`.

---

## 19. Stage 6 Acceptance Test Scorecard (`tests/phase_b/test_stage6_backup_recovery.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 1 | `test_01_database_export_succeeds` | Database export generates valid DDL and data SQL without error. | Verified schema, data SQL, table counts, and auth summary. | **PASS** |
| 2 | `test_02_database_export_contains_expected_tables_and_data` | Export captures all domain tables (`organisations`, `users`, `invoices`, `documents`, `audit_events`). | Verified row counts and SQL statements. | **PASS** |
| 3 | `test_03_custom_application_roles_and_grants_accounted_for` | Roles export contains `ap_app_user`, schema grants, and audit immutability revoke. | Verified role creation DDL and permissions. | **PASS** |
| 4 | `test_04_storage_object_listing_handles_pagination` | Storage listing handles pagination and retrieves all items across pages. | Verified paginated chunking and aggregation. | **PASS** |
| 5 | `test_05_all_expected_invoice_files_are_exported` | Export downloads and packages all expected invoice files. | Verified 100% download and manifest inclusion. | **PASS** |
| 6 | `test_06_file_checksum_matches_document_record` | Computed SHA-256 matches the database `Document` record exactly. | Verified cryptographic byte-level integrity. | **PASS** |
| 7 | `test_07_missing_files_are_reported` | Missing storage file is flagged as `MISSING_FROM_STORAGE` and backup marked `FAILED`. | Verified detection and failure status. | **PASS** |
| 8 | `test_08_corrupted_files_are_rejected` | Altered file in storage is flagged as `CORRUPTED` and backup marked `FAILED`. | Verified SHA-256 mismatch detection and failure status. | **PASS** |
| 9 | `test_09_manifest_matches_exported_archive_contents` | Manifest recorded in archive accurately matches internal files and bytes. | Verified manifest structure and archive tarball contents. | **PASS** |
| 10 | `test_10_archive_encryption_and_decryption_work` | Authenticated Fernet encryption protects archive; wrong key or tampering raises `DecryptionError`. | Verified authenticated ciphertext integrity. | **PASS** |
| 11 | `test_11_restored_files_match_original_sha256` | Restored files into target storage match original SHA-256 checksums. | Verified restored bytes match originals byte-for-byte. | **PASS** |
| 12 | `test_12_failed_or_incomplete_backup_is_never_marked_successful` | Incomplete or corrupted backups are strictly flagged as `FAILED`. | Verified `completion_status == "FAILED"`. | **PASS** |
| 13 | `test_13_existing_audit_records_remain_intact` | Audit events are preserved and restored with identical properties. | Verified audit count, actor IDs, and actions restored. | **PASS** |
| 14 | `test_14_tenant_relationships_remain_valid_after_restoration` | Restored documents, invoices, and users retain exact `org_id` isolation. | Verified foreign keys, composite keys, and tenant ownership. | **PASS** |
| 15 | `test_15_live_supabase_backup_restore_truthful_state` | Live Supabase project verification reports `BLOCKED` when credentials not configured. | Gracefully skipped; reports `BLOCKED`. | **BLOCKED** |
| 16 | `test_16_restoration_without_confirmation_guard_fails_safe` | Attempting restoration without `confirm_restore=True` is strictly blocked. | Verified `BackupError` raised on unconfirmed restore. | **PASS** |
| 17 | `test_17_backup_status_endpoint_truthful_disclosure` | Status endpoint reports `NOT_CONFIGURED` when empty, and documents manual execution mode. | Verified HTTP 200 and truthful scheduling disclosure. | **PASS** |

---

## 20. Stage 6.1: Auth Recovery and Restore Integrity Verification

### 1. Architectural Safeguards Delivered
- **Official Supabase Auth Migration Realities:** Verified that `supabase db dump` excludes the `auth` schema by default. GoTrue Admin API does not reliably support arbitrary client-specified UUIDs across hosted projects. Restoring into a fresh Supabase project invalidates pre-existing sessions and tokens due to project-specific JWT secret rotation.
- **Automated User UUID Reconciliation Cascade:** Delivered `DatabaseBackupManager.reconcile_auth_user()` to reconcile newly generated GoTrue UUIDs with `public.users` and cascade updates to `role_assignments.user_id` inside an atomic transaction, recording an immutable `USER_AUTH_RECONCILED` audit event.
- **Deep Restore Integrity Validation (`verify_restore_integrity`):**
  - **Foreign Key Checker:** Iterates across `Base.metadata.sorted_tables` checking for orphaned foreign keys after `session_replication_role = replica;` restoration.
  - **Multi-Tenant Consistency:** Enforces strict `org_id` matching across `organisations`, `legal_entities`, `users`, `role_assignments`, `invoices`, `invoice_lines`, `documents`, and `audit_events`.
  - **Audit Immutability Trigger Test:** Executes an ORM modification inside a nested savepoint to verify that `trg_audit_events_immutable` actively blocks updates post-restore.
  - **Cryptographic Storage Verification:** Verifies restored document SHA-256 hashes against `manifest.json` and database records.
- **Secure Key Input Governance:** Enhanced `get_encryption_key()` to prioritize `BACKUP_ENCRYPTION_KEY` environment variable, provide a hidden interactive password prompt (`getpass.getpass()`), and warn if CLI `--key` flags are passed.

### 2. Stage 6.1 Acceptance Test Scorecard (`tests/phase_b/test_stage6_backup_recovery.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 18 | `test_18_foreign_key_violation_caught_post_restore` | Post-restore validation raises `DatabaseRestoreError` upon detecting orphaned records. | Verified detection and rollback. | **PASS** |
| 19 | `test_19_tenant_isolation_mismatch_caught_post_restore` | Post-restore validation raises `DatabaseRestoreError` upon detecting cross-tenant `org_id` mismatch. | Verified tenant boundary verification. | **PASS** |
| 20 | `test_20_audit_immutability_verification_post_restore` | Post-restore validation tests that audit immutability triggers actively reject mutation. | Verified trigger enforcement post-restore. | **PASS** |
| 21 | `test_21_secure_key_handling_prefers_env_and_warns_on_cli` | Key resolution prefers env vars, warns on CLI args, and supports hidden prompt. | Verified secure key handling. | **PASS** |
| 22 | `test_22_auth_reconciliation_updates_user_id_and_logs_audit` | User ID reconciliation cascades to role assignments and logs immutable audit event. | Verified cascade and audit record. | **PASS** |

---

## 21. Stage 7: Google Cloud Run Deployment Preparation

### 1. Architectural Safeguards Delivered
- **Multi-Stage Container Architecture (`Dockerfile`):**
  - Stage 1 (`frontend-builder`): Uses `node:20-slim` with `npm ci` and `npm run build` to compile the React TypeScript SPA.
  - Stage 2 (`runner`): Uses `python:3.12-slim` to assemble the FastAPI application, Alembic migrations, and static compiled frontend assets.
  - **Non-Root Execution:** Creates unprivileged user `appuser` (UID 1000, GID 1000) and explicitly switches to `USER appuser`.
  - **Port & Probing:** Exposes standard Cloud Run ingress port `8080` and defines Docker `HEALTHCHECK` targeting `/api/v1/liveness`.
- **Clean Container Packaging (`.dockerignore`):**
  - Excludes Git directories, Python bytecode, Node modules, local virtual environments, test suites, local backup archives, and `.env*` files while preserving `.env.cloudrun.example`.
- **Knative v1 Cloud Run Specification (`deploy/cloudrun/service.yaml`):**
  - Targets `asia-south1` (Mumbai).
  - Implements Pilot Scenario A (`minScale: 0`, `maxScale: 3`, `cpu: 1000m`, `memory: 512Mi`, `concurrency: 80`, `timeout: 300s`).
  - Enables `startup-cpu-boost` and `cpu-throttling` to optimize cold-start performance while staying within free allowances.
  - Configures `startupProbe` and `livenessProbe` targeting `/api/v1/liveness` on port 8080.
  - **Zero Plaintext Secrets:** Maps all database, Supabase, Gmail, and encryption keys from Google Secret Manager via `secretKeyRef`.
- **Automated Deployment & Cron Setup (`deploy/cloudrun/deploy.sh`):**
  - Pre-flight checks: Verifies `gcloud`, active GCP project, and verified billing account.
  - Service enablement: Enables Cloud Run, Artifact Registry, Secret Manager, Cloud Scheduler, Pub/Sub, and Cloud Build.
  - IAM Governance: Creates `ap-cloudrun-sa` with `roles/secretmanager.secretAccessor` and `gmail-pubsub-push` with `roles/run.invoker`.
  - Artifact Registry & Build: Automates container build and push via Google Cloud Build.
  - Cloud Scheduler Background Jobs: Configures 3 cron schedules with OIDC Bearer token authentication:
    1. Daily Gmail watch renewal (`0 0 * * *`).
    2. 6-hour Gmail missed-message reconciliation (`0 */6 * * *`).
    3. Daily encrypted backup (`30 20 * * *` = 02:00 AM IST).
- **Environment Contract (`.env.cloudrun.example`):**
  - Comprehensive documentation of all environment variables and corresponding Secret Manager secret names.
- **Dynamic Port & Server Binding:**
  - Enhanced `Settings` in `backend/core/config.py` to dynamically resolve `PORT` from the environment.
  - Updated `run_production.py` to bind to `0.0.0.0` and dynamic `PORT`.

### 2. Stage 7 Acceptance Test Scorecard (`tests/phase_b/test_stage7_cloudrun_deployment.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 1 | `test_01_dockerfile_structure_and_multistage` | Multi-stage Dockerfile builds React frontend and Python runtime cleanly. | Verified Node 20 builder and Python 3.12-slim runner. | **PASS** |
| 2 | `test_02_dockerfile_security_and_non_root_user` | Dockerfile creates unprivileged appuser (UID 1000), exposes 8080, and configures healthcheck. | Verified non-root execution and liveness probe. | **PASS** |
| 3 | `test_03_dockerignore_completeness` | .dockerignore excludes sensitive secrets, tests, node_modules, and backups. | Verified exclusion list completeness. | **PASS** |
| 4 | `test_04_cloudrun_service_yaml_structure_and_schema` | Service YAML conforms to Knative v1, region asia-south1, 512Mi limits, and probes. | Verified schema, autoscaling, and probe paths. | **PASS** |
| 5 | `test_05_cloudrun_service_yaml_secret_manager_references` | All 8 sensitive credentials bound via Secret Manager secretKeyRef without plaintext. | Verified zero plaintext secrets in YAML. | **PASS** |
| 6 | `test_06_cloudrun_deploy_script_validations` | deploy.sh executes pre-flight checks, IAM, Cloud Build, and Cloud Scheduler crons. | Verified API enablement and cron triggers. | **PASS** |
| 7 | `test_07_env_cloudrun_example_completeness` | .env.cloudrun.example provides honest template without placeholder credentials. | Verified variable completeness. | **PASS** |
| 8 | `test_08_config_port_environment_variable_precedence` | Settings dynamically adopts PORT=8080 from environment for Cloud Run compatibility. | Verified dynamic port resolution. | **PASS** |
| 9 | `test_09_production_liveness_and_health_probes` | /api/v1/liveness and /api/v1/health endpoints respond properly to container probes. | Verified HTTP 200 liveness and health diagnostics. | **PASS** |

---

### Complete Regression Test Suite Summary (Post Stage 7)
- **Phase A Test Suite:** 21 PASSED, 0 FAILED.
- **Stage 1 & Stage 1.1 Test Suite:** 13 PASSED, 9 SKIPPED (live PostgreSQL RLS), 0 FAILED.
- **Stage 2 Test Suite:** 16 PASSED, 0 FAILED.
- **Stage 3 Test Suite:** 15 PASSED, 0 FAILED.
- **Stage 4 Test Suite:** 10 PASSED, 0 FAILED.
- **Stage 5 Test Suite:** 17 PASSED, 1 SKIPPED (live GCP Pub/Sub), 0 FAILED.
- **Stage 5.1 Test Suite:** 8 PASSED, 0 FAILED.
- **Stage 5.2 Test Suite:** 8 PASSED, 0 FAILED.
- **Stage 6 & Stage 6.1 Test Suite:** 21 PASSED, 1 SKIPPED (live Supabase project BLOCKED), 0 FAILED.
- **Stage 7 Test Suite:** 9 PASSED, 0 FAILED.
- **Legacy Engine & API Tests:** 31 PASSED, 0 FAILED.
---

## 22. Stage 7.1: Deployment Readiness and Scheduler Security Corrections

### 1. Architectural Safeguards Delivered
- **Removal of Backup Scheduler from Cloud Run:** Removed `daily-encrypted-backup` from `deploy/cloudrun/deploy.sh`. Recognized that Cloud Run's ephemeral filesystem makes in-container backups non-durable. Backups remain strictly operator-driven via the Python CLI on trusted workstations and must be copied to offline/external storage. Backup status truthfully reports `execution_mode: "OPERATOR_MANUAL"` and `background_scheduler: "NOT_CONFIGURED"`.
- **Dedicated Cloud Scheduler Service Account:** Introduced `ap-cloud-scheduler-sa@<project>.iam.gserviceaccount.com`, strictly isolated from the Pub/Sub push identity (`gmail-pubsub-push`).
- **Application-Level Maintenance Verification (`require_maintenance_auth`):**
  - Secured `/watch/renew`, `/reconcile`, and `/pubsub/reclaim`.
  - Verifies incoming Google OIDC tokens against `CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL` and target audience.
  - Rejects unauthorized service accounts (e.g. `gmail-pubsub-push` or rogue identities) with HTTP 403 Forbidden.
  - Preserves full Supabase Auth JWT validation and RBAC for human operators (`SYSTEM_ADMIN` / `CONTROLLER`) as an administrative fallback.
  - Does not accept Google service account tokens on normal business routes.
- **Pub/Sub Acknowledgement Deadline Configuration (300s):**
  - Explicitly configured Pub/Sub push subscription `gmail-ap-inbox-push-sub` with `--ack-deadline=300`.
  - Aligned Cloud Run container timeout (`timeoutSeconds: 300`) and per-mailbox lease duration (`300s`).
  - Analyzed realistic Gmail synchronization timing: typical batches complete in 2–5 seconds; bursts of 20 invoices complete in 20–45 seconds.
  - If a timeout occurs, durable notification persistence and monotonic watermarks ensure duplicate delivery is safe and idempotently reclaimed.
- **Truthful Local Docker Availability Reporting:**
  - Evaluated local Docker status (`docker info`). When the Docker daemon is not active on the host, image build is truthfully marked `BLOCKED (Docker engine inactive on host)` rather than falsely reported as passed.
  - Container runtime invariants (liveness, health diagnostics, SPA fallback, dynamic port binding) verified via simulated test suites.
- **Deployment Script Safety Controls (`deploy/cloudrun/deploy.sh`):**
  - Displays target GCP project, region `asia-south1` (Mumbai), container specs (1 vCPU, 512 MB, min 0, max 3), zero AWS resources, and estimated costs (~$0.06/month for Scenario A) before prompting for operator confirmation.
  - Guard checks prevent execution without verified Secret Manager secrets.
  - Script prepared and validated, but NOT executed during this task.

### 2. Stage 7.1 Acceptance Test Scorecard (`tests/phase_b/test_stage7_cloudrun_deployment.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 10 | `test_10_backup_scheduler_excluded_from_deploy_script_and_status_truthful` | Automated backup trigger excluded from deploy.sh; status reports OPERATOR_MANUAL. | Verified absence from script and truthful status. | **PASS** |
| 11 | `test_11_scheduler_maintenance_auth_accepts_dedicated_service_account` | Dedicated Cloud Scheduler service account successfully triggers maintenance endpoints. | Verified OIDC token validation. | **PASS** |
| 12 | `test_12_scheduler_maintenance_auth_rejects_unauthorized_service_identity` | Unauthorized service accounts (e.g. Pub/Sub push identity) receive HTTP 403. | Verified rejection of non-scheduler service accounts. | **PASS** |
| 13 | `test_13_scheduler_maintenance_auth_accepts_human_system_admin_and_rejects_associate` | Human SYSTEM_ADMIN/CONTROLLER can trigger maintenance; AP_ASSOCIATE rejected. | Verified RBAC enforcement. | **PASS** |
| 14 | `test_14_pubsub_ack_deadline_and_lease_alignment` | Pub/Sub ack deadline configured to 300s matching Cloud Run request timeout. | Verified parameter alignment. | **PASS** |
| 15 | `test_15_docker_daemon_status_truthful_reporting` | Live Docker daemon status checked; reports BLOCKED when engine inactive. | Truthfully reported as BLOCKED. | **BLOCKED** |
| 16 | `test_16_container_runtime_invariants_and_frontend_asset_serving` | Container runtime invariants: liveness, health diagnostics, and SPA fallback verified. | Verified HTTP 200 responses. | **PASS** |

---

### Complete Regression Test Suite Summary (Post Stage 7.1)
- **Phase A Test Suite:** 21 PASSED, 0 FAILED.
- **Stage 1 & Stage 1.1 Test Suite:** 13 PASSED, 9 SKIPPED (live PostgreSQL RLS), 0 FAILED.
- **Stage 2 Test Suite:** 16 PASSED, 0 FAILED.
- **Stage 3 Test Suite:** 15 PASSED, 0 FAILED.
- **Stage 4 Test Suite:** 10 PASSED, 0 FAILED.
- **Stage 5 Test Suite:** 17 PASSED, 1 SKIPPED (live GCP Pub/Sub), 0 FAILED.
- **Stage 5.1 Test Suite:** 8 PASSED, 0 FAILED.
- **Stage 5.2 Test Suite:** 8 PASSED, 0 FAILED.
- **Stage 6 & Stage 6.1 Test Suite:** 21 PASSED, 1 SKIPPED (live Supabase project BLOCKED), 0 FAILED.
- **Stage 7 & Stage 7.1 Test Suite:** 15 PASSED, 1 SKIPPED (live Docker build BLOCKED), 0 FAILED.
- **Legacy Engine & API Tests:** 31 PASSED, 0 FAILED.
- **Total Test Suite:** **175 PASSED, 12 SKIPPED, 0 FAILED** (9.33s).
- **Frontend Production Build:** Passed cleanly (0 TypeScript errors, 489ms).

---

## 23. Stage 7.2: Final Secret Hygiene and Pub/Sub Timeout Safety

### 1. Implementation Summary

#### A. Cloud Run Secret Hygiene & Least-Privilege IAM
1. **Gmail Refresh Token Hygiene:**
   - Evaluated production multi-tenant architecture: Gmail refresh tokens are managed per tenant and stored encrypted in PostgreSQL (`gmail_accounts.encrypted_refresh_token` using Fernet).
   - Removed `GMAIL_REFRESH_TOKEN` / `ap-gmail-refresh-token` from `service.yaml`, `deploy.sh`, and production environment contracts.
   - Kept `GMAIL_REFRESH_TOKEN` optional in `backend/core/config.py` exclusively for local development and standalone harness testing.
2. **Operator Backup Key Exclusion:**
   - In accordance with Stage 7.1 ephemeral container protections, backups are managed exclusively by operators via CLI on trusted workstations.
   - Removed `BACKUP_ENCRYPTION_KEY` / `ap-backup-encryption-key` from `service.yaml`, `deploy.sh`, and Cloud Run service account access grants.
3. **Supabase JWT Verification Audit:**
   - Inspected `verify_token_claims` in `backend/core/auth.py`.
   - Verified that the implemented token verification routine requires `SUPABASE_JWT_SECRET` for cryptographically validating HMAC signatures on Supabase Auth JWTs.
   - Retained `SUPABASE_JWT_SECRET` (`ap-supabase-jwt-secret`) in Google Secret Manager as a mandatory server-side secret.
4. **Supabase Anon Key Separation:**
   - Classified `SUPABASE_ANON_KEY` as a public/client-facing publishable key.
   - Removed `ap-supabase-anon-key` from Secret Manager bindings in `service.yaml` and `deploy.sh`.
   - Configured `SUPABASE_ANON_KEY` as a standard environment variable (`value: "${SUPABASE_ANON_KEY}"`).
5. **Least-Privilege IAM Secret Accessor:**
   - Updated `deploy/cloudrun/deploy.sh` to restrict `roles/secretmanager.secretAccessor` bindings strictly to retained secrets (`ap-database-url`, `ap-secret-key`, `ap-supabase-service-key`, `ap-supabase-jwt-secret`, `ap-gmail-client-secret`, `ap-gmail-encryption-key`).

#### B. Pub/Sub and Cloud Run Timeout Safety
1. **Internal Processing Deadline (240s vs 300s):**
   - Configured `GMAIL_SYNC_TIMEOUT_SECONDS = 240` in `backend/core/config.py`, `service.yaml`, `deploy.sh`, and `.env.cloudrun.example`.
   - Provides a guaranteed 60-second safety margin below Cloud Run's 300-second container timeout and Pub/Sub's 300-second acknowledgement deadline.
2. **Individual External Call Bounding:**
   - Bounded all external Gmail API network requests and attachment downloads to 15 seconds (`timeout=15.0`).
3. **Safe Early Termination & Watermark Protection:**
   - In `sync_gmail_history` and `sync_gmail_mailbox`, tracked elapsed processing time.
   - If elapsed time approaches `GMAIL_SYNC_TIMEOUT_SECONDS`, the processing loop halts safely.
   - Documents and invoices processed so far are committed to PostgreSQL.
   - The mailbox watermark (`account.last_history_id`) is **NOT** advanced, preventing unprocessed backlog messages from being orphaned.
   - The exclusive per-mailbox lease (`with mailbox_sync_lease`) is released immediately upon exit.
   - The event status is preserved as `RECEIVED` with timeout details recorded in `error_message`.
4. **Deduplicated Unfinished Event Recovery:**
   - When Pub/Sub redelivers the event or the 30-minute maintenance reclaim job (`reclaim_unfinished_pubsub_events`) triggers, the event is re-processed.
   - Already-processed invoices are recognized via SHA-256 hash deduplication and skipped as duplicates (zero duplicate invoices or audit records).
   - Remaining messages are processed, and the watermark is safely advanced upon completion.

---

### 2. Stage 7.2 Acceptance Test Scorecard (`tests/phase_b/test_stage7_cloudrun_deployment.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 05 | `test_05_cloudrun_service_yaml_secret_manager_references` | Retains verified secrets; excludes anon key, refresh token, and backup key from Secret Manager. | Verified Knative manifest secret hygiene. | **PASS** |
| 06 | `test_06_cloudrun_deploy_script_validations` | deploy.sh checks retained secrets only, passes anon key via env vars, and sets timeout to 240s. | Verified deploy.sh automation rules. | **PASS** |
| 07 | `test_07_env_cloudrun_example_completeness` | .env.cloudrun.example documents public anon key, DB-backed refresh tokens, operator backup key, and 240s timeout. | Verified configuration contract completeness. | **PASS** |
| 17 | `test_17_secret_hygiene_and_least_privilege_audit` | GMAIL_SYNC_TIMEOUT_SECONDS=240, secret redaction, and SUPABASE_JWT_SECRET verification verified. | Verified cryptographic secret requirements. | **PASS** |
| 18 | `test_18_gmail_sync_timeout_safety_and_unfinished_recovery` | Internal deadline triggers safe halt; watermark preserved; lease released; subsequent recovery completes with zero duplicates. | Verified end-to-end timeout safety & recovery. | **PASS** |

---

### Complete Regression Test Suite Summary (Post Stage 7.2)
- **Phase A Test Suite:** 21 PASSED, 0 FAILED.
- **Stage 1 & Stage 1.1 Test Suite:** 13 PASSED, 9 SKIPPED (live PostgreSQL RLS), 0 FAILED.
- **Stage 2 Test Suite:** 16 PASSED, 0 FAILED.
- **Stage 3 Test Suite:** 15 PASSED, 0 FAILED.
- **Stage 4 Test Suite:** 10 PASSED, 0 FAILED.
- **Stage 5 Test Suite:** 17 PASSED, 1 SKIPPED (live GCP Pub/Sub), 0 FAILED.
- **Stage 5.1 Test Suite:** 8 PASSED, 0 FAILED.
- **Stage 5.2 Test Suite:** 8 PASSED, 0 FAILED.
- **Stage 6 & Stage 6.1 Test Suite:** 21 PASSED, 1 SKIPPED (live Supabase project BLOCKED), 0 FAILED.
- **Stage 7, 7.1 & Stage 7.2 Test Suite:** 17 PASSED, 1 SKIPPED (live Docker build BLOCKED), 0 FAILED.
- **Legacy Engine & API Tests:** 31 PASSED, 0 FAILED.
- **Total Test Suite:** **177 PASSED, 12 SKIPPED, 0 FAILED** (8.46s).
- **Frontend Production Build:** Passed cleanly (0 TypeScript errors, 516ms).

---

## 24. Stage 7.3: Final JWT Verification and Event Recovery Scheduler Audit

### 1. Implementation Summary

#### A. Asymmetric Supabase JWT Verification Architecture
1. **Asymmetric Verification via Supabase JWKS:**
   - Implemented in [`backend/core/auth.py`](file:///c:/Zamp Casse Study/backend/core/auth.py): [`verify_token_claims`](file:///c:/Zamp Casse Study/backend/core/auth.py#L93-L240) natively supports modern Supabase asymmetric signing algorithms (`RS256` and `ES256`).
   - Fetches and parses public keys from `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` (or `SUPABASE_JWKS_URL`).
   - Matches the incoming JWT's `kid` (Key ID) header against the JWKS keys and constructs public keys via `jose.jwk.construct`.
2. **Safe Public Key Caching & DoS Protection:**
   - Public keys are cached in-memory with a 1-hour TTL (`_JWKS_CACHE_TTL_SECONDS = 3600.0`).
   - If an incoming token arrives with an unknown `kid`, triggers an auto-refresh against the JWKS endpoint.
   - Enforces a 5-second debounce interval (`_JWKS_MIN_REFRESH_INTERVAL = 5.0`) to protect against cache-stampede attacks from arbitrary unauthenticated `kid` values.
   - Fails closed with HTTP 401 Unauthorized if the `kid` cannot be resolved after refresh.
3. **Legacy HS256 Compatibility Path:**
   - Symmetric `HS256` tokens are supported exclusively as an explicitly configured compatibility path when `SUPABASE_JWT_SECRET` is set.
   - If an `HS256` token is received on an asymmetric project without `SUPABASE_JWT_SECRET`, it fails closed with HTTP 401.
   - `SUPABASE_JWT_SECRET` is **NOT** required when the project uses asymmetric signing keys (`RS256`/`ES256`).
4. **Strict Security Guards:**
   - Whitelist restricted to `ALLOWED_JWT_ALGORITHMS = {"RS256", "ES256", "HS256"}`.
   - Rejects unsigned tokens (`alg: "none"`) and unsupported algorithms upfront before cryptographic evaluation.
   - Validates `iss` (issuer), `aud` (audience: "authenticated"), `exp` (expiry), and required claims (`sub`, `email`).
5. **Modern Supabase API Key Architecture (`sb_secret_`):**
   - Evaluated Supabase's newer scoped server-side API keys (`sb_secret_...`) against legacy JWT service role keys (`eyJhbGciOi...`).
   - In [`backend/core/storage.py`](file:///c:/Zamp Casse Study/backend/core/storage.py), [`SupabaseStorageAdapter._get_auth_headers`](file:///c:/Zamp Casse Study/backend/core/storage.py#L99-L107) injects `SUPABASE_SERVICE_ROLE_KEY` into both `apikey` and `Authorization: Bearer` headers. Supabase's API gateway transparently accepts both key formats.
   - Elevated service keys are restricted strictly to backend server-side operations and are never exposed to the frontend.

#### B. Thirty-Minute Pub/Sub Event Recovery Scheduler Audit
1. **Deployment Script Verification (`deploy/cloudrun/deploy.sh`):**
   - Confirmed the 30-minute reclaim Cloud Scheduler job `gmail-pubsub-reclaim` is configured on schedule `*/30 * * * *`.
   - Targets `POST ${SERVICE_URL}/api/v1/integrations/gmail/pubsub/reclaim`.
   - Uses dedicated maintenance identity `ap-cloud-scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com` (`SCHEDULER_SA`).
   - OIDC token audience matches the exact target URI.
   - `SCHEDULER_SA` is granted `roles/run.invoker` on the Cloud Run service.
2. **Runtime Safety & Idempotency:**
   - Protected by [`require_maintenance_auth`](file:///c:/Zamp Casse Study/backend/core/auth.py), rejecting unauthorized service identities with HTTP 403.
   - When 0 unfinished events exist, safely returns HTTP 200 with `scanned_count: 0`.
   - When unfinished events exist, reclaims them under exclusive per-mailbox lease with zero duplicate invoices or audit events (SHA-256 deduplicated).

---

### 2. Stage 7.3 Acceptance Test Scorecard (`tests/phase_b/test_stage7_cloudrun_deployment.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 19 | `test_19_supabase_jwt_asymmetric_rs256_and_es256_verification` | Verifies asymmetric verification of RS256 and ES256 JWTs using Supabase JWKS without requiring SUPABASE_JWT_SECRET. | Verified kid matching, RSA and EC public key construction, and claims validation. | **PASS** |
| 20 | `test_20_supabase_jwt_security_guards_and_algorithm_rejection` | Verifies strict fail-closed guards on unsigned tokens (none), unapproved algs (HS512), missing kid, unknown kid, tampering, and expiration. | Verified HTTP 401 fail-closed protections. | **PASS** |
| 21 | `test_21_pubsub_30m_reclaim_scheduler_audit` | Confirms deploy.sh configures gmail-pubsub-reclaim (every 30m) with dedicated SA, correct audience, invoker role, and safe 0-event execution. | Verified Cloud Scheduler automation and runtime safety. | **PASS** |

---

### Complete Regression Test Suite Summary (Post Stage 7.3)
- **Phase A Test Suite:** 21 PASSED, 0 FAILED.
- **Stage 1 & Stage 1.1 Test Suite:** 13 PASSED, 9 SKIPPED (live PostgreSQL RLS), 0 FAILED.
- **Stage 2 Test Suite:** 16 PASSED, 0 FAILED.
- **Stage 3 Test Suite:** 15 PASSED, 0 FAILED.
- **Stage 4 Test Suite:** 10 PASSED, 0 FAILED.
- **Stage 5 Test Suite:** 17 PASSED, 1 SKIPPED (live GCP Pub/Sub), 0 FAILED.
- **Stage 5.1 Test Suite:** 8 PASSED, 0 FAILED.
- **Stage 5.2 Test Suite:** 8 PASSED, 0 FAILED.
- **Stage 6 & Stage 6.1 Test Suite:** 21 PASSED, 1 SKIPPED (live Supabase project BLOCKED), 0 FAILED.
- **Stage 7, 7.1, 7.2 & 7.3 Test Suite:** 20 PASSED, 1 SKIPPED (live Docker build BLOCKED), 0 FAILED.
- **Legacy Engine & API Tests:** 31 PASSED, 0 FAILED.
- **Total Test Suite:** **180 PASSED, 12 SKIPPED, 0 FAILED** (9.87s).
- **Frontend Production Build:** Passed cleanly (0 TypeScript errors, 547ms).

---

## 25. Operator's First Test-Environment Provisioning Checklist (Frozen Release)

With the completion of Stage 7.3, code implementation and deployment automation are **FROZEN**. When the operator is ready to provision live cloud resources for the initial pilot / test environment, follow this step-by-step checklist:

### Phase 1: Supabase Free Project Provisioning
1. **Create Supabase Project:**
   - Organization: Target Company Pilot
   - Region: `ap-south-1` (Mumbai, India) to match Cloud Run.
   - Pricing Tier: Free plan ($0/mo).
2. **Retrieve Project Parameters:**
   - `SUPABASE_URL`: `https://<project-ref>.supabase.co`
   - `SUPABASE_ANON_KEY`: Copy from Project Settings -> API (Public Anon Key).
   - `SUPABASE_SERVICE_ROLE_KEY`: Copy from Project Settings -> API (Service Role Key or `sb_secret_...`).
   - `SUPABASE_JWKS_URL`: `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`
   - `DATABASE_URL`: Connection string using Transaction Pooler port 6543 (`postgresql://postgres.<project-ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require`).
3. **Configure Storage Bucket:**
   - In Supabase Dashboard -> Storage: create bucket `invoices`.
   - Set bucket visibility to **PRIVATE** (Public bucket is strictly barred).
4. **Apply Database Migrations:**
   - Run Alembic migration against the live Supabase PostgreSQL database:
     ```bash
     DATABASE_URL="postgresql://postgres.<ref>:<pass>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require" python -m alembic upgrade head
     ```
   - Verify all 16 multi-tenant tables and RLS policies are active.

### Phase 2: Google Cloud Platform Setup
1. **Configure GCP Project:**
   - Set active project: `gcloud config set project <PROJECT_ID>`
   - Confirm billing account is associated (required for Cloud Run & Secret Manager).
2. **Populate Google Secret Manager:**
   ```bash
   # 1. Database URL
   echo -n "postgresql://postgres.<ref>:<pass>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require" | \
       gcloud secrets create ap-database-url --data-file=-

   # 2. Application Secret Key
   openssl rand -hex 32 | gcloud secrets create ap-secret-key --data-file=-

   # 3. Supabase Service Role Key (Supports legacy JWT 'eyJ...' or modern 'sb_secret_...')
   echo -n "<SUPABASE_SERVICE_ROLE_KEY>" | gcloud secrets create ap-supabase-service-key --data-file=-

   # 4. Supabase JWT Secret (Optional if using asymmetric JWKS; required if using HS256)
   echo -n "<SUPABASE_JWT_SECRET>" | gcloud secrets create ap-supabase-jwt-secret --data-file=-

   # 5. Gmail Client Secret (OAuth Client configured strictly for https://www.googleapis.com/auth/gmail.readonly)
   echo -n "<GMAIL_CLIENT_SECRET>" | gcloud secrets create ap-gmail-client-secret --data-file=-

   # 6. Database Token Encryption Key (Fernet)
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode(), end='')" | \
       gcloud secrets create ap-gmail-encryption-key --data-file=-
   ```
3. **Configure Operator Workstation Backup Key:**
   - Generate and save on operator local machine:
     ```bash
     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode(), end='')"
     ```
   - Note: Do NOT upload this key to Cloud Run Secret Manager (backups are operator CLI only).

### Phase 3: Execute Deployment Automation
1. **Run Automated Script:**
   ```bash
   chmod +x deploy/cloudrun/deploy.sh
   ./deploy/cloudrun/deploy.sh
   ```
2. **Confirm Deployment Outputs:**
   - Service deployed in `asia-south1` with scale-to-zero (minScale 0, maxScale 3).
   - Dedicated service accounts created:
     - `ap-cloudrun-sa` (Runtime)
     - `gmail-pubsub-push` (Pub/Sub invoker)
     - `ap-cloud-scheduler-sa` (Maintenance invoker)
   - Cloud Scheduler triggers active:
     - `gmail-watch-renewal` (Daily at 00:00 UTC)
     - `gmail-history-reconciliation` (Every 6 hours)
     - `gmail-pubsub-reclaim` (Every 30 minutes)
   - Liveness probe verified: `curl -s https://<SERVICE_URL>/api/v1/liveness` returns HTTP 200.

---

## 26. Stage 7.3.1 — Final Supabase API Key and Gmail Scope Corrections

### 1. Architectural Adjustments
- **Supabase Format-Aware Storage Headers:**
  - `SupabaseStorageAdapter._get_auth_headers()` inspects key format before dispatching requests.
  - Legacy JWT keys (`eyJ...`) are sent in both `apikey` and `Authorization: Bearer <key>`.
  - Modern `sb_secret_...` keys are sent strictly through `apikey: <key>` and never as `Authorization: Bearer`.
  - `sb_secret_` keys are treated as opaque tokens and are never decoded or parsed as JWTs.
  - Server-side exclusivity is preserved: keys are never exposed in error responses, logs, or client-side bundles.
- **Gmail Least-Privilege Scope (`gmail.readonly`):**
  - Scope is strictly constrained to `https://www.googleapis.com/auth/gmail.readonly`.
  - `gmail.modify` has been completely eliminated from documentation, checklists, and configuration templates.
  - Fixed query string generation in `build_authorization_url` to guarantee canonical, singular URL parameter encoding.

### 2. Stage 7.3.1 Acceptance Test Scorecard (`tests/phase_b/test_stage7_cloudrun_deployment.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 22 | `test_22_supabase_storage_header_format_awareness` | Verifies format-aware header construction for both legacy JWT and modern `sb_secret_`/`sb_pub_` keys; verifies secrecy in health status. | Verified `apikey`-only headers for new keys, both headers for legacy keys, and key suppression. | **PASS** |
| 23 | `test_23_gmail_least_privilege_scope_verification` | Verifies `GMAIL_SCOPE` and canonical OAuth authorization URL contain exclusively `gmail.readonly` and zero modify/compose scopes. | Verified URL query params, `/authorize` and `/status` responses. | **PASS** |

### Complete Regression Test Suite Summary (Post Stage 7.3.1)
- **Phase A Test Suite:** 21 PASSED, 0 FAILED.
- **Stage 1 & Stage 1.1 Test Suite:** 13 PASSED, 9 SKIPPED (live PostgreSQL RLS), 0 FAILED.
- **Stage 2 Test Suite:** 16 PASSED, 0 FAILED.
- **Stage 3 Test Suite:** 15 PASSED, 0 FAILED.
- **Stage 4 Test Suite:** 10 PASSED, 0 FAILED.
- **Stage 5 Test Suite:** 17 PASSED, 1 SKIPPED (live GCP Pub/Sub), 0 FAILED.
- **Stage 5.1 Test Suite:** 8 PASSED, 0 FAILED.
- **Stage 5.2 Test Suite:** 8 PASSED, 0 FAILED.
- **Stage 6 & Stage 6.1 Test Suite:** 21 PASSED, 1 SKIPPED (live Supabase project BLOCKED), 0 FAILED.
- **Stage 7, 7.1, 7.2, 7.3 & 7.3.1 Test Suite:** 23 PASSED, 1 SKIPPED (live Docker build BLOCKED), 0 FAILED.
- **Legacy Engine & API Tests:** 31 PASSED, 0 FAILED.
- **Total Test Suite:** **183 PASSED, 12 SKIPPED, 0 FAILED** (10.02s).
- **Frontend Production Build:** Passed cleanly (0 TypeScript errors, 416ms).

---

## 27. Final Operator Provisioning Readiness (Pre-Flight Freeze)

### 1. Operational Clarifications & Hardening
- **Google OAuth Testing Limitations:** Documented that external Google OAuth applications in "Testing" mode have a 7-day refresh token expiration limit. Mailbox reconnection via UI is documented as the standard procedure. Indefinite automated ingestion requires Google Workspace Internal app configuration or Google App Verification & CASA Tier 2 assessment.
- **Supabase Database Connection Separation:**
  - `DATABASE_URL`: Cloud Run runtime connection via Supabase Transaction Pooler (port 6543) with prepared-statement compatibility.
  - `MIGRATION_DATABASE_URL`: Alembic migration connection via Direct PostgreSQL (port 5432) or Session Pooler (port 5432). Transaction poolers disallow transactional DDL and advisory locks.
  - `BACKUP_DATABASE_URL`: Operator CLI backup and restoration connection via Direct PostgreSQL or Session Pooler (port 5432).
- **Supabase Storage Privileged Key Enforcement:** `SupabaseStorageAdapter` strictly requires `SUPABASE_SERVICE_ROLE_KEY` (`sb_secret_...` or legacy JWT `eyJ...`). Unprivileged anon or publishable keys are never silently substituted.

### 2. Pre-Flight Acceptance Test Scorecard (`tests/phase_b/test_stage7_cloudrun_deployment.py`)

| # | Test Name | Invariant / Requirement Verified | Result | Status |
|---|---|---|---|:---:|
| 22 | `test_22_supabase_storage_header_format_awareness` | Verifies format-aware header construction for both legacy JWT and modern `sb_secret_` keys; verifies that unprivileged anon keys are never substituted and health reports honest `NOT_CONFIGURED`. | Verified `apikey`-only headers for new keys, both headers for legacy keys, and strict service key requirement. | **PASS** |
| 23 | `test_23_gmail_least_privilege_scope_verification` | Verifies `GMAIL_SCOPE` and canonical OAuth authorization URL contain exclusively `gmail.readonly` and zero modify/compose scopes. | Verified URL query params, `/authorize` and `/status` responses. | **PASS** |
| 24 | `test_24_database_connection_separation_audit` | Verifies distinct separation between runtime (`DATABASE_URL`), migration (`MIGRATION_DATABASE_URL`), and backup (`BACKUP_DATABASE_URL`) connection strings and verifies credential masking in `redacted_dict()`. | Verified Alembic URL precedence, config isolation, and password masking. | **PASS** |





