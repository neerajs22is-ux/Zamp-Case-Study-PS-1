# AP Command Center — UX & Architecture Implementation Roadmap

| Metadata | Details |
|---|---|
| **Audited Spec** | [`FRONTEND_UX_IMPLEMENTATION_SPEC.md`](file:///c:/Zamp%20Casse%20Study/FRONTEND_UX_IMPLEMENTATION_SPEC.md) |
| **Verification Basis** | [`docs/UX_AUDIT_VERIFICATION.md`](file:///c:/Zamp%20Casse%20Study/docs/UX_AUDIT_VERIFICATION.md) |
| **Architecture Review** | [`docs/IMPLEMENTATION_DECISIONS.md`](file:///c:/Zamp%20Casse%20Study/docs/IMPLEMENTATION_DECISIONS.md) |
| **Target Codebase** | `c:\Zamp Casse Study` @ commit `cda5c44` (Branch: `handoff/ap-command-center`) |
| **Design Frameworks Mandated** | **`stageshow`** (realistic framed UI, restrained typography, authentic data budgets), **`impeccable`** (Operate mode, high-density scannability, 14px hierarchy, keyboard navigation), **`taste-skill`** (anti-slop, no decorative card spam, high-contrast layouts). |
| **Execution Policy** | **PLANNING ONLY.** No application code, database migrations, or test fixtures are modified in this turn. |

---

## 1. Roadmap Architecture & Phasing Overview

The implementation is structured into **5 sequential phases**, ordered strictly by dependency: durable backend pipeline wiring and data integrity must precede UI components that consume that data; routing and navigation foundation must precede individual workspace screens; and polish/accessibility wraps the cohesive application.

```mermaid
flowchart TD
    subgraph Phase 1: Core Backend & Data Truth [Phase 1: P0 Core Backend, Durable Leases & Data Truth]
        B01["Task 1.1: Durable Ingestion Pipeline & Postgres Leases (B-01)"] --> B02["Task 1.2: Nuanced Exception Lifecycle (B-02)"]
        B02 --> B03["Task 1.3: Rejection Action & Substatus States (B-03, B-07)"]
        B03 --> B04["Task 1.4: Status Vocabulary Normalization (B-04)"]
        B04 --> B06["Task 1.5: Isolated Eval Tenant ERP Seeding & Prod Guard (B-06)"]
        B06 --> B07["Task 1.6: Database URL Precedence & Test Fix (D-10)"]
    end

    subgraph Phase 2: Navigation & Queue Foundation [Phase 2: P0 Router & Consolidated Queues]
        R01["Task 2.1: React Router Path Migration"] --> S01["Task 2.2: Global Sidebar Shell (stageshow/impeccable)"]
        S01 --> V01["Task 2.3: Pure Status Normalizer (statusFor)"]
        V01 --> I01["Task 2.4: Consolidated Invoices Queue (Inbox/Exceptions/Quarantine)"]
        B07 -.-> I01
    end

    subgraph Phase 3: Flagship Review Workspace [Phase 3: P0/P1 Review Workspace]
        I01 --> W01["Task 3.1: Embedded Document Viewer"]
        W01 --> W02["Task 3.2: Side-by-Side PO Line Comparison (B-05)"]
        W02 --> W03["Task 3.3: Match Gates with Evidence Notes"]
        W03 --> W04["Task 3.4: Dynamic Verdict Banner"]
        W04 --> W05["Task 3.5: Action Bar, Confirm Panel & Overrides"]
    end

    subgraph Phase 4: Workflow-First Screens [Phase 4: P1 Task-Led Screens]
        W05 --> T01["Task 4.1: Today Page (replaces Dashboard)"]
        T01 --> A01["Task 4.2: Dedicated Approvals Queue (B-10)"]
        A01 --> C01["Task 4.3: Slimmed Connections & Gmail Status"]
        C01 --> M01["Task 4.4: Member Roster & Team Access (B-11)"]
        M01 --> U01["Task 4.5: Audit Trail State-Diff & Investigation"]
    end

    subgraph Phase 5: Onboarding & Enterprise Craft [Phase 5: P1/P2 Onboarding & Ergonomics]
        U01 --> O01["Task 5.1: 7-Step Onboarding Flow & Checklist"]
        O01 --> K01["Task 5.2: Keyboard Shortcuts & ARIA Accessibility"]
        K01 --> P01["Task 5.3: Impeccable Operate Mode Polish & Anti-Slop Audit"]
    end

    Phase 1 --> Phase 2
    Phase 2 --> Phase 3
    Phase 3 --> Phase 4
    Phase 4 --> Phase 5
```

---

## 2. Phase 1: Ingestion-to-Decision Pipeline Wiring & Lifecycle Integrity (P0 Core BE)

The objective of Phase 1 is to eliminate the architectural disconnect identified in **F-01**: turning the AP Command Center from a demo shell driven by CLI seed scripts into an authentic, durable processing engine.

---

### Task 1.1: Durable Document Ingestion & Postgres-Backed Leases (B-01, D-01)
- **Priority:** **P0**
- **Exact Problem:** Uploaded documents (`POST /documents/upload`) and synced Gmail messages (`POST /integrations/gmail/sync`) create an `Invoice` with `stage="RECEIVED"` and an `IngestionJob` with `status="QUEUED"`. No backend service consumes this job or triggers `engine/hybrid_extractor.py` or `engine/deterministic_matching.py`.
- **Render Free Environmental Constraint:** On Render Free, services sleep after 15 minutes of inactivity and restart arbitrarily. In-memory threads or bare FastAPI `BackgroundTasks` are killed mid-flight on `SIGTERM`. There is NO persistent background daemon worker.
- **Durable Solution Architecture:**
  1. **Postgres-Backed Leases in `ingestion_jobs`:**
     - Add `lease_expires_at: DateTime` and `lock_token: String(64)` to `IngestionJob` (matching the pattern in `GmailAccount`).
     - Atomic lease acquisition via `SELECT ... FOR UPDATE SKIP LOCKED`.
  2. **Active Client Keep-Alive Polling:**
     - When the client uploads an invoice or triggers sync, the browser polls `GET /api/v1/invoices/{id}` every 3 seconds.
     - Because HTTP traffic arrives every 3 seconds, Render is actively prevented from sleeping while processing is underway.
  3. **Opportunistic Piggyback Recovery:**
     - On any authenticated inbound request for the tenant (or client poll), the server detects jobs where `status = 'PROCESSING'` and `lease_expires_at < now()`.
     - Reclaims the job back to `QUEUED`, increments `retry_count` (up to 3 retries), or marks `FAILED` with error diagnostics.
  4. **Transactional Idempotency:**
     - Execution runs inside a database transaction. If processing fails midway, rollback ensures no partial gate state is stored.
- **Affected Files:**
  - [`backend/core/pipeline.py`](file:///c:/Zamp%20Casse%20Study/backend/core/pipeline.py) (New)
  - [`backend/models/domain.py`](file:///c:/Zamp%20Casse%20Study/backend/models/domain.py)
  - [`backend/api/v1/documents.py`](file:///c:/Zamp%20Casse%20Study/backend/api/v1/documents.py)
  - [`backend/core/gmail.py`](file:///c:/Zamp%20Casse%20Study/backend/core/gmail.py)
  - [`backend/api/v1/integrations_gmail.py`](file:///c:/Zamp%20Casse%20Study/backend/api/v1/integrations_gmail.py)

---

### Task 1.2: Nuanced Exception Lifecycle & State Synchronization (B-02, D-06)
- **Priority:** **P0**
- **Exact Problem:** In [`backend/api/v1/invoices.py`](file:///c:/Zamp%20Casse%20Study/backend/api/v1/invoices.py), when actions are executed, `ExceptionRecord.status` is never updated. However, **exceptions must NOT all be blindly marked as RESOLVED!**
- **Required Lifecycle Enforcement:**
  - **Single Approval (`APPROVE_AP_REVIEW`):** `ExceptionRecord.status = "RESOLVED"`, `resolved_at = now`, `resolution_notes = "Approved by {actor}: {reason}"`.
  - **First Approval of Dual Approval:** `ExceptionRecord.status = "IN_REVIEW"`, `resolution_notes = "First approval complete by {actor}. Pending Controller sign-off."`.
  - **Second Approval of Dual Approval:** `ExceptionRecord.status = "RESOLVED"`, `resolved_at = now`, `resolution_notes = "Dual approval completed by {actor}: {reason}"`.
  - **Rejection (`REJECT_INVOICE`):** `ExceptionRecord.status = "RESOLVED"`, `resolved_at = now`, `resolution_notes = "Rejected by {actor}: {reason}. Closed without payment."`.
  - **Quarantine (`QUARANTINE`):** **Do NOT mark as RESOLVED.** Document is moved to quarantine holding; `ExceptionRecord.status = "IN_REVIEW"` (or `QUARANTINED`), `resolution_notes = "Quarantined by {actor}: {reason}. Pending compliance review."`.
  - **Hold (`HOLD_PENDING_EVIDENCE`):** `ExceptionRecord.status = "IN_REVIEW"`, `resolution_notes = "Hold placed by {actor}: {reason}"`.
  - **Supplier Correction (`REQUEST_SUPPLIER_CORRECTION`):** `ExceptionRecord.status = "IN_REVIEW"`, `resolution_notes = "Supplier correction requested by {actor}: {reason}"`.
  - **Debit Note (`RAISE_DEBIT_NOTE`):** `ExceptionRecord.status = "IN_REVIEW"`, `resolution_notes = "Debit note initiated by {actor}: {reason}"`.
  - **Escalate (`ESCALATE`):** `ExceptionRecord.status = "IN_REVIEW"`, `assigned_user_id = target_user`, `resolution_notes = "Escalated by {actor}: {reason}"`.
- **Affected Files:**
  - [`backend/api/v1/invoices.py`](file:///c:/Zamp%20Casse%20Study/backend/api/v1/invoices.py)
  - [`backend/models/domain.py`](file:///c:/Zamp%20Casse%20Study/backend/models/domain.py)

---

### Task 1.3: Rejection Action (`REJECT_INVOICE`) & Explicit Workflow Sub-states (B-03, B-07)
- **Priority:** **P0**
- **Exact Problem:** `REJECT_INVOICE` action does not exist; holds, supplier queries, debit notes, and escalations all collapse into `stage="ACTION_REQUIRED"` with identical state signatures.
- **Required Backend Changes:**
  1. Add `REJECT_INVOICE` to `InvoiceAction` enum. Sets `stage = InvoiceStage.ACTION_REQUIRED`, `decision = InvoiceDecision.REJECTED`. Closes exceptions with note "Closed without payment".
  2. Add `workflow_substatus` column (nullable string) to `invoices`: `ON_HOLD`, `SUPPLIER_CORRECTION_REQUESTED`, `DEBIT_NOTE_PENDING`, `ESCALATED`, `PENDING_SECOND_APPROVAL`.
  3. Ensure unrecognized action strings raise HTTP 422 rather than falling into unhandled `else`.
- **Affected Files:**
  - [`backend/models/domain.py`](file:///c:/Zamp%20Casse%20Study/backend/models/domain.py)
  - [`backend/api/v1/invoices.py`](file:///c:/Zamp%20Casse%20Study/backend/api/v1/invoices.py)
  - [`backend/migrations/versions/008_workflow_substatus.py`](file:///c:/Zamp%20Casse%20Study/backend/migrations/versions/008_workflow_substatus.py) (New)

---

### Task 1.4: Status Vocabulary Normalization (B-04)
- **Priority:** **P0**
- **Exact Problem:** Backend exposes raw fragmented enums (`stage` and `decision`) that require complex, inconsistent client-side interpretation.
- **Required Backend Changes:** Add computed property `user_facing_status` to API schemas mapping all combinations to canonical user-facing statuses (*Received*, *Processing*, *Ready to approve*, *Needs attention*, *On hold*, *Waiting for second approval*, *Approved*, *Not an invoice*, *Rejected*).
- **Affected Files:**
  - [`backend/models/domain.py`](file:///c:/Zamp%20Casse%20Study/backend/models/domain.py)
  - [`backend/api/v1/invoices.py`](file:///c:/Zamp%20Casse%20Study/backend/api/v1/invoices.py)
  - [`backend/api/v1/inbox.py`](file:///c:/Zamp%20Casse%20Study/backend/api/v1/inbox.py)

---

### Task 1.5: Isolated Eval Tenant ERP Line Seeding & Production Guards (B-06, D-09)
- **Priority:** **P0**
- **Exact Problem:** `erp_po_lines` has 0 rows in the evaluation database, preventing side-by-side PO comparison.
- **Strict Production Safeguard:**
  - Seeding synthetic CSV fixtures (`purchase_orders.csv`, `goods_receipts.csv`, `quality_inspections.csv`) must be strictly locked to tenant `org_sme_eval`.
  - Add explicit guard in [`engine/sme_eval_setup.py`](file:///c:/Zamp%20Casse%20Study/engine/sme_eval_setup.py):
    ```python
    if settings.ENVIRONMENT == "production" and org_id != "org_sme_eval":
        raise RuntimeError("CRITICAL: Synthetic evaluation fixtures cannot be seeded into production!")
    ```
- **Production Reference Data Pathways:**
  - Real ERP reference data in production enters via:
    1. `POST /api/v1/integrations/erp/sync` (Authenticated ERP webhook/API delta endpoint).
    2. `POST /api/v1/reference-data/upload` (Admin CSV bulk upload for SMEs without direct SAP OData connectivity).
- **Affected Files:**
  - [`engine/sme_eval_setup.py`](file:///c:/Zamp%20Casse%20Study/engine/sme_eval_setup.py)

---

### Task 1.6: Database URL Precedence & Test Separation Resolution (D-10)
- **Priority:** **P0**
- **Exact Problem:** `test_24_database_connection_separation_audit` fails because `backend/migrations/env.py` queries `os.getenv("MIGRATION_DATABASE_URL")` before `settings.MIGRATION_DATABASE_URL`, and the test only monkeypatches `settings`.
- **Required Backend & Test Changes:**
  1. In [`backend/migrations/env.py`](file:///c:/Zamp%20Casse%20Study/backend/migrations/env.py): Query `settings.MIGRATION_DATABASE_URL` before `os.getenv()`, making Pydantic validated settings authoritative.
  2. In [`tests/phase_b/test_stage7_cloudrun_deployment.py`](file:///c:/Zamp%20Casse%20Study/tests/phase_b/test_stage7_cloudrun_deployment.py): Set both `monkeypatch.setenv("MIGRATION_DATABASE_URL", migration_url)` and `monkeypatch.setattr(settings, ...)` to maintain strict connection separation in test fixtures.
- **Affected Files:**
  - [`backend/migrations/env.py`](file:///c:/Zamp%20Casse%20Study/backend/migrations/env.py)
  - [`tests/phase_b/test_stage7_cloudrun_deployment.py`](file:///c:/Zamp%20Casse%20Study/tests/phase_b/test_stage7_cloudrun_deployment.py)

---

## 3. Phase 2: Navigation, Queue Consolidation & Status Foundation (P0 Core FE + BE Data Contracts)

- **Task 2.1:** Path Router Migration (`react-router-dom`) with persistent URL query parameters.
- **Task 2.2:** Global Navigation Shell & Sidebar (`stageshow` desktop framing, `impeccable` Operate scannability, system health popover).
- **Task 2.3:** Pure Status Normalizer (`statusFor`) & Token System in [`frontend/src/utils/status.ts`](file:///c:/Zamp%20Casse%20Study/frontend/src/utils/status.ts).
- **Task 2.4 (B-09 & B-12):** Inbox Summary API (`GET /inbox/summary`), multi-term search, and explicit `org_id` SQL tenant hardening.
- **Task 2.5:** Consolidated Invoices Page (Merging Inbox, Exceptions, Quarantine, and Uploads with full pagination and upload queue).

---

## 4. Phase 3: The Flagship 3-Pane Review Workspace Redesign (P0/P1 FE + Evidence)

- **Task 3.1:** Embedded Document Viewer in Pane 1 (`<object>` / `<iframe>` with auto signed-URL refresh on 403).
- **Task 3.2 (B-05):** Return `po_comparison[]` and `tax_breakdown` in `GET /api/v1/invoices/{id}`.
- **Task 3.3:** Side-by-Side Matching Evidence (Billed vs PO lines, variance chips, Checks tab rendering gate notes and evidence source IDs).
- **Task 3.4:** Dynamic Verdict Summary Banner ("Verdict $\rightarrow$ Evidence $\rightarrow$ Decision").
- **Task 3.5:** Decision bar with context-sensitive reason chips, failed-gate override guard (checkbox acknowledgement required), and auto-advance.

---

## 5. Phase 4: Workflow-First Task Screens & Information Architecture (P1 FE + BE Queues)

- **Task 4.1:** Today Page (Replaces Dashboard with Next Up priority table, 3 outcome tiles, and pipeline strip).
- **Task 4.2 (B-10):** Dedicated Approvals Queue ([`ApprovalsPage.tsx`](file:///c:/Zamp%20Casse%20Study/frontend/src/pages/ApprovalsPage.tsx)) for high-value dual approvals.
- **Task 4.3:** Slimmed Connections Page querying tenant-level `GET /api/v1/integrations/gmail/status` and reading OAuth return query parameters.
- **Task 4.4:** Reference Data Side Drawer for PO, GRN, and QC lookups.
- **Task 4.5 (B-11):** Member Roster & Role Management tab under Settings $\rightarrow$ Team & Access.
- **Task 4.6:** Audit Trail Slide-over Drawer with Before $\rightarrow$ After JSON state diffs and actor name resolution.

---

## 6. Phase 5: Onboarding Experience & Enterprise Ergonomics (P1/P2 FE + Polish)

- **Task 5.1:** 7-Step Onboarding Flow & Live-Derived Checklist.
- **Task 5.2:** Keyboard Shortcuts (`J`/`K`/`A`/`H`/`1-4`/`Ctrl+Enter`/`?`) for mouseless AP clerk workflow.
- **Task 5.3:** `impeccable` Operate Mode Polish (14px base font, tabular numbers, WCAG AA contrast, anti-slop sweep).

---

## 7. Implementation Safety, Immutability & Rollback Procedures

### 7.1 Database Migration Safety (Migration 008)
- **Zero Data Loss Guarantee:** Migration `008_workflow_substatus.py` adds a single nullable column `workflow_substatus = Column(String(32), nullable=True)` and optional index on `invoices`.
- **Postgres DDL Non-Locking:** Adding a nullable column without a default value is a metadata-only change in PostgreSQL 11+. It requires no table rewrites and completes in $< 10\text{ ms}$, creating zero locking impact on existing rows.
- **Preservation of Existing Invoices & Audit Records:**
  - Existing invoices simply have `workflow_substatus = NULL`.
  - `AuditTrailEvent` is strictly append-only. No existing events are ever modified or deleted.
- **Rollback Runbook:**
  - Migration rollback: `alembic downgrade -1` removes the column cleanly.
  - Automated database backup trigger: `python -m backend.scripts.backup` creates a verified snapshot before applying migration.

### 7.2 Background Pipeline Safety Flag
- Ingestion pipeline invocation in [`backend/core/pipeline.py`](file:///c:/Zamp%20Casse%20Study/backend/core/pipeline.py) is guarded by environment variable `ENABLE_BACKGROUND_PIPELINE` (default: `true`).
- If an issue occurs with AWS Bedrock or PDF rendering, setting `ENABLE_BACKGROUND_PIPELINE=false` immediately reverts the system to safe `QUEUED` ingestion without service interruption.
