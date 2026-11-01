# AP Command Center — Security Architecture & Governance Notes

**Governance Standard:** ISO 27001 / SOC 2 Type II Alignment  
**Scope:** Phase A Foundation Architecture

---

## 1. Authentication & Identity Management
- **Zero Local Passwords:** All human users authenticate against enterprise OIDC / SAML identity providers (Google Workspace / Azure AD / Okta).
- **Server-Side Token Verification:** Bearer tokens are cryptographically verified using IdP JWKS public keys. The client-provided claims are never trusted blindly.
- **Strict Role-Based Access Control (RBAC):** Every route and mutation enforces one of 6 discrete roles:
  1. `AP_ASSOCIATE`: Triage assigned invoices, trigger validation.
  2. `AP_LEAD`: Queue allocation, escalation management, first-tier approval.
  3. `CONTROLLER`: High-value approvals ($\ge$ threshold), financial risk oversight.
  4. `CATEGORY_MANAGER`: Discrepancy resolution for PO, GRN, and rate variances.
  5. `AUDITOR`: Read-only access to audit logs, decision traces, and evidence bundles.
  6. `SYSTEM_ADMIN`: Connection configuration, health monitoring, integration setup.
- **Anti-Bypass Guardrail:** `LOCAL_AUTH_BYPASS` is cryptographically and logically barred when `APP_ENV` is set to `production` or `staging`.

## 2. Append-Only Database Audit Architecture
- **Database-Level Immutability:** The `audit_events` table enforces an append-only invariant.
  - A PostgreSQL trigger (`trg_audit_events_immutable`) raises an exception on any `UPDATE` or `DELETE` attempt.
  - In addition, production database deployment scripts execute `REVOKE UPDATE, DELETE ON TABLE audit_events FROM ap_app_user;`.
  - SQLAlchemy ORM listeners intercept and abort any update/delete operations before they can be sent to the database.
- **Compensating Actions:** Financial corrections require new compensating audit records rather than modifications of historical events.

## 3. Data Protection & File Storage
- **Zero Public File Buckets:** Invoice PDFs and raw attachments are stored exclusively in private, encrypted object storage (SSE-KMS / AES-256).
- **Preserved Byte Integrity:** Every uploaded original is hashed (SHA-256) at the boundary. The stored byte stream must match the hash byte-for-byte.
- **Short-Lived Signed URLs:** File previews are served via time-bounded presigned URLs (default 15 minutes) with user-level and entity-level authorization checks.
- **No Local Production Storage:** Local disk is never used as a production storage fallback. Missing cloud storage credentials block application readiness.

## 4. Secrets Management & Telemetry Redaction
- **No Secrets in Code:** Credentials, private keys, and connection strings are injected via environment variables or cloud secret managers (AWS Secrets Manager / GCP Secret Manager).
- **Structured Redaction:** Application logging filters all output to redact authorization tokens, Bearer headers, refresh tokens, and customer PII.
- **No Telemetry Leakage:** Document OCR text and confidential financial payloads are excluded from third-party application monitoring metrics.

## 5. Tenant Isolation & PostgreSQL Row Level Security (RLS)
- **Composite Foreign Key Defense:** Every child record in the database includes `org_id`, and foreign keys are enforced as composite pairs `(org_id, parent_id)`. Cross-tenant data linking is structurally rejected by the database engine.
- **PostgreSQL RLS with Force Security:** RLS is enabled and forced (`FORCE ROW LEVEL SECURITY`) on all tables for the application database user `ap_app_user`.
- **Permissive Scoped Policy:** PostgreSQL RLS policy uses `AS PERMISSIVE` with `org_id::text = NULLIF(TRIM(current_setting('app.current_org_id', true)), '')`. When the session setting is absent or empty, PostgreSQL evaluates to null and strictly denies all reads, inserts, updates, and deletes (fail-closed default).
- **Transaction-Local Isolation:** `set_tenant_context` uses `is_local=true` to bound tenant configuration strictly to the current database transaction. Pool check-in hooks execute `RESET ALL` to eliminate connection reuse leakage.

## 6. Supabase Auth & Secure User Provisioning Governance
- **Cryptographic Token Verification:** Bearer tokens are validated using Supabase Auth configuration (HMAC secret or JWKS public keys) with mandatory verification of signature, issuer, audience, expiration, and subject claims. Unsigned or forged tokens receive HTTP 401.
- **Bootstrap Sequence Resolution:** Server-side identity resolution queries user memberships *before* establishing tenant context, preventing circular bootstrap dependencies while strictly preserving RLS integrity.
- **Strict Single-Use Invitations:** Invitations are single-use, 32-byte cryptographic tokens (`secrets.token_urlsafe(32)`) stored as SHA-256 hashes with 7-day expiration. The recipient email must strictly match the authenticated Google email address.
- **Access Requests Review Guardrail:** Uninvited users submitting access requests receive `PENDING` status. Automatic membership grant is structurally prohibited; requests require manual review and approval by an authorized administrator (`SYSTEM_ADMIN` or `CONTROLLER`).
- **Anti-Self-Promotion Invariant:** Users cannot alter their own assigned role or deactivate their own active account (`PATCH /auth/users/{id}/role` and `POST /auth/users/{id}/deactivate` reject self-modification with HTTP 400).
- **Immediate Revocation Enforcement:** When a user is marked `is_active=False`, server-side membership lookup immediately filters out the membership, failing closed with HTTP 403 on all tenant-scoped routes.

## 7. Supabase Storage & Document Ingestion Security
- **Private Storage Architecture:** Physical invoice files reside in private Supabase Storage buckets only (`invoices`). Public buckets or public access URLs are structurally prohibited and flagged as `DEGRADED` in health monitoring.
- **Tenant Isolation Path Structure:** Object keys are constructed as `org_{org_id}/invoices/{document_id}/{filename}` where `org_id` is derived strictly from the verified authenticated user session. Path traversal attempts (`../../`) are sanitized at the boundary.
- **Capped Presigned URL Expiry:** Presigned URLs for invoice access are enforced with a strict maximum TTL of 300 seconds (`STORAGE_SIGNED_URL_EXPIRY_SECONDS = 300`). User-requested expirations beyond 300 seconds are clamped.
- **File Validation & 50 MB Free Plan Boundary:** Uploads require explicit MIME type check (`application/pdf`) and magic-byte signature check (`%PDF-`). Upload sizes are strictly limited to $\le 50$ MB (`MAX_UPLOAD_FILE_SIZE_BYTES`), matching Supabase Free plan boundaries.
- **Compensating Rollback on DB Error:** To avoid untracked orphaned files in object storage without a 2-phase commit, any database transaction failure during document ingestion triggers an immediate compensating cleanup (`storage_adapter.delete_file(storage_key)`).
- **Cryptographic Integrity Verification on Download:** Document retrieval validates SHA-256 integrity over the raw streamed bytes against the hash recorded at ingestion time before returning the payload to the user. Mismatches raise HTTP 500 and trigger critical security alerts.
- **Soft Deletion Lifecycle & Permanent Purge Control:** Soft deletion preserves the original physical file in storage and logs a `DOCUMENT_SOFT_DELETED` audit event. Permanent file purging from storage is strictly guarded by dual-control authorization requiring two distinct authorized approvers (`SYSTEM_ADMIN` or `CONTROLLER`) and statutory retention verification (`DOCUMENT_RETENTION_DAYS = 2920`). Unconfigured purge policy returns honest `BLOCKED` responses. Audit history is strictly preserved and never cascade-deleted.

## 8. Gmail OAuth 2.0 & Mailbox Ingestion Security (Phase B Stage 4 & Stage 4.1)
- **Minimum Privileged Scope:** Restricted exclusively to `https://www.googleapis.com/auth/gmail.readonly`. Application never requests write, delete, send, or full mailbox access.
- **Dedicated Mailbox Isolation:** Mailbox connection is completely decoupled from employee identity authentication. Employee Google login does not grant mailbox access; dedicated administrative authorization is mandatory.
- **Server-Side Refresh Token Encryption:** OAuth refresh tokens are encrypted using Fernet symmetric cryptography (128-bit AES in CBC mode with PKCS7 padding and HMAC-SHA256 authentication) using server-side `GMAIL_ENCRYPTION_KEY`. Plaintext tokens are strictly forbidden from database storage, API serialization, and logging.
- **Single-Use State Nonce & Anti-Replay Protection:** OAuth authorization requests use tamper-evident HMAC-SHA256 signed state tokens containing `org_id`, `user_id`, cryptographically random 24-byte nonce, and 10-minute bounded expiration. Nonces are persisted in `oauth_state_nonces` and atomically marked `is_consumed=True` on callback; replayed states receive HTTP 400.
- **Reconnect Token Preservation:** Re-authenticating a connected mailbox preserves the existing encrypted refresh token if Google omits the token on re-authorization.
- **Attachment Ingestion & Quarantine Pipeline:** Mailbox attachments are filtered strictly for `.pdf` extension and `application/pdf` MIME type. Supports both inline (`body.data`) and external (`messages.attachments.get`) attachments across complex multipart MIME structures. Corrupt headers lacking `%PDF-` magic bytes or exceeding 50 MB are diverted to `QuarantinedDocument`.
- **Truthful Compliance Disclosure:** Status endpoint reports `PRODUCTION_GOOGLE_VERIFICATION_PENDING`. Discloses that development and pilot testing uses Google test users, with CASA Tier 2 assessment and Google OAuth app verification required for full production authorization.

## 9. Google Cloud Pub/Sub Push Webhook & Event-Driven Ingestion (Phase B Stage 5)
- **OIDC Bearer Token Verification:** Pub/Sub push requests authenticate via Google-signed OIDC ID tokens. Validates issuer (`https://accounts.google.com`), audience (`PUBSUB_VERIFICATION_AUDIENCE`), and service account email (`PUBSUB_SERVICE_ACCOUNT_EMAIL`). Unauthenticated, expired, or mismatched-audience requests are rejected with HTTP 401/400.
- **Zero Sensitive Data in Pub/Sub:** Pub/Sub push messages carry only metadata (`emailAddress`, `historyId`). No invoice attachments, PDF bytes, financial amounts, or vendor secrets are ever transmitted via Pub/Sub.
- **Durable Notification Persistence:** Incoming Pub/Sub messages are committed to `gmail_pubsub_events` with status `RECEIVED` prior to initiating document retrieval, guaranteeing an immutable audit trail of all webhook activity.
- **At-Least-Once Delivery Idempotency:** Redelivered Pub/Sub notifications are deduplicated using `message.messageId`. Duplicate notifications are acknowledged promptly (HTTP 200 `DUPLICATE`) without redundant invoice processing.
- **History Synchronization & Atomic Watermark:** Incremental message fetching via `users.history.list` processes only new messages added since the last processed `historyId`. The stored watermark is advanced atomically only upon successful processing.
- **Automatic History Expiration Recovery:** When Gmail API returns HTTP 404 (`HistoryExpiredError`) indicating the history ID has expired, the pipeline catches the error, triggers an automatic full mailbox synchronization, and resets the watermark.
- **48-Hour Watch Renewal & 6-Hour Reconciliation:** Background schedules renew 7-day Gmail watches every 48 hours and perform periodic reconciliation audits every 6 hours to catch any dropped push events.
- **Strict Multi-Tenant Boundary Enforcement:** Push notifications cannot specify an `org_id`. The application resolves tenant ownership strictly by matching the verified `mailbox_address` against active `GmailAccount` records in the database. Notifications for unmapped mailboxes are safely acknowledged as `UNKNOWN_MAILBOX` without cross-tenant leakage.

## 10. Mailbox Concurrency, Monotonic Watermarks & Durable Acknowledgement (Phase B Stage 5.1)
- **Per-Mailbox Concurrency Lease (`sync_lock_token`, `sync_lock_expires_at`):** Database-backed distributed processing leases prevent concurrent workers from simultaneously executing history synchronization for the same mailbox. Concurrent contention safely defers processing (`CONCURRENT_DEFERRED`) without history corruption.
- **Durable Acknowledgement Invariant:** Webhooks refuse HTTP 200/204 acknowledgement if the database transaction committing the `PubSubEvent` record fails, returning HTTP 500 to trigger Google Cloud Pub/Sub delivery retry.
- **Strictly Monotonic Watermark Invariant:** Stored history watermarks (`account.last_history_id`) can only advance monotonically. Delayed or out-of-order notifications referencing older history IDs are safely acknowledged (`OUT_OF_ORDER_SKIPPED`) without regressing stored watermarks.
- **Partial Failure Resiliency:** Partial message processing failures do not advance the stored watermark. Subsequent retries detect already-ingested attachments via tenant-scoped SHA-256 deduplication and process remaining items without duplicating financial or audit records.
- **Honest Scheduling Boundary:** 48-hour watch renewal and 6-hour reconciliation functions/endpoints are implemented, but automated external scheduling is documented as `NOT_CONFIGURED` until Cloud Run deployment preparation, avoiding unapproved worker frameworks.

## 11. Unfinished Event Recovery & Lease Governance (Phase B Stage 5.2)
- **Status-Discriminated Redelivery:** Pub/Sub notifications for already-persisted events only treat `COMPLETED` or `OUT_OF_ORDER_SKIPPED` records as duplicates. Events in `RECEIVED`, `FAILED`, or `CONCURRENT_DEFERRED` status are reclaimed for execution, preventing transient delivery glitches or runtime crashes from creating dead-letter blackholes.
- **Retry Auditing & Tracking (`retry_count`, `last_attempted_at`):** Reclaimed events increment an atomic retry counter and timestamp each attempt, providing visibility into repeated processing failures.
- **Stale Processing Lease Eviction:** Expired per-mailbox processing locks (`sync_lock_expires_at < now`) are safely cleared during reconciliation and retry routines, preventing crashed or abruptly terminated workers from permanently locking mailbox synchronization.
- **Monotonic Watermark Resilience:** Incomplete or failed synchronization attempts never advance the mailbox history watermark (`last_history_id`). Reclaiming an event checks the current mailbox watermark; if a subsequent sync already advanced beyond the event's `historyId`, the event is safely finalized without redundant Gmail API queries.
- **Tenant-Scoped SHA-256 Deduplication Invariant:** Retrying an event that previously failed midway through batch ingestion safely checks existing document hashes (`sha256_hash`), skipping already-persisted invoice documents and preventing duplicate database or audit records.
- **Truthful Scheduling Invariant:** Automated background reconciliation is truthfully exposed via `/api/v1/integrations/gmail/status` as `NOT_CONFIGURED` for external triggers, confirming synchronous webhook processing with on-demand administrative recovery endpoints.

## 12. Supabase Backup Encryption & Recovery Governance (Phase B Stage 6)
- **Zero Secrets in Backup Archives:** Backup tarballs strictly omit database passwords, JWT secrets, service-role keys, and encryption keys. `auth_summary.json` includes only metadata (user ID, email, full name, role, organization ID) required for administrative provisioning without passwords or secrets.
- **Authenticated Archive Encryption:** Archives are encrypted using Fernet (128-bit AES in CBC mode with PKCS7 padding and HMAC-SHA256 authenticated encryption). Tampered ciphertexts, truncated files, or incorrect keys are immediately rejected with `DecryptionError`.
- **Key Decoupling Invariant:** Decryption keys are managed exclusively by operators via external password managers or vaults. The key is never committed to Git and never bundled within the archive.
- **Cryptographic Storage Validation:** Every physical object downloaded during backup is verified against `Document.sha256_hash`. If any file is missing from storage or corrupted, the backup is strictly marked `completion_status = "FAILED"`.
- **Destructive Restore Guardrail:** Database and storage restoration requires the explicit `--confirm-restore` flag. Restoring onto an unconfirmed or live production environment is rejected by the restoration orchestrator.
- **Audit Immutability & Tenant Integrity Post-Restore:** Restoration verifies that `audit_events` row counts match pre-backup manifests, and validates that restored documents maintain exact `org_id` alignment with invoices.
- **Disaster Recovery Notice:** Backups stored exclusively on the same host machine do not satisfy independent disaster recovery standards; encrypted archives must be moved to physically decoupled offline or secondary storage.
- **Scheduling Disclosure:** Status endpoint reports `execution_mode: "OPERATOR_MANUAL"` and `background_scheduler: "NOT_CONFIGURED"`. No Celery, ARQ, or unapproved worker frameworks are permitted.

## 13. Auth Recovery, Restore Integrity & Key Security Safeguards (Phase B Stage 6.1)
- **Interactive Hidden Key Prompts:** Backup and restore CLI utilities prioritize `BACKUP_ENCRYPTION_KEY` from the environment. When omitted, operators are prompted via a hidden, un-echoed password prompt (`getpass.getpass()`), eliminating plaintext secret exposure in process tables (`ps aux`), shell history, or console logs. Passing keys via `--key` emits an explicit security alert.
- **GoTrue Auth Schema Isolation:** Verified that Supabase CLI excludes `auth` tables by default. Because destination Supabase projects generate new JWT signing secrets, old client tokens are invalidated upon restore.
- **Deterministic User Re-Invitation & Reconciliation Cascade:** If an employee re-authenticates on a restored project and GoTrue generates a new UUID, `reconcile_auth_user()` securely updates `public.users.id` and cascades to `role_assignments.user_id` inside an atomic transaction, while persisting an immutable `USER_AUTH_RECONCILED` audit record.
- **Post-Restore Foreign Key & Multi-Tenant Constraint Verification:** Immediately following `session_replication_role = replica` restoration, the engine programmatically inspects all schema relationships, detecting orphaned children or cross-tenant `org_id` leakage before allowing traffic.
- **Active Post-Restore Audit Immutability Test:** In addition to row count validation, post-restoration verification actively attempts an ORM mutation against `audit_events` inside a nested transaction savepoint to ensure database triggers (`trg_audit_events_immutable`) and ORM listeners are functional post-restore.

## 14. Google Cloud Run Container Security & Secret Manager Architecture (Phase B Stage 7)
- **Unprivileged Non-Root Container Execution:** The production container builds using a 2-stage multi-stage Docker architecture (Node 20 builder + Python 3.12-slim runtime). It creates an unprivileged user `appuser` (UID/GID 1000) and explicitly drops root privileges before application startup.
- **Zero Plaintext Secrets in Manifests or Container Images:** All retained sensitive credentials (`DATABASE_URL`, `SECRET_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `GMAIL_CLIENT_SECRET`, `GMAIL_ENCRYPTION_KEY`) are stored in Google Secret Manager and mounted as environment variables via Knative `secretKeyRef` bindings. No secrets are baked into container layers or Git repositories.
- **Stateless Serverless Execution:** Cloud Run containers are strictly stateless. Transient local filesystem storage is never used for invoice files; all uploads and attachments stream directly into private Supabase Storage buckets.
- **Container Healthcheck Probes:** Cloud Run startup and liveness probes target `/api/v1/liveness`, while Docker `HEALTHCHECK` ensures process liveness without exposing sensitive database or internal connection metrics to unauthenticated network clients.

## 15. Scheduler Security, Identity Separation & Pub/Sub Timing Governance (Phase B Stage 7.1)
- **Strict Service Identity Separation:** Cloud Run differentiates between three separate service identities:
  1. `ap-cloudrun-sa`: Runtime identity running the FastAPI container.
  2. `gmail-pubsub-push`: Restricted identity authorized solely to invoke the push webhook (`/pubsub/push`).
  3. `ap-cloud-scheduler-sa`: Dedicated maintenance identity authorized to invoke `/watch/renew`, `/reconcile`, and `/pubsub/reclaim`.
- **Application-Level Maintenance Verification (`require_maintenance_auth`):** Maintenance endpoints verify incoming Google OIDC tokens against `CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL` and the configured target audience. If an unauthorized service account (e.g. `gmail-pubsub-push` or rogue identity) attempts to trigger maintenance routines, the request is rejected with HTTP 403 Forbidden.
- **Unweakened Normal User JWT Validation:** Normal user APIs strictly enforce Supabase Auth JWT validation and RBAC. Google service-account JWTs are never accepted as employee credentials on business routes. Human administrators (`SYSTEM_ADMIN` / `CONTROLLER`) can execute maintenance tasks as an authorized fallback.
- **Pub/Sub Acknowledgement Deadline Alignment (300s):** The Pub/Sub push subscription is explicitly created with `--ack-deadline=300`, perfectly aligned with Cloud Run's container request timeout (`300s`) and the per-mailbox sync lease (`300s`).
- **Ephemeral Container Protection:** Automated backup jobs are excluded from Cloud Run's deployment script. Because container storage is destroyed on scale-down, backups are restricted to manual operator execution from secure workstations, preserving truthfulness in backup status reporting (`execution_mode: "OPERATOR_MANUAL"`).

## 16. Secret Hygiene, Least-Privilege IAM & Pub/Sub Timeout Safety Governance (Phase B Stage 7.2)
- **Secret Manager Hygiene & Least Privilege:**
  - `SUPABASE_ANON_KEY`: Classified as a public client publishable key; removed from Secret Manager and configured via standard environment variables.
  - `GMAIL_REFRESH_TOKEN`: In production multi-tenant operations, refresh tokens are stored encrypted per-mailbox in PostgreSQL (`gmail_accounts.encrypted_refresh_token`). The global static token was eliminated from Secret Manager and Cloud Run service definitions.
  - `BACKUP_ENCRYPTION_KEY`: Backups remain operator-managed on trusted operator workstations. The key was removed from Secret Manager and Cloud Run container runtime access.
  - `SUPABASE_JWT_SECRET`: Backend cryptographic verification (`verify_token_claims`) was verified to strictly require `SUPABASE_JWT_SECRET` for HMAC token signature verification; retained in Secret Manager.
  - `CLOUDRUN_SA` Secret Access: IAM policy bindings grant `roles/secretmanager.secretAccessor` only on the retained server-side secrets, preventing runtime access to unneeded operator or external keys.
- **Internal Processing Timeout & Graceful Halting (240s vs 300s):**
  - Configured `GMAIL_SYNC_TIMEOUT_SECONDS = 240` to create a 60-second internal processing deadline comfortably below the 300-second container timeout and Pub/Sub ack deadline.
  - Individual external Gmail API calls and attachment downloads are bounded to 15 seconds (`timeout=15.0`).
  - If a large synchronization batch approaches 240 seconds, the loop halts safely before container SIGTERM or HTTP 504 gateway timeout occurs.
  - Already processed messages are committed to the database; the mailbox watermark (`account.last_history_id`) is **NOT** advanced; the per-mailbox lease is immediately released; and the event remains in a retryable state (`RECEIVED`).
  - Upon subsequent redelivery or scheduled reclaim, Stage 5.2 recovery finishes remaining messages without duplicating invoices or audit logs (guaranteed via SHA-256 deduplication).

## 17. Asymmetric Supabase JWT Verification & Modern Key Architecture (Phase B Stage 7.3)
- **Supabase JWKS Asymmetric Verification (RS256 & ES256):**
  - Backend [`verify_token_claims`](file:///c:/Zamp Casse Study/backend/core/auth.py) fetches and cryptographically validates JWTs using public keys from the official Supabase JWKS endpoint (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json` or `SUPABASE_JWKS_URL`).
  - Supports modern Supabase signing key standards: `ES256` (Elliptic Curve P-256) and `RS256` (RSA 2048).
  - Matches the JWT header `kid` against cached public keys to reconstruct the appropriate verification key via `jose.jwk.construct`.
- **Safe Public Key Caching & Auto-Refresh:**
  - Caches public keys in memory with a 1-hour TTL (`_JWKS_CACHE_TTL_SECONDS = 3600`).
  - If an incoming token presents an unknown `kid`, triggers a forced cache refresh against the JWKS endpoint.
  - Implements a 5-second minimum refresh interval debounce (`_JWKS_MIN_REFRESH_INTERVAL = 5.0`) to protect the service against cache-stampede or denial-of-service attacks from malicious unauthenticated tokens with arbitrary `kid` values.
  - Fails closed with HTTP 401 Unauthorized if the `kid` cannot be resolved after refresh.
- **Legacy HS256 Compatibility Path:**
  - Symmetric `HS256` verification is preserved strictly as an explicitly configured fallback when `SUPABASE_JWT_SECRET` is present.
  - If an `HS256` token is received on an asymmetric-only deployment (no `SUPABASE_JWT_SECRET`), it fails closed with HTTP 401.
  - `SUPABASE_JWT_SECRET` is **NOT** required when the project uses asymmetric signing keys.
- **Strict Algorithm Whitelist & Anti-None Protections:**
  - Restricts accepted algorithms strictly to `ALLOWED_JWT_ALGORITHMS = {"RS256", "ES256", "HS256"}`.
  - Unsigned tokens (`alg: "none"`) and arbitrary algorithms (e.g. `HS512`, `RS512`) are rejected upfront before cryptographic processing.
- **Supabase Modern API Key Architecture (`sb_secret_`):**
  - Evaluated Supabase's newer scoped server-side API keys (`sb_secret_...`) versus legacy JWT service role keys (`eyJhbGciOi...`).
  - Elevated service keys are restricted strictly to backend server-side operations and are never exposed to the client frontend.

## 18. Thirty-Minute Pub/Sub Event Recovery Scheduling Audit (Phase B Stage 7.3)
- **Automated Cloud Scheduler Configuration:** Verified that [`deploy/cloudrun/deploy.sh`](file:///c:/Zamp Casse Study/deploy/cloudrun/deploy.sh) configures `gmail-pubsub-reclaim` on schedule `*/30 * * * *` (every 30 minutes).
- **Target URI & Authentication:** Invokes `POST ${SERVICE_URL}/api/v1/integrations/gmail/pubsub/reclaim` using dedicated maintenance identity `SCHEDULER_SA` (`ap-cloud-scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com`) with OIDC token audience matching the exact reclaim URI.
- **Invoker Authorization:** Service account `ap-cloud-scheduler-sa` is explicitly granted `roles/run.invoker` on the Cloud Run service.
- **Application Identity Enforcement:** Endpoint is protected by [`require_maintenance_auth`](file:///c:/Zamp Casse Study/backend/core/auth.py), rejecting unauthorized service accounts (e.g. Pub/Sub push identity or arbitrary accounts) with HTTP 403 Forbidden.
- **Idempotency & Safe Zero-State Execution:** When no unfinished events exist, the endpoint safely returns HTTP 200 with `scanned_count: 0`. When unfinished events (`RECEIVED`, `FAILED`, `CONCURRENT_DEFERRED`, `PARTIALLY_PROCESSED`) exist, they are reclaimed under exclusive per-mailbox lease and ingested with zero duplicate invoices or audit records via SHA-256 deduplication.

## 19. Supabase API Key Header Format Awareness & Least-Privilege Gmail Scope (Stage 7.3.1)
- **Format-Aware Supabase Storage Headers:**
  - Supabase documents that modern secret and publishable keys (`sb_secret_...`, `sb_pub_...`) are not JWTs and must only be supplied via the `apikey` header. Sending an `sb_secret_` key as an `Authorization: Bearer` token causes API gateways to reject requests due to failed JWT parsing.
  - [`SupabaseStorageAdapter._get_auth_headers`](file:///c:/Zamp%20Casse%20Study/backend/core/storage.py) implements format-aware request construction:
    - **Legacy JWT-based Keys (`eyJ...`):** Transmitted via both `apikey: <key>` and `Authorization: Bearer <key>` for complete backward compatibility.
    - **Modern Secret Keys (`sb_secret_...` / `sb_pub_...`):** Transmitted exclusively via `apikey: <key>`; `Authorization: Bearer` is strictly omitted.
    - **Anti-Decoding Guard:** `sb_secret_` keys are treated as opaque strings and are never decoded or parsed as JWTs.
    - **Server-Side Exclusivity:** Service role keys are kept strictly on the backend server, never returned in API payloads, health checks, or frontend bundles, and never logged in plaintext.
- **Strict Least-Privilege Gmail Scope (`gmail.readonly`):**
  - The application strictly requires read-only access to read inbound invoice emails and PDF attachments.
  - Scope is strictly constrained to `https://www.googleapis.com/auth/gmail.readonly`.
  - All write, modify, delete, and send scopes (specifically `https://www.googleapis.com/auth/gmail.modify`) are barred and excluded from OAuth configurations, documentation, and provisioning checklists.
  - Verification tests confirm that the canonical OAuth authorization URL generated by `build_authorization_url` contains exclusively `scope=https://www.googleapis.com/auth/gmail.readonly` with no escalated permissions.

## 20. Operational Security Hardening & Connection Decoupling (Final Readiness)
- **Google OAuth Testing Limitations & Refresh Token Lifecycle:**
  - Google Cloud restricts external OAuth applications in "Testing" mode to 7-day refresh token lifetimes.
  - Automated ingestion halts cleanly when tokens expire (`status: "EXPIRED"`), with zero silent data corruption or false health reports.
  - Re-authorization utilizes existing cryptographic safeguards: 10-minute state nonces (`OAuthStateNonce`), single-use consumption, and tenant-binding validation.
  - Production verification and CASA Tier 2 restricted-scope assessment remain mandatory prerequisites for indefinite token lifespans.
- **Supabase Database Connection Separation & Least Privilege:**
  - Separated runtime (`DATABASE_URL`), migration (`MIGRATION_DATABASE_URL`), and backup/restore (`BACKUP_DATABASE_URL`) connection strings.
  - Serverless runtime uses Supavisor transaction pooler (port 6543) with prepared-statement safety and check-in sanitization.
  - DDL migrations and operator backups use direct PostgreSQL (port 5432) or session poolers (port 5432), preventing transactional DDL failures and advisory lock collisions on transaction poolers.
  - Sensitive connection credentials across all three URLs are masked in logs, diagnostics, and configurations via [`Settings.redacted_dict`](file:///c:/Zamp%20Casse%20Study/backend/core/config.py).
- **Mandatory Privileged Storage Credentials:**
  - [`SupabaseStorageAdapter`](file:///c:/Zamp%20Casse%20Study/backend/core/storage.py) enforces server-side exclusivity: privileged storage operations (file upload, private presigned URL creation, purge, listing) strictly require `SUPABASE_SERVICE_ROLE_KEY`.
  - Unprivileged `SUPABASE_ANON_KEY` or publishable keys are **never silently substituted**.
  - Missing or invalid credentials immediately report honest `NOT_CONFIGURED` or `BLOCKED` states without attempting unauthenticated operations.





