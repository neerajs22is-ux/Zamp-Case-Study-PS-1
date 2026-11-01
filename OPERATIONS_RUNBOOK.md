# AP Command Center — Operations & Maintenance Runbook

**Environment Target:** Production & Staging  
**Version:** Phase A Foundation

---

## 1. Application Lifecycle & Startup

### Environment Prerequisites
- Python 3.11+
- PostgreSQL 15+ with SSL enabled
- S3 / GCS private bucket with KMS encryption key
- Enterprise OIDC Client ID and secret

### Starting the Production Service
```bash
# 1. Activate virtual environment
source venv/bin/activate  # Or Windows: .\venv\Scripts\Activate.ps1

# 2. Run database migrations
python -m alembic upgrade head

# 3. Start production ASGI server with multiple workers
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers
```

### Readiness & Liveness Health Checks
- **Liveness Probe:** `GET /api/v1/health/liveness` (Returns HTTP 200 if process is running).
- **Readiness Probe:** `GET /api/v1/health` (Verifies live database connectivity and object storage health. In `production`, returns HTTP 503 if PostgreSQL or S3 is unavailable).

---

## 2. Database Migrations & Rollback

### Apply Migrations
```bash
python -m alembic upgrade head
```

### Check Migration Status
```bash
python -m alembic current
```

### Rollback Previous Migration
```bash
python -m alembic downgrade -1
```

---

## 3. Incident Management & Operator Recovery

### Handling Database Connectivity Loss
1. Check RDS / Cloud SQL connection pool saturation.
2. Verify network security groups and VPC peering routing.
3. The application returns HTTP 503 `SETUP_BLOCKED` or `DEGRADED` on `/api/v1/health` without exposing database credentials.

### Audit Immutability Alert
If an alert is triggered regarding an attempted update or delete on `audit_events`:
1. The attempt was blocked at the database level by trigger `trg_audit_events_immutable`.
2. Inspect server logs for the originating correlation ID and authenticated user identity.
3. Escalate immediately to Security & Compliance Officer as an unauthorized tampering attempt.

### Refresh Token Revocation (Gmail / ERP)
If an integration token is compromised or revoked:
1. Navigate to `/connections` in the AP Command Center UI (System Administrator role required).
2. Click `Revoke Authorization`.
3. In the identity provider console, invalidate active tokens.
4. Issue new credentials in the secrets manager and trigger reconnect.

---

## 4. Supabase Backup & Recovery Runbook (Phase B Stage 6)

### 4.1 Architectural Overview
The AP Command Center utilizes a Supabase-first, zero-AWS backup architecture designed for development and controlled customer pilots:
- **Database:** Supabase PostgreSQL (schema, custom application roles, RLS policies, alembic migration history, and business data).
- **Storage:** Private Supabase Storage bucket (`invoices`) containing raw invoice PDFs and attachments.
- **Archive Format:** Authenticated encrypted archive (`.tar.gz.enc`) using Fernet (128-bit AES in CBC mode with PKCS7 padding and HMAC-SHA256 authentication).
- **Execution Mode:** Manual operator-initiated execution via CLI or API.
- **Scheduling Status:** Automated background worker scheduling is `NOT_CONFIGURED` until Cloud Run deployment preparation. No Celery, ARQ, or unapproved worker frameworks are used.

### 4.2 Supabase CLI Dump Exclusions & Separate Exports
When using the Supabase CLI, standard database dumps omit critical components:
- **Excluded Schemas:** By default, `supabase db dump` excludes platform-managed schemas including `auth`, `storage`, `extensions`, `realtime`, `cron`, `vault`, etc.
- **Custom Roles Omitted:** Standard schema dumps do NOT include custom database roles (e.g. `ap_app_user`) or role-level grants.
- **Mandatory 3-Part Dump:** An operator running Supabase CLI commands must execute three distinct exports:
  ```bash
  # 1. Export Custom Roles & Grants
  supabase db dump --db-url "$DATABASE_URL" --role-only -f roles.sql

  # 2. Export Application Schema (Tables, Indexes, RLS Policies, Functions)
  supabase db dump --db-url "$DATABASE_URL" --schema public -f schema.sql

  # 3. Export Application Data (Disabling triggers during restore via session_replication_role)
  supabase db dump --db-url "$DATABASE_URL" --data-only --schema public -f data.sql
  ```

### 4.3 Supabase Auth Recovery & User Reconciliation Procedure (Stage 6.1)
- **Identity & Password Boundaries:** Supabase Auth stores user identities, encrypted credentials, and MFA factors in the managed `auth.users` and `auth.identities` tables.
- **Cross-Project User ID Realities:**
  1. The Supabase CLI `supabase db dump` command excludes `auth` schema tables by default.
  2. While the Auth Admin API (`supabase.auth.admin.create_user`) allows programmatic user creation, in many hosted GoTrue versions client-specified UUIDs are overridden by server-generated UUIDs.
  3. Destination Supabase projects utilize distinct JWT signing secrets, instantly invalidating pre-existing sessions and tokens upon restore.
- **Pilot Recovery & Reconciliation Protocol:**
  1. When restoring public schema data into a fresh Supabase project, employees sign in via Google OAuth.
  2. If GoTrue generates a new random UUID for the employee, the operator executes the automated reconciliation utility:
     ```python
     from backend.core.backup import DatabaseBackupManager
     from backend.core.database import get_db_session

     with get_db_session() as session:
         DatabaseBackupManager.reconcile_auth_user(
             session=session,
             email="employee@company.com",
             new_auth_id=new_gotrue_uuid,
             actor_id="OPERATOR_RECONCILE"
         )
     ```
  3. This reconciles `public.users.id` and cascades to `role_assignments.user_id`, immediately restoring organizational access while recording an immutable `USER_AUTH_RECONCILED` audit event.
  4. *Truthful Invariant:* Never claim Auth recovery is complete without verifying actual login on the restored project.

### 4.4 Supabase Storage Backup & Manifest Integrity
- The Python backup utility connects to Supabase Storage via authenticated REST API, traversing pagination to enumerate every physical object in the `invoices` bucket.
- Each physical file is downloaded, and a cryptographic SHA-256 hash is computed and compared against `Document.sha256_hash` in the database.
- **Manifest File (`manifest.json`):** Records per-document metadata (document ID, tenant ID, bucket, storage key, filename, size, content type, SHA-256, verification result).
- **Strict Failure Invariant:** If any expected document is missing from storage (`MISSING_FROM_STORAGE`) or exhibits a checksum mismatch (`CORRUPTED`), the backup is marked `completion_status = "FAILED"`. An incomplete or corrupted backup is NEVER marked successful.

### 4.5 Encryption Key Management & Disaster Recovery Caveat
- **Key Generation:** Generate a cryptographically secure 32-byte Fernet key:
  ```bash
  python -m backend.scripts.backup --generate-key
  ```
- **Key Storage & Prompt Handling (Stage 6.1):**
  - Store the encryption key in an external operator password manager (e.g. 1Password, Bitwarden, or Google Secret Manager).
  - Prefer passing keys via the `BACKUP_ENCRYPTION_KEY` environment variable.
  - If omitted from both CLI and environment, the backup and restore utilities safely prompt via a hidden interactive password prompt (`getpass.getpass()`), preventing secret exposure in shell process tables or history.
  - Passing keys via the `--key` flag emits an explicit security warning.
- **Disaster Recovery Notice:** Backups stored exclusively on the same host or development computer do NOT constitute independent disaster recovery. Operators must transfer encrypted `.tar.gz.enc` archives to external, physically decoupled offline or secondary storage.

### 4.6 Post-Restore Integrity Verification (Stage 6.1)
During restoration, `session_replication_role = replica;` temporarily disables user triggers to allow data import. Immediately following data restoration, the system automatically executes rigorous integrity verification:
1. **Foreign Key Integrity:** Iterates over all table relationships and checks for orphaned records.
2. **Tenant Isolation:** Enforces strict `org_id` alignment across legal entities, users, role assignments, invoices, lines, and documents.
3. **Audit Immutability Verification:** Tests that `trg_audit_events_immutable` actively rejects mutation post-restore.
4. **Storage Checksum Validation:** Restored files in Supabase Storage are verified byte-for-byte against the manifest and database SHA-256 hashes.

### 4.7 Operator Execution Commands

#### Running an On-Demand Backup
```bash
# Set encryption key via environment (recommended)
export BACKUP_ENCRYPTION_KEY="your-32-byte-fernet-key"

# Execute backup with default 30-day / 10-archive retention pruning
python -m backend.scripts.backup --backup-dir ./backups
```

#### Restoring into a Clean Disposable Test/Staging Environment
```bash
# Execute controlled restoration (prompts for encryption key securely if unset)
python -m backend.scripts.restore \
  --archive ./backups/backup_20261031_120000.tar.gz.enc \
  --target-db-url "postgresql://postgres:postgres@localhost:5432/test_restore_db" \
  --confirm-restore
```

### 4.8 Archive Structure
Inside each encrypted archive (`.tar.gz.enc`):
```text
backup_<timestamp>/
├── manifest.json              # Full document manifest, counts, and completion status
├── database/
│   ├── roles.sql              # ap_app_user role creation, permissions, and grants
│   ├── schema.sql             # Schema DDL metadata and Alembic head revision
│   ├── data.sql               # Foreign-key ordered table inserts with replica triggers
│   └── metadata.json          # Table row counts and Alembic version
├── storage/
│   └── invoices/
│       └── org_<org_id>/invoices/<doc_id>/<filename>.pdf
└── auth_summary.json          # User emails, roles, and org mappings (zero secrets)
```

---

## 5. Google Cloud Run Deployment Runbook (Phase B Stage 7)

### 5.1 Architecture & Hosting Topology
- **Host Platform:** Google Cloud Run (Fully Managed Serverless Container).
- **Target Region:** `asia-south1` (Mumbai, India) for data sovereignty and sub-10ms network proximity to enterprise customers.
- **Execution Profile (Scenario A Pilot):**
  - Scale-to-zero enabled (`minScale: 0`, `maxScale: 3`) for minimal pilot operating costs.
  - Concurrency: 80 requests per instance.
  - Compute Limits: 1 vCPU, 512 MB RAM with CPU boost enabled during container cold-starts.
  - Unprivileged non-root runtime (`appuser`, UID 1000).
- **Network Ingress:**
  - HTTPS ingress enabled with automated Google-managed TLS certificates.
  - Google Cloud Pub/Sub push webhook delivers Gmail notifications with OIDC Bearer token verification.
- **External Inter-Cloud Egress:**
  - TLS 1.3 egress to Supabase AWS Mumbai (`ap-south-1`) PostgreSQL pooler (port 6543) and Storage REST API.

### 5.2 Google Secret Manager Setup (Stage 7.2 Secret Hygiene)
Before initiating Cloud Run deployment, the retained sensitive server-side secrets must be created in Google Secret Manager within the target project. In accordance with Stage 7.2 least-privilege standards:
- `SUPABASE_ANON_KEY` is a client-facing publishable key and is supplied via standard environment variables (not Secret Manager).
- `GMAIL_REFRESH_TOKEN` is stored per mailbox encrypted in PostgreSQL (`gmail_accounts.encrypted_refresh_token`) and is not stored as a global Secret Manager secret.
- `BACKUP_ENCRYPTION_KEY` is retained exclusively by operators on trusted workstations for CLI backup operations and is excluded from Cloud Run Secret Manager access.

```bash
# 1. Supabase PostgreSQL Connection URL (Pooler)
echo -n "postgresql://postgres.<ref>:<pass>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require" | \
    gcloud secrets create ap-database-url --data-file=-

# 2. Application Session & Token Signing Key
openssl rand -hex 32 | gcloud secrets create ap-secret-key --data-file=-

# 3. Supabase Service Role Key
echo -n "eyJhbGciOi..." | gcloud secrets create ap-supabase-service-key --data-file=-

# 4. Supabase JWT Secret (Required by backend verify_token_claims)
echo -n "your-supabase-jwt-secret" | gcloud secrets create ap-supabase-jwt-secret --data-file=-

# 5. Gmail Client Secret & Database Token Encryption Key
echo -n "GOCSPX-your-gmail-oauth-client-secret" | gcloud secrets create ap-gmail-client-secret --data-file=-

python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode(), end='')" | \
    gcloud secrets create ap-gmail-encryption-key --data-file=-
```

### 5.3 Automated Operator Deployment
Deploy the full stack using the automated deployment script:
```bash
# Make script executable
chmod +x deploy/cloudrun/deploy.sh

# Run automated deployment
./deploy/cloudrun/deploy.sh
```

### 5.4 Google Cloud Scheduler Background Automations (Stage 7.1)
The deployment script configures maintenance cron jobs using a **dedicated Cloud Scheduler service account** (`ap-cloud-scheduler-sa@<project>.iam.gserviceaccount.com`), strictly separate from the Pub/Sub push identity (`gmail-pubsub-push`):

1. **Gmail Watch Renewal (`gmail-watch-renewal`):**
   - **Schedule:** `0 0 * * *` (Daily at 00:00 UTC).
   - **Target:** `POST /api/v1/integrations/gmail/watch/renew`
   - **Authentication:** Google OIDC token issued to `ap-cloud-scheduler-sa`.
   - **Purpose:** Renews the 7-day Gmail Pub/Sub watch push notification before expiration.
2. **Gmail Missed-Message Reconciliation (`gmail-history-reconciliation`):**
   - **Schedule:** `0 */6 * * *` (Every 6 hours).
   - **Target:** `POST /api/v1/integrations/gmail/reconcile`
   - **Authentication:** Google OIDC token issued to `ap-cloud-scheduler-sa`.
   - **Purpose:** Synchronizes any missed messages or attachments if Pub/Sub notifications experienced transient delivery drops.
3. **Unfinished Pub/Sub Event Recovery (`gmail-pubsub-reclaim`):**
   - **Schedule:** `*/30 * * * *` (Every 30 minutes).
   - **Target:** `POST /api/v1/integrations/gmail/pubsub/reclaim`
   - **Authentication:** Google OIDC token issued to `ap-cloud-scheduler-sa`.
   - **Purpose:** Scans and reclaims unfinished `RECEIVED`, `FAILED`, or `CONCURRENT_DEFERRED` events.

> [!IMPORTANT]
> **Ephemeral Filesystem Invariant: No Automated Backup Scheduler in Cloud Run**
> Cloud Run container filesystems are strictly ephemeral and are destroyed when instances scale to zero. Therefore, automated backups are NOT scheduled in Cloud Run.
> Backups must be executed manually by operators via CLI (`python -m backend.scripts.backup`) from a trusted workstation and transferred to an external, physically decoupled, secure location.
> Backup status reports `execution_mode: "OPERATOR_MANUAL"` and `background_scheduler: "NOT_CONFIGURED"`.

### 5.5 Pub/Sub Push Subscription & Timeout Safety Architecture (Stage 7.2)
- **Subscription Name:** `gmail-ap-inbox-push-sub`
- **Topic:** `projects/<project-id>/topics/gmail-ap-inbox`
- **Push Endpoint:** `https://<SERVICE_URL>/api/v1/integrations/gmail/pubsub/push`
- **Push Service Account:** `gmail-pubsub-push@<project-id>.iam.gserviceaccount.com` (dedicated identity granted `roles/run.invoker`).
- **Acknowledgement Deadline:** Explicitly configured to **300 seconds** (matching Cloud Run container request timeout of 300s).
- **Internal Processing Deadline:** **240 seconds** (`GMAIL_SYNC_TIMEOUT_SECONDS = 240`), providing a 60-second safety buffer before infrastructure timeout.
- **External Request Bounds:** Individual Gmail API calls and attachment downloads are bounded to 15 seconds (`timeout=15.0`).
- **Timeout Safety & Safe Halting:**
  - If processing a large message backlog approaches 240 seconds:
    1. The sync loop halts safely before the container timeout or HTTP 504 gateway drop.
    2. Any documents and invoices processed so far are committed to PostgreSQL.
    3. The mailbox watermark (`account.last_history_id`) is **NOT** advanced, ensuring remaining messages are not lost.
    4. The exclusive per-mailbox lease is immediately released.
    5. The event status is preserved as `RECEIVED` with timeout details recorded in `error_message`.
  - When Pub/Sub redelivers the notification or the 30-minute reclaim job runs:
    - Stage 5.2 unfinished-event recovery re-triggers processing.
    - Already processed messages are skipped via SHA-256 hash deduplication with zero duplicate invoice or audit records.
    - Remaining unprocessed messages are ingested, and the watermark is advanced to the final historyId upon successful completion.

### 5.6 Production Monitoring & Health Verification
- **Liveness Probe:** `curl -s https://<SERVICE_URL>/api/v1/liveness`
  Returns `{"status": "ALIVE", "timestamp": "...", "app_env": "production"}`.
- **Comprehensive Health Check:** `curl -s https://<SERVICE_URL>/api/v1/health`
  Validates live PostgreSQL connection, Supabase Storage bucket readiness, and integration statuses.
- **Container Logs:** Inspect real-time logs via Cloud Logging:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=ap-command-center" --limit 50 --format="json"
  ```

### 5.7 Supabase Database Connection Separation & Pooler Architecture
Never assume port 6543 or port 5432 is universally applicable to all database tasks. Supabase provides distinct endpoints with specific protocol characteristics:

1. **`DATABASE_URL` (Cloud Run Runtime Application Connection):**
   - **Target:** Supabase Transaction Pooler (port **6543**), e.g.:
     `postgresql://postgres.<project-ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require`
   - **Characteristics:** Managed by Supavisor in transaction pooling mode. Ideal for serverless, scale-to-zero environments (Cloud Run) where stateless connections are pooled efficiently.
   - **Prepared Statement Compatibility:** Configured with `pool_pre_ping=True` and connection check-in sanitization. Prepared statements are not held across pooled sessions.
2. **`MIGRATION_DATABASE_URL` (Alembic DDL Migration Connection):**
   - **Target:** Direct PostgreSQL Connection (port **5432**) or Session Pooler (port **5432** on the pooler host):
     `postgresql://postgres.<project-ref>:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require`
     *(or `...pooler.supabase.com:5432/postgres?sslmode=require` if direct IPv6/IPv4 is restricted)*
   - **Why Transaction Pooler (6543) Fails for Migrations:** Transaction poolers disallow transactional DDL (`CREATE TABLE`, `ALTER TABLE`, `DROP INDEX`), schema modifications, and advisory locks required by Alembic (`alembic_version` state tracking). Migrations executed against port 6543 will fail with `prepared statement does not exist` or syntax errors.
   - **Execution Precedence:** `backend/migrations/env.py` checks `MIGRATION_DATABASE_URL` first before falling back to `DATABASE_URL`.
3. **`BACKUP_DATABASE_URL` (Operator Backup & Restoration CLI):**
   - **Target:** Direct PostgreSQL Connection (port **5432**) or Session Pooler (port **5432**):
     `postgresql://postgres.<project-ref>:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require`
   - **Characteristics:** Required for native schema table inspection, cursor-based streaming table dumps, and foreign-key ordered restorations without transaction-interleaving interference.
   - **CLI Usage:** `python -m backend.scripts.backup` and `python -m backend.scripts.restore` check `BACKUP_DATABASE_URL` first before falling back to `DATABASE_URL`.

### 5.8 Google OAuth Testing Limitations & Reconnection Runbook
1. **The Seven-Day Expiration Limitation:**
   - In Google Cloud Console, OAuth consent screens with publishing status **"Testing"** issue refresh tokens that expire after **7 days** when the user type is External.
   - **Sole Permitted Scope:** Must remain strictly and exclusively `https://www.googleapis.com/auth/gmail.readonly` (least privilege; `gmail.modify` is prohibited).
   - **Automated Ingestion Impact:** Operators must not claim uninterrupted automated ingestion while the project is in testing status. Ingestion will pause every 7 days when the token expires (`status: "EXPIRED"` and `readiness: false`).
2. **Simple Mailbox Reconnection Procedure:**
   - When token expiry occurs:
     1. An operator or tenant admin accesses the web UI and clicks **"Reconnect Mailbox"** on the Connections page (or visits `GET /api/v1/integrations/gmail/authorize`).
     2. Authenticate with the target Google AP mailbox account and grant read-only consent.
     3. Google redirects to `/api/v1/integrations/gmail/callback`, which automatically decrypts/encrypts and persists the new refresh token in `gmail_accounts.encrypted_refresh_token` and resets status to `AUTHORIZED` / `CONNECTED`.
     4. Cloud Scheduler triggers (`gmail-history-reconciliation` or `gmail-pubsub-reclaim`) immediately resume synchronizing any pending messages without message loss or duplication.
3. **Path to Uninterrupted Production Authorization:**
   - To achieve indefinite refresh token validity without 7-day expirations:
     - **Option A (Google Workspace Internal App):** If the Google Workspace domain matches the deployment, configure User Type to **Internal** in the OAuth Consent Screen. Internal apps issue permanent refresh tokens and do not require verification.
     - **Option B (Google OAuth Verification & CASA Assessment):** If using an External User Type, the project must undergo Google OAuth App Verification and a CASA Tier 2 (Cloud Application Security Assessment) restricted-scope assessment. This is a separate production release milestone and not required for test/pilot environments.

### 5.9 Supabase Storage Privileged Key Requirement
- **Privileged Key Exclusivity:** All server-side object storage operations (uploading invoices, generating private presigned URLs, soft deletion, physical purging, object listing) require elevated server privileges.
- **Strict Prohibition of Anon/Publishable Key Substitution:** `SupabaseStorageAdapter` strictly requires `SUPABASE_SERVICE_ROLE_KEY` (either modern `sb_secret_...` or legacy JWT `eyJ...`). It will **never silently substitute** `SUPABASE_ANON_KEY` or a publishable key.
- **Truthful Status Reporting:** If `SUPABASE_SERVICE_ROLE_KEY` is missing or invalid, storage health returns an honest `NOT_CONFIGURED` or `BLOCKED` state, preventing silent data ingestion into unauthenticated or failing endpoints.

### 5.10 Operator's First Test-Environment Provisioning Checklist (Frozen Release — Final)
With the completion of Stage 7.3.1 and operational hardening, code implementation and deployment automation are **FROZEN**. When provisioning the pilot/test environment, execute the following steps:

1. **Supabase Free Project Setup:**
   - Create project in region `ap-south-1` (Mumbai).
   - In Storage dashboard: create a **private** bucket named `invoices` (uncheck "Public bucket", 50 MB max file size).
   - Apply database schema migrations using Direct PostgreSQL or Session Pooler port 5432:
     ```bash
     MIGRATION_DATABASE_URL="postgresql://postgres.<ref>:<pass>@db.<ref>.supabase.co:5432/postgres?sslmode=require" python -m alembic upgrade head
     ```
2. **GCP Secret Manager Configuration:**
   - Populate secrets:
     - `ap-database-url`: Cloud Run runtime connection string (Transaction Pooler port **6543**, `sslmode=require`).
     - `ap-secret-key`: Random 32+ character session signing key (`openssl rand -hex 32`).
     - `ap-supabase-service-key`: Server-side service key. Accepts either modern Supabase secret key (`sb_secret_...`) or legacy JWT format (`eyJ...`). Handled automatically by the format-aware Storage adapter (`apikey` header only for `sb_secret_`). Unprivileged publishable/anon keys are never accepted.
     - `ap-supabase-jwt-secret`: Required ONLY if the Supabase project uses legacy symmetric `HS256` signing; optional if asymmetric `RS256`/`ES256` JWKS is used.
     - `ap-gmail-client-secret`: Google Cloud OAuth Web Client Secret. The OAuth consent screen and client MUST be restricted strictly and exclusively to `https://www.googleapis.com/auth/gmail.readonly` (least privilege; `gmail.modify` is barred). Note: In Google "Testing" mode, refresh tokens expire every 7 days requiring simple UI reconnection.
     - `ap-gmail-encryption-key`: 32-byte urlsafe Fernet key for token encryption at rest.
   - Generate operator backup key on trusted local workstation CLI (`python -m backend.scripts.backup --generate-key`). Do NOT save in Cloud Run Secret Manager.
3. **Execute Automated Deployment:**
   - Run `./deploy/cloudrun/deploy.sh`.
   - Verify 3 Cloud Scheduler cron triggers are active:
     - `gmail-watch-renewal` (Daily at 00:00 UTC)
     - `gmail-history-reconciliation` (Every 6 hours)
     - `gmail-pubsub-reclaim` (Every 30 minutes)
   - Confirm liveness probe returns HTTP 200 on `https://<SERVICE_URL>/api/v1/liveness`.



