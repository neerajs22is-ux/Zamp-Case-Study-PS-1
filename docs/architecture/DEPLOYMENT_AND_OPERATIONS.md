# AP Command Center — Deployment & Operations Runbook

> **Document Status:** Active Standard  
> **Deployment Blueprint:** Render Free Web Service (\$0.00/month target baseline) `[IMPLEMENTED]` (Live Deployment `[CONFIGURATION REQUIRED]`)  
> **Database & Storage Blueprint:** Supabase Free PostgreSQL & Supabase Storage `[LIVE VERIFIED]`  
> **External Integration Blueprint:** Direct Google Gmail API OAuth 2.0 `[IMPLEMENTED]` (Google Cloud Console `[CONFIGURATION REQUIRED]`)

---

## 1. Prerequisites & Required Accounts `[CONFIGURATION REQUIRED]`

Before beginning deployment, ensure you have access to the following accounts (all on free tiers):
1. **GitHub Account:** Repository containing the AP Command Center code.
2. **Render Account (Free):** [render.com](https://render.com) for hosting the web service container.
3. **Supabase Account (Free):** [supabase.com](https://supabase.com) for PostgreSQL, Auth, and Storage.
4. **Google Cloud Console (Free):** [console.cloud.google.com](https://console.cloud.google.com) for creating the OAuth 2.0 Client ID (zero billing required; strictly for OAuth 2.0 and Gmail API activation).
5. **Local Operator Workstation:** Python 3.12+, Git, and `psql` (or Docker).

---

## 2. Step 1: Supabase Project Setup `[LIVE VERIFIED]`

> **Live Status:** Completed and verified for Supabase Project Ref `qxrrbyjczuqkgnexwqyh` (PostgreSQL 17, AWS `ap-south-1`).
> - Direct Port 5432 and Transaction Pooler Port 6543 verified.
> - Private `invoices` bucket created (50 MB limit, `application/pdf` MIME type).
> - Asymmetric ES256 JWKS public key verified.
> - Revisions 001 through 007 applied to head (`007_stage52_pubsub_recovery`).
> - PostgreSQL RLS enabled and forced across all 28 tenant tables.

1. **Active Live Credentials (Configured in Environment):**
   * `SUPABASE_URL`: `https://qxrrbyjczuqkgnexwqyh.supabase.co`
   * `SUPABASE_JWKS_URL`: `https://qxrrbyjczuqkgnexwqyh.supabase.co/auth/v1/.well-known/jwks.json`
   * `SUPABASE_STORAGE_BUCKET`: `invoices` (private)
   * `DATABASE_URL`: Transaction pooler port 6543 (`aws-0-ap-south-1.pooler.supabase.com`)
   * `MIGRATION_DATABASE_URL`: Direct port 5432 (`db.qxrrbyjczuqkgnexwqyh.supabase.co`)

---

## 3. Step 2: Google Cloud Console Setup (Gmail API) `[CONFIGURATION REQUIRED]`

1. **Create Google Cloud Project:**
   * Go to [console.cloud.google.com](https://console.cloud.google.com) and create project `ap-command-center`.
   * No billing account is required.

2. **Enable Gmail API:**
   * Go to **APIs & Services -> Library**.
   * Search for **Gmail API** and click **Enable**.

3. **Configure OAuth Consent Screen:**
   * Go to **APIs & Services -> OAuth consent screen**.
   * User Type: Select **External** (or **Internal** if using Google Workspace).
   * App Name: `AP Command Center`.
   * User support email: Select your admin email.
   * Scopes: Add `https://www.googleapis.com/auth/gmail.readonly`.
   * Test Users: Add the mailbox address that will receive vendor invoices (e.g. `ap-inbox@company.com`).

4. **Create OAuth 2.0 Credentials:**
   * Go to **APIs & Services -> Credentials -> Create Credentials -> OAuth client ID**.
   * Application type: **Web application**.
   * Name: `AP Command Center Web Client`.
   * Authorized Redirect URIs:
     * `https://[YOUR_RENDER_SERVICE_NAME].onrender.com/api/v1/integrations/gmail/callback`
     * (For local testing: `http://localhost:8080/api/v1/integrations/gmail/callback`)
   * Click **Create**. Copy the **Client ID** and **Client Secret**.

---

## 4. Step 3: Database Migration Execution

Database migrations must be applied using port `5432` (direct session connection) because transaction poolers (port 6543) do not support transactional DDL.

Run migrations from your local workstation:
```bash
# 1. Export direct migration URL targeting port 5432
export MIGRATION_DATABASE_URL="postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres?sslmode=require"

# 2. Execute Alembic upgrade to head
python -m alembic upgrade head
```

Verify tables in the Supabase Table Editor:
* `organisations`, `users`, `role_assignments`
* `documents`, `invoices`, `invoice_lines`, `purchase_orders`
* `gmail_accounts`, `oauth_state_nonces`, `audit_events`

---

## 5. Step 4: Render Free Web Service Deployment

1. **Connect Repository to Render:**
   * Log into [dashboard.render.com](https://dashboard.render.com).
   * Click **New + -> Blueprint** (or **New + -> Web Service**).
   * Connect your GitHub repository.
   * If using Blueprint, Render automatically detects `render.yaml`.

2. **Manual Web Service Configuration (Alternative to Blueprint):**
   * **Name:** `ap-command-center`
   * **Language / Runtime:** `Docker`
   * **Region:** Oregon (or closest region)
   * **Branch:** `master`
   * **Instance Type:** `Free`
   * **Health Check Path:** `/api/v1/liveness`

3. **Configure Environment Variables:**
   Set the following variables in the Render Dashboard (Environment tab):

| Variable Name | Required Value / Source |
| :--- | :--- |
| `APP_ENV` | `production` |
| `PORT` | `8080` |
| `BASE_URL` | `https://ap-command-center.onrender.com` |
| `SECRET_KEY` | Generate 32+ random hex characters |
| `ENCRYPTION_KEY` | Generate Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATABASE_URL` | Supabase Port 6543 pooler URL |
| `SUPABASE_URL` | `https://[PROJECT_REF].supabase.co` |
| `SUPABASE_JWKS_URL` | `https://[PROJECT_REF].supabase.co/auth/v1/.well-known/jwks.json` |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` |
| `SUPABASE_SERVICE_ROLE_KEY`| Supabase Secret Service Role Key (`sb_secret_...`) |
| `SUPABASE_ANON_KEY` | Supabase Publishable / Anon Key |
| `GMAIL_CLIENT_ID` | Google OAuth Client ID |
| `GMAIL_CLIENT_SECRET` | Google OAuth Client Secret |
| `GMAIL_TARGET_MAILBOX` | AP Mailbox Email Address (e.g. `ap-inbox@company.com`) |

4. **Deploy Service:**
   * Click **Create Web Service** (or **Apply Blueprint**).
   * Render will pull the repository, build the multi-stage Docker container (React frontend + FastAPI backend), and launch the container on port 8080.
   * Deployment takes ~3 minutes.

---

## 6. Step 5: Post-Deployment Smoke Test & Verification

1. **Liveness & Health Probe Check:**
   ```bash
   curl -f https://ap-command-center.onrender.com/api/v1/liveness
   # Output: {"status":"ALIVE","timestamp":"..."}

   curl -f https://ap-command-center.onrender.com/api/v1/health
   # Output: {"status":"HEALTHY","database":"CONNECTED","storage":"CONFIGURED"}
   ```

2. **Frontend UI Verification:**
   * Open `https://ap-command-center.onrender.com` in your browser.
   * Verify the React SPA loads with the dark-mode AP Command Center interface.
   * Navigate to `/connections` to check the status of all integration pillars.

3. **Gmail Mailbox Connection:**
   * In the **Connections Hub**, click **Connect Mailbox**.
   * Authenticate with the test Google account and grant read-only permissions.
   * Verify you are redirected back to `/connections?gmail=connected`.
   * Verify Gmail status displays **CONNECTED** with `gmail.readonly` scope.

4. **End-to-End Invoice Ingestion Test:**
   * Send an email with a sample PDF invoice attached to `ap-inbox@company.com`.
   * In the AP Command Center Inbox (`/inbox`), click **Sync Mailbox Now**.
   * Verify the sync banner reports: `Synced (History API): 1 ingested, 0 duplicate(s) skipped`.
   * Verify the invoice appears in the Inbox ledger.
   * Click the invoice to inspect extracted lines, matching status, and audit events.

---

## 7. Step 6: Ongoing Operational Procedures

### 7.1. Weekly Operator Backup
Run this script weekly from your workstation:
```bash
export BACKUP_DATABASE_URL="postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres?sslmode=require"
export SUPABASE_URL="https://[PROJECT_REF].supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="[YOUR_SUPABASE_SERVICE_ROLE_KEY]"
export BACKUP_ENCRYPTION_KEY="[YOUR_BACKUP_FERNET_KEY]"

# Run full encrypted backup (database schema, tables, and invoice files)
python backend/scripts/backup.py --all

# Output file: backups/ap_backup_YYYYMMDD_HHMMSS.tar.enc
```
Copy `ap_backup_*.tar.enc` to an encrypted external storage location (e.g., corporate Google Drive or offline drive).

### 7.2. Restoring from Backup
To test or execute a disaster recovery restore:
```bash
python backend/scripts/restore.py --archive backups/ap_backup_20261101_120000.tar.enc --verify-only
```

### 7.3. Handling Render Cold Starts
Render Free containers spin down after 15 minutes of inactivity. When users access the system after an idle period, expect a ~50-second wait on the first request.
* **Operator Tip:** If presenting a demo to stakeholders, open the dashboard URL 2 minutes in advance to wake up the container.

### 7.4. Handling Supabase 7-Day Inactivity Pause
Supabase Free pauses databases that experience zero queries for 7 consecutive days.
* **To Unpause:** Log into [supabase.com/dashboard](https://supabase.com/dashboard), navigate to the paused project, and click **Restore Project**. The database will be back online in ~2 minutes.
* **Prevention:** The weekly backup CLI or regular operator usage automatically prevents the project from pausing.

### 7.5. Reconnecting Gmail When Expired (7-Day Testing Limit)
While the Google Cloud OAuth application is in **Testing** status, refresh tokens expire every 7 days.
* **Symptom:** Syncing returns `AUTH_FAILED` with `invalid_grant`.
* **Fix:** Go to `/connections`, click **Reconnect Mailbox**, and re-approve the test mailbox. Takes 30 seconds.

---

## 8. Troubleshooting Guide: 10 Common Failure Scenarios

### Scenario 1: Render Cold Start Timeout (504 Gateway Timeout)
* **Symptom:** Browser shows HTTP 504 Gateway Timeout on first visit in the morning.
* **Cause:** The Docker container took slightly longer than 50 seconds to initialize and pass the liveness check.
* **Fix:** Refresh the browser. Once initialized, the container remains awake for 15 minutes.

### Scenario 2: Database Connection Refused / Pool Exhausted
* **Symptom:** API logs report `FATAL: remaining connection slots are reserved for non-replication superuser connections`.
* **Cause:** Application traffic was pointed to direct PostgreSQL port `5432` instead of transaction pooler port `6543`.
* **Fix:** Update `DATABASE_URL` in Render environment to use port `6543`.

### Scenario 3: Alembic Migration Fails with "Prepared Transactions / Advisory Locks"
* **Symptom:** `alembic upgrade head` fails with `cannot execute CREATE TABLE in a transaction block`.
* **Cause:** Alembic was pointed to transaction pooler port `6543`, which does not support DDL locks.
* **Fix:** Ensure Alembic uses `MIGRATION_DATABASE_URL` pointing to direct session port `5432`.

### Scenario 4: Upload Fails with HTTP 413 "File Too Large"
* **Symptom:** Invoice upload fails with "File size exceeds 50 MB Supabase Free limit."
* **Cause:** The PDF invoice package exceeds 50 MB.
* **Fix:** Compress the PDF using Ghostscript or split into separate billing attachments.

### Scenario 5: Duplicate Document Detected (HTTP 409 Conflict)
* **Symptom:** Upload returns HTTP 409: "A document with identical SHA-256 hash already exists."
* **Cause:** The vendor or clerk uploaded a file whose content hash is already registered in the tenant.
* **Fix:** System behavior working as designed to prevent duplicate payments. Locate existing document in `/inbox`.

### Scenario 6: Gmail Sync Returns "AUTH_FAILED: invalid_grant"
* **Symptom:** Clicking "Sync Mailbox Now" returns "Gmail access token refresh failed: invalid_grant".
* **Cause:** 7 days elapsed on a Google OAuth app in "Testing" status, or password was changed.
* **Fix:** Re-authorize the mailbox via `/connections`.

### Scenario 7: Storage Upload Fails with HTTP 401/403
* **Symptom:** Document upload returns HTTP 502 with Supabase Storage error.
* **Cause:** `SUPABASE_SERVICE_ROLE_KEY` is missing or invalid, or bucket `invoices` does not exist.
* **Fix:** Verify private bucket `invoices` exists in Supabase Storage and verify service role key in Render.

### Scenario 8: Asymmetric JWT Verification Fails (HTTP 401)
* **Symptom:** All authenticated API calls return HTTP 401 Unauthorized: "Invalid token signature".
* **Cause:** `SUPABASE_JWKS_URL` is pointing to an incorrect project reference or cannot reach Supabase.
* **Fix:** Verify `SUPABASE_JWKS_URL=https://[PROJECT_REF].supabase.co/auth/v1/.well-known/jwks.json`.

### Scenario 9: Dual-Control Approval Blocked (HTTP 403 Forbidden)
* **Symptom:** Approving an invoice returns "Dual control violation: Creator cannot self-approve."
* **Cause:** The current user who created/ingested the invoice is attempting to approve it.
* **Fix:** Log in as an independent user with `CONTROLLER` role to approve high-value invoices.

### Scenario 10: Container Crashes with Exit Code 137 (OOM Killer)
* **Symptom:** Render deployment logs display `Container exited with status 137`.
* **Cause:** 512 MB memory limit exceeded during concurrent batch parsing of large PDF files.
* **Fix:** Lower `max_messages` query parameter on sync calls to `5` or `10`.
