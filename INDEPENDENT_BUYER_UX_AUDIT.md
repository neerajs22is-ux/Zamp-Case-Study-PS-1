# Independent Buyer UX Audit: AP Command Center

**Repository:** `neerajs22is-ux/Zamp-Case-Study-PS-1-`
**Branch / commit audited:** `handoff/ap-command-center` @ `eb0e591` (2 Nov 2026, "rebalance procurement verification flow…")
**Audit date:** 3 Nov 2026
**Nature of this document:** read-only audit. No application code was changed, nothing was committed or pushed.
**Audience lens:** a first-time, non-technical finance manager or HR evaluator, with no developer beside them.

---

## 0. How this audit was done, and its limits

### Evidence tags used throughout

| Tag | Meaning |
|---|---|
| **[B]** | Observed in a real browser session (headless Chromium) against the running app |
| **[C]** | Read directly in source code (file and line given where useful) |
| **[D]** | Stated only in a repository document; not independently confirmed |
| **[U]** | Not verified. Needs checking before anyone relies on it |

### What was run

- PostgreSQL 16, the repo's Alembic migrations, and the repo's own seed script (`engine/sme_eval_setup.py`) were run from a **throwaway copy** of the repo, so the audited tree stayed pristine.
- The FastAPI backend served the built React SPA. I logged in through the UI as "SME AP Lead", visited every route, uploaded a PDF, opened all six resulting invoices, and walked the approve dialog.
- The legacy "live run" app (`engine/server.py` + `engine/templates/index.html`) was run separately and a scenario was executed in the browser.

### Harness deviations (these affect what you can conclude)

1. **No AWS Bedrock Mantle key was available.** The repo's own seed script fails without one (`MantleAuthError`, `engine/hybrid_extractor.py:368-372`). To seed anyway I substituted the repo's **deterministic regex extractor** for the LLM call, in a harness file outside the repo. The *stage and decision* assigned to each seeded invoice are hard-coded by scenario label in the seed (`engine/sme_eval_setup.py:~247-260`), so they do not depend on which extractor ran. **The live LLM extraction path was not exercised.**
2. **Storage:** a local-filesystem shim replaced Supabase Storage. The in-page PDF viewer rendered blank in headless Chromium, which is a known limitation of headless PDF embedding. **I make no claim about the PDF pane either way.**
3. **Legacy live-run page** loads Tailwind and Lucide from public CDNs, which my sandbox blocked. I served local equivalents, so I judge that page's **behaviour and content, not its visual styling**.
4. Not tested: mobile and tablet layouts, the Controller dual-approval flow, the Auditor role, and the Connections, Procurement Records and Team pages (I measured their word and control counts only; I did not review their screens).
5. No Antigravity UX/design skill is installed in this repo. `.agents/skills/` contains only `company-research` and `stageshow` (a demo-animation kit), and `skills-lock.json` lists only those two. None were used; the findings stand on direct observation.

### Existing documents consulted

`README.md`, `docs/AP_BUSINESS_RULES.md`, `docs/PRODUCT_CAPABILITY_TRUTH.md`, `docs/KNOWN_LIMITATIONS.md`, `docs/HR_SHOWCASE_GUIDE.md`, `docs/VIDEO_WORD_FOR_WORD_SCRIPT.md`, and the root file `AP Command Center Comprehension and Demo-Readiness UX Audit.md`. Where they disagree with the running code, the code wins.

---

## 1. Executive diagnosis

**A finance manager can find their way around this product. They cannot easily trust it, and they cannot see it working.**

The interface is competently built: consistent layout, clear role cards on login, and a genuinely good "blocked, here is what to do" banner. The complaints you described are real, but the root causes are not mainly cosmetic. There are four:

1. **The product contradicts itself in places a buyer will notice.** The "clean" invoice says *All 7 Automatic Checks Passed* while the same screen shows the goods-receipt and inspection records as *Snapshot Unavailable* and a billed total 18% above the PO total [B]. An unreadable scan says *6 validation checks failed* and tells the user to renegotiate a price that was never read [B]. One wrong-looking number costs more credibility than ten clean screens earn.
2. **There is no live processing experience in the product people will actually use.** The React app shows one sentence after upload and never updates [B]. The only "live" run is a separate legacy page whose stages are timed delays with hard-coded success messages [C]. Neither tells a user truthfully what is happening to their invoice.
3. **The core task is hidden and then over-guarded.** Uploading an invoice, the product's first action, exists only as step 5 of a setup wizard [B][C]. Approving a clean invoice takes five clicks and a dialog of roughly 600 words [B].
4. **Every screen carries an explanation layer instead of being self-evident.** Banners, subtitle paragraphs, "invariant" notices, tours, glossaries and consequence essays compete with the decision the user came to make. The previous audit recommended *adding* more of this (see §9). This audit recommends the opposite.

### One-line verdict by dimension

| Dimension | Verdict |
|---|---|
| Visual quality | Good. Not the problem. |
| Navigation | Mostly clear, with one orphaned page and two misleading counters |
| Amount of text | Too much, on almost every screen |
| Clicks to complete basic tasks | Too many for upload and for approval |
| Terminology | Developer and compliance vocabulary leaks into user-facing text |
| Trustworthiness of what is shown | **The biggest problem**: verdicts disagree with their own evidence |
| Live-processing clarity | Absent in the main app; theatrical in the legacy page |

---

## 2. Measured baseline

All figures from the running app at 1440×900, logged in as AP Lead, with the six seeded/uploaded records. Word counts are the visible body text.

| Screen | Words | Interactive controls | Notes |
|---|---:|---:|---|
| Login | 126 | 6 | Cleanest screen in the product [B] |
| Today | 380 | 23 | Seven distinct blocks; page scrolls to ~1,350 px [B] |
| Invoices (list) | 232 | 27 | Table is clear; no "why" column [B] |
| Invoice detail, clean | 373 | 26 | Plus the sticky action bar [B] |
| Invoice detail, exception | 456 | 25 | [B] |
| Invoice detail, unreadable scan | 493 | 25 | [B] |
| Approve confirmation dialog | ~600 (body incl. page behind) | 6 buttons (close, 3 reason chips, Cancel, Confirm) + text area | [B] |
| Approvals | 178 | 17 | Empty in the seeded state [B] |
| Exceptions (not in nav) | 228 | 25 | Orphaned page [B][C] |
| Audit | 269 | 27 | [B] |
| Connections & Storage | 297 | 20 | Not reviewed visually |
| Procurement Records | 277 | 19 | Not reviewed visually |
| Team & Access | 224 | 19 | Not reviewed visually |
| Setup wizard | 51–117 per step, 7 steps | ~4 per step | [B] |

### Click counts for the two basic tasks

| Task | Clicks measured | Path |
|---|---:|---|
| Get from login to the invoice file chooser | **~6** after login (+1 for login itself) | Setup Checklist → Get started → Continue ×3 → file input appears at step 5 [B] |
| Approve a clean invoice | **5** after login | Invoices → Review → Approve Review → pick a reason template (or type) → Confirm [B] |
| Reach "ready to approve" invoices from Today | Dead end | Card goes to a list with **0 rows** (see P0-4) [B] |

---

## 3. Page-by-page problems

Each finding gives the **observed problem** and the **expected user benefit** of fixing it. IDs are referenced in §10.

### 3.1 Login screen

**Observed [B]:** Four role cards, a recommended default, and a one-click evaluation login. This is the best-judged screen in the product. Problems are only vocabulary: "Supabase Cloud", "Production IdP", "Developer & Diagnostics Access (JWT Inspection)", "OCR parsing validation".

- **F-LOGIN-1:** Remove infrastructure terms from the buyer-visible card text and move the SSO and JWT blocks behind a single "Other sign-in options" link.
  *Benefit:* A non-technical evaluator sees a plain role choice and no unexplained acronyms on first impression.

### 3.2 Today (`DashboardPage.tsx`)

**Observed [B][C]:** Seven blocks compete for attention: a "Pre-Payment Invoice Verification & Controls" explainer banner with a four-step strip; three KPI cards; an "Operational Readiness" strip with six chips; a "Pipeline Velocity" strip; the action queue; "Integration Pillars"; and "Recent Audit Trail". The same count of 3 appears four times (sidebar badge, "Needs attention" card, "Exceptions: 3" in the pipeline strip, and "3 In Queue"). The Setup Checklist is reachable from the sidebar, the banner button, and the Readiness strip's "Setup Wizard" button. The statutory MSME note appears twice in the queue card.

- **F-TODAY-1:** Reduce Today to the question "what needs me now". Keep the queue and two or three counts; remove the explainer banner, readiness strip, pipeline strip and integration pillars from this screen.
  *Benefit:* One glance answers "what do I do first", and the page fits a laptop screen without scrolling.
- **F-TODAY-2:** The queue shows two rows reading "UNKNOWN / Supplier: Unknown / ₹0" for unreadable scans. Show "Couldn't read this document" with the filename instead.
  *Benefit:* The user can tell a scan problem from a real supplier named "Unknown".
- **F-TODAY-3:** The "Ready to approve" card routes to `/invoices?decision=AUTO_APPROVED` (`DashboardPage.tsx:236`) and lands on **0 rows**, because the card counts `MATCH_CANDIDATE` invoices, not `AUTO_APPROVED` ones [B][C]. See P0-4.
  *Benefit:* The most positive path in the product stops being a dead end.

### 3.3 Invoices list (`InboxPage.tsx`)

**Observed [B]:** A usable table with four plain tabs (All, Needs Attention, Ready to Approve, Approved), status chips, and search. Problems:

- **F-LIST-1:** **There is no "Upload invoice" action on this page.** The only button is "Sync Mailbox", which does nothing useful without a Gmail connection. The core action of the product lives elsewhere (see §3.8).
  *Benefit:* Upload becomes a one-click action from the screen where invoices live.
- **F-LIST-2:** "Needs attention" rows give no reason. The user must open each invoice to learn why.
  *Benefit:* A one-line reason ("Price 18.9% above PO", "Couldn't read scan", "Inspection not recorded") lets the user triage from the list.
- **F-LIST-3:** Page title "Invoice Inbox Ledger" and subtitle "Server-paginated operational ledger of genuine supplier invoices and compliance states" describe implementation, not purpose. Two filter dropdowns ("All Processing Stages", "All Verification Decisions") expose internal enums.
  *Benefit:* Fewer words and no jargon; the four tabs already do the job of those dropdowns.

### 3.4 Invoice detail (`InvoiceDetailPage.tsx`, 1,182 lines)

**What works and must be kept [B]:** the verdict-first banner; for blocked invoices, "Failing checks & required next actions"; failed checks sorted first; a sticky action bar; the explicit "Approval blocked" state.

**Problems:**

- **F-DETAIL-1 (trust, P0):** On the clean invoice AP-26-009 the banner reads **"All 7 Automatic Checks Passed — Ready to Approve"** while the Procurement Verification Flow on the same screen shows GRN and QC as *Snapshot Unavailable* with "Unavailable / Exempt / Not Filed", and *Billed ₹2,31,280 vs PO ₹1,96,000* [B]. Database rows confirm Gates 3 and 4 are stored as PASS with evidence "goods_receipts.csv" and "quality_inspections.csv", while the panel says that data is unavailable [B]. The seed loads purchase orders but no goods-receipt or inspection records [C: `sme_eval_setup.py` provisions vendors and POs only].
  *Benefit:* A finance manager can believe the verdict. Either the data supports the claim or the screen says "not checked".
- **F-DETAIL-2 (trust, P0):** For unreadable scans, the page says "Blocked: 6 Validation Check(s) Failed" and lists six next actions, including "Price and quantity match the PO: Variance 0.0% → Contact supplier to amend billed price" [B]. The invoice number is "UNKNOWN" and the total is "—". The honest cause, "we could not read this document", is not stated on the page; it appears only as "check scan" in a list chip and "OCR Readability Inspection" on the Exceptions page.
  *Benefit:* One truthful message and one action replace six misleading ones, and the user is not told to dispute a price that was never read.
- **F-DETAIL-3:** Failing-check reasons show raw evidence-source filenames as the explanation, for example "Quality inspection (QC) accepted: **quality_inspections.csv** → Next Action…" [B]. This is a database field (`evidence_source_id`) surfaced as prose.
  *Benefit:* The reason reads as a sentence a finance person understands.
- **F-DETAIL-4:** Above the fold the user sees: header, banner (with up to six bullets), "Decision Guide" strip, then a two-pane split with a PDF on the left and a tab strip on the right, and a sticky bar of six action buttons labelled TRIAGE and GOVERNANCE. The actual proof (billed vs ordered vs received vs inspected) is below the fold in a four-box flow whose two lower boxes are "Unavailable".
  *Benefit:* The decisive facts sit next to the verdict, not under three layers of framing.
- **F-DETAIL-5:** Six equal-weight action buttons with no recommended next step. "Triage" and "Governance" are group labels that mean little to a first-time user. "Set Aside (Quarantine)" and "Ask Supplier to Correct" suggest effects that do not occur: per `PRODUCT_CAPABILITY_TRUTH.md` §D, **no email is sent and no quarantine notice is issued**; they only change an internal status [D].
  *Benefit:* The user picks the one recommended action, or opens "More" for rare ones, and is not misled into thinking a supplier was contacted.
- **F-DETAIL-6:** Four tabs ("Matching & Lines", "Policy Checks (7/7)", "Extracted Information", plus Audit) plus "Expand Analysis", a Glossary button and a Tour button. The same pass/fail facts appear in the banner, the Decision Guide, the Policy Checks tab and the flow.
  *Benefit:* One place for each fact; fewer tabs to open.

### 3.5 Approve confirmation dialog (`ConsequenceAwareActionModal.tsx`, 406 lines)

**Observed [B]:** Titled "Confirm Action: Approve Invoice (Internal Sign-Off)" with a badge `APPROVE_AP_REVIEW`; four numbered sections ("What this does", "Resulting workflow state: `INTERNAL_APPROVAL_COMPLETE` (or ACTION_REQUIRED if dual-control active)", "Does this require another person?", "What happens next"); a yellow box of four "does NOT" bullets; a required "Audit Justification Reason" with three template chips; Cancel and a long confirm button.

- **F-MODAL-1:** Roughly 600 words to confirm a routine approval. Two of the four sections restate each other and the yellow box repeats a guarantee already shown in the page header ("AP Sign-Off Only • No Bank Disbursements").
  *Benefit:* A decision the user takes dozens of times a day takes seconds. The safety message remains, in one line.
- **F-MODAL-2:** Raw state names (`INTERNAL_APPROVAL_COMPLETE`, `APPROVE_AP_REVIEW`) appear in a user dialog.
  *Benefit:* No decoding needed.
- **F-MODAL-3:** The mandatory reason requires either typing or an extra click on a template chip. The reason is a legitimate audit control and **should stay required**, but for an invoice where all checks passed the system can offer a pre-filled, editable reason. This is a control decision for the finance owner, flagged in the blueprint (§9 there), not decided here.
  *Benefit:* Approval drops from five clicks to three while keeping a recorded justification.

### 3.6 Approvals (`ApprovalsPage.tsx`)

**Observed [B][C]:**

- **F-APPR-1:** The sidebar "Approvals" badge shows **2** while the page shows "0 Awaiting Second Sign-off" and no rows. The badge is `ready_to_approve + pending_second_approval` (`AppShell.tsx:36-47`) while the page lists only second-approval items [B][C].
  *Benefit:* A badge that leads somewhere real; no "where did my two items go" moment.
- **F-APPR-2:** The page and the Invoices "Ready to Approve" tab are two lists answering overlapping questions with different definitions.
  *Benefit:* One mental model of "waiting for me" vs "waiting for someone else".

### 3.7 Exceptions (`ExceptionsPage.tsx`, route `/exceptions`)

**Observed [B][C]:**

- **F-EXC-1:** The page is **unreachable from any link or menu**. The only reference is its route in `App.tsx:156`. A tester can only reach it by typing the URL. It duplicates the Invoices "Needs Attention" tab, with an added statutory-law banner and an owner-assignment column.
  *Benefit:* One exception list, in the place users already look.
- **F-EXC-2:** The browser header reads "Dashboard" on this page [B].
- **F-EXC-3:** It labels the unreadable-scan cause as "Gate #1: OCR Readability Inspection", while the business rules define Gate 1 as Vendor Master Verification [B][D]. Three different gate numbering schemes are now visible across screens and docs.
  *Benefit:* One vocabulary.
- **F-EXC-4:** "Resolve" and "Reassign" sit beside every row with no visible description of what they do. I did not exercise them.

### 3.8 Setup wizard (`OnboardingPage.tsx`, 1,005 lines) and the upload path

**Observed [B][C]:** Seven steps: Welcome, Workspace & Team (invite a teammate), Connect Gmail, Connect ERP (optional), Bring in Your First Invoice, a tour step, and a checklist summary. The only invoice upload control in the whole React app is on step 5. A user who wants to upload an invoice must pass three unrelated steps first.

- **F-SETUP-1:** Move upload to the Invoices page as a primary button and drop-zone. Keep the wizard as an optional administrator checklist under Settings.
  *Benefit:* The first and most common task takes one click.
- **F-SETUP-2:** Steps 2–4 (invite, Gmail, ERP) are administrator tasks shown to every first-time user. Step 4's copy ("Without procurement reference snapshots, tolerance gates cannot pass") is a warning about the product's own prerequisites.
  *Benefit:* The buyer's first minutes are spent seeing value, not configuring integrations.
- **F-SETUP-3:** After upload the screen shows exactly one line: "Invoice registered into queue: inv_4d44314d8afc" with a "Continue to Review" button. The page made **one API request** and never polled [B]. The user sees no progress, no result, and no failure.
  See §6 for the live-processing consequences.

### 3.9 Audit (`AuditPage.tsx`)

**Observed [B]:** A clear table with filters and four summary tiles. Verified against the API that all events appear (an early apparent discrepancy was a timing artefact of my own test, not a defect). Problems are wording only: "Immutable Audit Ledger", "Append-Only (PostgreSQL Trigger Enforced)", "State Diff / Inspect Diff", "Actor ID (e.g. usr_…)".

- **F-AUDIT-1:** Lead with "History" and the plain sentence "Every action is recorded and can't be edited." Put trigger and database detail in a footer or in documentation.
  *Benefit:* The reassurance an auditor wants, in words a manager reads.
- **Keep:** the table, filters, CSV export, and role-restricted access.

### 3.10 Header and global chrome (`AppShell.tsx`, `Sidebar.tsx`)

**Observed [B][C]:**

- A permanent "AP Sign-Off Only • No Bank Disbursements" chip, a "Showcase Tour" button, a keyboard "?" button, and a theme toggle sit in the header of every page.
- Sidebar: Today, Invoices, Approvals, Audit, then a Management group (Setup Checklist, Connections & Storage, Procurement Records, Team & Access): eight items for four daily tasks.
- Footer text "Environment: Production" appeared in my local development run. The code shows `isDevMode = !import.meta.env.PROD` (`AppShell.tsx:82, 229`), so any production build labels itself "Production" regardless of backend environment [C].
- **F-CHROME-1:** Reduce the header to page title, one help menu (tour, shortcuts, glossary), and the user menu. Keep the "no bank payments" reassurance as a single line in the approve dialog and in the help text, not a permanent chip.
  *Benefit:* Calmer pages; demo and developer affordances stop competing with work.
- **F-CHROME-2:** The footer environment label should reflect backend `app_env`, or be removed.
  *Benefit:* No false statement about the running environment.

### 3.11 Legacy "Live Run" app (`engine/server.py`, `engine/templates/index.html`)

This is a **separate application**, launched by `run.py` and not part of the Docker image's entry point (`backend.main:app`) [C]. It uses USD, "Apex Cloud Technologies Inc.", PO-1042, and its own five-scenario fixtures, so it shares no data with the Indian-GST React product [B][C].

- **F-LEGACY-1 (truthfulness, P0):** The stream (`engine/server.py:163-209`) emits stage 1, 2 and 3 as `asyncio.sleep` delays followed by hard-coded `STAGE_COMPLETE … status: SUCCESS` events. The engine runs once, inside stage 4. For scenario runs, the invoice is read from a pre-made JSON file, so "Structured Extraction" does no extraction [C].
- **F-LEGACY-2:** In the browser the stage timers finished at 0.04 ms, 0.28 ms, 0.03 ms, 0.42 ms and "1.01 ms (Total)" after about three seconds of visible animation [B]. The numbers are real compute time and contradict what the user just watched.
- **F-LEGACY-3:** On the duplicate-invoice scenario, which ends in **REJECTED**, all five stages show green ticks, including "ERP System-of-Record Cross-Reference" [B]. A green tick means "this step ran", but a buyer reads it as "this step passed".
- **F-LEGACY-4:** The result area uses the labels "CFO Audit Trail & Reasoning" and "Exception Analysis", where the latter is a raw JSON block (`"prior_invoice_id": …`) [B]. Stage names include "PEV pipeline", "AOP Policy Matching & Tolerance Math", and "Structured Extraction & Arithmetic Sanity".
- **F-LEGACY-5:** The page loads `cdn.tailwindcss.com` and `unpkg.com/lucide@latest` at runtime (`index.html:8,10`). With no internet, or on blocked venue wifi, the dropdown is empty and the page does not work (observed in my sandbox: 0 scenarios loaded) [B]. `@latest` is also unpinned.
- **F-LEGACY-6:** A JavaScript error (`Cannot read properties of undefined (reading 'toLocaleString')`) was thrown during the scenario run [B]. I did not isolate the cause.
  *Benefit of fixing all of the above:* the one place that *looks* like live processing becomes honest, and a demo does not depend on external CDNs.

---

## 4. Cross-cutting problems

### 4.1 Terminology: terms a finance manager will not recognise

| Where | Term | Plain replacement |
|---|---|---|
| Today, list, detail | "Verification Decision", "Processing Stage" (two filters) | Status (one) |
| Today | "Pipeline Velocity", "Integration Pillars", "Operational Readiness" | Remove, or "Setup status" under Settings |
| Detail, modal | `APPROVE_AP_REVIEW`, `INTERNAL_APPROVAL_COMPLETE`, `FLAGGED_EXCEPTION`, `MATCH_CANDIDATE` | Approved by you / Needs you / Ready for approval |
| Detail | "Policy Checks", "Gate 6: PO Price & Quantity Tolerance" | "Price and quantity match the order" |
| Detail | "Three-Way Match", "GRN", "QC" | "Invoice vs order vs delivery vs inspection" (explain "three-way" once, if at all) |
| Detail | "Set Aside (Quarantine)", "Triage", "Governance" | Set aside, Actions, (no label) |
| Audit | "Immutable", "PostgreSQL Trigger", "State Diff" | History, "cannot be edited", "What changed" |
| Legacy | PEV, AOP, "CFO Audit Trail", "HITL Gateway" | Plain stage names; "Decision and reasons"; "Needs a person" |
| Login | IdP, Supabase, JWT | Remove from buyer view |

### 4.2 The same fact stated repeatedly

The "no payment, no ERP posting" guarantee appears as a permanent header chip, in the Setup welcome, as an "Explicit Safety & Control Guarantees" box in the dialog, in the Today banner, and in docs. One authoritative statement, where a user is about to act, is enough; the rest is noise.

### 4.3 Three vocabularies for gates

| Source | Gate 1 is |
|---|---|
| `docs/AP_BUSINESS_RULES.md` | Vendor Master Verification |
| Exceptions page [B] | "OCR Readability Inspection" |
| Invoice detail [B] | "Supplier is registered and verified" |

### 4.4 Documentation versus code (relevant to trust, not just UX)

| Item | Doc says | Code or run shows |
|---|---|---|
| GST rounding tolerance | ₹1.00 (`PRODUCT_CAPABILITY_TRUTH.md`) | `ROUNDING_TOLERANCE_INR: float = 20.00` in `backend/core/config.py:131`, surfaced via `invoices.py:252`; `.env.example` and `AP_BUSINESS_RULES.md` also say ₹20 [C]. The ₹1 claim concerns `engine/indian_tax_rules.py`, which I did not read **[U]**. |
| Tour copy "₹1,00,000 dual approval", "2.50% variance" | Flagged as outdated in `PRODUCT_CAPABILITY_TRUTH.md` §E | Not re-checked in the tour code during this audit **[U]** |
| Keyboard shortcuts and reason templates | `KNOWN_LIMITATIONS.md` says resolved in Phase 5 | Reason-template chips confirmed in the dialog and a keyboard-help button in the header [B]; individual shortcuts not exercised **[U]** |
| "Reads PDF invoices… Pane 2 compares billed lines to PO contracted rates" (README) | | The comparison panels show "Unavailable" for GRN and QC in the seeded state [B] |

### 4.5 Seeded data limits what a first-time buyer sees

An evaluator cloning this repo cannot recreate the demo tenant without a paid AWS key (`sme_eval_setup.py` calls `extract_hybrid`, which raises without `MANTLE_API_KEY`) [B][C]. All five invoices from the seeded corpus share one supplier and one GSTIN (`29SYNTH0001A1Z5`), and two seeded records are unreadable scans [B]. A reader's first impression of "the product" is therefore two clean invoices, one exception, and two "UNKNOWN" rows.

---

## 5. Current user journeys

### 5.1 Current journey: "I have an invoice, I want to process it"

```
Login ─▶ Today (7 blocks, 23 controls)
        └▶ [find Setup Checklist: sidebar, banner button, or readiness strip]
            └▶ Welcome ─▶ Team invite ─▶ Gmail ─▶ ERP ─▶ Upload (step 5)
                 ─▶ "Invoice registered into queue: inv_…" (no progress, no result)
                 ─▶ "Continue to Review" ─▶ Invoice detail
Clicks to upload: ~6.   Feedback about processing: none.
```

### 5.2 Current journey: "I want to approve what's ready"

```
Today ─▶ "Review clean match queue" ─▶ /invoices?decision=AUTO_APPROVED ─▶ 0 rows   (dead end)
  or
Sidebar "Approvals (2)" ─▶ "0 Awaiting Second Sign-off"                               (badge/page mismatch)
  or
Invoices ─▶ Review ─▶ Approve Review ─▶ ~600-word dialog ─▶ reason ─▶ Confirm
Clicks (working path): 5.
```

### 5.3 Current journey: "Why was this blocked?"

```
Invoices ─▶ Review ─▶ banner + Decision Guide + 2 panes + tabs
  Clean invoice:    "All 7 passed"  vs  "Snapshot Unavailable"  and  Billed ≠ PO
  Unreadable scan:  "6 checks failed"  with 6 next actions, one contradicting itself
```

---

## 6. Is the live run truthful, and should it be replaced?

### What the main app has today [B][C]

- After upload, `documents.py` creates an invoice at stage `RECEIVED`, decision `NEEDS_REVIEW`, and queues an `IngestionJob` whose status is `QUEUED, PROCESSING, COMPLETED, FAILED` (`backend/models/domain.py:653`). A background task runs the pipeline if `ENABLE_BACKGROUND_PIPELINE` is true.
- The invoice's persisted stage goes from `RECEIVED` straight to `PENDING_APPROVAL` or `ACTION_REQUIRED` (`backend/core/pipeline.py:397, 402`). **There are no intermediate extraction or matching stages stored**, so a granular live view cannot be built honestly from current data.
- The frontend never polls an invoice or job. The dashboard exposes only an aggregate `active_ingestion_jobs` count (`types/index.ts:76`). **Per-invoice job status and `error_message` are not exposed to the frontend [C].**
- When extraction fails (my run: no Mantle key), the invoice stays `RECEIVED` with the reason "Uploaded via manual intake. Awaiting pipeline execution." and the failure is visible only in the server log [B].

### What the legacy page does [C][B]

Stages 1–3 are timed delays with unconditional "SUCCESS". It is theatre that happens to precede one real engine call.

### Recommendation

**Replace technical stage names with a small number of real, business-facing states, and show only states the backend can truthfully report.** The five-step business journey you proposed maps as follows:

| Business step | What the user sees | Backed by today? |
|---|---|---|
| 1. Invoice received | "Received" with filename, time | Yes: `RECEIVED` and the job `QUEUED` |
| 2. Information extracted | "Reading the invoice…" then "Read: supplier, number, amount" or "Couldn't read this" | Partly: job `PROCESSING/COMPLETED/FAILED` exists but is not exposed per invoice [C] |
| 3. Records verified | "Checked against your supplier list, purchase order, delivery and inspection records" | Partly: gate results exist; "not checked" is not a stored value for unreadable scans (they are stored as FAIL) [B] |
| 4. Issues identified | "2 issues: price 18.9% above order; inspection not recorded" | Yes for gate failures; reasons need rewriting (F-DETAIL-3) |
| 5. Human decision | "Needs you" or "Ready for approval" | Yes: `ACTION_REQUIRED` / `PENDING_APPROVAL` |

Do **not** invent finer-grained stages (for example "extracting line 3 of 7") unless the pipeline emits them. A four-state track, with an honest failure state, is more credible than a five-step animation. Drop millisecond timers entirely.

---

## 7. What to remove, retain, simplify, consolidate, hide

### Remove
- Today: explainer banner, "Operational Readiness" strip, "Pipeline Velocity" strip, "Integration Pillars".
- Permanent header chip "AP Sign-Off Only • No Bank Disbursements" and the "Showcase Tour" button from every page.
- The orphaned `/exceptions` page (fold its useful part, owner assignment, into Invoices if needed).
- Millisecond stage timers and fake-success stages in the legacy live run.
- Duplicate statements of the "no payment" guarantee.
- The "UNKNOWN / ₹0" rendering for unreadable documents.

### Retain
- Role-card login; one-click evaluation access.
- Verdict-first banner and the "blocked, here is the next action" pattern.
- Failed checks first, plain-language gate names.
- Reason templates and keyboard shortcuts (but keep the shortcut help out of the main header).
- Dual control, anti-self-approval, role restrictions and Auditor read-only. All are enforced in the backend per `PRODUCT_CAPABILITY_TRUTH.md` §H [D].
- Append-only audit and CSV export.
- Approval blocked while any check fails; no gate overrides.
- The explicit "does not pay or post to the ERP" guarantee, once, at the moment of approval.

### Simplify
- Today: one question, "what needs me".
- Invoice detail: verdict, reason, proof, one primary action.
- Approve dialog: one line of consequence plus the reason.
- Status vocabulary: six plain words (see blueprint).
- Audit page copy.

### Consolidate
- Exceptions + Invoices "Needs attention" into one list.
- Approvals badge and page into one definition.
- Policy Checks tab, Decision Guide, banner and flow into one "Why" section.
- Setup wizard steps 2–4 into Settings.

### Hide (progressive disclosure)
- Extracted-field table, raw confidence values, tabs for audit trail on the invoice.
- Rare actions (Escalate, Set Aside, Raise Debit Note) behind "More actions".
- Glossary, tour and shortcuts behind one Help menu.
- Infrastructure vocabulary (database, trigger, JWT, SSO) in a technical footer or documentation.

---

## 8. Do not solve this with more text

The previous audit (`AP Command Center Comprehension and Demo-Readiness UX Audit.md`) correctly found the copy contradictions (wrong thresholds, "Approved for Payment Run", etc.) and correctly praised the verdict banner. Its main remedy, however, was a **new explanation layer**: case-story strips, a three-way-match card, teaching gate cards, a consequence-aware action panel, first-use terms and a glossary (its §6). The repo has since built much of that: `CaseSummaryCard.tsx`, `ConsequenceAwareActionModal.tsx`, `GlossaryModal.tsx`, `HRShowcaseModal.tsx`, `PolicyChecksGrouped.tsx`. The result, observed above, is the density you are complaining about.

This audit's position: **an interface that needs a glossary and a tour to be understood should be simplified, not annotated.** Explanation should be reserved for the one or two moments where a user would otherwise make a wrong decision, and everywhere else the screen should state the fact, the reason and the next step in a sentence.

---

## 9. Consolidated findings register (observed problem, expected benefit, components, backend dependency)

Priorities: **P0** = trust or blocking defect, fix before any demo; **P1** = core usability; **P2** = polish and later.

| ID | Pri | Observed problem | Expected user benefit | Components / files | Backend dependency |
|---|---|---|---|---|---|
| P0-1 | P0 | "All 7 passed" shown beside "Snapshot Unavailable" and Billed ≠ PO (F-DETAIL-1) | Verdict is believable; no contradictions on screen | `CaseSummaryCard.tsx`, `ProcurementVerificationFlow.tsx`, `PolicyChecksGrouped.tsx`, `InvoiceDetailPage.tsx`; seed `engine/sme_eval_setup.py` | Seed must load GRN/QC records or gates must not pass without them; gate evidence vs panel data must come from one source |
| P0-2 | P0 | Unreadable scan shows "6 checks failed" and a self-contradicting price action (F-DETAIL-2) | One true message and one action | `InvoiceDetailPage.tsx`, `statusNormalizer.ts`, `ExceptionsPage.tsx`, `DashboardPage.tsx` | Interim: derive "couldn't read" from `decision = FLAGGED_HITL_REVIEW` plus no invoice number; proper: store `NOT_EVALUATED` for downstream gates when extraction fails |
| P0-3 | P0 | No upload on Invoices; upload is step 5 of a wizard (F-LIST-1, F-SETUP-1) | Upload in one click | `InboxPage.tsx`, `OnboardingPage.tsx`, `api/client.ts` (`uploadDocument` exists) | None (endpoint `POST /documents/upload` exists) |
| P0-4 | P0 | "Ready to approve" card leads to 0 rows; Approvals badge ≠ page (F-TODAY-3, F-APPR-1) | Counts lead to what they count | `DashboardPage.tsx:236`, `AppShell.tsx:36-47`, `ApprovalsPage.tsx` | Confirm `decision` value for ready items (`MATCH_CANDIDATE`); `list_approvals` definition in `approvals.py` |
| P0-5 | P0 | Upload shows one line, then nothing; failures invisible (F-SETUP-3, §6) | User sees received → read → checked → needs you, or a clear failure | New processing-status component; `InboxPage.tsx`; `api/client.ts` | **Expose per-invoice ingestion job status and `error_message`** (job model has them: `domain.py:653-655`) and poll |
| P0-6 | P0 | Legacy live run emits sleeps and unconditional SUCCESS (F-LEGACY-1..3) | No false progress. Either truthful or retired | `engine/server.py:163-209`, `engine/templates/index.html` | Decide whether the legacy app is retired or the SSE is driven by real pipeline events |
| P1-1 | P1 | Today carries seven blocks, repeated counts (F-TODAY-1) | One glance, no scrolling | `DashboardPage.tsx` | None |
| P1-2 | P1 | Approve takes 5 clicks and a ~600-word dialog (F-MODAL-1..3) | 3 clicks; short dialog; reason still recorded | `ConsequenceAwareActionModal.tsx` | None for UI; finance-owner decision needed on pre-filled reason |
| P1-3 | P1 | Reason missing in list; user must open each invoice (F-LIST-2) | Triage from the list | `InboxPage.tsx` | Confirm the list API returns a short reason (`decision_reason` exists on invoice); add if not in the response |
| P1-4 | P1 | Raw filenames and enums in user text (F-DETAIL-3, F-MODAL-2, §4.1) | Reads as plain sentences | `statusNormalizer.ts`, `PolicyChecksGrouped.tsx`, `StatusBadge.tsx` | Gate evidence notes need human-readable text (or map from gate number) |
| P1-5 | P1 | Invoice detail: verdict, proof and action separated by layers (F-DETAIL-4..6) | Decisive facts beside the verdict; one recommended action | `InvoiceDetailPage.tsx`, `CaseSummaryCard.tsx`, `ProcurementVerificationFlow.tsx` | Recommended action rule can be derived from failing gate (UI) |
| P1-6 | P1 | Orphaned Exceptions page; three gate vocabularies (F-EXC-1..3) | One list, one vocabulary | `ExceptionsPage.tsx`, `App.tsx:156` | None |
| P1-7 | P1 | Header and sidebar chrome (F-CHROME-1, §3.10) | Quieter pages | `AppShell.tsx`, `Sidebar.tsx`, `HRShowcaseModal.tsx`, `GlossaryModal.tsx`, `KeyboardShortcutsModal.tsx` | None |
| P1-8 | P1 | Action labels imply effects that do not happen (F-DETAIL-5) | No false belief that a supplier was emailed | `ConsequenceAwareActionModal.tsx`, `InvoiceDetailPage.tsx` | None (per `PRODUCT_CAPABILITY_TRUTH.md` §D no outbound email exists) |
| P2-1 | P2 | Login and Audit vocabulary (F-LOGIN-1, F-AUDIT-1) | First impression, auditor comprehension | `AuthScreen.tsx`, `AuditPage.tsx` | None |
| P2-2 | P2 | Footer "Environment: Production" in dev runs (F-CHROME-2) | No false label | `AppShell.tsx:82,229` | Use backend `app_env` from `/health` |
| P2-3 | P2 | Legacy page CDN dependency and JS error (F-LEGACY-5,6) | Works offline and on venue wifi | `engine/templates/index.html:8,10` | None |
| P2-4 | P2 | Seeded demo needs a paid AWS key; one supplier for all invoices (§4.5) | An evaluator can reproduce the demo | `engine/sme_eval_setup.py` | Provide a documented no-LLM seed path that includes GRN/QC records |
| P2-5 | P2 | Doc conflicts: ₹20 vs ₹1 rounding; outdated tour copy | Docs and UI say the same thing | `docs/PRODUCT_CAPABILITY_TRUTH.md`, `README.md`, tour text in `InvoiceDetailPage.tsx` | Confirm which tolerance `indian_tax_rules.py` applies |
| P2-6 | P2 | No bulk approval (`KNOWN_LIMITATIONS.md` §1.D) | Faster for high volume | `InboxPage.tsx` | **Do not build until P0-1 is fixed.** Bulk approval magnifies an untrustworthy verdict. Needs finance-owner threshold. |

---

## 10. Items I could not verify (to be checked before relying on this document)

1. The live LLM extraction path and how it behaves on real invoices.
2. Whether the PDF viewer renders correctly in a normal browser.
3. The Controller dual-approval flow and the Auditor view.
4. Mobile and tablet layouts.
5. Which rounding tolerance `engine/indian_tax_rules.py` actually applies (₹1 per one doc, ₹20 per config).
6. Whether the tour copy still shows outdated thresholds.
7. What "Resolve" and "Reassign" do on the Exceptions page.
8. Whether the invoice-list API already returns a short decision reason.
9. The cause of the legacy page's `toLocaleString` error.
10. Connections, Procurement Records and Team page content beyond word and control counts.

---

## 11. Answer to the final question

*If I redesigned this from scratch for a non-technical finance manager, what would I remove, keep and fundamentally change?*

**Five highest-impact changes**

1. **Make every verdict provable on the same screen.** Show the invoice amount against the order, delivery and inspection, with "not checked" wherever the data does not exist.
2. **Make processing visible and truthful.** Received → read → checked → needs you, with a real failure state, and no timers.
3. **Say "couldn't read this" once.** Stop cascading six false failures from one unreadable document.
4. **Put Upload on the Invoices page and make approval three clicks.** Keep the required reason.
5. **Reduce Today and Invoice detail to one question each.** What needs me, and what should I do about this invoice.

**Remove:** tours and showcase chrome from working screens, readiness and integration panels, the orphaned Exceptions page, fake stage timers, repeated guarantees.
**Keep:** role login, the blocked-with-next-action banner, reason templates, dual control and read-only auditor, append-only history, and the no-payment guarantee at the point of decision.
**Fundamentally change:** build around three states (Needs you, Ready, Done), one vocabulary, and evidence-first screens instead of a gate checklist. See `docs/BUYER_FIRST_UX_REDESIGN_BLUEPRINT.md`.
