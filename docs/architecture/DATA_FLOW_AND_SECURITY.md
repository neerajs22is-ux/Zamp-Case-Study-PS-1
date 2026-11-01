# AP Command Center — Data Flow & Security Controls

> **Document Status:** Active Standard  
> **Security Model:** Zero-Trust Multi-Tenant Architecture  
> **Cryptographic Framework:** Asymmetric JWKS (RS256/ES256) + Authenticated Fernet (AES-128-CBC + HMAC-SHA256)

---

## 1. End-to-End System Data Flows

### 1.1. Gmail OAuth 2.0 Authorization & Token Encryption Flow

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Tenant Administrator
    participant UI as React Frontend
    participant API as FastAPI Backend
    participant Google as Google OAuth 2.0
    participant DB as Supabase PostgreSQL

    Admin->>UI: Click "Connect Mailbox" in Connections Hub
    UI->>API: GET /api/v1/integrations/gmail/authorize
    API->>API: Generate 10-min HMAC State Nonce (org_id, user_id, nonce)
    API->>DB: Store Nonce in oauth_state_nonces (is_consumed=false)
    API-->>UI: Return Google Auth URL (gmail.readonly scope)
    UI->>Google: Redirect Admin to Google Consent Screen
    Admin->>Google: Grant Consent for ap-inbox@company.com
    Google-->>UI: Redirect to /api/v1/integrations/gmail/callback?code=CODE&state=STATE
    UI->>API: GET /api/v1/integrations/gmail/callback
    API->>DB: Atomic Validation: State Signature & Single-Use Nonce
    API->>Google: POST https://oauth2.googleapis.com/token (code exchange)
    Google-->>API: Return access_token & refresh_token
    API->>Google: GET /gmail/v1/users/me/profile
    Google-->>API: Return emailAddress
    API->>API: Fernet Encrypt refresh_token (AES-128-CBC + HMAC-SHA256)
    API->>DB: Upsert gmail_accounts (encrypted_token, last_history_id=None)
    Note over API, DB: Watermark left None so first sync executes full query across existing emails
    API->>DB: Insert AuditEvent (GMAIL_MAILBOX_CONNECTED)
    API-->>UI: Redirect to /connections?gmail=connected
```

---

### 1.2. Email Invoice Ingestion Flow (On-Demand / Incremental History API with Fallback Recovery)

> **Initial Sync vs Incremental:** On initial connection (`last_history_id=None`), step 6 executes full query reconciliation (`has:attachment filename:pdf`), ingesting all pre-existing invoice emails and then seeding the watermark. On subsequent synchronizations, step 6 uses `users.history.list`. If Gmail returns HTTP 404 (`HistoryExpiredError`), the system automatically executes full reconciliation fallback and refreshes the watermark. Both flows run under the per-mailbox lease lock.

```mermaid
sequenceDiagram
    autonumber
    actor User as AP Clerk / Operator
    participant UI as React Frontend
    participant API as FastAPI Backend
    participant DB as Supabase PostgreSQL
    participant Google as Gmail History API
    participant Store as Supabase Storage

    User->>UI: Click "Sync Mailbox Now" (or App Load Catch-Up)
    UI->>API: POST /api/v1/integrations/gmail/sync
    API->>DB: SELECT gmail_accounts WHERE org_id = tenant_id
    API->>DB: Acquire per-mailbox DB Lock (mailbox_sync_lease)
    API->>API: Decrypt stored refresh_token using ENCRYPTION_KEY
    API->>Google: POST https://oauth2.googleapis.com/token (refresh access token)
    Google-->>API: Return short-lived access_token
    API->>Google: GET /gmail/v1/users/me/history?startHistoryId=WATERMARK
    Google-->>API: Return new message IDs & latest historyId
    
    loop For Each New Message with PDF Attachment
        API->>Google: GET /gmail/v1/users/me/messages/{id}
        Google-->>API: Return MIME structure
        API->>Google: GET /gmail/v1/users/me/messages/{id}/attachments/{att_id}
        Google-->>API: Return raw attachment bytes
        API->>API: Validate PDF Header (%PDF-) & Compute SHA-256
        API->>DB: Check (org_id, sha256_hash) uniqueness
        alt Document Already Exists
            API->>API: Increment duplicates_skipped counter
        else Unique Document
            API->>Store: Upload raw bytes to org_{org_id}/invoices/{doc_id}/{filename}
            Store-->>API: Storage Confirmation (HTTP 200)
            API->>DB: INSERT INTO documents (id, sha256, storage_key, status='READY')
            API->>DB: INSERT INTO invoices (id, document_id, stage='PARSING')
            API->>DB: INSERT INTO audit_events (INVOICE_INGESTED)
        end
    end

    API->>DB: Monotonically Advance account.last_history_id
    API->>DB: Release per-mailbox DB Lock
    API-->>UI: Return JSON { status: SUCCESS, ingested_count: X, duplicates_skipped: Y }
    UI->>UI: Refresh Inbox Ledger table
```

---

### 1.3. Direct Document Upload & SHA-256 Deduplication Flow

```mermaid
sequenceDiagram
    autonumber
    actor Clerk as AP Clerk
    participant UI as React Frontend
    participant API as FastAPI Backend
    participant DB as Supabase PostgreSQL
    participant Store as Supabase Storage

    Clerk->>UI: Select vendor_invoice.pdf & click Upload
    UI->>UI: Client Validation: .pdf extension & size <= 50 MB
    UI->>API: POST /api/v1/documents/upload (multipart/form-data)
    API->>API: Server Validation: Verify %PDF- magic bytes & size <= 50 MB
    API->>API: Compute cryptographic SHA-256 digest
    API->>DB: SELECT id FROM documents WHERE org_id=org AND sha256_hash=hash
    alt Hash Matches Existing Document (Duplicate)
        API-->>UI: HTTP 409 Conflict { status: DUPLICATE_DETECTED, existing_doc_id }
        UI->>Clerk: Display "Duplicate Detected: Document already ingested"
    else Hash is Unique
        API->>Store: Upload stream to org_{org}/invoices/{doc_id}/vendor_invoice.pdf
        Store-->>API: Storage 200 OK
        API->>DB: INSERT INTO documents (id, org_id, sha256_hash, storage_key, status='READY')
        API->>DB: INSERT INTO invoices (id, org_id, document_id, stage='PARSING')
        API->>DB: INSERT INTO audit_events (DOCUMENT_UPLOADED)
        API-->>UI: HTTP 201 Created { document_id, invoice_id, sha256 }
        UI->>Clerk: Display "Upload Complete: Document Ready"
    end
```

---

### 1.4. Invoice Review, Three-Way Matching & Dual-Control Approval Flow

```mermaid
sequenceDiagram
    autonumber
    actor Lead as AP Lead (Ingestor)
    actor Controller as Financial Controller
    participant API as FastAPI Backend
    participant DB as Supabase PostgreSQL

    Lead->>API: POST /api/v1/invoices/{id}/match
    API->>DB: Perform 3-Way Match (Invoice Lines vs PO Lines vs Goods Receipt)
    API->>DB: Calculate variance; determine policy approval threshold
    API->>DB: UPDATE invoices SET stage='MATCHED', decision='NEEDS_REVIEW'
    API-->>Lead: Return Match Breakdown & Line Variance

    Note over Lead, Controller: Policy Rule: Creator cannot approve their own high-value invoice.
    Lead->>API: POST /api/v1/invoices/{id}/approve (Self-Approval Attempt)
    API->>DB: Check invoice.created_by == current_user.id
    alt Creator Tries to Approve High-Value Invoice
        API-->>Lead: HTTP 403 Forbidden { detail: "Dual control violation: Creator cannot self-approve." }
    end

    Controller->>API: POST /api/v1/invoices/{id}/approve (Second Control Actor)
    API->>DB: Verify Controller role & distinct actor_id
    API->>DB: UPDATE invoices SET stage='APPROVED', approved_by=Controller.id
    API->>DB: INSERT INTO audit_events (INVOICE_APPROVED, actor_role='CONTROLLER')
    API-->>Controller: HTTP 200 OK { status: "APPROVED" }
```

---

### 1.5. Authentication & Authorization Flow (Asymmetric JWKS)

```mermaid
sequenceDiagram
    autonumber
    actor User as User Browser
    participant Auth as Supabase Auth Service
    participant API as FastAPI Backend
    participant JWKS as Supabase JWKS Endpoint (/.well-known/jwks.json)
    participant DB as Supabase PostgreSQL

    User->>Auth: Authenticate (Email Magic Link / Google SSO)
    Auth-->>User: Issue asymmetric JWT (signed with RS256/ES256 private key)
    User->>API: GET /api/v1/invoices (Authorization: Bearer <jwt>)
    API->>API: Inspect JWT header for 'kid' and 'alg'
    alt Public Key Cached in Memory
        API->>API: Retrieve cached public key
    else Key Not in Cache (or Expired)
        API->>JWKS: Fetch latest public keys
        JWKS-->>API: Return JSON Web Key Set
        API->>API: Cache public keys with TTL
    end
    API->>API: Verify cryptographic signature, iss, aud, and exp
    API->>DB: Reconcile JWT sub (UUID) with public.users & role_assignments
    API->>API: Verify UserRole satisfies required endpoint permission
    API->>DB: Execute query filtered strictly by user.org_id
    DB-->>API: Return tenant data
    API-->>User: Return HTTP 200 JSON Response
```

---

### 1.6. Operator Backup & Restore Flow

```mermaid
sequenceDiagram
    autonumber
    actor Operator as System Operator Workstation
    participant CLI as backup.py / restore.py
    participant DB as Supabase PostgreSQL (Port 5432)
    participant Store as Supabase Storage API

    Operator->>CLI: python backend/scripts/backup.py --all
    CLI->>DB: Connect to Port 5432 (BACKUP_DATABASE_URL) via pg_dump
    DB-->>CLI: Stream PostgreSQL relational schema & data (pg_dump format)
    CLI->>Store: List and download all files for tenant buckets
    Store-->>CLI: Stream invoice PDF binaries
    CLI->>CLI: Assemble tar archive (database.sql + storage_files/)
    CLI->>CLI: Fernet Encrypt archive using BACKUP_ENCRYPTION_KEY
    CLI-->>Operator: Output ap_backup_YYYYMMDD_HHMMSS.enc (Encrypted Archive)

    Note over Operator: Archive can be safely stored on external operator drives.

    Operator->>CLI: python backend/scripts/restore.py --archive ap_backup_...enc
    CLI->>CLI: Decrypt archive using BACKUP_ENCRYPTION_KEY
    CLI->>DB: Execute psql to restore schema, tables, and data to target database
    CLI->>Store: Upload files to target Supabase Storage bucket
    CLI->>DB: Verify row counts, foreign key integrity, and tenant isolation
    CLI-->>Operator: Output Restore Verification Report (PASS/FAIL)
```

---

## 2. Security Controls & Defensive Invariants Inventory

### 2.1. Encryption Controls

| Layer | Implementation | Specification | Status |
| :--- | :--- | :--- | :--- |
| **In-Transit Encryption** | TLS 1.3 / HTTPS | All external communication with Render, Supabase, and Google is strictly encrypted over TLS 1.3. Plain HTTP connections are automatically redirected to HTTPS. | `[IMPLEMENTED]` |
| **At-Rest Database Encryption** | Supabase Transparent Data Encryption (TDE)| Underlying AWS storage volumes utilized by Supabase are encrypted at rest with AES-256. | `[IMPLEMENTED]` |
| **At-Rest Credential Encryption**| Server-Side Fernet Cipher | Gmail OAuth `refresh_token`s are encrypted using Fernet (AES-128-CBC + HMAC-SHA256 authenticated encryption) prior to SQL insertion. Decryption occurs only in volatile memory during active synchronization. | `[IMPLEMENTED]` |
| **At-Rest Backup Encryption** | Fernet Archive Encryption | Database dumps and invoice binaries are packed into tarballs and encrypted with AES-128-CBC before writing to disk. | `[IMPLEMENTED]` |

### 2.2. Authentication & Identity Controls

| Mechanism | Implementation | Security Benefit | Status |
| :--- | :--- | :--- | :--- |
| **Asymmetric JWKS Verification** | RS256 / ES256 | Backend validates signatures using public keys fetched from Supabase JWKS. No shared signing secret is stored in application environment variables. | `[IMPLEMENTED]` |
| **Fail-Closed Verification** | Cryptographic Signature Check | Malformed, expired, tampered, or unsigned tokens are immediately rejected with HTTP 401 Unauthorized. | `[IMPLEMENTED]` |
| **Dynamic Key Rotation** | In-Memory JWKS Cache | Public keys are cached in memory; encountering an unknown `kid` triggers a safe key refresh from Supabase without restarting the application. | `[IMPLEMENTED]` |
| **Multi-Factor Authentication** | Supabase Auth MFA | End users can enroll in TOTP (Authenticator App) directly through Supabase Auth without backend code changes. | `[IMPLEMENTED]` |

### 2.3. Authorization & Tenant Isolation Controls

| Mechanism | Implementation | Enforcement Point | Status |
| :--- | :--- | :--- | :--- |
| **Strict Multi-Tenant Scoping** | Mandatory `org_id` on all entities | Every database query and storage path includes `org_id`. The application context extracts `org_id` from validated user claims; users cannot supply an arbitrary `org_id`. | `[IMPLEMENTED]` |
| **Role-Based Access Control (RBAC)**| 5-Tier Hierarchical Roles | Roles: `SYSTEM_ADMIN`, `CONTROLLER`, `AP_LEAD`, `CLERK`, `READ_ONLY`. Endpoints enforce role guards using FastAPI dependency injection (`require_role`). | `[IMPLEMENTED]` |
| **Dual-Control Separation of Duties**| Anti-Self-Approval Check | Users who upload or ingest an invoice are prohibited from approving that same invoice if it exceeds the low-value policy limit. Approval requires an independent controller. | `[IMPLEMENTED]` |
| **Row-Level Security (RLS)** | PostgreSQL RLS Policies | Supabase tables maintain RLS policies ensuring that even direct database access is constrained to the authenticated tenant. | `[IMPLEMENTED]` |

### 2.4. Storage & File Security Controls

| Mechanism | Implementation | Security Benefit | Status |
| :--- | :--- | :--- | :--- |
| **Private Buckets Only** | Supabase Storage `invoices` | Public read access is completely disabled. Direct HTTP requests without authentication return HTTP 403 Forbidden. | `[IMPLEMENTED]` |
| **Short-Lived Presigned URLs** | TTL = 300 seconds (5 minutes) | Documents are accessed via temporary signed URLs generated on-demand by authorized users. URLs expire after 5 minutes, preventing link leakage. | `[IMPLEMENTED]` |
| **File Format & Header Validation**| Magic byte check (`%PDF-`) | Prevents malicious executable uploads disguised as PDF files. Uploads must strictly start with PDF magic bytes. | `[IMPLEMENTED]` |
| **File Size Ceilings** | Client & Server Limit &le; 50 MB | Rejects oversized files before processing, preventing Denial-of-Service (DoS) memory exhaustion on free hosting instances. | `[IMPLEMENTED]` |
| **SHA-256 Deduplication** | Cryptographic hash unique index | Unique constraint on `(org_id, sha256_hash)` blocks duplicate invoice processing and prevents storage exhaustion. | `[IMPLEMENTED]` |

### 2.5. Audit Trail & Immutability Controls

| Mechanism | Implementation | Compliance Value | Status |
| :--- | :--- | :--- | :--- |
| **Append-Only Ledger** | `audit_events` table | All state changes (ingestion, approval, rejection, soft-delete) generate an audit log entry with actor ID, role, action, and timestamp. | `[IMPLEMENTED]` |
| **Database-Enforced Immutability**| PostgreSQL triggers | Database triggers intercept and raise exceptions on any `UPDATE` or `DELETE` statement targeting `audit_events`. Even application administrators cannot modify audit records. | `[IMPLEMENTED]` |
| **Two-Tier Soft-Delete Lifecycle**| Soft-delete with storage preservation| Deleting an invoice marks the database record as deleted (`is_deleted=True`), preserving the original file in Supabase Storage. Permanent file purge requires explicit admin privileges. | `[IMPLEMENTED]` |

### 2.6. Operational Secret Hygiene

| Rule | Enforcement Mechanism | Status |
| :--- | :--- | :--- |
| **Zero Plaintext Secrets in Database** | Fernet encryption on all refresh tokens; zero unencrypted API keys stored. | `[IMPLEMENTED]` |
| **Redacted Logging** | `Settings.redacted_dict()` masks passwords in connection URLs across logs and diagnostics. | `[IMPLEMENTED]` |
| **Zero Secrets Committed to Git** | `.gitignore` covers `.env`, `*.enc`, `*.key`, `backups/`, and service account keys. | `[IMPLEMENTED]` |
| **Separated Connection Strings** | `DATABASE_URL` (Port 6543 pooler), `MIGRATION_DATABASE_URL` (Port 5432 direct), `BACKUP_DATABASE_URL` (Port 5432 direct). | `[IMPLEMENTED]` |
