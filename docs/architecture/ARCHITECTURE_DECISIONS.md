# AP Command Center — Architecture Decision Records (ADRs)

> **Document Status:** Active Standard  
> **Architecture Pivot:** Zero-Cost Hosting & Direct Gmail Integration  
> **Target Cost Baseline:** **\$0.00 / month** (Within provider free tier quotas; operator setup required)

---

## Index of Architecture Decision Records

1. [ADR-001: Render Free Web Service over Cloud Run, AWS, or Railway](#adr-001-render-free-web-service-over-cloud-run-aws-or-railway) `[IMPLEMENTED]` (Blueprint) / `[CONFIGURATION REQUIRED]` (Live Service)
2. [ADR-002: Supabase Free PostgreSQL over Self-Hosted Database](#adr-002-supabase-free-postgresql-over-self-hosted-database) `[LIVE VERIFIED]` (PostgreSQL 17, AWS ap-south-1)
3. [ADR-003: Supabase Storage over AWS S3 or Cloudflare R2](#adr-003-supabase-storage-over-aws-s3-or-cloudflare-r2) `[LIVE VERIFIED]` (Private Bucket 'invoices')
4. [ADR-004: Direct Gmail API (OAuth 2.0) over Pub/Sub Push Webhooks](#adr-004-direct-gmail-api-oauth-20-over-pubsub-push-webhooks) `[IMPLEMENTED]` (Engine) / `[CONFIGURATION REQUIRED]` (Google Cloud Console OAuth)
5. [ADR-005: Synchronous On-Demand Ingestion over Async Background Workers](#adr-005-synchronous-on-demand-ingestion-over-async-background-workers) `[IMPLEMENTED]`
6. [ADR-006: Asymmetric JWKS JWT Verification over Static Symmetric Secrets](#adr-006-asymmetric-jwks-jwt-verification-over-static-symmetric-secrets) `[LIVE VERIFIED]` (ES256 P-256)
7. [ADR-007: Fernet Symmetric Encryption over Dedicated Cloud KMS](#adr-007-fernet-symmetric-encryption-over-dedicated-cloud-kms) `[IMPLEMENTED]`
8. [ADR-008: SHA-256 Content Hashing for Deduplication over Message-ID-Only](#adr-008-sha-256-content-hashing-for-deduplication-over-message-id-only) `[IMPLEMENTED]`
9. [ADR-009: Unified Multi-Stage Docker Container over Separate Frontend/Backend Services](#adr-009-unified-multi-stage-docker-container-over-separate-frontendbackend-services) `[IMPLEMENTED]`
10. [ADR-010: Operator-Managed Encrypted Backups over Paid Automated Backup Add-ons](#adr-010-operator-managed-encrypted-backups-over-paid-automated-backup-add-ons) `[IMPLEMENTED]`

---

### ADR-001: Render Free Web Service over Cloud Run, AWS, or Railway
* **Status:** `[IMPLEMENTED]` (Container & Blueprint) / `[CONFIGURATION REQUIRED]` (Live Provisioning)
* **Context:** The application requires a container hosting environment for a multi-stage Docker image (FastAPI backend + React SPA frontend). The initial environment aims for \$0.00/month baseline within provider free quotas for development and customer pilot evaluation.
* **Decision:** Deploy the application to **Render Free Web Service** using `render.yaml` blueprint configuration. Provisioning the live service on Render is an operator responsibility.
* **Rationale:**
  * Render provides a genuine free web service tier with 512 MB RAM, 0.1 vCPU, automatic SSL certificate provisioning, and HTTP/2 ingress without requiring credit card pre-authorization or monthly minimum spend.
  * Google Cloud Run, while cost-effective at small scale, has minimum billable unit nuances (Artifact Registry storage costs, Secret Manager access costs, Cloud Build pipeline costs, egress network billing) that make guaranteed \$0.00/month difficult to guarantee without strict budget caps that shut down services.
  * Railway discontinued its perpetual free tier in favor of a \$5/month trial or paid usage plans. AWS App Runner has no perpetual free tier. Fly.io requires credit card verification and charges for IPv4 addresses.
* **Alternatives Considered:**
  * *Google Cloud Run:* Highly capable, but introduces GCP IAM, Secret Manager, Cloud Build, and Pub/Sub dependencies.
  * *Railway:* Excellent developer experience, but requires \$5/month minimum.
  * *Fly.io:* Capable, but strict limits on free persistent IPs and sudden credit card billing risk.
* **Trade-offs:** Render Free spins down after 15 minutes of inactivity and takes ~50 seconds to cold start on the next incoming HTTP request. Free instances share CPU and have 512 MB memory ceiling.
* **Consequences:** Cold starts affect the first user request after idle periods. Scheduled background workers cannot run continuously in the web service while asleep.
* **Reconsideration Triggers:**
  * When pilot users require instant sub-second response times without the 50-second cold start (triggering an upgrade to Render Starter at \$7/month).
  * When memory consumption during simultaneous PDF parsing exceeds 450 MB.

---

### ADR-002: Supabase Free PostgreSQL over Self-Hosted Database
* **Status:** `[LIVE VERIFIED]` (PostgreSQL 17, Revisions 001-007, RLS Forced, Project qxrrbyjczuqkgnexwqyh)
* **Context:** The AP Command Center requires a relational database supporting ACID transactions, JSONB document fields, row-level security (RLS), and connection pooling.
* **Decision:** Use **Supabase Free Tier PostgreSQL** (in operator-selected AWS region) as the central relational database.
* **Rationale:**
  * Provides a fully managed PostgreSQL 15+ database with 500 MB storage and 2 dedicated connection modes: PgBouncer transaction pooler (port 6543) for stateless application requests, and direct connection (port 5432) for Alembic migrations and backups.
  * Zero infrastructure management overhead: no VPS maintenance, Linux patching, disk resizing, or PostgreSQL tuning required.
  * Colocated with Supabase Auth and Supabase Storage on the same managed project boundary.
* **Alternatives Considered:**
  * *Self-hosted PostgreSQL on a \$4-5/month VPS (Hetzner / DigitalOcean):* Violates the zero-cost requirement and creates an unmanaged maintenance burden (patching, backups, firewall).
  * *Neon Free:* Excellent serverless Postgres, but lacks the unified Auth and S3-compatible Storage integration provided by Supabase.
  * *AWS RDS Free Tier:* Free for 12 months only (not perpetual), and incurs storage/snapshot charges if misconfigured.
* **Trade-offs:** Supabase Free projects pause after 7 consecutive days of zero database activity. Restoring from pause requires a manual dashboard click or an API wake-up call. Free tier limits disk to 500 MB.
* **Consequences:** Production environments must establish an active usage cadence or an operator unpause runbook. Connection strings must explicitly route application traffic through port 6543 to avoid connection pool exhaustion.
* **Reconsideration Triggers:**
  * Total database size exceeds 400 MB (80% of free quota).
  * Active tenant count exceeds 10, necessitating dedicated database compute without 7-day pause risk (triggering Supabase Pro at \$25/month).

---

### ADR-003: Supabase Storage over AWS S3 or Cloudflare R2
* **Status:** `[LIVE VERIFIED]` (Private Bucket 'invoices' created, 50MB PDF upload/get/delete verified)
* **Context:** Ingested vendor invoices (PDF files) must be securely stored in private object storage, isolated per tenant, and accessible only via time-limited presigned URLs.
* **Decision:** Use **Supabase Storage** (private bucket `invoices`) accessed through the backend via privileged service role credentials.
* **Rationale:**
  * Included in the Supabase Free tier at \$0.00/month with 1 GB storage and 50 MB max single file upload limit.
  * Unifies authentication, relational metadata, and binary file storage under a single project boundary and API key architecture.
  * Eliminates AWS account creation, AWS IAM policy configuration, S3 bucket encryption setup, and AWS billing credentials.
* **Alternatives Considered:**
  * *AWS S3:* Standard enterprise choice, but requires AWS account setup, KMS keys, IAM policies, and potential micro-charges for PUT/GET requests and egress bandwidth.
  * *Cloudflare R2:* Zero egress fees, but introduces an additional cloud provider account, separate S3-compatible credentials, and additional setup friction.
  * *Local Filesystem in Render Container:* Catastrophic failure mode: Render web services use an ephemeral filesystem that is completely erased on every deployment, restart, or cold sleep.
* **Trade-offs:** Storage is capped at 1 GB on the free tier (approximately 2,000–5,000 scanned PDF invoices). Single file size is capped at 50 MB.
* **Consequences:** Backend must enforce strict file size checks before uploading (`file.size <= 50MB`). Operator must track storage volume in the Connections Hub.
* **Reconsideration Triggers:**
  * Tenant cumulative invoice storage reaches 800 MB (80% of 1 GB).
  * Invoices regularly exceed 50 MB (e.g. multi-hundred-page consolidated billing packets).

---

### ADR-004: Direct Gmail API (OAuth 2.0) over Pub/Sub Push Webhooks
* **Status:** `[IMPLEMENTED]` (Direct API Engine) / `[CONFIGURATION REQUIRED]` (Google Cloud Console OAuth Setup)
* **Context:** The system must ingest vendor invoices received via email. Previously, Phase B Stage 5 implemented Google Cloud Pub/Sub push webhooks requiring Google Cloud runtime infrastructure.
* **Decision:** Replace Google Cloud Pub/Sub push infrastructure with **Direct Gmail API integration** using incremental History API synchronization (`users.history.list`) triggered on-demand or during active user presence.
* **Rationale:**
  * Eliminates Google Cloud runtime hosting and messaging infrastructure: no Cloud Pub/Sub topics, no push subscriptions, no Cloud Run OIDC invoker service accounts, no Cloud Scheduler jobs, and no Cloud Build pipelines.
  * **Google Cloud Console is still required** to create the OAuth 2.0 Client ID / Secret and enable the read-only Gmail API for mailbox synchronization.
  * Gmail API is completely free under standard Google Workspace and consumer quotas (250 quota units/second, 1 billion quota units/day). Standard API calls consume 5 units for `messages.get` and 2 units for `history.list`.
  * **Initial Sync vs Incremental Sync:** On initial OAuth authorization, `account.last_history_id` is left `None`. The very first synchronization performs full query reconciliation (`has:attachment filename:pdf`) to discover and ingest pre-existing invoices. Subsequent synchronizations use incremental History API (`users.history.list`), fetching only new message additions.
  * **History Expiration (HTTP 404) Recovery:** If Gmail returns HTTP 404 `HistoryExpiredError`, the system automatically recovers via full query reconciliation fallback, ingests any missing messages idempotently, and updates `account.last_history_id` with the fresh profile `historyId`.
  * The Gmail History API maintains persistent message logs on Google's servers. By persisting `account.last_history_id`, the application can retrieve all new messages since the last synchronization, even if the application was asleep for days.
* **Alternatives Considered:**
  * *Google Cloud Pub/Sub Push:* Real-time ingestion within seconds of email receipt, but requires active GCP project, Pub/Sub topic setup, service accounts, and an always-available webhook endpoint (incompatible with Render's 50s cold start).
  * *IMAP/POP3 Polling:* Legacy protocol requiring plain application passwords or fragile OAuth2 SASL mechanisms; higher security risk and lacks granular scopes.
  * *Email Ingestion Webhook (SendGrid / Mailgun / Postmark Inbound Parse):* Requires paid domain MX record redirection, exposes email parsing to external SaaS, and violates zero-cost constraint.
* **Trade-offs:** Email ingestion is not instantaneous. Invoices are ingested when an operator clicks "Sync Mailbox Now", when an operator opens the application, or via optional browser session polling.
* **Consequences:** The application must not claim unattended 24/7 background ingestion while asleep. Documentation and UI must clearly indicate on-demand synchronization.
* **Reconsideration Triggers:**
  * When customer workflows require guaranteed sub-minute invoice ingestion from receipt to inbox without human presence.
  * When company moves to a paid hosting tier that can host an always-on background worker.

---

### ADR-005: Synchronous On-Demand Ingestion over Async Background Workers
* **Status:** `[IMPLEMENTED]`
* **Context:** Email processing involves fetching messages, downloading PDF attachments, computing SHA-256 hashes, uploading to storage, and running invoice data extraction.
* **Decision:** Execute ingestion **synchronously within the request cycle** under a per-mailbox processing lease (`mailbox_sync_lease`), with safe timeout deadlines and on-demand recovery.
* **Rationale:**
  * Dedicated asynchronous worker frameworks (Celery, ARQ, Dramatiq) require a persistent broker (Redis, RabbitMQ) and a continuously running worker daemon. On free hosting tiers, running a separate worker service either doubles hosting requirements or requires a paid Redis instance.
  * Render Free Web Service only keeps the web container running while HTTP requests are active or for 15 minutes thereafter. A standalone background queue process would sleep or be terminated.
  * Ingestion workloads during development and pilot phases average 1 to 10 invoices per sync batch. Synchronous execution with per-mailbox locking takes 2 to 8 seconds, comfortably within browser and HTTP client timeouts.
* **Alternatives Considered:**
  * *Celery + Upstash Redis Free:* Upstash provides a free Redis tier (10,000 commands/day), but running Celery workers requires an always-on process not supported on Render Free without running it inside the web service.
  * *FastAPI BackgroundTasks:* Executes tasks after response return, but Render can terminate or freeze container execution immediately after response if the idle timer expires.
  * *Google Cloud Tasks:* Requires GCP infrastructure and paid execution beyond free credits.
* **Trade-offs:** If a mailbox has 50 new invoices with large attachments, the sync request may take 30–60 seconds. The frontend must display a spinner and progress indicator.
* **Consequences:** The sync endpoint limits batch size to `max_messages=10` (default) with a maximum of 50. Internal processing enforces a deadline to prevent gateway 504 timeouts.
* **Reconsideration Triggers:**
  * Sync batches routinely exceed 20 invoices, causing sync requests to approach HTTP gateway timeout limits (60 seconds).
  * Background OCR and AI extraction tasks exceed 15 seconds per document.

---

### ADR-006: Asymmetric JWKS JWT Verification over Static Symmetric Secrets
* **Status:** `[LIVE VERIFIED]` (Supabase ES256 P-256 Public Keys fetched and cached)
* **Context:** The backend must authenticate API requests using JWT tokens issued by Supabase Auth.
* **Decision:** Implement **asymmetric JWT verification using Supabase JWKS endpoint** (`/.well-known/jwks.json`), supporting RS256 and ES256 algorithms with in-memory key caching and dynamic key rotation.
* **Rationale:**
  * Modern Supabase projects use asymmetric signing keys (RS256 or ES256) where the private key is held exclusively by Supabase Auth, and public keys are published via JWKS.
  * Eliminates the requirement to provision or manage a static `SUPABASE_JWT_SECRET` in application environment variables or Secret Manager.
  * Matches Supabase's current and future security architecture.
  * Retains legacy HS256 verification strictly as an opt-in fallback when `SUPABASE_JWT_SECRET` is explicitly configured.
* **Alternatives Considered:**
  * *Symmetric HS256 with Shared Secret:* Legacy approach requiring the operator to manually extract the JWT secret from Supabase project settings. Incompatible with modern Supabase instances using asymmetric keys.
  * *Calling Supabase `/auth/v1/user` on every request:* Introduces a 100–250ms network round-trip overhead on every single API request, exhausting network limits and degrading performance.
* **Trade-offs:** Initial request requires fetching public keys from JWKS URL (mitigated by in-memory caching with TTL and stale-key re-fetch).
* **Consequences:** Application startup verifies that `SUPABASE_JWKS_URL` or `SUPABASE_URL` is configured. Token verification fails closed if the signature cannot be validated.
* **Reconsideration Triggers:**
  * Supabase changes their JWKS specification or OIDC discovery format.

---

### ADR-007: Fernet Symmetric Encryption over Dedicated Cloud KMS
* **Status:** `[IMPLEMENTED]`
* **Context:** Gmail OAuth `refresh_token`s and sensitive tenant credentials must be encrypted before persistence in PostgreSQL to prevent exposure in case of database leakage.
* **Decision:** Use **Fernet symmetric encryption** (AES-128-CBC + HMAC-SHA256 authenticated encryption) with an application-level key (`ENCRYPTION_KEY`).
* **Rationale:**
  * Cloud KMS providers (AWS KMS, Google Cloud KMS, HashiCorp Vault) introduce external cloud dependencies, API latency, credential requirements, and per-key/per-operation billing.
  * Fernet is a robust, battle-tested standard specification (part of Python's `cryptography` library) providing authenticated encryption: any tampering with encrypted ciphertext results in immediate decryption failure.
  * `ENCRYPTION_KEY` is supplied via environment variables in Render, keeping the database completely decoupled from cryptographic keys.
* **Alternatives Considered:**
  * *Google Cloud KMS / AWS KMS:* Enterprise standard, but violates the zero-cost and zero-GCP constraints.
  * *PostgreSQL `pgcrypto` extension:* Stores encryption logic and keys inside the database engine, increasing risk if the database user is compromised.
* **Trade-offs:** Key rotation must be handled by an application-level script rather than an automated cloud KMS lifecycle policy.
* **Consequences:** The operator must securely generate and back up the `ENCRYPTION_KEY`. Loss of `ENCRYPTION_KEY` renders stored mailbox refresh tokens unrecoverable, requiring re-authorization.
* **Reconsideration Triggers:**
  * Compliance mandate (e.g. SOC 2 Type II or PCI-DSS) strictly requiring hardware security module (HSM) key isolation.

---

### ADR-008: SHA-256 Content Hashing for Deduplication over Message-ID-Only
* **Status:** `[IMPLEMENTED]`
* **Context:** Invoices may be forwarded multiple times, sent to multiple mailboxes, or re-uploaded by clerks. The system must prevent duplicate invoice records, duplicate payment approvals, and duplicate storage consumption.
* **Decision:** Implement **cryptographic SHA-256 content hashing** on the exact raw binary payload of every PDF document, enforced by an immutable database unique index on `(org_id, sha256_hash)`.
* **Rationale:**
  * Email headers, subject lines, and Google message IDs are ephemeral and easily duplicated or altered. A vendor may send the exact same invoice under two different email threads.
  * Two different emails containing identical invoice PDFs will be caught by the SHA-256 unique constraint, preventing duplicate approval workflows.
  * Re-uploading an existing invoice returns HTTP 409 Conflict with the existing document ID, preventing wasted storage.
* **Alternatives Considered:**
  * *Deduplication by Gmail Message ID:* Fails when the same invoice is forwarded, re-sent, or uploaded manually.
  * *Deduplication by Invoice Number + Vendor Name:* Fails when OCR extraction hasn't run yet or extracts slightly different text across scans.
* **Trade-offs:** If a vendor re-exports an invoice with identical data but different PDF creation timestamps or metadata, the SHA-256 hash will differ.
* **Consequences:** Content-level deduplication is bulletproof for identical files. Secondary business-level deduplication (Vendor + Invoice Number + Date) is enforced downstream during three-way matching.
* **Reconsideration Triggers:**
  * Requirement for fuzzy document deduplication (e.g., detecting scanned copies of existing electronic invoices).

---

### ADR-009: Unified Multi-Stage Docker Container over Separate Frontend/Backend Services
* **Status:** `[IMPLEMENTED]`
* **Context:** The application consists of a React/TypeScript Single Page Application (SPA) and a FastAPI REST API backend.
* **Decision:** Package both frontend and backend into a **single multi-stage Docker container** where the FastAPI backend serves the compiled static SPA assets under `/` and handles API requests under `/api/v1/*`.
* **Rationale:**
  * Render Free allows only **one free web service** per account. Deploying frontend and backend as separate services would require either a paid plan or two separate hosting accounts.
  * Eliminates Cross-Origin Resource Sharing (CORS) complexity and pre-flight `OPTIONS` request overhead in production, as API and UI share the exact same origin (`https://ap-command-center.onrender.com`).
  * Simplifies deployment and version synchronization: a single git commit deploys matching frontend and backend versions atomically.
* **Alternatives Considered:**
  * *Separate Vercel / Netlify Frontend + Render Backend:* Free, but introduces multi-service orchestration, separate environment management, CORS configuration, and potential version skew between UI and API.
  * *Static Frontend in Cloud Storage / CDN:* Requires separate cloud configuration and DNS routing.
* **Trade-offs:** Docker image build time takes 2–3 minutes due to Node.js build followed by Python pip install (mitigated by Docker layer caching). Container memory includes static file cache in Uvicorn.
* **Consequences:** Backend code includes an SPA fallback router: non-API GET requests serve `frontend/dist/index.html` to allow React client-side routing.
* **Reconsideration Triggers:**
  * Frontend traffic scales significantly, requiring global edge CDN caching and micro-frontend architecture.

---

### ADR-010: Operator-Managed Encrypted Backups over Paid Automated Backup Add-ons
* **Status:** `[IMPLEMENTED]`
* **Context:** The application database and stored invoice files must have a reliable backup and recovery mechanism. Supabase Free does not include point-in-time recovery (PITR) or automated downloadable backup scheduling.
* **Decision:** Provide an **operator-run CLI utility (`backend/scripts/backup.py` and `restore.py`)** that dumps the database, downloads storage files, compresses them into an archive, and encrypts it using Fernet.
* **Rationale:**
  * Zero recurring cost: operates entirely on the operator's local machine or CI/CD runner.
  * Security: backup archives are encrypted before writing to disk using `BACKUP_ENCRYPTION_KEY`, ensuring that even if backup files are stored in external cloud drives (e.g. Google Drive, OneDrive), credentials and invoice PDFs remain protected.
  * Verifiability: restores can be executed and tested locally against a test database to prove restore integrity without paying for enterprise recovery infrastructure.
* **Alternatives Considered:**
  * *Supabase Pro Daily Backups (\$25/month):* Automated and managed, but requires paid plan.
  * *Automated Cloud Run / Cron backup to AWS S3:* Ephemeral container filesystem cannot store backups; sending to S3 requires AWS billing and credentials.
* **Trade-offs:** Requires an operator or scheduled workstation script to run the backup CLI. Backups are not continuous point-in-time recovery.
* **Consequences:** The operator runbook must explicitly document backup execution, verification, and disaster recovery steps.
* **Reconsideration Triggers:**
  * Production data volume or transaction velocity requires automated hourly or continuous replication.
  * Upgrade to Supabase Pro (\$25/month) which includes 7-day automated daily backups.
