# AP Command Center — Alternatives & Trade-Off Analysis

> **Document Status:** Active Standard  
> **Evaluation Horizon:** Pilot (\$0.00/mo) to Enterprise (\$500+/mo)

---

## 1. Hosting Platform Evaluation Matrix

| Feature / Metric | Render Free (Selected) | Google Cloud Run | Railway Starter | AWS App Runner | Fly.io Free |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Monthly Cost** | **\$0.00 / month** | \$5 – \$35 / mo (min. GCP) | \$5.00 / month min. | \$15 – \$40 / month | \$0 – \$5 / month |
| **Free Tier Model** | Perpetual Free Tier | 2M req/mo (GCP billing req) | \$5 trial / no perpetual | No free tier | 3 shared-cpu VMs (CC req) |
| **Memory Ceiling** | 512 MB RAM | 512 MB – 32 GB | 512 MB – 8 GB | 1 GB – 4 GB | 256 MB per VM |
| **CPU Allocation** | 0.1 vCPU (shared) | 1 to 4 vCPUs | Shared / Dedicated | 1 to 2 vCPUs | 1 shared vCPU |
| **Idle Behavior** | **Spins down after 15m** | Scales to zero instances | Sleeps after inactivity | Stays active (billed min) | Suspends container |
| **Cold Start Latency** | **~50 seconds** | 2 to 5 seconds | 2 to 4 seconds | N/A (always on) | 2 to 4 seconds |
| **Inbound Bandwidth** | 100 GB / month free | Free | Included | AWS data transfer rates | 100 GB / month |
| **Custom Domain & SSL**| Free automatic SSL | Free automatic SSL | Free automatic SSL | Free automatic SSL | Free automatic SSL |
| **Docker Support** | Multi-stage Dockerfile | Container images | Dockerfile / Nixpacks | Container images | Dockerfile |
| **GCP / AWS Lock-In** | **Zero** | High (IAM, Secret Mgr) | Zero | High (AWS IAM, VPC) | Minimal |
| **Suitability Verdict** | **Ideal for \$0 pilot** `[IMPLEMENTED]` | Excellent for paid prod | Good, but paid only | Too expensive for pilot | High billing surprise risk |

---

## 2. Relational Database Evaluation Matrix

| Feature / Metric | Supabase Free (Selected) | Neon Serverless Postgres | Self-Hosted Postgres (VPS) | AWS RDS PostgreSQL |
| :--- | :--- | :--- | :--- | :--- |
| **Monthly Cost** | **\$0.00 / month** | \$0.00 / month | \$4 – \$10 / mo (Hetzner/DO)| \$15 – \$35 / month |
| **Included Storage** | 500 MB PostgreSQL 15 | 500 MB data | VPS disk size (20–40 GB) | 20 GB (12 mo free only) |
| **Connection Pooling** | **PgBouncer (Port 6543)** | Built-in PgBouncer | Manual PgBouncer setup | AWS RDS Proxy (\$15+/mo) |
| **Direct Connections** | Port 5432 (DDL / Migrations)| Port 5432 session pool | Port 5432 | Port 5432 |
| **Inactivity Pausing** | **Pauses after 7 days** | Scales to zero compute | Never pauses | Never pauses |
| **Unpause Latency** | Manual click or API wake | Automatic (1–3 seconds) | Zero | Zero |
| **Ecosystem Synergy** | **Native Auth + Storage** | Database only | Database only | Database only |
| **Backup Features** | Operator CLI dump | Point-in-time branch | Manual cron pg_dump | Automated snapshots |
| **Suitability Verdict** | **Selected: Complete stack** | Excellent standalone DB | Unnecessary maintenance | Too expensive / expires |

---

## 3. Invoice Document Storage Evaluation Matrix

| Feature / Metric | Supabase Storage (Selected)| AWS S3 | Cloudflare R2 | Local Render Filesystem |
| :--- | :--- | :--- | :--- | :--- |
| **Monthly Cost** | **\$0.00 / month** | \$0.023/GB + req fees | \$0.00 (10 GB free) | **\$0.00 (UNUSABLE)** |
| **Free Storage Limit** | **1 GB free** | 5 GB (12 mo free only) | 10 GB perpetual | Ephemeral only |
| **Max Single File** | **50 MB** | 5 TB | 5 TB | Memory-limited |
| **Presigned URLs** | **Native signed URLs** | S3 presigned URLs | S3-compatible URLs | None |
| **Path Isolation** | `org_{org_id}/invoices/...` | Key prefix isolation | Key prefix isolation | Ephemeral directory |
| **Data Durability** | AWS S3 backed (Supabase) | 99.999999999% (11 9s) | 99.999999999% (11 9s) | **0% on restart/sleep** |
| **Egress Fees** | 2 GB / month free | \$0.09 / GB | **\$0.00 (Zero egress)** | None |
| **Setup Overhead** | **Zero (same API key)** | AWS IAM, bucket policy | Cloudflare API tokens | Zero |
| **Suitability Verdict** | **Selected: Unified stack** | Enterprise standard | Good secondary choice | **Catastrophic data loss** |

---

## 4. Email Ingestion Architecture Evaluation Matrix

| Feature / Metric | Direct Gmail API (Selected) | Cloud Pub/Sub Push Webhook | IMAP / POP3 Polling | Inbound Email SaaS (SendGrid) |
| :--- | :--- | :--- | :--- | :--- |
| **Monthly Cost** | **\$0.00 / month** (Free API) | \$0.00 – \$10 / mo (GCP) | \$0.00 / month | \$15 – \$90 / month |
| **Latency** | On-Demand (User / Load) | Real-time (1–5 seconds) | 1 to 5 minutes | Real-time (webhook) |
| **Infrastructure Req.**| **Google Cloud Console OAuth Client Only** (Runtime GCP removed) | GCP Pub/Sub, Service Acct | Mailbox host server | Domain MX DNS records |
| **API Quotas** | 1B units/day (Free) | GCP messaging quotas | Server connection limits | Monthly email quotas |
| **Incremental Sync** | **Gmail History API** | History ID in Pub/Sub | UID SEARCH UNSEEN | Webhook payload |
| **Scope Sensitivity** | `gmail.readonly` | `gmail.readonly` + PubSub | Full account access | Third-party MX redirect |
| **Render Sleep Compat.**| **100% Compatible** | **Incompatible (50s wake)** | Needs background process | Needs always-on webhook |
| **Suitability Verdict** | **Selected: Zero-cost fit** | Best for paid always-on | Outdated & insecure | Expensive & domain privacy |

---

## 5. Background Work & Processing Model Matrix

| Feature / Metric | Synchronous On-Demand (Selected) | Celery + Upstash Redis | Cloud Tasks + Cloud Run | Google Cloud Scheduler |
| :--- | :--- | :--- | :--- | :--- |
| **Monthly Cost** | **\$0.00 / month** | \$0.00 (Upstash free limits)| \$5 – \$25 / month | \$0.10/job/mo (after 3 free)|
| **Process Overhead** | **Zero extra processes** | 1 web + 1 worker + Redis | Serverless task router | External cron pinger |
| **Concurrency Lock** | **Database processing lease** | Redis distributed lock | Task queue deduplication | Idempotent HTTP handler |
| **Render Sleep Compat.**| **100% Compatible** | **Worker sleeps on Render**| Needs always-on target | Fails if cold start > 30s |
| **Failure Recovery** | **On-demand replay / catch-up**| Dead letter queue | Automatic retry backoff | Retried next schedule |
| **User Transparency** | Progress spinner in UI | Optimistic UI / WebSockets | Asynchronous status polling| Background update |
| **Suitability Verdict** | **Selected for Zero-Cost** | Overkill for pilot | Cloud locked | Fragile with cold starts |

---

## 6. Cost vs. Capability Spectrum (Evolution Roadmap)

```
+------------------------------------------------------------------------------------------------------+
|                                   THE AP COMMAND CENTER MATURITY SPECTRUM                            |
+------------------------------------------------------------------------------------------------------+
|  TIER 1: ZERO-COST PILOT   |  TIER 2: LOW-COST PROD     |  TIER 3: GROWING SCALE  |  TIER 4: ENTERPRISE    |
|  $0.00 / month             |  $15 - $32 / month         |  $50 - $125 / month     |  $350 - $750+ / month  |
+----------------------------+----------------------------+-------------------------+------------------------+
| - Render Free Web Service  | - Render Starter ($7/mo)   | - Render Standard ($25) | - Cloud Run / ECS Fargate
| - Supabase Free Postgres   | - Supabase Micro ($10/mo)  | - Supabase Pro ($25/mo) | - Dedicated Aurora RDS
| - Supabase Free Storage    | - 0 cold starts            | - Automated Daily PITR  | - AWS S3 Multi-region
| - Direct Gmail History API | - No 7-day DB pause        | - Celery + Redis worker | - Pub/Sub Real-Time Push
| - On-Demand Mailbox Sync   | - Active session polling   | - 8 GB DB / 100 GB files| - CASA Tier 2 Certified
| - Operator Encrypted Dump  | - Operator Encrypted Dump  | - 100k Invoices / month | - 99.99% Multi-AZ SLA
+----------------------------+----------------------------+-------------------------+------------------------+
```

### Trade-Off Summary
1. **At \$0.00/month (Current Architecture):** The system trades latency (50-second cold start after 15 min idle) and real-time push (replaced by on-demand and catch-up sync) for **zero mandatory cloud expenditure**. All business rules, dual-control approvals, tenant isolation, and cryptographic security remain 100% intact.
2. **At \$15–32/month (Tier 2):** Upgrading Render to Starter (\$7/mo) immediately eliminates cold starts. Adding Supabase Micro (\$10/mo) eliminates the 7-day inactivity pause. The code requires zero architectural changes.
3. **At \$50–125/month (Tier 3):** Upgrading Supabase to Pro (\$25/mo) unlocks automated daily backups, 8 GB database storage, and 100 GB invoice storage.
4. **At \$350+/month (Tier 4):** Transition to Google Cloud Run, Cloud Pub/Sub, and CASA Tier 2 certified security for high-volume enterprise compliance.
