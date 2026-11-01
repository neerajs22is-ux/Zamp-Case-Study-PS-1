# AP Command Center — Free-Tier Limitations & Growth Boundaries

> **Document Status:** Active Standard  
> **Infrastructure Baseline:** Render Free + Supabase Free + Google Cloud OAuth Free  
> **Mandatory Rule:** Truthful disclosure of all operational ceilings and breaking points.

---

## 1. Exhaustive Free-Tier Limits Inventory

### 1.1. Render Free Web Service

| Constraint | Limit Value | Operational Impact | Mitigation / Remedy | Status Tag |
| :--- | :--- | :--- | :--- | :--- |
| **Idle Sleep** | 15 minutes of inactivity | Container spins down to zero. Next request triggers cold start. | Expected for pilot; active tabs keep it alive. | `[VERIFIED LIMITATION]` |
| **Cold Start Latency**| **~50 seconds** | First request after idle experiences 40–55s HTTP connection wait. | Frontend displays loading spinner; upgrade to Starter (\$7/mo). | `[VERIFIED LIMITATION]` |
| **Memory Ceiling** | **512 MB RAM** | Heavy PDF parsing or concurrent uploads can cause Linux OOM kill. | Stream uploads to disk/buffer; process batches of &le; 10 invoices. | `[VERIFIED LIMITATION]` |
| **CPU Allocation** | **0.1 vCPU (shared)** | PDF OCR or cryptographic hashing is slower under high load. | Asynchronous single-document processing. | `[VERIFIED LIMITATION]` |
| **Filesystem Durability**| **100% Ephemeral** | Any file written to local container disk is wiped on sleep/redeploy. | **Strictly prohibited:** All files must go to Supabase Storage. | `[IMPLEMENTED]` |
| **Free Instance Hours**| **750 hours / month** | Exactly enough to run 1 web service continuously for a 31-day month. | Do not add a second free web service under the same account. | `[CONFIGURATION REQUIRED]` |
| **Outbound Bandwidth** | **100 GB / month** | Sufficient for ~100,000 document downloads or API responses. | Use direct signed URLs from Supabase Storage to offload bandwidth. | `[IMPLEMENTED]` |
| **HTTP Request Timeout**| **100 seconds** | Any single HTTP request exceeding 100s is aborted by Render gateway. | Ingestion sync enforces 60s processing deadline per batch. | `[IMPLEMENTED]` |

### 1.2. Supabase Free Tier

| Constraint | Limit Value | Operational Impact | Mitigation / Remedy | Status Tag |
| :--- | :--- | :--- | :--- | :--- |
| **Database Disk Size** | **500 MB** | Exceeding 500 MB causes PostgreSQL to enter read-only mode. | Soft-delete purge routine; compress audit tables. | `[VERIFIED LIMITATION]` |
| **Storage Disk Size** | **1 GB** | Uploads fail with HTTP 413 / storage quota exceeded. | Purge temporary files; upgrade to Supabase Pro (\$25/mo) for 100 GB. | `[VERIFIED LIMITATION]` |
| **Max Single File Upload**| **50 MB** | Supabase Storage rejects uploads larger than 50 MB. | Backend enforces `file.size <= 50MB` before initiating upload. | `[IMPLEMENTED]` |
| **Project Inactivity Pause**| **7 consecutive days** | If 0 DB queries occur in 7 days, project pauses. App throws 500. | Log into dashboard to unpause (takes 2 minutes); or weekly health check. | `[VERIFIED LIMITATION]` |
| **Transaction Pooler Limits**| **15 direct / 200 pooler**| Exhausting pooler connections causes HTTP 500 connection errors. | **Port 6543:** App uses PgBouncer pooler (`DATABASE_URL`). | `[IMPLEMENTED]` |
| **Monthly Active Users**| **50,000 MAU** | Supabase Auth throttles user creation beyond 50k MAU. | Far exceeds requirements for AP finance operations. | `[IMPLEMENTED]` |
| **Automated Backups** | **None** | Free tier does NOT include automated daily backups or PITR. | Operator must run `python backend/scripts/backup.py` weekly. | `[IMPLEMENTED]` |

### 1.3. Google Gmail API & OAuth 2.0 `[CONFIGURATION REQUIRED]`

> **Google Cloud Console Requirement:** While runtime Google Cloud infrastructure (Cloud Run, Pub/Sub, Cloud Scheduler, Secrets) has been completely removed to avoid hosting fees, the **Google Cloud Console is still required** to create the OAuth 2.0 Client ID and Secret and enable the Gmail API.

| Constraint | Limit Value | Operational Impact | Mitigation / Remedy | Status Tag |
| :--- | :--- | :--- | :--- | :--- |
| **Daily Quota Units** | **1,000,000,000 / day** | Quota exhaustion blocks Gmail API calls until midnight Pacific. | Ingestion consumes &le; 100 units/sync; essentially unlimited for AP. | `[IMPLEMENTED]` |
| **Per-Second Rate Limit**| **250 quota units / sec** | Rapid bursts can trigger HTTP 429 Too Many Requests. | Sequential message fetching with exponential backoff. | `[IMPLEMENTED]` |
| **OAuth "Testing" Expiry**| **7 days refresh token** | Google expires refresh tokens after 7 days if OAuth app is in "Testing". | Documented re-auth runbook; or publish app to "Production" (internal). | `[VERIFIED LIMITATION]` |
| **Restricted Scope Audit**| **CASA Tier 2 Audit** | Public Google verification of `gmail.readonly` requires \$15k–\$75k audit. | Kept in "Testing" or "Internal" Google Workspace mode for pilot. | `[VERIFIED LIMITATION]` |
| **History Retention Purge**| **~30 days on Google** | After ~30 days, Gmail purges old history IDs, returning HTTP 404. | App catches `HistoryExpiredError`, runs full reconciliation fallback, and updates watermark. | `[IMPLEMENTED]` |
| **Initial Synchronization**| **Full scan required** | New mailbox connection leaves history ID unseeded (`None`). | First sync scans full query (`has:attachment filename:pdf`) to import existing emails before switching to incremental sync. | `[IMPLEMENTED]` |

---

## 2. "What Breaks First as Usage Grows?" — Ordered Breaking Points

Below is the definitive chronological sequence of infrastructure bottlenecks as invoice processing volume expands:

```
[Level 1: Day 7 Inactivity]
  └── Symptom: Supabase Free project pauses if no testing occurred for 7 days.
  └── Metric: 0 database queries for 168 consecutive hours.
  └── Remedy: Log into Supabase dashboard and click "Restore Project", or run weekly health check.

[Level 2: Day 7 Google Refresh Token Expiration]
  └── Symptom: Sync returns "AUTH_FAILED" with "invalid_grant: Token has expired or been revoked."
  └── Metric: 7 days elapsed since Google OAuth authorization while in Google Cloud "Testing" status.
  └── Remedy: Admin clicks "Re-authorize Mailbox" in Connections Hub (takes 30 seconds).

[Level 3: Render Cold Start Friction]
  └── Symptom: First AP user in the morning experiences a 50-second white screen / loading spinner.
  └── Metric: 15 minutes of inactivity on Render Free Web Service.
  └── Remedy: Upgrade Render service from Free (\$0) to Starter (\$7/month) to enable always-on container.

[Level 4: Memory Ceiling on Large Scanned Invoices]
  └── Symptom: Container crashes with Exit Code 137 (Linux OOM killer) during sync.
  └── Metric: 512 MB RAM exhausted during simultaneous PDF parsing of multi-page scans (>20 MB).
  └── Remedy: Process PDF pages iteratively in generator streams; keep batch size at 5–10 invoices.

[Level 5: Ingestion Gateway Timeout on High-Volume Mailboxes]
  └── Symptom: Frontend displays "504 Gateway Timeout" when clicking "Sync Mailbox Now".
  └── Metric: Mailbox accumulated >50 unread PDF invoices; sync loop exceeds 60s gateway deadline.
  └── Remedy: Sync loop halts safely after 45 seconds, commits ingested invoices, and allows user to click sync again.

[Level 6: Supabase Storage 1 GB Quota Exhaustion]
  └── Symptom: Document uploads fail with HTTP 413 / "storage quota exceeded" error.
  └── Metric: Cumulative stored invoices exceed 1,024 MB (~2,500 to 5,000 PDF invoices).
  └── Remedy: Run operator storage archive CLI to offload older invoices, or upgrade to Supabase Pro (\$25/mo) for 100 GB.

[Level 7: Supabase Database 500 MB Quota Exhaustion]
  └── Symptom: Database enters read-only mode; inserts into `invoices` or `audit_events` fail.
  └── Metric: Database disk space exceeds 500 MB (~50,000 invoice line items + audit logs).
  └── Remedy: Vacuum database tables; archive historical fiscal year data; upgrade to Supabase Pro (\$25/mo) for 8 GB.

[Level 8: Database Connection Pool Exhaustion]
  └── Symptom: Application logs report `FATAL: remaining connection slots are reserved for non-replication superuser connections`.
  └── Metric: Concurrent requests exceed 15 direct connections if misrouted to port 5432.
  └── Remedy: Verify all application connections use `DATABASE_URL` targeting PgBouncer on port 6543 (`pool_size=10`).

[Level 9: Bandwidth Egress Limits on Render Free]
  └── Symptom: Render disables the web service until the end of the calendar month.
  └── Metric: Monthly outbound egress exceeds 100 GB.
  └── Remedy: Verify that invoice PDF viewing uses direct Supabase Storage presigned URLs, bypassing Render egress entirely.

[Level 10: Restricted Scope Security Assessment Requirement]
  └── Symptom: Google OAuth consent screen displays "Unverified App" warning to external users.
  └── Metric: Mailbox integration moves from internal pilot to multi-tenant commercial SaaS.
  └── Remedy: Complete Google Cloud Restricted Scope Verification and third-party CASA Tier 2 security assessment.
```

---

## 3. Preventive Maintenance Runbook for Free Tier

To ensure 100% reliability during development and pilot evaluation:

1. **Keep-Alive Cadence:** Run `curl -f https://ap-command-center.onrender.com/api/v1/health` at least once every 5 days to ensure the Supabase Free database never enters the 7-day inactivity pause state.
2. **Weekly Operator Backup:** Run the operator backup utility every Friday:
   ```bash
   python backend/scripts/backup.py --all
   ```
3. **Storage Health Audit:** Check the Connections Hub `/connections` to inspect current document count and storage consumption against the 1 GB ceiling.
4. **Clean Mailbox Syncs:** Encourage AP operators to use the "Sync Mailbox Now" button at the beginning of each processing batch to keep incremental message deltas small (1–10 invoices).
