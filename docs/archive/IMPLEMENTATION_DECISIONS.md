# AP Command Center — Architecture & UX Implementation Decisions

| Metadata | Details |
|---|---|
| **Audited Spec** | [`FRONTEND_UX_IMPLEMENTATION_SPEC.md`](file:///c:/Zamp%20Casse%20Study/FRONTEND_UX_IMPLEMENTATION_SPEC.md) |
| **Document Purpose** | Explicit identification of architectural, product, policy, and business decisions requiring stakeholder approval before and during implementation. |
| **Status Taxonomy** | **RECOMMENDED** (Engineered proposal), **ALTERNATIVE** (Viable trade-off), **BLOCKED PENDING DECISION** (Requires user confirmation). |
| **Review Scope** | Incorporates final architectural review covering Render Free lifecycle, durable Supabase job leases, nuanced exception states, reference data isolation, test environment isolation, and migration safety. |
| **Design Frameworks Applied** | `stageshow`, `impeccable`, `taste-skill`. |

---

## Decision D-01: Ingestion Pipeline Execution Architecture for Web Uploads & Gmail Sync

### Context & Problem
Finding **F-01 / B-01** demonstrated that document uploads (`POST /documents/upload`) and Gmail sync create database records in `RECEIVED` stage with `IngestionJob(status="QUEUED")`, but no backend process triggers the document intelligence engine (`engine/hybrid_extractor.py` and `engine/deterministic_matching.py`).

### Environmental Constraint: Render Free + Supabase
- **Render Free Lifecycle:** The web service spins down after 15 minutes of inbound HTTP inactivity.
- **Process Loss:** If the app restarts, sleeps, or crashes, in-memory threads and standard FastAPI `BackgroundTasks` are abruptly terminated (`SIGTERM` $\rightarrow$ `SIGKILL`). Any job executing in memory is lost.
- **Zero Cost Constraint:** The architecture must operate entirely within the existing infrastructure (Render Free web service + Supabase PostgreSQL), without assuming an always-running paid background worker, Redis, or Celery.

### Options
- **Option A (Recommended): Durable Postgres-Backed Transactional Job Lease with Request-Driven Claim & Client Polling**
  - *Mechanism:*
    1. **Transactional State Machine in Supabase:** Utilize `IngestionJob` table with columns: `status` (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`), `lease_expires_at: DateTime`, `lock_token: String(64)`, `retry_count: Integer`, and `idempotency_key: String(128)`.
    2. **Atomic Lease Acquisition:** When a job is claimed, execute:
       ```sql
       UPDATE ingestion_jobs
       SET status = 'PROCESSING',
           lock_token = :token,
           lease_expires_at = now() + INTERVAL '180 seconds'
       WHERE id = (
           SELECT id FROM ingestion_jobs
           WHERE (status = 'QUEUED' OR (status = 'PROCESSING' AND lease_expires_at < now()))
             AND org_id = :org_id
           ORDER BY created_at ASC
           LIMIT 1
           FOR UPDATE SKIP LOCKED
       )
       RETURNING *;
       ```
    3. **Active Client Keep-Alive Polling:** During document upload or sync, the client polls `GET /api/v1/invoices/{id}` every 3 seconds. Because inbound HTTP traffic occurs every 3 seconds, Render is actively prevented from sleeping while the user is waiting!
    4. **Opportunistic Crash Recovery (Piggyback Reclaim):** If a worker crashes, the machine sleeps, or AWS Bedrock times out:
       - The lease expires after 180 seconds.
       - On the next authenticated inbound request for the tenant (or the next client poll), the server detects expired leases (`lease_expires_at < now()`), increments `retry_count` (max 3), and reclaims the job back to `QUEUED` or executes recovery.
    5. **Pipeline Idempotency:** Text extraction and policy gate checks are executed within a single database transaction. If processing fails midway, the transaction rolls back, leaving no corrupted partial lines or gate checks.
  - *Pros:* 100% durable and crash-recoverable; zero extra cost; zero additional infrastructure; zero reliance on persistent daemon workers.
  - *Cons:* Heavy batch processing is constrained to active user sessions.
- **Option B: Pure In-Memory `BackgroundTasks` (Fragile)**
  - *Cons:* If Render sleeps or restarts mid-extraction, jobs remain stuck in `PROCESSING` forever with no recovery mechanism.
- **Option C: Dedicated Background Worker (Paid Tier)**
  - *Cons:* Requires paid infrastructure ($7+/month) on Render.

### Recommendation & Dependent Implementation
**Adopt Option A.** Update [`docs/UX_IMPLEMENTATION_ROADMAP.md`](file:///c:/Zamp%20Casse%20Study/docs/UX_IMPLEMENTATION_ROADMAP.md) to implement the Postgres-backed atomic lease pattern in [`backend/core/pipeline.py`](file:///c:/Zamp%20Casse%20Study/backend/core/pipeline.py).

---

## Decision D-02: Approver Role Policy for High-Value Dual Control ($\ge$ ₹5,00,000)

### Context & Problem
Finding **B-08** revealed a discrepancy between project documentation and backend code:
- `README.md` and `AP_BUSINESS_RULES.md` claim high-value invoices require secondary sign-off by a **Financial Controller** (`UserRole.CONTROLLER`).
- In [`backend/api/v1/invoices.py#L200-L205`](file:///c:/Zamp%20Casse%20Study/backend/api/v1/invoices.py#L200-L205), the server only enforces `user.id != first_approval.approver_user_id` (any distinct user, including an AP Associate, can provide second approval).

### Options
- **Option A (Recommended): Enforce Strict Controller / Admin Role for Second Approval**
  - *Mechanism:* Require `role in [UserRole.CONTROLLER, UserRole.SYSTEM_ADMIN]` in addition to `user.id != first_approval.approver_user_id`.
  - *Pros:* Enforces institutional Segregation of Duties (SoD) and aligns with published compliance rules.
  - *Cons:* In a small team with only one Controller, absences require delegation to System Admin.
- **Option B: Preserve Distinct User Policy (Permit AP Lead or Controller)**
  - *Cons:* Weakens internal accounting controls.

### Recommendation & Dependent Implementation
**Adopt Option A.**

---

## Decision D-03: Rejection Policy & Financial Semantics (`REJECT_INVOICE`)

### Context & Problem
Finding **F-04 / B-07** confirmed that `REJECT_INVOICE` does not exist in the codebase. Clerks cannot reject duplicate or fraudulent submissions.

### Options
- **Option A (Recommended): Introduce Explicit `REJECT_INVOICE` Action & Terminal `REJECTED` Decision**
  - *Mechanism:*
    1. Add `REJECT_INVOICE` to `InvoiceAction` enum.
    2. Set `stage = InvoiceStage.ACTION_REQUIRED`, `decision = InvoiceDecision.REJECTED`.
    3. Update open exceptions to `status = "RESOLVED"`, `resolution_notes = "Rejected: {reason}. Closed without payment."`.
    4. Write append-only `AuditTrailEvent`.
    5. Terminal state: Invoice cannot be subsequent approved.
  - *Pros:* Clear operational audit trail; prevents accidental subsequent approvals; cleanly clears the exception queue.
- **Option B: Treat Rejection as Quarantine (`QUARANTINE`)**
  - *Cons:* Conflates non-payable/malformed files with legitimate business rejections.

### Recommendation & Dependent Implementation
**Adopt Option A.**

---

## Decision D-04: Failed-Gate Override Policy (3-Tier Governance Taxonomy)

### Status: SPECIFIED & DOCUMENTED (Deferred Implementation to Phase 2/3)

### Context & Problem
Finding **F-05 / B-08** revealed that previously any user (except read-only Auditor) could approve invoices even if all 7 match gates failed, without entering mandatory justification acknowledging the failure. A blanket override would destroy financial controls, while an absolute hard block on all gates would paralyze operations when acceptable tolerances occur.

### Approved Policy: 3-Tier Gate Governance Framework
Under NO circumstances can an invoice proceed to approval if either of these two gates fail. Any approval request is rejected unconditionally with HTTP 403 / 422:
1. **Gate 1: Vendor Identity Registered**
   - *Rationale:* Anti-fraud and statutory compliance. Payment cannot be made to an unregistered, inactive, or unverified GSTIN entity.
   - *Resolution Path:* Vendor Master record must be created or updated with verified GSTIN evidence before reprocessing.
2. **Gate 7: Duplicate Invoice Check**
   - *Rationale:* Absolute prevention of duplicate disbursement.
   - *Resolution Path:* The invoice must be rejected via `REJECT_INVOICE` or quarantined if fraudulent.

#### Tier 2: Conditionally Overridable by Authorized Roles (`AP_LEAD`, `CONTROLLER`)
These gates may be overridden by authorized roles only when specific bounded tolerance thresholds are met:
1. **Gate 3: GRN Receipt Confirmed**
   - *Permitted Tolerance:* Physical receipt verified via secondary warehouse delivery challan or gate pass, exposure amount <= ₹10,000.
2. **Gate 5: GST Arithmetic Reconciled**
   - *Permitted Tolerance:* Minor rounding discrepancy <= ₹2.00 attributable to fractional paise rounding across line-item tax distributions.
3. **Gate 6: PO Price & Quantity Tolerance**
   - *Permitted Tolerance:* Unit price variance <= ±5% within approved Master Service Agreement contractual bandwidth.
- *Mandatory Override Requirements:*
  - Operator must hold `AP_LEAD`, `CONTROLLER`, or `SYSTEM_ADMIN` role (`AP_ASSOCIATE` and `AUDITOR` are strictly forbidden).
  - Operator must select an approved operational reason code from the dropdown.
  - Operator must provide a written justification >= 25 characters.
  - Operator must tick an explicit confirmation: *"I acknowledge that Gate [X] has failed and accept financial responsibility for this operational override."*
  - The backend records an immutable `AuditEvent` with `action = "GATE_OVERRIDE_AUTHORIZED"`, documenting the overridden gate number, user ID, justification, and timestamp.

#### Tier 3: Subject to Additional Escalated Approval / Supporting Evidence
These gates cannot be overridden by an AP Lead alone and require dual-control executive sign-off or external documentation:
1. **Gate 2: PO Authorization Valid**
   - *Requirement:* Requires non-PO expense voucher signed by Legal Entity Head attached as verified documentary evidence before approval.
2. **Gate 4: QC Inspection Accepted**
   - *Requirement:* Material rejected or pending QC requires formal Plant Controller concession waiver and secondary Controller approval.

---

## Decision D-05: Default UI Theme & Shift Ergonomics

### Context & Problem
Finding **F-13** highlighted that the application currently defaults to a dark-only theme with 10-12px low-contrast text. The `impeccable` design skill emphasizes that 8-hour AP shift workers suffer visual fatigue with low-contrast dark themes and requires an `Operate` mode featuring 14px high-contrast typography.

### Options
- **Option A (Recommended): Light Theme by Default (Operate Mode) with Dark Mode Toggle**
  - *Mechanism:* `#ffffff` canvas, `slate-900` body copy, `slate-100` panels, `slate-200` borders, 14px base font (`text-sm` with 20px leading), tabular figures on numbers. Persistent user toggle for dark mode.
  - *Pros:* High scannability, reduced eye strain, matches institutional finance tooling standards.
- **Option B: Preserve Dark Theme Exclusively**
  - *Cons:* Retains high visual fatigue.

### Recommendation & Dependent Implementation
**Adopt Option A.**

---

## Decision D-06: Exception Lifecycle & Nuanced State Synchronization

### Context & Problem
Finding **F-05 / B-02** proved that `ExceptionRecord.status` is never updated when an invoice is acted upon. However, **exceptions must NOT all be blindly marked as `RESOLVED`**! In particular, quarantining an invoice does not mean the underlying exception was resolved.

### Comprehensive Lifecycle Specification
The table below specifies the exact, consistent state transitions across all actions:

| User Action | Invoice Stage | Invoice Decision | Workflow Substatus | `ExceptionRecord.status` | Resolution Notes Semantics |
|---|---|---|---|---|---|
| **Approve (Single Approval)** | `INTERNAL_APPROVAL_COMPLETE` | `MANUALLY_APPROVED` | `None` | **`RESOLVED`** | "Approved by {actor}: {reason}" |
| **Approve (1st of Dual)** | `ACTION_REQUIRED` | `MATCH_CANDIDATE` | `PENDING_SECOND_APPROVAL` | **`IN_REVIEW`** | "First approval by {actor}. Pending Controller sign-off." |
| **Approve (2nd of Dual)** | `INTERNAL_APPROVAL_COMPLETE` | `MANUALLY_APPROVED` | `None` | **`RESOLVED`** | "Final approval by {actor}: {reason}" |
| **Reject Invoice** | `ACTION_REQUIRED` | `REJECTED` | `None` | **`RESOLVED`** | "Rejected by {actor}: {reason}. Invoice closed without payment." |
| **Quarantine File** | `QUARANTINED` | `QUARANTINED` | `None` | **`IN_REVIEW`** (or `QUARANTINED`) | **Do NOT mark RESOLVED.** Set to `IN_REVIEW` with note "Quarantined by {actor}: {reason}. Pending compliance investigation." Document moved to Quarantine queue. |
| **Hold for Evidence** | `ACTION_REQUIRED` | (unchanged) | `ON_HOLD` | **`IN_REVIEW`** | "Hold placed by {actor}: {reason}. Awaiting GRN/QC evidence." |
| **Ask Supplier to Correct** | `ACTION_REQUIRED` | (unchanged) | `SUPPLIER_CORRECTION_REQUESTED` | **`IN_REVIEW`** | "Supplier correction requested by {actor}: {reason}." |
| **Raise Debit Note** | `ACTION_REQUIRED` | (unchanged) | `DEBIT_NOTE_PENDING` | **`IN_REVIEW`** | "Debit note initiated by {actor}: {reason}." |
| **Escalate** | `ACTION_REQUIRED` | (unchanged) | `ESCALATED` | **`IN_REVIEW`** | "Escalated by {actor} to {target}: {reason}." |

### Recommendation & Dependent Implementation
**Adopt this granular lifecycle.** Enforce that `RESOLVED` is reserved exclusively for terminal payment-approved or formally rejected invoices. Quarantined, held, escalated, and supplier-chased items remain `IN_REVIEW` with explicit operational tracking.

---

## Decision D-07: MSME Statutory Due Date Fallback & Policy

### Context & Problem
In seeded evaluation data, `msme_statutory_deadline` is null for all invoices because external Udyam verification is not provisioned. The UI currently labels this as "Unestablished", confusing clerks.

### Options
- **Option A (Recommended): Truthful Reporting ("No legal deadline set")**
  - *Mechanism:* If `msme_statutory_deadline` is null, render `"—"` with tooltip: *"No statutory deadline set — MSME registration status unverified."* Sort order places these after invoices with active deadlines.
  - *Pros:* Adheres strictly to the project's Production Truth Protocol; never fabricates compliance deadlines.
- **Option B: Synthetic 45-Day Fallback from Invoice Date**
  - *Cons:* Legally misleading under the Indian MSMED Act.

### Recommendation & Dependent Implementation
**Adopt Option A.**

---

## Decision D-08: Document Viewer Strategy (Native Object vs PDF.js)

### Context & Problem
Finding **F-03** identified that Pane 1 currently opens signed URLs in external browser tabs rather than displaying the document inline.

### Options
- **Option A (Recommended for P0/P1): Native Browser Embed (`<object>` / `<iframe>`)**
  - *Mechanism:* Embed `<object data={previewUrl} type="application/pdf">` with iframe fallback. Add automatic refresh on token expiry (calling `GET /api/v1/documents/{id}/signed-url` on 403).
  - *Pros:* Zero bundle weight; uses browser's native hardware-accelerated PDF engine; includes built-in zoom, pagination, search, and print controls.
- **Option B: Full Canvas PDF.js Renderer**
  - *Cons:* Adds ~400KB to bundle size; slower initial page render; complex text layer selection.

### Recommendation & Dependent Implementation
**Adopt Option A for P0/P1**, and plan Option B as a progressive enhancement in Phase 5 once bounding box coordinates are populated by the extraction engine.

---

## Decision D-09: Reference Data Isolation & Production Ingestion Strategy

### Context & Problem
Synthetic evaluation fixtures (`tests/evaluation_corpus_v2/reference_data/purchase_orders.csv`, `goods_receipts.csv`, `quality_inspections.csv`) are currently used to test matching logic. We must guarantee that synthetic fixtures never contaminate production databases, while defining how real ERP reference data enters production.

### Policy & Implementation Safeguards
1. **Strict Tenant Isolation:**
   - Synthetic fixtures are strictly restricted to `org_sme_eval` and ephemeral test tenants (`test_org_*`).
   - Seeding scripts must enforce an explicit environment check:
     ```python
     if settings.ENVIRONMENT == "production" and org_id != "org_sme_eval":
         raise RuntimeError("CRITICAL: Synthetic reference data seeding is prohibited in production!")
     ```
2. **Production Ingestion Pathways for Real ERP Reference Data:**
   - **Path A: Secure ERP Webhook / Batch API (`POST /api/v1/integrations/erp/sync`)**:
     - Accepts authenticated batch snapshots or delta payloads from SAP/Oracle/custom ERP.
     - Validates payloads against Pydantic schemas (`ErpPoPayload`, `ErpGrnPayload`, `ErpQcPayload`).
     - Inserts/updates `erp_purchase_orders`, `erp_po_lines`, `erp_goods_receipts`, `erp_goods_receipt_lines`, `erp_quality_inspections` partitioned by `org_id`.
   - **Path B: Bulk CSV Ingestion via Settings $\rightarrow$ Reference Data (`POST /api/v1/reference-data/upload`)**:
     - Designed for SMEs without direct SAP OData connectivity: authorized Admin or Controller uploads clean CSV exports of POs and GRNs.
     - Validates format (GSTIN, PO number, line items, rates, quantities, HSN codes) before committing.

### Recommendation & Dependent Implementation
**Adopt Policy D-09.** Add the production environment guard to `engine/sme_eval_setup.py` and specify Path A & B endpoints for production reference data.

---

## Decision D-10: Database Connection Separation & Test Precedence Resolution

### Context & Problem
Execution of `pytest` revealed 1 failing test:
`FAILED tests/phase_b/test_stage7_cloudrun_deployment.py::test_24_database_connection_separation_audit`.
The test verifies that migration connections (`MIGRATION_DATABASE_URL`) take precedence over runtime connections (`DATABASE_URL`).

### Root Cause Analysis
1. In `backend/migrations/env.py#L21-L31`, `get_url()` evaluates:
   ```python
   url = os.getenv("MIGRATION_DATABASE_URL") or settings.MIGRATION_DATABASE_URL or ...
   ```
2. When `.env` is loaded into the host environment, `os.environ["MIGRATION_DATABASE_URL"]` holds the live Supabase direct URL.
3. In `test_24`, the test executes `monkeypatch.setattr(settings, "MIGRATION_DATABASE_URL", migration_url)`, but fails to set `monkeypatch.setenv("MIGRATION_DATABASE_URL", migration_url)`.
4. As a result, `env.py` reads the un-mocked value from `os.environ` instead of the mocked setting. In line 943 of the same test, the author did remember to call `monkeypatch.delenv("MIGRATION_DATABASE_URL")`, confirming the asymmetry in the test setup.

### Recommended Resolution (Without Weakening the Test)
1. In `tests/phase_b/test_stage7_cloudrun_deployment.py`: Set both `monkeypatch.setenv("MIGRATION_DATABASE_URL", migration_url)` and `monkeypatch.setattr(settings, "MIGRATION_DATABASE_URL", migration_url)` at the beginning of the test.
2. In `backend/migrations/env.py`: Align precedence so `settings.MIGRATION_DATABASE_URL` (Pydantic validated settings) is checked before raw `os.getenv()`.
This preserves 100% of the security assertion while resolving the environment variable precedence defect.
