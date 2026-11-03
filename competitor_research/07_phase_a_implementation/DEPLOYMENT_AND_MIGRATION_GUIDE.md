# Phase A Deployment & Migration Guide
## AP Command Center — Production Rollout, Schema Upgrades & Rollback Procedures

**Author:** AP Engineering & Infrastructure Operations  
**Target Environment:** Staging & Production (Supabase PostgreSQL, FastAPI, React/Vite)  
**Release Version:** Phase A (Build 2026.11-A)  

---

## 1. Prerequisites & Environment Verification

Before applying the Phase A deployment, verify that the target environment meets the following baseline requirements:

- **Python Runtime:** Python 3.12.x with `pip` and virtual environment.
- **Node Runtime:** Node.js 20.x+ with `npm` 10.x+.
- **Database Engine:** PostgreSQL 15.x+ (Supabase hosted or self-hosted) with Row Level Security (RLS) enabled.
- **Current Database Head:** Revision `008_phase1_durable_jobs` applied cleanly.
- **Git Branch:** Clean working tree on `handoff/ap-command-center`.

---

## 2. Step-by-Step Deployment Procedure

### Step 1: Code Deployment & Dependencies
1. Checkout the deployment branch:
   ```bash
   git checkout handoff/ap-command-center
   git pull origin handoff/ap-command-center
   ```
2. Verify Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Verify Node dependencies in the frontend directory:
   ```bash
   cd frontend
   npm ci
   cd ..
   ```

---

### Step 2: Database Migration Execution (Alembic)
Phase A introduces revision `009_phase_a_core.py`, which adds tracking columns to `invoice_lines` and a composite B-tree index to `invoices`:

1. Inspect current migration status:
   ```bash
   python -m alembic current
   ```
   *Expected Output:* `008_phase1_durable_jobs (head)`
2. Run database migration to upgrade to head:
   ```bash
   python -m alembic upgrade head
   ```
   *Expected Output:*
   ```
   INFO  [alembic.runtime.migration] Running upgrade 008_phase1_durable_jobs -> 009_phase_a_core, Phase A: line item corrections, tracking columns, and temporal index
   ```
3. Verify that the columns and index exist in PostgreSQL:
   ```sql
   SELECT column_name, data_type, is_nullable 
   FROM information_schema.columns 
   WHERE table_name = 'invoice_lines' AND column_name IN ('is_corrected', 'previous_unit_rate', 'line_version');

   SELECT indexname, indexdef 
   FROM pg_indexes 
   WHERE tablename = 'invoices' AND indexname = 'idx_invoices_org_invoice_date';
   ```

---

### Step 3: Frontend Production Build
1. Build the production client bundle:
   ```bash
   cd frontend
   npm run build
   ```
2. Confirm output generation in `frontend/dist/`:
   - `dist/index.html` (~0.69 kB)
   - `dist/assets/index-*.css` (~97 kB)
   - `dist/assets/index-*.js` (~711 kB)
3. Return to project root:
   ```bash
   cd ..
   ```

---

### Step 4: Server Launch & Service Verification
1. Start the AP Command Center production FastAPI service:
   ```bash
   python run.py
   ```
2. Verify system health and Phase A endpoints:
   ```bash
   # 1. System health check
   curl -s http://127.0.0.1:8000/api/v1/health | grep '"status":"healthy"'

   # 2. Executive exposure scorecard endpoint
   curl -s -H "Authorization: Bearer <TOKEN>" http://127.0.0.1:8000/api/v1/dashboard/exposure

   # 3. Temporal inbox query
   curl -s -H "Authorization: Bearer <TOKEN>" "http://127.0.0.1:8000/api/v1/inbox?fy=2026-27&month=4"
   ```

---

## 3. Post-Deployment Verification Checklist

Execute the following post-deployment checklist to confirm complete operational readiness:

- [ ] **Database Schema:** `invoice_lines.is_corrected` is present with default `False`.
- [ ] **Database Schema:** `invoice_lines.line_version` is present with default `1`.
- [ ] **Database Index:** `idx_invoices_org_invoice_date` is active and indexed.
- [ ] **Backend Health:** `/api/v1/health` returns `200 OK` with database connection verified.
- [ ] **Automated Tests:** Run verification test suite:
  ```bash
  python -m pytest tests/test_phase_a_ux_roadmap.py tests/test_p0_buyer_trust_remediation.py -v
  ```
  *Requirement:* 12 passed, 0 failed.
- [ ] **AppShell Banner:** Persistent `[Evaluation Mode — Sample ERP Data]` banner is visible across all screens.
- [ ] **Dashboard Scorecard:** 3-card exposure strip displays Blocked Liability, Operational Ageing (> 30 Days), and Cleared for ERP.
- [ ] **Inbox Toolbar:** FY and Month dropdowns filter invoices accurately and persist selections in `localStorage`.
- [ ] **Line Item Correction:** Editing line rate recalculates invoice grand total, flips Gate 6 to `PASS`, and writes `LINE_ITEM_CORRECTED` to `audit_events`.
- [ ] **Audit Trail:** History & Evidence tab displays complete append-only event stream with actor ID, timestamp, and justification.
- [ ] **RBAC Security:** Auditor role (`AUDITOR`) cannot edit lines or trigger demo resets (`HTTP 403 Forbidden`).

---

## 4. Rollback & Disaster Recovery Procedures

In the event of an unexpected regression or deployment failure, execute the following rollback procedure:

### Procedure A: Database Schema Rollback
1. Stop the application service.
2. Downgrade the database migration by one revision:
   ```bash
   python -m alembic downgrade -1
   ```
   *Expected Output:*
   ```
   INFO  [alembic.runtime.migration] Running downgrade 009_phase_a_core -> 008_phase1_durable_jobs
   ```
3. Verify current revision:
   ```bash
   python -m alembic current
   ```
   *Result:* Must display `008_phase1_durable_jobs (head)`.

### Procedure B: Code Rollback
1. Checkout the previous release commit:
   ```bash
   git checkout 61602f6
   ```
2. Rebuild the frontend bundle from the previous commit:
   ```bash
   cd frontend
   npm run build
   cd ..
   ```
3. Restart the server:
   ```bash
   python run.py
   ```

---

## 5. Security & Support Contacts

For any deployment anomalies or production incidents:
- **Lead AP Engineer:** AP Operations Team (`engineering@apcommand.internal`)
- **Security & Compliance:** Security Architecture Group (`security@apcommand.internal`)
- **Escalation Path:** VP of Financial Engineering
