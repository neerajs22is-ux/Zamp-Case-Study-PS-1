# AP Command Center — Word-for-Word Narration Script
## Zamp AI Solutions Associate Case Study Demonstration

**Presenter:** Candidate (First-Person Spoken Narration)  
**Total Target Spoken Duration:** 4 minutes 35 seconds to 4 minutes 45 seconds (Limit: 5:00)  
**Total Word Count:** 632 words (Average speaking pace: 138 words per minute)  
**Pacing Rule:** Speak calmly, clearly, and conversationally. Do not rush. Let visual transitions breathe for 1–2 seconds.

---

### SEGMENT 1: The Operational Problem & The Stakes
- **Timestamp:** `0:00 – 0:25` (25 seconds)
- **Target Word Count:** 58 words
- **Screen:** Dashboard (`http://localhost:5173/`)
- **Visual Action:** Cursor rests on *"Today's AP Operations"* header, then glides across the 4 KPI cards (`Blocked Working Capital`, `Needs Your Review`, `Statutory MSMED Exposure`).

> *"Every month, a growing company receives hundreds of vendor invoices as messy PDF attachments. Today, an Accounts Payable clerk has to open every single PDF, search through ERP spreadsheets to find the matching purchase order, manually calculate taxes, and decide whether to approve it.*
> *It's slow, tedious, and on a Friday afternoon, tired humans make expensive errors."*

---

### SEGMENT 2: What I Built — Solution Architecture & Inbox
- **Timestamp:** `0:25 – 0:55` (30 seconds)
- **Target Word Count:** 71 words
- **Screen:** Invoices Inbox (`/invoices`)
- **Visual Action:** Click *"Invoices"* in the left sidebar. Table loads with 8 active documents. Hover over status tabs (`All`, `Needs Review`, `Pending Approval`), then hover over row `AP-26-009`.

> *"To solve this, I built the AP Command Center—an intelligent pre-accounting verification checkpoint.*
> *Here in the main inbox, incoming invoices are ingested, fingerprinted, and triaged automatically.*
> *The system separates responsibilities cleanly: multimodal AI extracts the messy invoice data, a deterministic engine checks seven strict business policy gates, and human AP operators retain full sovereign authority over exceptions and sign-offs.*
> *Let's look at a live clean invoice."*

---

### SEGMENT 3: Live Execution — The Happy Path (`AP-26-009`)
- **Timestamp:** `0:55 – 2:20` (85 seconds)
- **Target Word Count:** 192 words
- **Screen:** Invoice Detail Workspace (`/invoices/inv_d76401c096d0`)
- **Visual Action:**
  1. Click invoice `AP-26-009`. Split-screen workspace opens.
  2. Point to original PDF on the left, structured metadata on the right.
  3. Point to the 4 connected lineage nodes (`Billed Claim` $\to$ `PO Contract` $\to$ `Receiving GRN` $\to$ `Quality QC`). All 4 show green checks.
  4. Scroll to Line Items: show unit price comparison (Billed ₹2,450 vs PO ₹2,450, 0.0% variance).
  5. Click tab *"Policy Checks (7/7)"*: point to all 7 green passing cards.
  6. Scroll to bottom sticky bar, click green *"Approve Review"* button. Modal appears. Point to Explicit Safety Guarantees. Click *"Cancel"*.

> *"This is invoice AP-26-009 from Asterion Precision Components for ₹2,31,280.*
> *On the left is the authentic original PDF. On the right, the multimodal AI has extracted the supplier details, GSTIN, line items, and tax amounts with high confidence.*
> *Notice our four-stage procurement lineage flow: we match the billed claim directly against Purchase Order PO-26-2001, the warehouse Goods Receipt Note, and the Quality Inspection record. All four nodes show verified green checks.*
> *Looking at the line item, eighty CNC machined steel housings were ordered at ₹2,450 per unit, eighty were delivered, and eighty passed quality inspection—resulting in exactly zero variance.*
> *When we open the Policy Checks tab, all seven deterministic gates pass completely: Vendor Master Registration, PO Authorization, GRN Delivery, QC Acceptance, GST 50/50 tax split arithmetic, rate tolerance, and duplicate detection.*
> *Because all checks pass, our primary decision bar lights up green with 'Approve Review'.*
> *Clicking it opens our consequence-aware modal. It clearly confirms what this action does—recording verified review sign-off—and what it does not do: it does not wire funds or post to the general ledger. It provides complete pre-payment governance."*

---

### SEGMENT 4: Live Execution — The High-Stakes Edge Case (`AP-26-011`)
- **Timestamp:** `2:20 – 3:30` (70 seconds)
- **Target Word Count:** 158 words
- **Screen:** Invoice Detail Workspace (`/invoices/inv_dbfcaf77ba9b`)
- **Visual Action:**
  1. Click *"Showcase Tour"* in header $\to$ Select Scenario #2 (or click *"Invoices"* and open `AP-26-011`).
  2. Point to orange banner: `ACTION_REQUIRED (FLAGGED_EXCEPTION)`.
  3. Point to line item rate comparison: Billed ₹2,850 vs PO ₹2,450 (+18.9% price variance).
  4. Click *"Policy Checks (5/7)"*: point to red failing Gate 4 (QC) and red failing Gate 6 (PO Price Tolerance).
  5. Scroll to bottom decision bar: point out that the primary button is locked as `Approval Blocked (2 Failing)`.
  6. Click *"Raise Debit Note"* in the secondary triage options. Modal appears with deduction breakdown. Click *"Cancel"*.

> *"Now, let's examine what happens when an invoice is non-compliant.*
> *This is invoice AP-26-011, also from Asterion, for ₹25,960. The AI extracted the document perfectly, but our business rule engine immediately caught critical problems.*
> *First, looking at the line item, the supplier billed us at ₹2,850 per unit against our contracted PO rate of ₹2,450. That's an unapproved eighteen-point-nine percent price markup, far exceeding our strict one-point-five percent commercial tolerance.*
> *Furthermore, on the Policy Checks tab, Gate Four failed because the warehouse receiving lot failed quality inspection, and Gate Six failed on price tolerance.*
> *Notice our core design invariant: the Approve button is permanently locked as 'Approval Blocked'. The system strictly prohibits clerks from overriding broken policy checks.*
> *Instead, the operator is guided toward structured triage: with one click, they can raise a commercial Debit Note to deduct the discrepancy from the vendor's balance."*

---

### SEGMENT 5: Engineering Architecture & Forensic Audit Ledger
- **Timestamp:** `3:30 – 4:15` (45 seconds)
- **Target Word Count:** 102 words
- **Screen:** Immutable Audit Ledger (`/audit`)
- **Visual Action:**
  1. Click *"Audit"* in the left sidebar.
  2. Ledger loads with event stream. Point to columns: Timestamp, Actor Email, Role, Action, SHA-256 Digest.
  3. Click top event row. Slide-over drawer opens showing side-by-side state diff and raw JSON payload.

> *"Here in the Immutable Audit Ledger, every single system event—from document intake to policy evaluation and triage decisions—is recorded with an actor email, role, timestamp, and SHA-256 document fingerprint.*
> *Clicking any entry opens a forensic drawer with side-by-side state diffs and raw JSON.*
> *This reflects our central architectural decision:*
> *We deliberately do not ask large language models to approve financial transactions. Generative AI is probabilistic; financial validation must be deterministic.*
> *We use AI where it excels—extracting unstructured text and vision data—while financial arithmetic, contract enforcement, and multi-tenant access control remain enforced by deterministic Python code and PostgreSQL database triggers."*

---

### SEGMENT 6: Business Value & Confident Closing
- **Timestamp:** `4:15 – 4:40` (25 seconds)
- **Target Word Count:** 51 words
- **Screen:** Dashboard (`/`)
- **Visual Action:** Close drawer, click *"Dashboard"* in left sidebar. Cursor hovers gently over the central KPI strip and MSMED statutory compliance meter.

> *"Returning to the dashboard, the AP Command Center transforms Accounts Payable from a chaotic paper chase into an orderly, exception-driven review process.*
> *It eliminates billing leakage, protects against duplicate payments and statutory MSME interest penalties, and gives financial controllers complete confidence before any money leaves the organization.*
> *Thank you."*

---

## Word Count & Timing Verification

| Segment | Timing | Duration | Word Count | Speaking Pace |
| :--- | :---: | :---: | :---: | :---: |
| 1. Problem & Stakes | 0:00 – 0:25 | 25s | 58 words | 139 wpm |
| 2. Architecture & Inbox | 0:25 – 0:55 | 30s | 71 words | 142 wpm |
| 3. Happy Path (`AP-26-009`) | 0:55 – 2:20 | 85s | 192 words | 136 wpm |
| 4. Edge Case (`AP-26-011`) | 2:20 – 3:30 | 70s | 158 words | 135 wpm |
| 5. Engineering & Audit | 3:30 – 4:15 | 45s | 102 words | 136 wpm |
| 6. Value & Closing | 4:15 – 4:40 | 25s | 51 words | 122 wpm |
| **TOTAL** | **0:00 – 4:40** | **280s (4m 40s)** | **632 words** | **135 wpm** |

*(Safe buffer remaining before the strict 5:00 cutoff: 20 seconds)*
