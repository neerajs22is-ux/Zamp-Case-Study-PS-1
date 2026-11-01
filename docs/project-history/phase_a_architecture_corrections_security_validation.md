# Phase A — Architecture Assessment & Operator Decision Register (Final Architecture Freeze)

**Document Reference:** `ARCH-SEC-VAL-2026-P2.6-FROZEN`  
**Status:** ARCHITECTURAL SPECIFICATION & OPERATIONAL BASELINE (FROZEN — NON-EXECUTING)  
**Scope:** Complete Supabase Multi-Schema Backup & Recovery Protocol, Stable Invoice Storage Backup Pipeline, Paused Free Project SLA Reality, 4-Stage Soft-Delete & Statutory Retention Lifecycle, Google Cloud Run Workload & Cost Analysis, and Free-Tier Production Limitations.  
**Binding Standard:** Strict Engineering Contract — Zero Simulated Functionality, Zero Auth Bypass, Zero Table-Level Tenant Leakage. Zero Infrastructure Provisioning without Explicit Authorisation.

---

## 1. Master Operator Decision Register (Frozen Baseline)

The following register establishes the frozen baseline for customer onboarding, identity, database, storage, ingestion, and backup operations. Every subsystem is explicitly categorized under `VERIFIED`, `APPROVED`, `DEFERRED`, `UNRESOLVED`, or `BLOCKED`:

```
+---------------------------------------------------------------------------------------------------+
| MASTER OPERATOR DECISION REGISTER (FROZEN BASELINE - P2.6)                                        |
+---------------------------------------------------------------------------------------------------+
| Subsystem / Area             | Status      | Technical Reality & Binding Architectural Constraint |
+------------------------------+-------------+------------------------------------------------------+
| 1. Primary Platform Provider | APPROVED    | Supabase selected as primary infrastructure provider.|
|                              |             | Initial development & pilot on Supabase Free plan.   |
+------------------------------+-------------+------------------------------------------------------+
| 2. AWS Dependencies          | REMOVED     | ALL AWS dependencies removed (No S3, No KMS, No IAM, |
|                              |             | No Object Lock, No ECS Fargate). Zero AWS accounts.  |
+------------------------------+-------------+------------------------------------------------------+
| 3. Application Database      | APPROVED    | Supabase PostgreSQL with Table-Level RLS isolation.  |
+------------------------------+-------------+------------------------------------------------------+
| 4. Employee Authentication   | APPROVED    | Supabase Auth (Google SSO) with invitation-only flow.|
+------------------------------+-------------+------------------------------------------------------+
| 5. Invoice Storage Backend   | APPROVED    | Supabase Storage (private buckets) with signed URLs  |
|                              |             | and SHA-256 verification via ObjectStorageAdapter.   |
+------------------------------+-------------+------------------------------------------------------+
| 6. Database Backup Protocol  | CORRECTED   | Multi-schema export protocol (public DDL, auth.users,|
|                              |             | storage metadata, custom roles). CLI default fails.  |
+------------------------------+-------------+------------------------------------------------------+
| 7. Storage Backup Protocol   | APPROVED    | Stable REST/S3 Python export script with manifest.   |
|                              |             | Stored in encrypted operator archive. No exp CLI.    |
+------------------------------+-------------+------------------------------------------------------+
| 8. Paused Project SLA        | CORRECTED   | Unsupported 10-30s wake-up claim removed. Paused     |
|                              |             | projects take several minutes; no SLA on Free tier.  |
+------------------------------+-------------+------------------------------------------------------+
| 9. Document Deletion Model   | APPROVED    | 4-stage lifecycle: ACTIVE -> SOFT_DELETED ->         |
|                              |             | RETENTION_EXPIRED -> AUTHORISED_PURGE (Audit-backed).|
+------------------------------+-------------+------------------------------------------------------+
| 10. FastAPI Hosting Provider | APPROVED    | Google Cloud Run in Mumbai (asia-south1) preferred.  |
|                              |             | Billing account required. Free allowances modeled.   |
+------------------------------+-------------+------------------------------------------------------+
| 11. Gmail Integration        | APPROVED    | Gmail API (gmail.readonly) via 3-legged OAuth for    |
|                              |             | AP mailbox; Pub/Sub push for event ingestion.        |
+------------------------------+-------------+------------------------------------------------------+
| 12. Production CASA Audit    | BLOCKED     | Do not assume fixed Tier 2 cost. Verify current      |
|                              |             | Google verification requirements before expenditure. |
+------------------------------+-------------+------------------------------------------------------+
| 13. Supabase Project Setup   | BLOCKED     | Project provisioning on Supabase is NOT authorised.  |
+------------------------------+-------------+------------------------------------------------------+
| 14. Execution Boundary       | BLOCKED     | Strict execution boundary: Zero code changes, zero   |
|                              |             | migrations, zero deployments, zero Phase B work.     |
+------------------------------+-------------+------------------------------------------------------+
```

---

## 2. Complete Database Backup & Multi-Schema Recovery Protocol

### 2.1 Default CLI Dump Exclusions & System Architecture

* **Classification:** `[VERIFIED TECHNICAL FINDING]` (Supabase Platform & PostgreSQL Documentation).
* **Critical Finding:** A standard `supabase db dump` command **does not produce a complete application backup**.
* **Default Exclusions in Supabase CLI:**
  - `auth` schema: Excluded by default. Contains `auth.users`, `auth.identities`, session records, and password hashes.
  - `storage` schema: Excluded by default. Contains bucket configurations (`storage.buckets`) and file catalog metadata (`storage.objects`).
  - Custom Roles & Grants: System roles and unprivileged application roles (such as `ap_app_user`) and their explicit table grants are omitted from data dumps.
  - Extension Schemas: `extensions`, `graphql`, `realtime`, `vault` are excluded.
* **Failure Consequence:** Restoring a default `supabase db dump` onto a fresh Supabase project results in broken foreign keys (`public.users` referencing missing `auth.users`), nonexistent storage bucket registrations, and missing role-based permissions for `ap_app_user`.

### 2.2 Complete Multi-Schema Export Specification

A valid, recoverable database backup requires an orchestrated sequence of four discrete exports:

```
+---------------------------------------------------------------------------------------------------+
| COMPLETE MULTI-SCHEMA DATABASE EXPORT PIPELINE                                                    |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [Step 1: Custom Roles & Permissions DDL]                                                         |
|      Command: pg_dump -h $DB_HOST -U postgres -d postgres --schema-only \                        |
|               --table=pg_roles --no-owner > 01_roles_and_grants.sql                               |
|      Captures: DDL for `ap_app_user` with NOSUPERUSER NOBYPASSRLS and table grants.               |
|                                                                                                   |
|  [Step 2: Core Relational Schema DDL & Public Data]                                               |
|      Command: supabase db dump --schema public > 02_public_schema.sql                             |
|      Command: supabase db dump --data-only --schema public > 03_public_data.sql                   |
|      Captures: All 26 domain tables, foreign keys, triggers, and append-only audit records.       |
|                                                                                                   |
|  [Step 3: Supabase Auth Identities & Users]                                                       |
|      Command: pg_dump -h $DB_HOST -U postgres -d postgres --data-only --schema=auth \             |
|               -t auth.users -t auth.identities > 04_auth_data.sql                                 |
|      Captures: UUID primary keys, verified email statuses, and encrypted credentials.             |
|                                                                                                   |
|  [Step 4: Storage Bucket Configuration & File Metadata]                                           |
|      Command: pg_dump -h $DB_HOST -U postgres -d postgres --data-only --schema=storage \          |
|               -t storage.buckets -t storage.objects > 05_storage_metadata.sql                     |
|      Captures: Private bucket configurations, file paths, MIME types, and storage keys.           |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

### 2.3 End-to-End Fresh Project Recovery Procedure

* **Mandatory Testing Requirement:** Recovery procedures cannot be verified merely by confirming that `.sql` export files exist on disk. **The disaster recovery procedure must be executed and validated against a fresh, completely separate Supabase project.**

```
+---------------------------------------------------------------------------------------------------+
| FRESH SUPABASE PROJECT RESTORATION SEQUENCE                                                       |
+---------------------------------------------------------------------------------------------------+
|  1. Target Setup: Provision clean target project; retrieve PostgreSQL connection URI.             |
|  2. Restore Roles: Execute `01_roles_and_grants.sql` (Creates `ap_app_user`).                     |
|  3. Restore DDL: Execute `alembic upgrade head` or `02_public_schema.sql` (Creates 26 tables).    |
|  4. Restore Auth: Execute `04_auth_data.sql` (Populates `auth.users` to satisfy foreign keys).     |
|  5. Restore App Data: Execute `03_public_data.sql` (Populates organisations, invoices, audit).    |
|  6. Restore Storage Catalog: Execute `05_storage_metadata.sql` (Registers buckets & metadata).    |
|  7. Restore Binary Objects: Run storage recovery script (Section 3) to re-upload PDF binaries.    |
|  8. Verification Assertion: Execute automated relational integrity test:                          |
|     - Assert `COUNT(*) FROM documents WHERE storage_key NOT IN (SELECT name FROM storage.objects)`|
|       evaluates to exactly ZERO.                                                                  |
|     - Execute `RLS-01` to `RLS-07` cross-tenant test suite to prove RLS enforcement post-restore.  |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. Stable Invoice File Storage Backup Pipeline

### 3.1 Rejection of Experimental CLI Functionality

* **Classification:** `[VERIFIED TECHNICAL CONSTRAINT]`
* Supabase CLI commands for direct storage object synchronization (`supabase storage cp`, `supabase storage sync`) are currently designated as experimental, lack granular error reporting, do not preserve SHA-256 metadata verification, and frequently change across minor CLI releases.
* **Architecture Rule:** Experimental CLI commands are **strictly prohibited** as a critical backup dependency.

### 3.2 Stable Operator-Controlled Backup Pipeline

* The backup pipeline is implemented as an automated Python script using the stable **Supabase Storage REST API** (or AWS Boto3 against Supabase's S3-compatible endpoint `https://<project-ref>.storage.supabase.co/s3`):

```
+---------------------------------------------------------------------------------------------------+
| STABLE OPERATOR-CONTROLLED STORAGE BACKUP PIPELINE                                                |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [Supabase Storage REST API]                                                                      |
|       |                                                                                           |
|       | 1. Script queries `documents` table for active/soft-deleted documents                     |
|       | 2. Fetches raw binary stream via GET /storage/v1/object/authenticated/{bucket}/{key}      |
|       v                                                                                           |
|  [In-Memory Checksum Verification]                                                                |
|       - Compute SHA-256: hashlib.sha256(file_bytes).hexdigest()                                   |
|       - Assert computed_hash == documents.sha256_hash (Detects corruption prior to archiving)    |
|       v                                                                                           |
|  [Local Staging Directory on Operator System]                                                     |
|       - Structure: /backups/invoices/{org_id}/{document_id}.pdf                                   |
|       v                                                                                           |
|  [Durable Export Manifest: manifest.json]                                                         |
|       - Generates signed metadata record per file:                                                |
|         {                                                                                         |
|           "document_id": "doc_12345",                                                             |
|           "org_id": "org_corp_acme",                                                              |
|           "storage_key": "org_corp_acme/invoices/doc_12345.pdf",                                  |
|           "sha256_hash": "a8f5c...",                                                              |
|           "content_type": "application/pdf",                                                      |
|           "file_size_bytes": 1048576,                                                             |
|           "backed_up_at": "2026-10-31T19:00:00Z"                                                 |
|         }                                                                                         |
|       v                                                                                           |
|  [Symmetric Archive Encryption]                                                                   |
|       - Compress & Encrypt: `tar -czf - /backups/invoices/ | gpg -c --batch --passphrase $KEY`    |
|       - Destination: Operator-controlled offline/cold storage volume.                             |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

### 3.3 Storage Restoration Verification Protocol

1. Decrypt archive: `gpg -d backup.tar.gz.enc | tar -xzf -`
2. Parse `manifest.json`.
3. For each file in manifest:
   - Compute `hashlib.sha256(bytes).hexdigest()`.
   - Assert `computed_hash == item['sha256_hash']`.
   - Upload file stream to target Supabase Storage project:  
     `POST /storage/v1/object/{bucket}/{key}` with `Content-Type: item['content_type']`.
4. Verification assertion: Every restored file must be accessible via a newly generated signed URL and validate byte-for-byte against the original invoice record.

---

## 4. Supabase Free Plan Operational Reality & Pausing Constraints

### 4.1 Correction of Paused Project Wake-Up Claims

* **Classification:** `[CORRECTED TECHNICAL FACT]` (Supabase Official Free Plan SLA Terms).
* **Correction:** The prior assertion that paused Free projects reliably wake up in 10–30 seconds is **unsupported and hereby retracted**.
* **Technical Reality:**
  - Supabase automatically pauses Free tier projects after **7 consecutive days of zero database or API activity**.
  - **Wake-Up Duration:** Restoring a paused project requires an administrative action in the Supabase Dashboard or an unpause API call. Container provisioning, disk re-attachment, and PostgreSQL startup frequently require **several minutes (typically 2 to 10 minutes)**.
  - **No Availability SLA:** Supabase explicitly provides **zero uptime SLA and zero guaranteed recovery time** for paused or active Free plan projects.
  - Under periods of platform maintenance or resource contention, waking a paused project can experience extended delays.
* **Operational Ruling:** Free tier availability is suitable **strictly for development, testing, and controlled single-tenant pilots**. It must not be represented to customers as an always-on, enterprise-grade production environment.

---

## 5. Comprehensive 4-Stage Document Soft-Delete & Statutory Retention Lifecycle

* **Classification:** `[APPROVED BASELINE]`
* In financial accounting, permanent deletion of invoices without statutory compliance checks violates tax laws. Conversely, retaining deleted files indefinitely exhausts the 1 GB Free tier storage quota.
* The application enforces an explicit 4-stage lifecycle:

```
+---------------------------------------------------------------------------------------------------+
| 4-STAGE INVOICE DOCUMENT RETENTION & PURGE LIFECYCLE                                              |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [Stage 1: ACTIVE]                                                                                |
|      - Invoice is operational, editable, and visible in AP dashboards.                            |
|      - documents.is_deleted = FALSE                                                               |
|            |                                                                                      |
|            | User action: Delete requested by AP Lead, Controller, or System Admin                 |
|            v                                                                                      |
|  [Stage 2: SOFT_DELETED]                                                                          |
|      - Physical file remains intact in Supabase Storage.                                          |
|      - documents.is_deleted = TRUE, deleted_at = now(), deleted_by = user.id                      |
|      - Filtered out of standard queries; visible only in Admin Trash / Compliance views.          |
|      - Immutable AuditEvent: action = 'INVOICE_SOFT_DELETED', actor = user.id.                    |
|      - Restorable: System Admin can revert status to ACTIVE.                                      |
|            |                                                                                      |
|            | Time elapsed: Statutory retention policy evaluated                                  |
|            v                                                                                      |
|  [Stage 3: RETENTION_EXPIRED]                                                                     |
|      - Statutory Check: Section 36 of Indian CGST Act 2017 & Section 128 of Companies Act 2013:   |
|        Mandatory retention of 72 months (6 years) from the annual return due date (~7–8 years).    |
|      - Automated check: now() >= invoice_date + statutory_retention_window.                       |
|      - Flagged as legally eligible for physical destruction.                                      |
|            |                                                                                      |
|            | Compliance action: Explicit dual-authorized destruction request                      |
|            v                                                                                      |
|  [Stage 4: AUTHORISED_PURGE]                                                                      |
|      - Authorisation: Dual approval required (SYSTEM_ADMIN + Corporate Compliance Officer).       |
|      - Storage Reclaimed: Physical file deleted via DELETE /storage/v1/object/invoices/{key}.     |
|      - Database Tombstone: documents row retains id, invoice_id, sha256_hash, purged_at, purged_by;|
|        storage_key set to NULL.                                                                   |
|      - Immutable AuditEvent: action = 'INVOICE_PERMANENTLY_PURGED', details = {sha256, reason}.   |
|      - Backup Reconciliation: Backup archives record purge; object purged from future sync cycles.|
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

---

## 6. FastAPI Hosting: Google Cloud Run (Mumbai `asia-south1`) Evaluation

### 6.1 Preferred Hosting Candidate Architecture

* **Classification:** `[APPROVED PREFERRED CANDIDATE; PROVISIONING NOT AUTHORISED]`
* **Candidate Platform:** Google Cloud Run located in Mumbai (`asia-south1`).
* **Justification:** Cloud Run provides native serverless container execution, automated TLS certificate provisioning, zero container orchestration overhead, and native integration with Google Cloud Pub/Sub.

```
+---------------------------------------------------------------------------------------------------+
| GOOGLE CLOUD RUN (MUMBAI) WORKLOAD & DATA FLOW TOPOLOGY                                           |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [Google Cloud Pub/Sub]                                                                           |
|       |                                                                                           |
|       | Native HTTPS Push with Google OIDC Bearer Token                                           |
|       v                                                                                           |
|  [Cloud Run Service: ap-command-center (asia-south1 Mumbai)]                                      |
|       - Authenticates OIDC token via Google JWKS.                                                 |
|       - Ingestion logic runs within container request context.                                    |
|       - Long-running extractions (>15m) offloaded to Cloud Run Jobs without Celery.               |
|            |                                                                                      |
|            | Egress via Public Internet over TLS 1.3 (Inter-Cloud: GCP Mumbai -> AWS Mumbai)       |
|            v                                                                                      |
|  [Supabase Free Project (AWS Mumbai ap-south-1)]                                                  |
|       - PostgreSQL DB (port 5432 / 6543 pooler)                                                   |
|       - Supabase Storage REST API                                                                 |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

### 6.2 Workload-Based Cost Modeling & Billing Realities

* **Mandatory Billing Prerequisite:** Deploying a container to Google Cloud Run requires linking an **active Google Cloud Billing Account**, even if total consumption remains within the free tier.
* **Monthly Free-Tier Allowances (Google Cloud per billing account):**
  - First 2,000,000 requests per month free.
  - 360,000 vCPU-seconds per month free.
  - 180,000 GiB-seconds per month free.
  - 1 GB egress to worldwide destinations per month.
* **Workload-Based Cost Projections:**

```
+---------------------------------------------------------------------------------------------------+
| WORKLOAD COST PROJECTIONS (CLOUD RUN MUMBAI)                                                      |
+---------------------------------------------------------------------------------------------------+
| Parameter / Scenario         | Scenario A: Pilot / Free Scale | Scenario B: Continuous Pilot      |
|                              | (Scale-to-Zero, 1,000 inv/mo)  | (min-instances: 1, 24/7/365)      |
+------------------------------+--------------------------------+-----------------------------------+
| Container Configuration      | 1 vCPU, 512 MB RAM             | 1 vCPU, 512 MB RAM                |
| Total Monthly Invocations    | ~10,000 requests/month         | ~10,000 requests/month            |
| Invocations Cost             | $0.00 (within 2M free quota)   | $0.00 (within 2M free quota)      |
| Execution Compute Time       | ~5,000 vCPU-sec (within free)  | 2,592,000 vCPU-sec (Continuous)   |
| Compute Billable Cost        | $0.00                          | $53.57 / month                    |
| Network Egress to Supabase   | ~1.5 GB egress (0.5 GB billable| ~1.5 GB egress                    |
|                              | at $0.12/GB in asia-south1)    |                                   |
| Egress Billable Cost         | $0.06 / month                  | $0.06 / month                     |
| Secret Manager (Secrets)     | 3 secrets, <10k access ($0.00) | 3 secrets, <10k access ($0.00)    |
+------------------------------+--------------------------------+-----------------------------------+
| ESTIMATED MONTHLY GCP BILL   | ~$0.06 / month                 | ~$53.63 / month                   |
+------------------------------+--------------------------------+-----------------------------------+
```

* **Cold-Start Tradeoff:** Scenario A achieves near-zero operating costs by scaling to zero when idle, accepting a **1 to 3-second cold start** on initial webhook arrival. Scenario B eliminates cold starts but incurs ~$53/month in continuous compute charges.

---

## 7. Explicit Free-Tier Production Reliability Limitations

* **Classification:** `[BINDING OPERATIONAL DISCLOSURE]`
* Before authorizing pilot deployment, the operator explicitly acknowledges the following production limitations inherent to the Supabase Free plan:

1. **No High Availability or Uptime SLA:** Supabase provides zero contractual uptime guarantees for Free tier projects.
2. **Inactivity Interruption:** Projects with zero traffic for 7 days sleep automatically. Waking the service requires manual intervention or an API call that takes several minutes.
3. **No Automated Recovery:** Database disaster recovery depends entirely on the operator's scheduled manual CLI dumps. If a hardware failure occurs on Supabase Free before an operator export, all data since the previous export is unrecoverable.
4. **Storage Volume Ceiling:** 1 GB total storage accommodates approximately 500 to 1,000 invoice PDFs. Reaching 1 GB hard-blocks all further invoice uploads until upgraded or purged.
5. **Certification Boundary:** **The application cannot be certified for enterprise production use on the Free tier.** Upgrading to Supabase Pro ($25/mo) is mandatory prior to onboarding commercial paying customers.

---

## 8. Frozen Decision Register & Implementation Blockers

### 8.1 Frozen Subsystem Status Summary

* **Platform Provider:** Supabase (Free Tier Baseline) — **`APPROVED`**
* **AWS Services:** All S3, KMS, IAM, ECS components — **`REMOVED`**
* **Application Database:** Supabase PostgreSQL with Table RLS — **`APPROVED`**
* **Employee Authentication:** Supabase Auth (Google SSO, Invitation-Only) — **`APPROVED`**
* **Storage Backend:** Supabase Storage Private Buckets — **`APPROVED`**
* **Storage Backup:** Operator REST/S3 Export Script with Manifest — **`APPROVED`**
* **Deletion Lifecycle:** 4-Stage Soft-Delete & Statutory Retention — **`APPROVED`**
* **Hosting Platform:** Google Cloud Run (Mumbai `asia-south1`) — **`APPROVED PREFERRED`**
* **Gmail Ingestion:** Gmail API + Cloud Pub/Sub Push Webhook — **`APPROVED`**

### 8.2 Final Implementation Blockers (Awaiting Explicit Authorisation)

The architecture assessment is now **FROZEN**. Implementation remains strictly **`[BLOCKED]`** until the operator explicitly authorizes execution:

1. **Google Cloud Test Project Provisioning `[BLOCKED]`:**
   - Creation of the dedicated Google Cloud test project in `asia-south1` (Mumbai).
   - Setup of Pub/Sub topic `projects/<id>/topics/gmail-notifications` with publisher permissions for `gmail-api-push@system.gserviceaccount.com`.
   - Creation of OAuth 2.0 Web Client credentials for Gmail mailbox testing.
2. **Supabase Free Project Creation `[BLOCKED]`:**
   - Operator creation of the free Supabase project in AWS `ap-south-1` (Mumbai).
   - Generation of application database credentials (`ap_app_user`) and provision of the connection URI.
3. **Formal Implementation Authorisation `[BLOCKED]`:**
   - Awaiting explicit user prompt authorising code modifications, schema migrations, and adapter implementation.

---

*End of Architecture Assessment & Frozen Decision Register ARCH-SEC-VAL-2026-P2.6-FROZEN.*
