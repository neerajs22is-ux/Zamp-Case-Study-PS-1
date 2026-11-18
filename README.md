# Autonomous Accounts Payable (AP) Command Center

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React 19](https://img.shields.io/badge/React-19.0-61DAFB?logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-v4-38B2AC?logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An AI-assisted accounts payable invoice processing and 3-way matching system built for the **Zamp AI Solutions Associate (Problem Statement 1)** take-home case study.

The application ingests vendor invoices, extracts structured data with multimodal AI, cross-checks line items against procurement and warehouse records (PO, GRN, and QC), evaluates seven deterministic financial policy gates, and routes exceptions for dual-control human review with an immutable database audit trail.

---

### Quick Navigation

- **[Live Application](https://zamp-case-study-ps-1-1.onrender.com/)** — Hosted production deployment on Render
- **[Decision Sandbox](https://zamp-case-study-ps-1-1.onrender.com/sandbox)** — Guided interactive workflow and custom PDF test studio
- **[Evaluator Quick Start (START_HERE.md)](START_HERE.md)** — 3-minute testing path for hiring evaluators
- **[System Architecture (ARCHITECTURE.md)](ARCHITECTURE.md)** — In-depth architectural specification and data flow
- **[Local Setup Guide (docs/LOCAL_SETUP.md)](docs/LOCAL_SETUP.md)** — Step-by-step local development setup
- **[Live Build Liveness Probe](https://zamp-case-study-ps-1-1.onrender.com/api/v1/liveness)** — Container status and Git commit parity

---

## Visual Showcase

### Two-Column Invoice Review Workspace
The flagship interface provides side-by-side verification: the original document rendered on the left, with extracted line items, 3-way reconciliation, and deterministic gate results on the right.

![Invoice Review Workspace](docs/assets/screenshots/flagship_02_invoice_review.png)

### Seven Deterministic Policy Gates
Every invoice is evaluated against seven sequential checks before any payment recommendation can be generated.

![Seven Policy Gates Verification](docs/assets/screenshots/flagship_03_seven_gates_verification.png)

---

## Evaluator Quick Start (3-Minute Live Verification)

Evaluators can test the end-to-end pipeline on the live deployment without configuring local environments or authoring personal mailbox permissions:

1. **Launch Workspace:**  
   Open the **[Live Deployment](https://zamp-case-study-ps-1-1.onrender.com/)** and click **Launch Live Demo Workspace** (or jump directly to the **[Decision Sandbox](https://zamp-case-study-ps-1-1.onrender.com/sandbox)**).
2. **Run a Clean 3-Way Match:**  
   In the Decision Sandbox, select **Option B: Custom PDF Upload**. Click **Download clean invoice**, then upload the resulting PDF. Follow the live processing stages (Ingestion $\rightarrow$ AI Extraction $\rightarrow$ Tax Validation $\rightarrow$ 7 Policy Gates). The job completes with decision `MATCH_CANDIDATE`.
3. **Test an Exception (Rate Variance):**  
   Click **Download price-variance invoice** and upload it. The pipeline detects that the billed rate (₹220.00/unit) exceeds the contracted PO rate (₹185.00/unit) beyond the 1.5% tolerance, failing Gate 6 and routing to `FLAGGED_EXCEPTION`.
4. **Test Cryptographic Deduplication:**  
   Re-upload the exact same PDF file. The system computes the SHA-256 hash at the boundary, detects an identical document in the ledger, and rejects it with `HTTP 409 Conflict`.

> [!NOTE]  
> **Cold Start Notice:** The live demo is hosted on Render's web service tier. If the instance has been idle, the initial page load may take 20 to 40 seconds while the container initializes. Subsequent requests respond within normal operational latencies.

> [!IMPORTANT]  
> **Prepared Records vs. Live Provider Runs:** The demo workspace contains five pre-seeded synthetic records for immediate interface exploration. Custom PDF uploads in Option B invoke the live processing pipeline (AWS Bedrock Mantle Qwen 235B and Supabase PostgreSQL).

---

## Architectural Principles: "Models Read, Rules Decide"

Accounts payable automation requires balancing flexible document interpretation with zero-tolerance financial accuracy. Large language models excel at parsing unstructured invoices, varying table layouts, and misaligned tokens. However, probabilistic models must never calculate tax totals, determine policy tolerances, or authorize disbursements.

```mermaid
flowchart TD
    subgraph Intake ["1. Document Ingestion"]
        PDF[Vendor Invoice PDF] --> Prescreen[Modality & Contrast Pre-screener]
        Prescreen -->|Digital Text| FastPath[Direct Text Stream]
        Prescreen -->|Scanned Raster| OCRPath[RapidOCR / Layout Analyzer]
    end

    subgraph Intelligence ["2. Document Intelligence"]
        FastPath --> Mantle[AWS Bedrock Mantle Qwen 235B]
        OCRPath --> Mantle
        Mantle --> ExtractedData[Structured JSON + Provenance Coordinates]
    end

    subgraph Grounding ["3. Grounding & Math Verification"]
        ExtractedData --> TaxEngine[Indian GST Calculator]
        TaxEngine --> GSTCheck{Subtotal + Taxes == Total?}
        GSTCheck -->|Within ₹20 Rounding| ProcurementGrounding[PO & GRN Ledger Grounding]
        GSTCheck -->|Mismatch| FlagTax[Flag Tax Arithmetic Exception]
    end

    subgraph PolicyGates ["4. Seven Deterministic Gates"]
        ProcurementGrounding --> Gate1[Gate 1: Vendor Master]
        Gate1 --> Gate2[Gate 2: PO Authorization]
        Gate2 --> Gate3[Gate 3: GRN Match]
        Gate3 --> Gate4[Gate 4: QC Acceptance]
        Gate4 --> Gate5[Gate 5: GST Arithmetic]
        Gate5 --> Gate6[Gate 6: Price & Qty Tolerances]
        Gate6 --> Gate7[Gate 7: Cryptographic Deduplication]
    end

    subgraph Governance ["5. Human Review & Audit Ledger"]
        Gate7 -->|All Gates Pass| MatchCandidate[Stage: MATCH_CANDIDATE]
        Gate7 -->|Any Gate Fails| ExceptionStage[Stage: FLAGGED_EXCEPTION]
        MatchCandidate --> DualControl{Payable ≥ ₹5,00,000?}
        DualControl -->|Yes| RequireTwoSigners[Dual Control: AP Lead + Controller]
        DualControl -->|No| SingleSigner[Single Reviewer: AP Lead]
        RequireTwoSigners --> AppendAudit[Append-Only PostgreSQL Audit Trigger]
        SingleSigner --> AppendAudit
        ExceptionStage --> AppendAudit
    end
```

### The Seven Deterministic Policy Gates

| Gate | Validation Rule | Deterministic Check | Exception Condition |
| :---: | :--- | :--- | :--- |
| **1** | **Vendor Master** | Supplier GSTIN, PAN, and active status exist in the ERP vendor registry. | Unregistered vendor or mismatched tax identifier. |
| **2** | **PO Authorization** | PO reference is valid, approved, unexpired, and has an open line balance. | Closed PO, missing authorization, or unapproved amendment. |
| **3** | **GRN Match** | Billed item quantities do not exceed accepted warehouse Goods Receipt Notes. | Billed quantity > warehouse received quantity. |
| **4** | **QC Acceptance** | Delivered goods have passed engineering quality inspection. | Inspection status is `HOLD` or `REJECTED`. |
| **5** | **GST Arithmetic** | Billed math satisfies $\left|\text{Subtotal} + \text{Taxes} - \text{Total}\right| \le ₹20.00$ and confirms intrastate (CGST+SGST) vs interstate (IGST) split. | Tax calculation discrepancy or invalid state code mapping. |
| **6** | **Tolerances** | Unit price variance $\le 1.50\%$; line total variance $\le ₹20.00$. | Billed unit rate exceeds contracted purchase order rate. |
| **7** | **Deduplication** | Unique SHA-256 file digest and `(vendor_id, invoice_number, fiscal_year)` composite key. | Duplicate payment submission or identical re-transmission. |

---

## Core Engineering Decisions

1. **Arbitrary-Precision Arithmetic:**  
   All monetary calculations, percentages, and taxes use Python `Decimal` and PostgreSQL `numeric(15,2)` types. Binary floating-point representation (`float`) is barred from financial code paths to prevent rounding drift.
2. **Indian Statutory GST Validation:**  
   Validates 15-character alphanumeric GSTIN formats, extracts 2-digit state prefixes, and deterministically enforces tax classification:
   - Same supplier and recipient state: mandatory 50/50 split between **CGST** and **SGST**.
   - Differing supplier and recipient state: 100% allocation to **IGST**.
   - Standard rounding tolerance allowed up to ₹20.00 to accommodate ERP truncation conventions.
3. **Database-Level Audit Immutability:**  
   Financial audit events are written to `audit_events`. Immutability is enforced at the database engine level via PostgreSQL trigger `trg_audit_events_immutable`, which aborts any `UPDATE` or `DELETE` statement. Corrections require new compensating ledger events.
4. **Tenant Isolation via PostgreSQL RLS:**  
   Multi-tenant security uses PostgreSQL Row-Level Security (RLS) forced across all tables. Queries set transaction-local configuration (`SET LOCAL app.current_org_id`), and connection poolers execute `RESET ALL` upon check-in to prevent cross-tenant session leakage.
5. **High-Value Dual-Control Workflow:**  
   Invoices with a net payable balance $\ge ₹5,00,000$ mandate secondary approval by a Financial Controller following initial sign-off by the AP Lead. Anti-self-approval rules prevent the initial approver from granting secondary clearance.

---

## Integration Status & Boundaries

To ensure complete clarity during evaluation, current integration boundaries are explicitly documented:

| Subsystem | Status | Details & Implementation Scope |
| :--- | :---: | :--- |
| **AWS Bedrock Mantle (Qwen 235B)** | **Live** | Active in `ap-south-1` (Mumbai). Zero-temperature structured extraction with fallback handling. |
| **Supabase PostgreSQL 15 & Storage** | **Live** | Production database and private S3-compatible document storage using 300s presigned URLs. |
| **Gmail Mailbox Ingestion** | **Configured** | Code implements OAuth 2.0, Fernet token encryption, Pub/Sub webhook receiver, and history sync. Mailbox OAuth consent is omitted from the public demo to avoid requiring evaluator personal credentials. |
| **SAP S/4HANA ERP Synchronization** | **Roadmap** | Procurement records are grounded against internal database models (`erp.py`). Direct bidirectional RFC/BAPI synchronization is an architectural roadmap item. |
| **Banking & Payment Rails** | **Decoupled** | The application governs accounts payable review and approval. Internal sign-off does not trigger disbursement or initiate automated bank transfers. |

---

## Testing & Verification Summary

The codebase is protected by automated tests across security invariants, matching gates, tenant isolation, and UI responsiveness:

- **Pytest Test Suite:** 278 test functions defining **625 collected test cases** across parametrized matrices in `tests/`.
- **Review Session Execution:** 75 focused Python tests and 8 frontend test suites executed and verified passing with **zero failures**.
- **Live Acceptance Suite:** 9 end-to-end browser tests executed via Playwright against the live Render deployment (`https://zamp-case-study-ps-1-1.onrender.com/`), confirming:
  - 1-click demo workspace launch (11.05s)
  - Fresh clean invoice upload to `MATCH_CANDIDATE` (28.03s)
  - Price variance upload to `FLAGGED_EXCEPTION` (26.74s)
  - Cryptographic duplicate rejection (`HTTP 409 Conflict`)
  - Container build parity matching Git commit `9354d404cad4`
- **Milestone Baseline Snapshot:** An earlier development baseline recorded 464 passed / 43 skipped across 507 collected tests. Subsequent test suite expansion across edge cases, parity testing, and isolation hardening brought the collection to 625 items.

---

## Repository Structure

```
├── backend/                       # FastAPI application & REST endpoints
│   ├── api/v1/                   # Route handlers (auth, invoices, dashboard, webhooks)
│   ├── core/                     # Infrastructure (config, database, security, storage)
│   ├── models/                   # SQLAlchemy domain models (invoice, enterprise, erp, audit)
│   └── migrations/               # Alembic database schema migrations
│
├── frontend/                      # React 19 / Vite single-page application
│   ├── src/pages/                # Primary views (Dashboard, Inbox, Review Workspace)
│   ├── src/components/           # Reusable UI components & authentication views
│   └── public/sandbox.html       # Standalone interactive Decision Sandbox
│
├── engine/                        # Provider-independent business logic
│   ├── mantle_client.py          # AWS Bedrock Mantle client (Qwen 235B)
│   ├── indian_tax_rules.py       # GST arithmetic & 7-gate matching engine
│   ├── duplicate_detector.py     # Cryptographic SHA-256 deduplication
│   └── ocr_engine.py             # PDF text extraction & contrast pre-screening
│
├── docs/                          # In-depth architectural & operational documentation
│   ├── assets/screenshots/       # High-resolution application screenshots
│   ├── AP_BUSINESS_RULES.md      # Detailed 7-gate specifications & GST formulas
│   └── LOCAL_SETUP.md            # Local developer installation guide
│
├── fixtures/                      # Synthetic vendor invoices & ERP reference datasets
├── tests/                         # Pytest test suite (Phases A–E, engine, parity)
├── Dockerfile                     # Multi-stage production container build
├── render.yaml                    # Render Web Service blueprint
└── requirements.txt               # Locked Python dependencies
```

---

## Documentation Index

| Topic | Document | Focus Area |
| :--- | :--- | :--- |
| **Evaluator Walkthrough** | **[START_HERE.md](START_HERE.md)** | Step-by-step 3-minute evaluation guide and live test instructions |
| **Architecture Specification** | **[ARCHITECTURE.md](ARCHITECTURE.md)** | System context, data models, and technical design decisions |
| **AP Business Rules** | **[docs/AP_BUSINESS_RULES.md](docs/AP_BUSINESS_RULES.md)** | Exact GST calculations, tolerance thresholds, and state transitions |
| **Local Development** | **[docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md)** | Prerequisites, local PostgreSQL, and running frontend/backend servers |
| **Operations Runbook** | **[OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md)** | Deployment triage, health check probes, and monitoring guides |
| **Security Architecture** | **[SECURITY_NOTES.md](SECURITY_NOTES.md)** | PostgreSQL RLS policies, audit immutability, and token governance |
| **Contributing Standards** | **[CONTRIBUTING.md](CONTRIBUTING.md)** | Coding conventions, commit guidelines, and security requirements |
| **License** | **[LICENSE](LICENSE)** | Open-source MIT License terms |
