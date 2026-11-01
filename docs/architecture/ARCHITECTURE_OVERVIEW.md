# AP Command Center — Architecture Overview

> **Version:** 2.0 (Zero-Cost Hosting Architecture)  
> **Status:** Deployment Blueprint & Local Test Verified (`[CONFIGURATION REQUIRED]` for Live Cloud Services)  
> **Target Baseline Cost:** **\$0.00 / month** (Within provider free tier quotas; subject to provider terms)

---

## 1. Executive Architecture Summary

The **Autonomous AP Command Center** is a multi-tenant Accounts Payable processing and compliance platform designed to ingest vendor invoices from email or direct upload, validate document integrity, extract accounting metadata, match against ERP purchase orders, and enforce strict dual-control separation of duties for payment authorization.

To support rapid development, security evaluation, and controlled customer pilots with **zero mandatory recurring cloud costs**, the architecture is intentionally streamlined to run on free-tier managed services without sacrificing enterprise-grade security controls.

> [!IMPORTANT]
> **Blueprint vs. Live Deployment Notice:**
> `render.yaml` provides an infrastructure-as-code *deployment blueprint*. The application codebase and its 190 automated unit and integration tests run entirely offline/locally with in-memory SQLite and mocks. Provisioning live instances on Render, Supabase, and Google Cloud Console is an operator action marked `[CONFIGURATION REQUIRED]`.
>
> **Google Cloud Console Prerequisite:**
> Although all Google Cloud *runtime infrastructure* (Cloud Run, Pub/Sub, Cloud Scheduler, Cloud Build, Secret Manager) has been completely removed to eliminate cloud hosting costs, the **Google Cloud Console is still required** to create the OAuth 2.0 Client ID / Secret and enable the read-only Gmail API for mailbox synchronization.

```
                      +------------------------------------------+
                      |         User Browser / AP Team           |
                      |  (React 18 SPA + Vite + TailwindCSS)    |
                      +--------------------+---------------------+
                                           | HTTPS (Port 443)
                                           v
+-----------------------------------------------------------------------------------------+
| RENDER FREE WEB SERVICE [BLUEPRINT] (Single Docker Container — 512 MB RAM / 0.1 vCPU)    |
|                                                                                         |
|   +---------------------------------------+   +-------------------------------------+   |
|   |         Static Asset Serving          |   |          FastAPI Backend            |   |
|   |  - Compiled React bundle (/app/dist)  |   |  - Port 8080 (Non-root appuser)     |   |
|   |  - Cache-busting hashed assets        |   |  - Uvicorn 2 workers + proxy hdrs   |   |
|   |  - SPA index.html fallback router     |   |  - Pydantic v2 input validation     |   |
|   +---------------------------------------+   +------------------+------------------+   |
|                                                                  |                      |
|                                                                  |                      |
+------------------------------------------------------------------+----------------------+
          |                               |                        |
          | Asymmetric JWKS               | SSL Pooler (Port 6543) | Privileged REST API
          v                               v                        v
+---------------------+         +--------------------+   +-----------------------+
|    SUPABASE AUTH    |         |    SUPABASE FREE   |   |   SUPABASE STORAGE    |
| - OIDC Identity     |         |     POSTGRESQL     |   | - Private 'invoices'  |
| - Asymmetric JWKS   |         | - AWS region (free)|   | - Path tenant prefix  |
| - RS256/ES256 keys  |         | - PgBouncer pooler |   | - Presigned URLs 300s |
| - Tenant user sync  |         | - Port 6543 app    |   | - 50 MB upload limit  |
| - Self-service MFA  |         | - Port 5432 mig/bk |   | - SHA-256 integrity   |
+---------------------+         +--------------------+   +-----------------------+
                                          ^
                                          | HTTPS / OAuth 2.0 (gmail.readonly)
                                          v
                                +--------------------+
                                |  GOOGLE GMAIL API  |
                                | - 3-legged OAuth   |
                                | - History API sync |
                                | - Zero Pub/Sub req |
                                | - Free 1B units/d  |
                                +--------------------+
```
                                | - History API sync |
                                | - Zero Pub/Sub req |
                                | - Free 1B units/d  |
                                +--------------------+
```

---

## 2. Core System Invariants

The platform maintains non-negotiable architectural and compliance invariants across all deployment tiers:

1. **Zero Fictional Data `[IMPLEMENTED]`:** The system never mocks success, fabricates invoice counts, or synthesizes fake metrics. Dashboards compute live zero metrics until genuine documents are processed.
2. **Strict Multi-Tenant Isolation `[IMPLEMENTED]`:** Every database query, storage path, audit event, and OAuth connection is scoped to an immutable `org_id`. Cross-tenant data leakage is structurally impossible.
3. **Dual-Control Payment Authorization `[IMPLEMENTED]`:** High-value invoices require explicit dual-control sign-off. The creator/ingestor cannot approve their own invoice, preventing fraud.
4. **Append-Only Immutable Audit Trail `[IMPLEMENTED]`:** All system actions generate `audit_events` rows with database-enforced row immutability (triggers reject `UPDATE` and `DELETE`).
5. **Least-Privilege Cryptography `[IMPLEMENTED]`:** Mailbox refresh tokens are encrypted at rest using server-side Fernet (AES-128-CBC + HMAC-SHA256). Storage uses private buckets with short-lived presigned URLs (300 seconds).

---

## 3. Component Breakdown

### 3.1. Frontend Web Client
* **Technology:** React 18, TypeScript, Vite, TailwindCSS, Lucide React icons.
* **Architecture:** Single-Page Application (SPA) compiled into static HTML/JS/CSS assets.
* **Hosting Model:** Embedded into the Docker container and served directly by the FastAPI backend under `/` and `/assets/*` with SPA client-side fallback routing (`index.html`).
* **Authentication:** Supabase Client SDK stores session tokens locally in browser storage and passes asymmetric JWTs in `Authorization: Bearer <token>` headers to backend endpoints.

### 3.2. Backend Application Server
* **Technology:** Python 3.12-slim, FastAPI, Starlette, Uvicorn, Pydantic v2, SQLAlchemy 2.0.
* **Execution:** Non-root execution (`appuser:appgroup`, UID 1000) inside a multi-stage Docker container on Render Free Web Service.
* **Endpoints:**
  * `/api/v1/health`, `/api/v1/liveness`: Container health and readiness probes.
  * `/api/v1/invoices`: Invoice lifecycle, parsing, three-way matching, and dual-control approval.
  * `/api/v1/documents`: PDF file upload, SHA-256 hash validation, signed URL generation, and two-tier soft-deletion.
  * `/api/v1/integrations/gmail`: Mailbox OAuth 2.0 management, incremental History API synchronization, and connection health inspection.
  * `/api/v1/audit`: Immutable compliance ledger and event inspection.
  * `/api/v1/users`: Tenant role-based access control (RBAC) and membership provisioning.

### 3.3. Database Layer (Supabase Free PostgreSQL) `[LIVE VERIFIED]`
* **Engine:** PostgreSQL 17 hosted on Supabase Free Tier (Project ID: `qxrrbyjczuqkgnexwqyh`, AWS `ap-south-1`).
* **Migration Status:** Revisions `001` through `007` applied to head (`007_stage52_pubsub_recovery`).
* **Row-Level Security (RLS):** Enabled and forced across all 28 tenant tables (`FORCE ROW LEVEL SECURITY`). Unprivileged role `ap_app_user` verified with zero superuser and zero bypass privileges.
* **Audit Immutability:** Enforced at database engine level via `trg_audit_events_immutable` preventing `UPDATE` and `DELETE`.
* **Connection Routing:**
  * **Runtime Application Traffic:** Port `6543` via Supabase PgBouncer Transaction Pooler with `DATABASE_URL`. Handles high concurrency and ephemeral connections safely without exhausting PostgreSQL connection limits.
  * **Schema Migrations (Alembic):** Port `5432` direct PostgreSQL connection with `MIGRATION_DATABASE_URL` (bypasses transaction pooler to allow transactional DDL statements, table locks, and Alembic versioning).
  * **Operator Backups:** Port `5432` direct PostgreSQL connection with `BACKUP_DATABASE_URL` for `pg_dump` execution.

### 3.4. Invoice Document Storage (Supabase Storage) `[LIVE VERIFIED]`
* **Bucket:** Private bucket `invoices` created and live-verified (public access disabled, `public: false`).
* **Constraints:** Maximum upload file size 50 MB (`52428800` bytes), restricted strictly to MIME type `application/pdf`.
* **Storage Path Hierarchy:** `org_{org_id}/invoices/{doc_id}/{filename}` ensuring strict tenant isolation.
* **Access Model:** Frontend and client browsers never access Supabase Storage directly with service keys. Download and preview access requires the backend to issue a time-limited presigned URL (TTL 300 seconds) after verifying tenant membership and RBAC permissions.
* **API Key Format:** Supports Supabase secret format (`sb_secret_...` via `apikey` header only) without sending invalid `Authorization: Bearer` headers. End-to-end save, retrieve, presigned URL generation, and delete operations live-verified.

### 3.5. Identity & Access Management (Supabase Auth) `[LIVE VERIFIED]`
* **Authentication Flow:** User authenticates via Supabase Auth (Email Magic Link, Google OAuth, or Enterprise SAML).
* **Token Verification:** FastAPI validates incoming JWTs against the Supabase JWKS endpoint (`/.well-known/jwks.json`).
* **Cryptographic Algorithms:** Asymmetric ES256 key (`kid: fac91365-77bc-4df4-b0cd-fafa4188f4d0`, `P-256`) live-verified with in-memory caching and automatic refresh on unknown `kid`. Legacy HS256 shared secrets are retained strictly as an opt-in fallback for backwards compatibility.
* **Tenant Synchronization:** On first authenticated request, the backend reconciles the `auth.users` UUID with `public.users` and establishes tenant role assignments (`SYSTEM_ADMIN`, `CONTROLLER`, `AP_LEAD`, `CLERK`, `READ_ONLY`).

### 3.6. External Email Integration (Direct Gmail API) `[CONFIGURATION REQUIRED]`
* **OAuth Scope:** Minimal privileged read-only scope: `https://www.googleapis.com/auth/gmail.readonly`. Configured via Google Cloud Console OAuth consent screen.
* **Token Security:** OAuth `refresh_token` is encrypted using symmetric Fernet encryption before database storage; zero plaintext credentials exist in PostgreSQL.
* **Initial Sync vs. Incremental Sync:**
  * **Initial Mailbox Connection:** On initial OAuth authorization, `account.last_history_id` is intentionally left `None`. The very first synchronization executes a full mailbox reconciliation query (`has:attachment filename:pdf`) to discover and ingest all pre-existing vendor invoice emails. Upon completing this initial scan, the watermark is seeded with Gmail's current profile `historyId`.
  * **Subsequent Ingestion:** All subsequent synchronizations use the incremental Gmail History API (`users.history.list`), fetching only new message additions since the watermark.
* **History Expiration (HTTP 404) Recovery:** If Gmail purges history records (typical after ~30 days) and returns HTTP 404 `HistoryExpiredError`, the system automatically recovers via full query reconciliation fallback, ingests any missing messages idempotently, and updates `account.last_history_id` with the fresh profile `historyId`.
* **Interrupted Sync Safety:** If a sync deadline or timeout is reached, all documents ingested up to that moment are safely committed, but the history watermark is NOT advanced, ensuring safe redelivery on the next sync attempt.
* **Concurrency Protection:** Both initial and incremental sync operations run under a per-mailbox database lease lock (`mailbox_sync_lease`), returning HTTP 409 Conflict if two sync requests arrive concurrently.

---

## 4. Continuous vs. On-Demand Execution Model

| Dimension | Cloud Run + Pub/Sub (Enterprise) | Render Free + Direct Gmail (Zero-Cost Pilot) | Status |
| :--- | :--- | :--- | :--- |
| **Hosting Model** | Scale-to-zero serverless container | Free Web Service container | `[IMPLEMENTED]` |
| **Idle Behavior** | Container sleeps after request ends | Container sleeps after 15 minutes of inactivity | `[VERIFIED LIMITATION]` |
| **Wake-up Latency** | 3 to 6 seconds cold start | ~50 seconds cold start on incoming request | `[VERIFIED LIMITATION]` |
| **Email Ingestion** | Real-time push via Google Pub/Sub Webhook | On-Demand sync ("Sync Mailbox Now" button) + Catch-up sync on app load | `[IMPLEMENTED]` |
| **Background Cron** | Cloud Scheduler invokes HTTP endpoints | Operator-triggered or client-presence polling | `[IMPLEMENTED]` |
| **Monthly Cost** | \$25 – \$65 / month | **\$0.00 / month** | `[IMPLEMENTED]` |
| **Cloud Dependencies** | Google Cloud Run, Pub/Sub, Scheduler, Secrets | Render Free + Supabase Free + Google OAuth Console | `[IMPLEMENTED]` |

### Why On-Demand Sync is Appropriate for Free Hosting
Render Free Web Services spin down after 15 minutes of user inactivity. In this state, the container does not consume CPU, and no daemon background worker can run continuously.

Rather than introducing fragile third-party cron pingers or paying for a dedicated background worker container, the platform aligns with human AP workflows:
1. **Application Load Catch-Up:** When an AP clerk or controller logs into the dashboard, the application checks the mailbox watermark and fetches new invoices.
2. **Explicit "Sync Mailbox Now" Action:** Users click the Sync button in the Inbox or Connections Hub to trigger immediate incremental ingestion.
3. **Active-Session Polling (Optional):** While an AP operator keeps the browser tab open, the frontend can poll `POST /api/v1/integrations/gmail/sync` every 5 to 15 minutes.
4. **Zero Missed Invoices:** Because the Gmail History API tracks message additions persistently on Google's servers, no invoices are ever lost while the system is asleep. When woken up, the system processes all accumulated messages monotonically.

---

## 5. Architectural Component Ledger

| Component | Technical Implementation | License / Plan | Status Tag |
| :--- | :--- | :--- | :--- |
| **Web Service Runtime** | Render Free Web Service (Docker Blueprint) | Free (\$0/mo baseline) | `[CONFIGURATION REQUIRED]` |
| **Relational Database** | Supabase PostgreSQL 15 (AWS chosen region) | Free (\$0/mo baseline) | `[CONFIGURATION REQUIRED]` |
| **Database Pooler** | PgBouncer Transaction Pooler (Port 6543) | Free Included | `[IMPLEMENTED]` |
| **Document Storage** | Supabase Storage (Private bucket `invoices`) | Free (1 GB baseline) | `[CONFIGURATION REQUIRED]` |
| **User Authentication** | Supabase Auth (Asymmetric JWKS verification) | Free (50k MAU) | `[CONFIGURATION REQUIRED]` |
| **Email Ingestion Client** | Google Cloud Console OAuth 2.0 Credentials | Free (Google API) | `[CONFIGURATION REQUIRED]` |
| **Email Ingestion Engine** | Direct Gmail History API (`users.history.list`)| Python HTTPX / Core | `[IMPLEMENTED]` |
| **Token Encryption** | Fernet Symmetric Encryption (AES-128-CBC) | Python Standard | `[IMPLEMENTED]` |
| **Database Migrations** | Alembic (Port 5432 Direct Session) | Open Source | `[IMPLEMENTED]` |
| **Operator Backups** | Encrypted CLI dump (`backup.py` / `restore.py`) | Operator Local | `[IMPLEMENTED]` |
| **Scheduled Background Workers** | Cloud Scheduler / Celery daemon | None (Excluded) | `[VERIFIED LIMITATION]` |
| **Google Cloud Pub/Sub Push** | Pub/Sub push subscription webhook | None (Excluded) | `[VERIFIED LIMITATION]` |
