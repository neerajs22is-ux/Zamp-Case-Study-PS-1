# Buyer-First UX Redesign Blueprint: AP Command Center

**Companion to:** `docs/INDEPENDENT_BUYER_UX_AUDIT.md` (finding IDs such as `P0-1` and `F-DETAIL-1` refer to it)
**Repository / commit:** `neerajs22is-ux/Zamp-Case-Study-PS-1-`, branch `handoff/ap-command-center` @ `eb0e591`
**Status:** proposal only. No application code was changed, nothing committed or pushed.
**Design target:** a non-technical finance manager, or an HR evaluator watching one, with nobody explaining the screen.

> **Rule for this blueprint.** Every element must earn its place by helping the user decide, act, or trust. Where the audit found a screen confusing, the fix is to remove, merge or restate, not to add explanation. A new element is proposed only where the audit found something missing (upload, processing status, a "why" column).

---

## 1. The one business journey

Every screen should be locatable on this single path, in these words:

```
 Invoice received  ─▶  Information read  ─▶  Records checked  ─▶  Issues found  ─▶  You decide
   "Received"           "Read"              "Checked"            "Needs you"       "Approved / Set aside / Rejected"
```

| Step | What the user is told | Source of truth today | Gap |
|---|---|---|---|
| Received | File name, time, who uploaded | `documents`, `invoices.stage = RECEIVED`, job `QUEUED` | None |
| Read | Supplier, invoice no., date, amount, or **"Couldn't read this"** | Job `PROCESSING/COMPLETED/FAILED` + `error_message` exist (`backend/models/domain.py:653-655`) | **Not exposed per invoice to the frontend** |
| Checked | "Checked against supplier list, purchase order, delivery and inspection records" | `match_gate_checks` (PASS/FAIL) | No "not checked" value; unreadable scans store FAIL for gates that never ran |
| Issues found | Plain-English reasons, each with the numbers | Gate `evidence_notes` | Notes are file names or terse strings; need readable text |
| You decide | Approve, or one of the other actions | `PENDING_APPROVAL` / `ACTION_REQUIRED`, dual-control rules | None |

Do not add stages the pipeline does not report. The persisted invoice stage goes straight from `RECEIVED` to `PENDING_APPROVAL` or `ACTION_REQUIRED` (`backend/core/pipeline.py:397,402`).

---

## 2. Design principles

1. **One question per screen.** Today: *what needs me?* Invoice: *can I approve this, and if not, what do I do?* Approvals: *what is waiting on someone else?*
2. **Evidence beside the verdict.** No claim without the number that supports it, on the same screen.
3. **Say "not checked" instead of "failed" or "passed"** when something was not actually evaluated.
4. **One name for each thing.** One status vocabulary, one gate vocabulary, one place to find each list.
5. **Guarantees once, at the moment of action.** "Approving records your sign-off. It does not pay the supplier or change your accounting system." Once. In the approve dialog.
6. **Progressive disclosure.** Rare actions, raw fields and audit detail sit one click behind the main path.
7. **Preserve controls.** Nothing in this blueprint weakens: approval blocked while any check fails, no gate overrides, dual control at ≥ ₹5,00,000, anti-self-approval, second approver must be Controller or System Admin, Auditor read-only, mandatory reason on every action, append-only audit, tenant isolation.

---

## 3. Information architecture

### Current navigation (8 items + header clutter)

```
OPERATIONS:  Today · Invoices (3) · Approvals (2) · Audit
MANAGEMENT:  Setup Checklist · Connections & Storage · Procurement Records · Team & Access
(not linked anywhere: /exceptions)
Header: [No-Bank-Disbursements chip] [Showcase Tour] [Keyboard ?] [Theme]
```

### Proposed navigation (4 daily items + Settings)

```
Invoices        ← home; Upload lives here
Approvals       ← only "waiting on a second person" (Controllers see "waiting for you")
History         ← audit trail (was "Audit")
Settings  ▸     Connections & mailbox · Procurement records · Team & access · Setup checklist
Header: page title ········· [Help ▾]  [user ▾]
        Help ▾ = Take the 2-minute tour · Glossary · Keyboard shortcuts
```

- **Today** becomes a thin top strip of the Invoices page ("2 need you · 2 ready · 0 waiting") rather than a separate page. If a separate landing page is kept, it must follow §4.2. (Decision for the product owner; either satisfies P1-1.)
- **Exceptions** is removed. Its content (reason, exposure, owner) moves into the Invoices "Needs you" tab (P1-6).
- **Setup Checklist** moves under Settings. It stays available, but is no longer on a first-time user's path to value.

*Benefit:* four verbs for the daily user (look at invoices, approve, review history, change settings), and no dead pages.

---

## 4. Screen designs

ASCII layouts show information hierarchy, not styling. Existing design tokens, Tailwind styling and components remain.

### 4.1 Login (minimal change)

```
┌──────────────────────────────────────────┐
│   AP Command Center                      │
│   Check supplier invoices, approve with  │
│   confidence.                            │
│                                          │
│   Sign in as (demo):                     │
│   ▸ AP Lead       Reviews and approves   │
│   ▸ Controller    Second approval ≥ ₹5L  │
│   ▸ Auditor       View only              │
│   ▸ AP Associate  Uploads and triages    │
│                                          │
│   Other sign-in options ▾                │
└──────────────────────────────────────────┘
```
Remove "Supabase", "IdP", "JWT", "OCR parsing" from the visible card text. (F-LOGIN-1)

### 4.2 Invoices: the home screen

```
Invoices                                          [ + Upload invoice ]   [Refresh]
─────────────────────────────────────────────────────────────────────────────────
 Needs you  3      Ready to approve  2      Waiting for others  0      Done  0
 ───────────
 ┌ Drop a PDF here or click Upload ────────────────────────────────────────────┐
 │  (shown only when the list is empty, or while dragging a file over the page) │
 └──────────────────────────────────────────────────────────────────────────────┘
 Search supplier, invoice no., PO…                                          5 invoices

 Supplier                Invoice     Amount         Status            Why / next
 Asterion Precision…     AP-26-011   ₹25,960.00     ● Needs you       Price 18.9% above order; inspection not recorded      [Review]
 Couldn't read           scan_037    —              ● Needs you       Couldn't read this document — upload a clearer copy   [Review]
 Asterion Precision…     AP-26-009   ₹2,31,280.00   ● Ready           Matches order, delivery and inspection                [Review]
 uploading…              10_inv…     —              ◌ Reading…        Received 10:03 · reading the invoice                   
```

**Changes and why**
- **Upload invoice** is a primary button on this page and a drag-and-drop target. *Benefit:* the first task is one click (P0-3, F-LIST-1).
- **Four tabs double as the only filters.** The two enum dropdowns are removed. *Benefit:* less to read (F-LIST-3).
- **"Why / next" column** gives one line per row. *Benefit:* triage without opening each invoice (F-LIST-2, P1-3). Content comes from the first failing check, rewritten in plain words (see §5).
- **Row states for in-progress and unreadable invoices** replace "UNKNOWN / ₹0". *Benefit:* a scan problem is not confused with a supplier named "Unknown" (F-TODAY-2).
- **Page title** becomes "Invoices". Subtitle removed.
- **Counts on the tabs are the same numbers as the sidebar and any summary strip.** One definition each (P0-4).

**Components affected:** `InboxPage.tsx`, `StatusBadge.tsx`, `statusNormalizer.ts`, `api/client.ts` (`uploadDocument` already exists).
**Backend dependencies:** a short reason per invoice in the list response (`decision_reason` exists on the invoice model; confirm it is in the inbox payload); per-invoice processing state for "Reading…" (§6).

### 4.3 Today (if retained as a page)

```
Today                                                      Tuesday 3 November
──────────────────────────────────────────────────────────────────────────
 3 need you · ₹25,960            2 ready to approve            0 waiting on others
 [Review them]                   [Review them]                 [Open approvals]

 Next up
  AP-26-011  Asterion Precision   ₹25,960   Price 18.9% above order            [Review]
  Couldn't read: scan_037                   Upload a clearer copy               [Review]
  Couldn't read: scan_036                   Upload a clearer copy               [Review]

 ⚠ Setup incomplete: connect a mailbox for automatic intake   [Open settings]   (only if relevant)
```
**Removed:** explainer banner, Operational Readiness strip, Pipeline Velocity strip, Integration Pillars, Recent Audit Trail, duplicate MSME note. **Kept:** the prioritised queue and the three counts, each linking to a list that contains what it counts. *Benefit:* one screen, no scrolling, no repeated "3" (F-TODAY-1).

The statutory MSME deadline stays, as a single badge on the specific invoices it applies to (see `docs/KNOWN_LIMITATIONS.md` R-01 for its deferred edge cases), not as a paragraph on every page.

### 4.4 Invoice review: the decision screen

**Information hierarchy (top to bottom, nothing scrolls before the user knows what to do):**

```
← Invoices     AP-26-011 · Asterion Precision Components          ₹25,960.00
────────────────────────────────────────────────────────────────────────────
 ● NEEDS YOU: price and inspection problems — can't approve yet
   1. Price is 18.9% above the order      Billed ₹X/unit · Ordered ₹Y/unit
   2. Inspection not recorded             No inspection record for this delivery
   Recommended: [ Ask supplier to correct ]            More actions ▾

 ┌ Does it match? ─────────────────────────────────────────┐ ┌ Invoice ─────────────┐
 │            Billed      Ordered     Delivered   Inspected │ │  [ PDF viewer ]      │
 │ Quantity     80          80          80          —  ⚠   │ │                      │
 │ Price/unit  ₹X         ₹Y           —           —       │ │                      │
 │ Total     ₹25,960     ₹14,800        —           —  ⚠   │ │                      │
 │ Tax          ✓ adds up · correct state split             │ │                      │
 │ Supplier     ✓ approved   Duplicate  ✓ none found         │ │                      │
 └──────────────────────────────────────────────────────────┘ └──────────────────────┘
 ▸ Details (extracted fields · all checks · history)   ← collapsed
```

**What changes and why**
- **One banner, three possible states.** *Ready* (green), *Needs you* (amber, with numbered reasons), *Couldn't read* (grey, one action). The "Decision Guide" strip is removed because it restated the banner (F-DETAIL-4, F-DETAIL-6).
- **A single comparison table (Billed / Ordered / Delivered / Inspected)** replaces the four-box "Procurement Verification Flow", the Policy Checks tab and most of the Matching tab. Cells with no data show "—" and a small "not recorded" note, never a pass. *Benefit:* the central idea of the product ("approve only when invoice, order, delivery and inspection agree") is visible in one glance, and the P0-1 contradiction cannot recur because verdict and evidence come from the same data.
- **Reasons are sentences with numbers**, not file names (F-DETAIL-3).
- **One recommended action, highlighted**; the other five behind "More actions". The recommendation is derived from the first failing check using a fixed table (see §5.3). *Benefit:* a first-time user is never asked to choose among six equal buttons (F-DETAIL-5).
- **PDF stays visible** beside the comparison; it is the proof the user trusts. The "Expand Analysis", Glossary, Tour buttons and tab strip are removed from this screen (they live in Help).
- **"Details" collapse** holds extracted fields, the full list of checks, and invoice history. Hidden by default, not removed. *Benefit:* power users and auditors keep full access.

**State variants**
- **Ready:** banner "Ready to approve: matches order, delivery and inspection." Primary action **Approve**. Comparison table all ✓.
- **Needs you:** as drawn above.
- **Couldn't read:** banner "We couldn't read this document." Table not shown; only the PDF and two actions, *Upload a clearer copy* and *Reject / set aside*. No gate list. *Benefit:* removes six misleading failures (P0-2).
- **Dual control (≥ ₹5,00,000):** banner "Needs a second approval from a Controller." The first approver sees *Approve (first sign-off)*; the second approver (a different user, role Controller or System Admin) sees *Approve (final)*. Unchanged rules, clearer wording.
- **Auditor:** same screen, actions replaced by "View only".

**Components affected:** `InvoiceDetailPage.tsx` (largest change; 1,182 lines to be split), `CaseSummaryCard.tsx`, `ProcurementVerificationFlow.tsx` (reshaped into the comparison table), `PolicyChecksGrouped.tsx` (moved under Details), `StatusBadge.tsx`, `statusNormalizer.ts`.
**Backend dependencies:** line-level or total-level delivered and inspected quantities must come from the same snapshot tables the gates use; for unreadable documents a "not evaluated" gate status (see §5.2).

### 4.5 Approve dialog

```
Approve AP-26-009?                                        ₹2,31,280.00
 Asterion Precision Components · matches order, delivery and inspection

 Reason (kept in the history)
 [ All checks matched the order, delivery and inspection records.      ]  ← pre-filled, editable
 [ Variance within agreed tolerance ] [ Goods receipt confirmed ]  ← other quick reasons

 Approving records your sign-off. It does not pay the supplier or change your accounting system.

                                              [ Cancel ]   [ Approve ]
```

- **~600 words → ~40.** Removed: state names, the "Resulting workflow state" section, the "Does this require another person" section (shown in the dialog only when it applies: "This is above ₹5,00,000, so a Controller must also approve"), and the four-bullet "does NOT" box (merged into one sentence).
- **Reason remains mandatory.** It is pre-filled for invoices where every check passed, and the approver can edit it. *Benefit:* 5 clicks becomes 3 (open, Approve, Approve) without removing the audit justification.
- **Decision needed from the finance owner (not made here):** whether a pre-filled reason is acceptable as the audit justification, or whether the approver must type or explicitly pick one. Two safe options: (a) require the approver to select a chip (still 4 clicks); (b) pre-fill but record in the audit event that the system text was accepted unchanged. Option (b) needs a small audit-payload addition. The backend today enforces a minimum 3-character reason per action [D: `PRODUCT_CAPABILITY_TRUTH.md` §A.6].
- For **Reject, Hold, Ask supplier, Debit note, Escalate, Set aside**: same short dialog, but the reason is **never pre-filled** because these are exceptions needing a human reason, and each dialog states plainly what does *not* happen, for example "This marks the invoice as waiting on the supplier. No email is sent." (`PRODUCT_CAPABILITY_TRUTH.md` §D [D]). *Benefit:* no false belief that the supplier was contacted (P1-8).

**Components affected:** `ConsequenceAwareActionModal.tsx`.
**Backend dependencies:** none for the UI change; optional audit flag per option (b).

### 4.6 Upload and processing: the "live run" replacement

**Where it appears:** inline on the Invoices page, as a row that updates in place, and optionally as an expandable "Progress" strip on the invoice screen. No separate "Live Run" app.

```
 Reading…  10_invoice_KF_26_015.pdf
 ● Received   ● Reading…   ○ Checking   ○ Ready for you
```
Possible end states, each a sentence:
- "Ready to approve." (links to the invoice)
- "Needs you: price is 18.9% above the order." (links to the invoice)
- "Couldn't read this document. Upload a clearer copy or enter the details." (links to the invoice)
- "Something went wrong on our side and your invoice was not processed. [Try again]" (shown when the job is `FAILED`)

**Rules to keep this truthful**
1. Show a stage only if the backend reports it. Four states are available from job and invoice status: Received, Reading, Checking-or-done, Ready/Needs you/Couldn't read/Failed. If "Reading" and "Checking" cannot be told apart, show one combined "Processing" state.
2. **No millisecond timers.** They measure compute, not what the user waits for (audit F-LEGACY-2).
3. **No success ticks on a stage that ended in rejection.** The legacy page showed five green ticks on a REJECTED duplicate (F-LEGACY-3). Use outcome wording ("Duplicate found") rather than a tick.
4. **A stalled job must show.** If the job is `FAILED` or older than a threshold without progress, say so.
5. **No fake stages.** Retire the `asyncio.sleep` + hard-coded `SUCCESS` stream (`engine/server.py:163-209`), or replace it by events emitted from the real pipeline.

**Legacy app decision (P0-6).** The `engine/server.py` + `index.html` app uses USD and different sample data from the GST product, and is not in the Docker image's entry point. Recommendation: **retire it as a demo surface**; if a scripted demo is wanted, run the real React flow on seeded data. If it is kept, it must follow the rules above, load its scripts locally (no `cdn.tailwindcss.com` or `unpkg …@latest`), and drop the "PEV", "AOP", "CFO Audit Trail" language.

**Components affected:** new small `ProcessingStatus` component; `InboxPage.tsx`; `InvoiceDetailPage.tsx`; `OnboardingPage.tsx` (step 5 reuses it); `api/client.ts` (polling).
**Backend dependencies (required):**
1. Return per-invoice ingestion job status and `error_message` in the inbox and invoice-detail responses (fields exist: `domain.py:653-655`).
2. Poll or stream while any job is `QUEUED` or `PROCESSING`. Polling every 2-3 seconds is enough; the SSE approach is not required.
3. When extraction fails, write a clear status (for example `FAILED` plus message) instead of leaving the invoice at `RECEIVED – Awaiting pipeline execution` forever (observed [B]).

### 4.7 Approvals

```
Approvals          Waiting on a second approval: 0
 Invoices of ₹5,00,000 or more need two people.
 (empty state)  "Nothing waiting. Invoices over ₹5,00,000 appear here after the first approval."
```
- Tab counts and the sidebar badge use **the same number**: invoices waiting for a *second* approver. "Ready to approve" lives on Invoices. (P0-4, F-APPR-1)
- Controllers see "Waiting for you"; others see "Waiting on a Controller".
**Components:** `ApprovalsPage.tsx`, `AppShell.tsx`, `Sidebar.tsx`. **Backend:** align the `approvals` list and the `dashboard` counts on one definition (`dashboard.py:112-144`, `approvals.py:30`).

### 4.8 History (was Audit)

Retitle and simplify; keep the table, filters, export and role gating.
```
History   Every action is recorded and can't be edited.            [Export CSV]
 Time · Who · What they did · Invoice · Reason          [What changed ▸]
```
Move "PostgreSQL trigger" and "Immutable" to documentation and an "About" footer. (F-AUDIT-1)

### 4.9 Settings

One page with three sections (Connections & mailbox, Procurement records, Team & access) plus the Setup checklist. Steps 2-4 of the old wizard (invite, Gmail, ERP) become their natural settings sections. *Benefit:* a first-time user is not forced through administrator tasks before seeing value (F-SETUP-2).

---

## 5. Language and status model

### 5.1 One status vocabulary (maps existing values, changes no backend value)

| Plain word | Shown when | Backend values (observed) |
|---|---|---|
| **Reading…** | upload accepted, job not finished | `RECEIVED` + job `QUEUED`/`PROCESSING` |
| **Needs you** | one or more checks failed, or doc unreadable | `ACTION_REQUIRED` (decisions `FLAGGED_EXCEPTION`, `FLAGGED_HITL_REVIEW`) |
| **Ready** | all checks passed, no one has approved | `PENDING_APPROVAL` (`MATCH_CANDIDATE`) |
| **Waiting for second approval** | first approver done, ≥ ₹5,00,000 | `ACTION_REQUIRED` + `PENDING_SECOND_APPROVAL` |
| **On hold / Waiting on supplier / Escalated** | those actions taken | `ON_HOLD`, `SUPPLIER_CORRECTION_REQUESTED`, `ESCALATED`, `DEBIT_NOTE_PENDING` substatuses |
| **Approved** | final sign-off | `INTERNAL_APPROVAL_COMPLETE` (`MANUALLY_APPROVED`) |
| **Rejected / Set aside** | rejected or quarantined | `REJECTED`, `QUARANTINED` |

### 5.2 One check vocabulary

Show **plain questions**, not "Gate N":

| Question shown | Today's gate |
|---|---|
| Is the supplier approved? | 1 |
| Is there a valid purchase order with budget left? | 2 |
| Was the delivery recorded? | 3 |
| Did the delivery pass inspection? | 4 |
| Does the tax add up? | 5 |
| Do price and quantity match the order (±1.5%)? | 6 |
| Is it a duplicate? | 7 |

Each check has three states: **Yes**, **No**, **Not checked**. "Not checked" is required for unreadable documents and for missing reference data. Gate numbers stay in the technical "Details" and in the audit trail.

*Backend note:* today unreadable scans store gates 1-6 as FAIL [B]. Interim (UI-only): when `decision = FLAGGED_HITL_REVIEW` and no invoice number was read, display the "Couldn't read" state and ignore the stored gate failures. Proper: have the pipeline store a `NOT_EVALUATED` gate status.

### 5.3 Reason and recommended-action table

| First failing check | Reason sentence (with numbers) | Recommended action |
|---|---|---|
| Unreadable document | "We couldn't read this document." | Upload a clearer copy |
| Supplier not approved | "Supplier [name] isn't on your approved list." | Reject, or Escalate |
| No valid PO / no budget left | "No open purchase order with enough budget." | Ask supplier to correct, or Escalate |
| Delivery not recorded | "No delivery recorded for this order." | Hold for evidence |
| Inspection not passed / not recorded | "Inspection [failed / not recorded]." | Hold for evidence |
| Tax doesn't add up | "Tax adds up to ₹X, invoice says ₹Y." | Ask supplier to correct |
| Price / quantity mismatch | "Price is X% above the order (limit 1.5%)." | Ask supplier to correct, or Raise debit note |
| Duplicate | "Looks like a duplicate of [invoice], processed [date]." | Reject |

These replace the six-bullet "Failing checks & required next actions" block and the raw filenames. (F-DETAIL-2, 3, 5)

---

## 6. Click-reduction summary

| Task | Today | Proposed | How |
|---|---:|---:|---|
| Upload an invoice (after login) | ~6 | **1** (+ file choice) | Upload button on Invoices; wizard no longer in the path |
| Approve a clean invoice (from list) | 5 | **3** | Review → Approve → Approve; reason pre-filled and editable (pending finance-owner decision) |
| Find what needs me | Today, then list, with a dead-end card | **1** | Invoices opens on "Needs you" when non-empty |
| Understand why one invoice is blocked | open + read banner + Decision Guide + flow + tab | **0 extra** | reasons and comparison table on first screen |
| Find a past decision | Audit (4 filters) | unchanged | already adequate |

---

## 7. Prioritised work plan

Each item: observed problem, benefit, components, backend dependencies. Finding IDs refer to the audit §9.

### P0: fix before any further demo or evaluation

| ID | Change | Observed problem | Benefit | Components | Backend dependency |
|---|---|---|---|---|---|
| P0-1 | Verdict must agree with evidence; show "Not recorded" instead of passing; comparison table | "All 7 passed" beside "Unavailable"; Billed ≠ PO | Believable verdicts | `CaseSummaryCard`, `ProcurementVerificationFlow`, `PolicyChecksGrouped`, `InvoiceDetailPage` | Seed (or real data) must include GRN/QC records; gate and panel read the same source |
| P0-2 | "Couldn't read" state; stop cascading failures | 6 false failures on a scan | One truthful message | `InvoiceDetailPage`, `statusNormalizer`, `InboxPage`, `DashboardPage` | Interim: UI derivation; proper: `NOT_EVALUATED` gate status |
| P0-3 | Upload on Invoices | Upload hidden in wizard step 5 | 1-click upload | `InboxPage`, `OnboardingPage` | None |
| P0-4 | Fix dead-end card and badge/page mismatch | 0-row list; badge 2 vs 0 | Counts lead somewhere | `DashboardPage.tsx:236`, `AppShell.tsx:36-47`, `ApprovalsPage` | One definition of ready/waiting in `dashboard.py` and `approvals.py` |
| P0-5 | Real processing status and visible failure | One line then nothing | User sees progress or failure | `ProcessingStatus` (new), `InboxPage`, `api/client` | Expose job status/`error_message`; poll |
| P0-6 | Retire or fix legacy live run | Sleeps + hard-coded SUCCESS | No false progress | `engine/server.py`, `engine/templates/index.html` | Product-owner decision |

### P1: core usability

| ID | Change | Benefit | Components | Backend dependency |
|---|---|---|---|---|
| P1-1 | Slim Today (or fold into Invoices) | One glance, no scroll | `DashboardPage` | None |
| P1-2 | Short approve dialog; 3-click approval | Faster routine work | `ConsequenceAwareActionModal` | Finance-owner decision on reason; optional audit flag |
| P1-3 | "Why / next" column in list | Triage without opening | `InboxPage` | Confirm `decision_reason` in list payload |
| P1-4 | Plain reasons, no filenames or enums | Readable | `statusNormalizer`, `PolicyChecksGrouped`, `StatusBadge` | Readable gate notes or UI mapping |
| P1-5 | Rebuild invoice screen per §4.4 | Evidence beside verdict; one action | `InvoiceDetailPage` (split), `CaseSummaryCard` | UI-derived recommendation table |
| P1-6 | Remove Exceptions page; one vocabulary | One list | `ExceptionsPage`, `App.tsx:156` | None |
| P1-7 | Quiet the chrome; Help menu | Calm pages | `AppShell`, `Sidebar`, `HRShowcaseModal`, `GlossaryModal`, `KeyboardShortcutsModal` | None |
| P1-8 | Honest action wording | No false "supplier contacted" belief | action dialogs | None |

### P2: polish and follow-ups

| ID | Change | Components | Backend dependency |
|---|---|---|---|
| P2-1 | Login and History wording | `AuthScreen`, `AuditPage` | None |
| P2-2 | Footer environment from backend | `AppShell.tsx:82,229` | `/health` `app_env` |
| P2-3 | Legacy page: local scripts, fix JS error | `engine/templates/index.html` | None |
| P2-4 | No-AWS-key seed path with GRN/QC and several suppliers | `engine/sme_eval_setup.py` | Data additions |
| P2-5 | Reconcile docs (₹20 vs ₹1; outdated tour text) | docs, tour text | Confirm engine tolerance |
| P2-6 | Bulk approve of clean invoices | `InboxPage` | **Only after P0-1**, with an owner-set value cap and an audit record per invoice |

---

## 8. What is deliberately preserved (control checklist)

| Control | Status in this blueprint |
|---|---|
| Approval blocked while any check fails | Preserved; the approve button is absent or disabled with a reason |
| No gate overrides (D-04) | Preserved |
| Dual control ≥ ₹5,00,000 | Preserved; wording clarified |
| Anti-self-approval; second approver = Controller or System Admin | Preserved (server-enforced; UI only reflects it) |
| Mandatory reason on every action | Preserved; pre-fill only for all-checks-passed approvals, pending owner decision |
| Auditor read-only | Preserved |
| Append-only audit, CSV export | Preserved; renamed History |
| Tenant isolation, signed document URLs | Untouched (backend) |
| "No payment, no ERP posting" | Preserved; stated once at point of approval |
| Duplicate detection, GST checks, MSME deadline | Preserved; MSME shown as a per-invoice badge |

---

## 9. Acceptance tests (buyer-first)

1. **Five-second test.** Show Invoices to someone unfamiliar for five seconds; they can say how many invoices need them and which is most urgent.
2. **No-contradiction test.** For each seeded state, every number and verdict on the invoice screen is consistent (no "passed" next to "unavailable"; no "failed" for a check that did not run).
3. **Click budget.** Upload ≤ 1 click to the chooser; approve a clean invoice ≤ 3 clicks; reach any needs-you invoice ≤ 2 clicks.
4. **Dead-end test.** Every card, badge and count lands on a list containing exactly that many items.
5. **Failure visibility.** With no AI key configured, an uploaded invoice shows a clear "could not be processed" state within the polling window, not "registered into queue" indefinitely.
6. **Vocabulary scan.** No visible string matches: `APPROVE_AP_REVIEW`, `INTERNAL_APPROVAL_COMPLETE`, `FLAGGED_`, `MATCH_CANDIDATE`, `.csv` as a reason, `PEV`, `AOP`, `JWT`, `Supabase`, `PostgreSQL` in the main user path.
7. **Word budget.** Invoices ≤ 150 words; invoice screen above the fold ≤ 150 words; approve dialog ≤ 60 words.
8. **Control regression.** Existing tests for dual approval, anti-self-approval, auditor 403s, and blocked approval still pass (the repo reports 266 passing, 12 skipped [D]; not re-run in this audit).
9. **Role pass.** Repeat 1-4 as Controller and Auditor (not covered by this audit).

---

## 10. Open questions for the product owner

1. May a clean-match approval carry a pre-filled reason (§4.5), and if so, should the audit record flag that it was accepted unchanged?
2. Is the legacy live-run app retired, or kept as a scripted demo (and then made truthful)?
3. Should Today remain a page, or become the summary strip on Invoices?
4. Which rounding tolerance is intended for GST arithmetic: ₹1 (one doc) or ₹20 (config and rules doc)?
5. Is a bulk-approve value cap acceptable, and who sets it?

---

## 11. Things this blueprint does not claim

- It does not claim the live LLM extraction behaves well or badly on real invoices (not exercised).
- It does not claim the PDF viewer works or fails (headless browser limitation).
- It does not propose capabilities the product lacks: no outbound supplier email, no payment, no ERP posting, no bounding-box overlay, no vendor portal (`PRODUCT_CAPABILITY_TRUTH.md` §D).
- Backend dependencies listed above are based on reading models and endpoints; each should be confirmed by the implementing engineer before work starts.
