# AP Command Center — Future Upgrade Path & Scaling Roadmap

> **Document Status:** Active Standard  
> **Current Baseline:** Stage 1 Zero-Cost Pilot `[IMPLEMENTED]`  
> **Future Horizon:** Phased Transition from Zero-Cost Pilot (\$0.00/mo) to Enterprise Multi-Region (\$500+/mo) `[PLANNED]`  
> **Principle:** Zero Waste — Every migration preserves existing database schemas, security controls, and business logic.

---

## 1. Evolution Roadmap Across Four Operational Stages

```
STAGE 1: Zero-Cost Pilot ($0.00 / mo)
  ├── Hosting: Render Free Web Service (Docker, 512 MB, 15m idle sleep, ~50s cold start)
  ├── Database: Supabase Free PostgreSQL (500 MB, Port 6543 pooler, 7-day pause risk)
  ├── Storage: Supabase Storage (1 GB private bucket)
  ├── Ingestion: Direct Gmail History API (on-demand sync / catch-up on load)
  └── Backups: Operator-managed encrypted CLI backup (weekly)

              │
              │  Trigger: First paying customer / Daily team usage / Cold start friction
              ▼

STAGE 2: Low-Cost Production ($17 - $25 / mo)
  ├── Hosting: Render Starter Web Service ($7.00 / mo — Always-on, 0 cold starts, 512 MB)
  ├── Database: Supabase Free or Compute Add-on ($10.00 / mo — Zero 7-day inactivity pause)
  ├── Storage: Supabase Storage (1 GB included)
  ├── Ingestion: Direct Gmail API + Frontend browser tab polling (every 5–15 mins)
  └── Backups: Operator-managed encrypted CLI backup (automated via GitHub Actions cron)

              │
              │  Trigger: >100 invoices/day / Storage >800 MB / Requirement for automated PITR
              ▼

STAGE 3: Growing AP Operation ($50 - $110 / mo)
  ├── Hosting: Render Standard ($25.00 / mo — 2 GB RAM, 1 vCPU, auto-scaling up to 3 instances)
  ├── Background: Render Background Worker ($7.00 / mo) + Upstash Redis ($0 - $10 / mo)
  ├── Database: Supabase Pro ($25.00 / mo — 8 GB DB, daily automated backups, 7-day PITR)
  ├── Storage: Supabase Pro Storage (100 GB storage included)
  ├── Ingestion: Asynchronous background polling worker running continuous History API checks
  └── Security: Google Cloud OAuth internal app verification

              │
              │  Trigger: Multi-tenant commercial SaaS / Enterprise SLA / CASA Tier 2 audit
              ▼

STAGE 4: Enterprise Compliance ($350 - $800+ / mo)
  ├── Hosting: Google Cloud Run (Dedicated multi-region, min-instances >= 1, VPC connector)
  ├── Database: Dedicated AWS Aurora PostgreSQL or Supabase Team/Enterprise Plan
  ├── Storage: AWS S3 or Google Cloud Storage with multi-region replication & immutability
  ├── Ingestion: Google Cloud Pub/Sub real-time push webhooks with OIDC verification
  ├── Compliance: Third-party CASA Tier 2 assessment, SOC 2 Type II certified
  └── Availability: 99.99% multi-AZ SLA with sub-minute disaster recovery failover
```

---

## 2. Upgrade Decision Triggers: Exact Metric Thresholds

| Metric | Stage 1 (Current Pilot) | Stage 2 Trigger | Stage 3 Trigger | Stage 4 Trigger |
| :--- | :--- | :--- | :--- | :--- |
| **Monthly Cost** | **\$0.00 / mo** | \$17 – \$25 / mo | \$50 – \$110 / mo | \$350 – \$800+ / mo |
| **Invoices / Month** | 1 to 500 | 500 to 2,500 | 2,500 to 25,000 | 25,000 to 500,000+ |
| **Active Users** | 1 to 5 operators | 5 to 15 operators | 15 to 75 operators | 75+ enterprise users |
| **Database Disk Size**| < 100 MB | 100 MB to 400 MB | 400 MB to 6 GB | > 6 GB |
| **Invoice Storage** | < 250 MB | 250 MB to 800 MB | 800 MB to 80 GB | > 80 GB |
| **Cold Start Tolerance**| ~50s acceptable | **0s required** | **0s required** | **Sub-second SLA** |
| **Sync Latency** | On-demand (seconds) | Active polling (5m) | Background worker (1m) | Real-time Pub/Sub (2s)|
| **Backup Requirement**| Operator manual | Scheduled CI/CD | Automated Daily PITR | Continuous Multi-AZ |

---

## 3. Step-by-Step Transition Guides (Zero Downtime)

### Transition 1: Eliminating Cold Starts (Stage 1 -> Stage 2)
* **Cost Impact:** +\$7.00/month (Render Starter).
* **Execution:**
  1. Go to [dashboard.render.com](https://dashboard.render.com) -> Select `ap-command-center`.
  2. Navigate to **Settings -> Plan**.
  3. Select **Starter (\$7/month)** and click Save.
* **Result:** The web service stays active 24/7/365. Cold starts drop from ~50 seconds to 0 seconds immediately. No code changes required.

---

### Transition 2: Eliminating 7-Day Supabase Pauses (Stage 1 -> Stage 2)
* **Cost Impact:** +\$10.00/month (Supabase Compute Add-on) or upgrade to Supabase Pro.
* **Execution:**
  1. In the Supabase Dashboard, go to **Settings -> Billing & Subscriptions**.
  2. Add a compute add-on or upgrade project tier.
* **Result:** Database never pauses due to inactivity. Transaction pooler connection ceiling increases. No code changes required.

---

### Transition 3: Upgrading Storage & Enabling Automated Backups (Stage 2 -> Stage 3)
* **Cost Impact:** +\$25.00/month (Supabase Pro).
* **Execution:**
  1. Upgrade project to **Supabase Pro Plan (\$25/month)**.
  2. Enable **Point-in-Time Recovery (PITR)** in Database Settings.
  3. Storage limit automatically expands from 1 GB to 100 GB.
  4. Database storage limit automatically expands from 500 MB to 8 GB.
* **Result:** Automatic daily backups with 7-day retention. Large invoice storage scale without risk of HTTP 413 upload rejection.

---

### Transition 4: Introducing Asynchronous Background Workers (Stage 3)
When invoice volumes exceed 50 per hour, background PDF extraction and email polling should be offloaded from the web service request cycle:
1. **Provision Upstash Redis (Free or \$0.20/100k requests):** Provides a lightweight Redis broker.
2. **Deploy Worker Service in Render:**
   * Create a new **Background Worker** service in Render pointing to the same repository.
   * Command: `python -m arq backend.worker.WorkerSettings`
3. **Behavior:** The web service enqueues jobs into Redis; the background worker consumes jobs, downloads attachments, runs OCR extraction, and writes results to PostgreSQL.

---

### Transition 5: Reactivating Real-Time Google Cloud Pub/Sub (Stage 3 -> Stage 4)
The application code already contains full support for Google Cloud Pub/Sub (`process_pubsub_push_notification` in `backend/core/gmail.py` and the push endpoint `/api/v1/integrations/gmail/pubsub/push`).

To switch from On-Demand History API sync to Real-Time Push Ingestion:
1. Enable Pub/Sub API in Google Cloud Console.
2. Create a Pub/Sub topic: `projects/[PROJECT_ID]/topics/gmail-notifications`.
3. Grant publish rights to Gmail service account: `serviceAccount:gmail-api-push@system.gserviceaccount.com`.
4. Create a Push Subscription pointing to:
   `https://[YOUR_SERVICE_URL]/api/v1/integrations/gmail/pubsub/push`
5. Configure Push Subscription with an OIDC Service Account token.
6. In AP Command Center, call `POST /api/v1/integrations/gmail/watch/setup`.
* **Result:** Gmail pushes instant push notifications on every new incoming email. The webhook processes messages in real time with durable deduplication.
