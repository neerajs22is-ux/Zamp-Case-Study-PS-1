# Evaluator Quick Start Guide

**Zamp AI Solutions Associate — Problem Statement 1 (Autonomous AP Processing & 3-Way Matching)**  
**Candidate:** Neeraj Shivkumar

This guide provides a 3-minute evaluation walkthrough for testing the live deployment, inspecting decisions, and observing edge case handling.

---

## Key Submission Links

- **Live Application:** [https://zamp-case-study-ps-1-1.onrender.com/](https://zamp-case-study-ps-1-1.onrender.com/)
- **Decision Sandbox:** [https://zamp-case-study-ps-1-1.onrender.com/sandbox](https://zamp-case-study-ps-1-1.onrender.com/sandbox)
- **GitHub Repository:** [https://github.com/neerajs22is-ux/Zamp-Case-Study-PS-1-](https://github.com/neerajs22is-ux/Zamp-Case-Study-PS-1-)
- **Live Build & Liveness Probe:** [https://zamp-case-study-ps-1-1.onrender.com/api/v1/liveness](https://zamp-case-study-ps-1-1.onrender.com/api/v1/liveness)

---

## 3-Minute Live Evaluation Walkthrough

Follow this route to observe live document intelligence and deterministic matching without setting up local tools or sharing personal credentials.

### Step 1: Launch the Demo Workspace
1. Navigate to the **[Live Deployment](https://zamp-case-study-ps-1-1.onrender.com/)**.
2. Click **"Launch Live Demo Workspace"**. The system initializes an isolated demonstration session seeded with synthetic procurement records (PO, GRN, and QC certificates).
3. Alternatively, open the **[Decision Sandbox](https://zamp-case-study-ps-1-1.onrender.com/sandbox)** directly.

### Step 2: Run a Fresh Happy-Path Invoice (Clean 3-Way Match)
1. In the Decision Sandbox, select **Option B: Custom PDF Upload**.
2. Click the button to **Download clean invoice** (saves a synthetic valid invoice PDF).
3. Upload the downloaded file into the upload zone.
4. Observe the live processing stages:
   - **Document Ingestion:** PDF header integrity and modality pre-screening.
   - **AI Extraction:** Live inference via AWS Bedrock Mantle Qwen 235B (~15–25 seconds) extracting line items and tax amounts with bounding-box coordinates.
   - **Grounding & Math:** Validates Indian GST statutory math against vendor and recipient state codes.
   - **Seven Policy Gates:** Evaluates vendor status, PO balance, warehouse GRN, QC inspection, tax math, price tolerance, and deduplication.
5. **Observed Outcome:** The run completes with decision **`MATCH_CANDIDATE`** and stage `PENDING_APPROVAL`. All seven gates pass with 0.00% variance.

### Step 3: Run Edge Cases (Rate Variance & Duplicate Rejection)
1. **Price Variance:**
   - In Option B, click **Download price-variance invoice** and upload it.
   - **Observed Outcome:** The pipeline identifies that the billed unit rate (₹220.00) exceeds the contracted PO rate (₹185.00) by +18.92% (violating the 1.5% tolerance limit).
   - Gate 6 fails, and the invoice is routed to stage `ACTION_REQUIRED` with decision **`FLAGGED_EXCEPTION`**.
2. **Cryptographic Deduplication:**
   - Immediately re-upload the same price-variance PDF file.
   - **Observed Outcome:** The system computes the SHA-256 digest at the boundary, detects an existing ledger entry, and rejects the upload with **`HTTP 409 Conflict`** (`DUPLICATE_DOCUMENT_DIGEST`).

---

## Important Evaluation Context & Boundaries

- **Prepared Records vs. Live Processing:**  
  The demo workspace includes five pre-seeded synthetic records (`SCN-01` through `SCN-05`) for immediate UI review. Custom PDF uploads in Option B trigger live, provider-backed execution (AWS Bedrock Mantle Qwen 235B and Supabase PostgreSQL).
- **Cold-Start Delay:**  
  The application is hosted on Render's web service tier. If the instance has been idle, the initial page load may take 20 to 40 seconds while the container boots. Subsequent requests operate at full speed.
- **Demo Role & Payment Boundary:**  
  The evaluator session operates with operational review permissions. Internal approval marks the invoice `MANUALLY_APPROVED` for AP ledger tracking. The application is intentionally decoupled from banking rails; internal approval does not initiate financial disbursement.
- **Gmail & Mailbox Integration:**  
  The backend codebase implements full Gmail OAuth 2.0 and Pub/Sub webhook ingestion. To eliminate evaluator login friction and protect privacy, the public web demo provides direct PDF upload rather than requiring personal mailbox authorization.
- **SAP S/4HANA ERP:**  
  Matching operates against relational procurement records (`erp.py`). Direct bidirectional ERP mutation is an architectural roadmap item.

---

## Core Architectural Principle: "Models Read, Rules Decide"

- **Multimodal AI (`engine/mantle_client.py`):** Extracts unstructured text, tables, and tax identifiers with coordinate provenance.
- **Deterministic Engines (`engine/indian_tax_rules.py`):** Calculates exact GST tax math using Decimal precision, checks 3-way tolerances, and enforces the 7 sequential policy gates.
- **Database Immutability (`backend/models/audit.py`):** PostgreSQL trigger `trg_audit_events_immutable` bars `UPDATE` and `DELETE` on all audit logs.

---

## Deep Dive Documentation

For architectural specifications, business rules, and local setup instructions:
- **[System Architecture (ARCHITECTURE.md)](ARCHITECTURE.md)**
- **[AP Business Rules & GST Specifications (docs/AP_BUSINESS_RULES.md)](docs/AP_BUSINESS_RULES.md)**
- **[Local Development Setup (docs/LOCAL_SETUP.md)](docs/LOCAL_SETUP.md)**
- **[Operations & Production Runbook (OPERATIONS_RUNBOOK.md)](OPERATIONS_RUNBOOK.md)**
- **[Security Architecture & RLS (SECURITY_NOTES.md)](SECURITY_NOTES.md)**
