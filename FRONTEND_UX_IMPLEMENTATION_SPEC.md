# AP Command Center — Frontend UX Audit & Implementation Specification

| | |
|---|---|
| **Repository audited** | `neerajs22is-ux/Zamp-Case-Study-PS-1-` @ commit `cda5c44` (2026-11-01) |
| **Audit method** | Static review of source code, schema, seed scripts, test-corpus metadata and the repo's own documentation. |
| **Not done** | The application was **not run**, the 244-test suite was **not executed**, no live service (Supabase, Bedrock, Gmail, SAP) was contacted. Anything that depends on runtime behaviour is marked `[?]`. |
| **Scope** | Specification only. No application code was written or changed; nothing was deployed. |
| **Audience** | A coding agent implementing the redesign, and the product owner approving scope. |

---

## 0. How to read this document

### 0.1 Evidence tags (used on every claim that matters)

| Tag | Meaning |
|---|---|
| **[V]** | **Verified** — read directly in code/schema. File path given. |
| **[BX]** | **Backend exists, UI does not expose it.** Frontend-only work unlocks it. |
| **[BM]** | **Backend missing or insufficient.** Needs backend development before the UI can be real. |
| **[UX]** | **Proposed UX change.** A design decision, not an existing capability. |
| **[?]** | **Unverified** — could not be confirmed from static inspection. |

### 0.2 Priority tags

- **P0** — essential for a usable end-to-end product.
- **P1** — important UX improvement.
- **P2** — refinement.

### 0.3 Work-type tags

- **FE** — frontend-only. **BE** — requires backend change. **FE+BE** — both.

### 0.4 Ground rule followed throughout

Nothing in this document treats planned functionality as implemented. Where the repo's README or `docs/` describe something the code does not contain, §1.3 lists the discrepancy and the spec follows the **code**.

---

# 1. Executive Summary & Current UX Assessment

## 1.1 The one-paragraph verdict

The existing frontend is an honest, tenant-aware operations shell — it never fabricates data and it surfaces real database state. But it is organised around **system components** (Connections, Source Records, Audit Ledger, "Pane 1/2/3") rather than around **the invoice workflow** a clerk performs. More importantly, an audit of the code shows that **the product's central promise — upload or email an invoice and have it extracted, matched and routed — is not reachable through the web application as shipped**. Uploads and Gmail sync create a `RECEIVED` invoice and a `QUEUED` job; nothing in `backend/` consumes that job or calls the extraction/matching engine. The impressive review-workspace data in the demo tenant is produced by a separate CLI seed script. A redesign must therefore do two things at once: make the workflow obvious and calm, **and** be truthful about the one dependency (B-01) that decides whether the product is a demo or a product.

## 1.2 Headline findings (all verified)

| ID | Finding | Evidence | Impact |
|---|---|---|---|
| **F-01** | **Ingestion does not trigger processing.** Manual upload creates `Invoice(stage="RECEIVED", decision="NEEDS_REVIEW")` + `IngestionJob(status="QUEUED")` with reason "Awaiting pipeline execution." Gmail sync does the same. No module under `backend/` imports `engine/`; the only code that writes `ExtractionRun`, `ExtractedField`, `MatchRun`, `MatchGateCheck`, `ExceptionRecord` is `engine/sme_eval_setup.py` (a CLI seeder). | `backend/api/v1/documents.py` L165-180; `backend/core/gmail.py` L534-556; grep for `from engine` in `backend/` returns nothing | A real customer's uploaded invoice sits in "Received" forever with no fields, lines or gates. **Blocks onboarding step 5-6 and the whole daily workflow in a non-seeded tenant.** → **B-01 (P0)** |
| **F-02** | **Seeded decisions are labelled, not computed.** The seeder maps scenario → stage/decision with `if scenario_type == …` (e.g. `CLEAN_3WAY_MATCH → PENDING_APPROVAL / MATCH_CANDIDATE`). Gate 6 is `PASS` iff the scenario label is clean. Every extracted field gets a hard-coded confidence of 0.99 (0.95 for PO ref). | `engine/sme_eval_setup.py` L249-263 (label→decision), L448 (gate 6), L398-412 (confidence) | The "99% conf" the UI shows is not a measurement. The demo is valid for teaching the **UI**, not as proof of automated accuracy. The UI must not over-emphasise confidence. |
| **F-03** | **The review workspace does not show the document or the PO comparison.** Pane 1 renders filename/SHA/size and a "Full PDF" link that opens a signed URL in a new tab. Pane 2 lists only *billed* lines — the API returns no PO lines, so there is no side-by-side. Gate `notes` and `evidence_source_id`, field `bounding_box`/`source_page` are returned by the API but never rendered. | `frontend/src/pages/InvoiceDetailPage.tsx` L125-215 (Panes 1-2), L139 ("Full PDF"); `backend/api/v1/invoices.py` L64-83, L110 | The page's core job — "show me why this was flagged and what to do" — is not done. |
| **F-04** | **Action set is incomplete and unvalidated.** UI offers 4 actions. Backend supports 7 (`APPROVE_AP_REVIEW`, `APPROVE_UNDISPUTED`, `HOLD_PENDING_EVIDENCE`, `REQUEST_SUPPLIER_CORRECTION`, `RAISE_DEBIT_NOTE`, `ESCALATE`, `QUARANTINE`). **There is no reject action anywhere** (`REJECT_INVOICE` does not exist). Unknown action strings fall into an `else` branch and are accepted. | `invoices.py` L170-293; grep `REJECT_INVOICE` → 0 hits | A clerk cannot reject a duplicate. Typos succeed silently. |
| **F-05** | **Exceptions are never closed.** `ExceptionRecord.status` supports `OPEN/IN_REVIEW/RESOLVED`, but no code ever changes it. After approve/quarantine, the invoice stays in the Exceptions queue and in "Open exceptions"/"Blocked value". | grep: no write to `ExceptionRecord.status` in `backend/` | The queue never empties; the dashboard KPI is permanently wrong after any action. → **B-02 (P0)** |
| **F-06** | **Inbox cannot reach most records and cannot filter its own data.** There are no next/prev controls (`setPage` is only ever called with `1`) so only the first 25 rows are reachable. Filter dropdowns offer raw enums that omit values the data actually contains (`PENDING_APPROVAL`, `INTERNAL_APPROVAL_COMPLETE`, `QUARANTINED` stages; `MATCH_CANDIDATE`, `FLAGGED_EXCEPTION`, `FLAGGED_HITL_REVIEW` decisions). Those rows render with the "unknown" purple badge. Load errors go only to `console.error`. | `InboxPage.tsx` L25, L165-185 (filters), L40 (`console.error`), L76 (badge); `sme_eval_setup.py` L249-263 | Seeded scenarios 1-3 are invisible to the filters and mislabelled. **P0 bug.** |
| **F-07** | **Overloaded `ACTION_REQUIRED`.** Hold, request-correction, escalate, debit-note, and "first approver signed, awaiting second" all set `stage=ACTION_REQUIRED` and leave `decision` unchanged. Only a free-text `decision_reason` distinguishes them. | `invoices.py` L196-266 | The UI cannot tell "needs first review" from "on hold" from "waiting for Controller". → **B-03 (P0)** |
| **F-08** | **Connections page conflates five jobs and reads the wrong Gmail status.** One page holds manual upload, a document catalogue (download/delete), four integration cards, and a quarantine table. The Gmail card uses `/connections` (environment-level: `settings.is_gmail_configured()`), not the tenant-level `/integrations/gmail/status` — which `api.getGmailStatus()` wraps but nothing calls. So "last synced", "initial sync pending" are never populated, and the card can say CONNECTED when no mailbox has been authorised. The OAuth callback redirects to `/connections?gmail=connected&mailbox=…`; the SPA never reads the query string. | `ConnectionsPage.tsx`; `connections.py` L47-58; `integrations_gmail.py` L52-140, L261; grep `gmail=` in `frontend/src` → 0 hits | The single most important onboarding step has no confirmation and misleading state. |
| **F-09** | **Dashboard is KPI-led, not task-led, and its copy is inconsistent.** Four count tiles + two enum lists. Fixed stage/decision lists omit seeded values. Copy says "5-way reconciliation" (engine has 7 gates). `touchless_rate_pct` and `active_ingestion_jobs` are computed by the API but never shown. Metric queries have no explicit `org_id` filter (isolation relies on Postgres RLS; the live cross-tenant RLS tests are among the 12 skipped tests). | `DashboardPage.tsx`; `dashboard.py` L48-93; `PROJECT_STATUS.md` §4 | Not actionable; potentially leaks cross-tenant counts if RLS is off `[?]`. |
| **F-10** | **ERP "Source Records" is empty by construction.** No non-test code populates PO/GRN/QC snapshot tables; there is no ERP sync endpoint; `origin_system` is a hard-coded string. The schema *does* have PO line tables (`erp_po_lines`, GRN lines) that the API never returns. | `source_records.py`; grep for snapshot constructors → tests only | "ERP connection" cannot be onboarded for real. Demo tenant shows vendors only. |
| **F-11** | **Team & Access has no roster.** Invite (token to copy, no email), review requests, and nothing else. `updateUserRole` / `deactivateUser` exist in the API client and backend but are used nowhere in the UI; there is no "list members" endpoint. | `AccessManagementPage.tsx`; `api/client.ts` L76-84; `auth.py` L693-780 | Admins can add people but never see or remove them. |
| **F-12** | **Audit page hides most of what the API provides.** UI filters by raw invoice ID only; API also supports `actor_id`, `action`, `correlation_id`. `before_state`, `after_state`, `source_reference` returned but not shown. Actors appear as IDs (`usr_sme_lead_01`). Hard cap 50 rows, no paging. Export button shown to every role (server allows only Auditor/Controller/Admin → `alert()`). | `AuditPage.tsx`; `audit.py` L27-121 | Auditors cannot answer "what changed, who, why" without leaving the UI. |
| **F-13** | **Visual & interaction quality is below enterprise baseline.** Dark-only theme; 96 uses of 10-11 px text and 154 of `text-xs` (12 px); monospace for most data; raw enum strings as labels; 9 `alert()` and 2 `window.confirm()` calls; **0 keyboard handlers**; 2 ARIA/role attributes in the whole app; fixed `h-[750px]` panes; footer reads "Binding Production Engineering Specification © 2026". Custom hash "router" in `App.tsx` drops selected-invoice state on navigation. | `grep` counts on `frontend/src`; `App.tsx` | Fatiguing for an 8-hour AP shift; not accessible; no back-to-queue context. |
| **F-14** | **Permission affordances do not match server rules.** Server: Auditor is read-only on actions; invitations and Gmail authorise require Admin/Controller/AP Lead; audit export requires Auditor/Controller/Admin; `POST /integrations/gmail/sync` and `POST /exceptions/{id}/reassign` need only an active membership (no role/read-only check; reassign also has no tenant filter). UI shows every action button to every role. | `auth.py` L249-253; `integrations_gmail.py` L140-146, L266-275; `exceptions.py` L77-95 | Auditors see "Approve" buttons that 403; Associates see "Connect Gmail" that 403s; two server gaps listed in §9. |

## 1.3 Documentation vs. code — discrepancies the implementer must not inherit

| README / docs claim | What the code shows | Spec treats as |
|---|---|---|
| "Pane 1 … rendering original PDF pages" | No PDF rendering; link out to signed URL (F-03) | Not implemented |
| "Pane 2 … comparing invoice lines against PO contracted rates" | Billed lines only; API returns no PO lines (F-03) | Not implemented; needs B-05 |
| "Action modal requires justification … `REJECT_INVOICE`" (`KNOWN_LIMITATIONS.md` §C) | Inline textarea; no reject action exists (F-04) | Not implemented; needs B-07 |
| "Search bar in Inbox filters invoice_number and vendor_name" (§F) | No search UI; API has a `vendor` filter only | Not implemented |
| "Real-time SSE stream support" in React SPA | No `EventSource` in `frontend/`. An SSE server exists in `engine/server.py`, a **separate** app on a mock ERP that the SPA does not call | Not connected |
| "Approved invoices … exported via batch voucher API" | No voucher/export code in `backend/` | Not implemented; UI must not imply export |
| "Secondary **Controller** sign-off" | Server requires only a *distinct user* for the second approval, not the Controller role | Policy gap; B-08 |
| "5 roles" | 6 in `UserRole` (adds `CATEGORY_MANAGER`, offered in invite UI, no behaviour attached) `[?]` | Treat as 6; Category Manager has no verified distinct capability |
| "Tailwind 3.4" | `package.json` has Tailwind `^4.3.3` (CSS-first `@import "tailwindcss"`) | Use v4 conventions |
| Persona names/emails (Priya Sharma, `sme_assoc@…`) | Seed uses `sme_associate@company.internal`, display names "SME AP Lead" etc. | Use the seed values |
| "7-gate engine runs on every invoice" | Only in the seeder/engine, not the API (F-01) | Conditional on B-01 |

## 1.4 Current page assessment

| Page (current) | What it does today `[V]` | Main problems | Verdict |
|---|---|---|---|
| Sign-in (`AuthScreen`) | Google via Supabase; dev quick-login when `!PROD`; accept-invite by pasting token; request access by **typing an org ID** | Org ID must be known; token paste; no invite link | Keep, simplify |
| Dashboard | 4 KPI tiles + stage list + decision list | Not task-led; raw enums; missing seeded values; wrong copy | Rebuild as **Today** |
| Connections | Upload + doc catalogue + 4 cards + quarantine | Five jobs on one page; wrong Gmail source; OAuth return unhandled | Split three ways |
| Invoice Inbox | Table, 2 enum filters, "Sync Mailbox" | No paging, no search, silent errors, filter/data mismatch | Rebuild |
| Invoice Detail | 3 fixed panes | No document, no PO compare, no guidance, `alert()`, all buttons for all roles | Rebuild (**most important**) |
| Exceptions | Table sorted by statutory deadline then exposure | Never empties (F-05); no assign; MSME copy says "Unestablished" | Merge into Invoices as "Needs attention" |
| ERP Source Records | 4 read-only lists | Empty in practice; no search; no PO lines | Move under Settings → Reference data |
| Audit Trail | Table + CSV export | Hides state diff; IDs not names; no paging | Rework |
| Team & Access | Requests + invite | No roster; role change/deactivate unused | Rework |

## 1.5 Design direction in five sentences

1. Organise by **what the user is doing** (Today → Invoices → Review → Approvals → Audit), and push system plumbing into **Settings**.
2. Replace every raw enum with a **plain-language status** and a one-line **reason**; keep raw values in a "Details" disclosure.
3. Make the review workspace answer three questions in order: *what is this, why is it blocked (or clear), what should I do next* — with the document always one glance away.
4. Be strictly truthful: label unprocessed invoices as "Received — not yet extracted", never imply payment or ERP posting, and mark demo data as synthetic.
5. Default to a **light, 14 px, high-contrast** interface with full keyboard support; offer dark as an option later.


---

# 2. Target Users & Core Workflows

## 2.1 Users and what each is responsible for

Roles are the six in `UserRole` (`backend/core/auth.py` L39-46). Permissions below are **only what the server code enforces** `[V]`; anything else is a UX convention that should be confirmed with the product owner.

| Persona (seed name) | Role | Day-to-day job | Server-enforced limits `[V]` |
|---|---|---|---|
| **AP Associate** — "SME AP Associate" `sme_associate@company.internal` | `AP_ASSOCIATE` | Gets invoices in, triages, chases suppliers, resolves simple exceptions | Can act on invoices (not read-only). **Cannot** issue invitations, authorise Gmail, export audit CSV |
| **AP Lead** — "SME AP Lead" `sme_lead@company.internal` | `AP_LEAD` | Owns the exception queue; approves below threshold; connects Gmail; invites team | Can invite, authorise Gmail. Cannot review access requests (Admin/Controller only, per UI) |
| **Financial Controller** — "SME Financial Controller" `sme_controller@company.internal` | `CONTROLLER` | Second approval on high-value invoices; reviews access requests; audit oversight | Can invite, authorise Gmail, export audit |
| **Auditor** — "SME Auditor (Read-Only)" `sme_auditor@company.internal` | `AUDITOR` | Inspects history and evidence; exports audit | `is_read_only()` → invoice actions return 403. Can export audit |
| **System Admin** | `SYSTEM_ADMIN` | Tenant setup, user lifecycle | Only role that may invite another `SYSTEM_ADMIN` |
| **Category Manager** | `CATEGORY_MANAGER` | "Commercial reviews" (label in invite UI only) | No distinct behaviour found `[?]`. Treated as an Associate-equivalent until product owner defines it |

> **High-value rule `[V]`:** `total_amount >= DUAL_APPROVAL_THRESHOLD_INR` (default ₹5,00,000, `config.py` L129) needs two approvals by two **distinct** users. The server does **not** require the second user to be a Controller (F-14 / B-08).

## 2.2 The core AP workflow (as the UI must teach it)

```
 ARRIVE            PROCESS            TRIAGE            REVIEW              DECIDE                RECORD
 ───────           ───────            ──────            ──────              ──────                ──────
 Gmail sync   ─►   Read the doc  ─►   Is it OK?    ─►   Open workspace ─►   Approve        ─►   Audit trail
 PDF upload        Extract fields     ├ Ready to        See document,       Hold for evidence    (who/what/why,
                   Match vs PO/GRN/   │  approve        evidence, gates     Ask supplier to      before→after)
                   QC, GST, dupes     ├ Needs           Read the verdict    correct
                                      │  attention                          Quarantine
                                      └ Not an                              Escalate / Debit note
                                         invoice                            (Reject: needs B-07)
        [B-01: not wired]
```

**Boundary the UI must state plainly `[V]`:** an approval means *internal AP review is complete*. The system does **not** pay, does **not** post to the ERP, and there is **no export** (invoices.py module docstring: "internal approvals never claim ERP posting or payment"). Every approved state must carry the label **"Approved for payment run — no payment or ERP posting has been made"**, wording to be confirmed by the product owner.

## 2.3 A typical working day, per role

| Time | Associate | Lead | Controller | Auditor |
|---|---|---|---|---|
| Start | Open **Today** → "Needs attention" list is the first thing visible | Same, plus "Waiting for second approval" | "Waiting for my approval" first | Open **Audit**, filter yesterday |
| Mid | Upload/forward new invoices; clear *Ready to approve*; place holds | Work the exception queue by due date; reassign | Second-approve high-value; review access requests | Open an invoice → History tab → state diff |
| End | Check nothing due within 3 days is untouched | Review holds older than 5 days | Spot-check approvals | Export CSV |

## 2.4 What a first-time user must experience

1. Within 60 seconds they know **what this tool does** (one sentence, one diagram).
2. Within 5 minutes an admin has **one real or demo invoice on screen** with a clear verdict.
3. They are never asked to understand "stage", "decision", "gate", "pillar" or "tenant" vocabulary to proceed.
4. At every moment there is **one obvious next action**.

---

# 3. Proposed Information Architecture

## 3.1 Navigation (left sidebar, replaces the 7-tab top bar)

```
┌ AP Command Center ───────────────┐
│ ▣ Acme Manufacturing        ▾    │  workspace switcher (only if available_orgs > 1) [V: /auth/me]
├──────────────────────────────────┤
│ ◉ Today                          │  P0  (was Dashboard)
│ ▤ Invoices                  (12) │  P0  (was Inbox + Exceptions + Quarantine)
│ ✓ Approvals                  (2) │  P1  (new; needs B-10)
│ ⏱ Audit                          │  P0
│ ─────────                        │
│ ⚙ Settings                       │  P0
│    Connections                   │       (was Connections, slimmed)
│    Reference data                │       (was ERP Source Records)
│    Team & access                 │       (admin roles only)
├──────────────────────────────────┤
│ ● Setup 3 of 5 complete →        │  checklist, until done (§4)
│ ● All systems normal             │  health pill → Settings ▸ Connections
│ AL  Ananya · AP Associate   ⋯    │  user menu
└──────────────────────────────────┘
```

**Decisions and rationale**

| Decision | Why |
|---|---|
| **Merge Exceptions Queue into Invoices** as a tab ("Needs attention") | An exception *is* an invoice in a state. Two lists with different columns and no shared filters forced users to remember which list held what. The tab keeps the exception-specific columns (blocking gate, due date, exposure, owner). |
| **Move Quarantine into Invoices** as "Not invoices" tab | Today it is buried at the bottom of Connections and unreachable from any workflow. |
| **Move manual upload to Invoices → "Add invoices"** | Upload is a daily action, not an integration setting. |
| **Move document catalogue/download/delete** to the invoice workspace ("Files" in More ▾) | These are per-invoice operations. A tenant-wide file table has no daily use. |
| **ERP Source Records → Settings → Reference data** | Lookup material consulted *from* an invoice (PO link) far more than browsed. |
| **Add Approvals** (P1) | Dual-control is a real, enforced rule with no home in the UI. |
| **Keep Audit top-level** | Auditor persona's primary page; also linked from every invoice (History tab). |
| **Top bar reduced to: global health pill + user menu + (P1) search** | Removes the dense identity/health bar; "Co. Code 1000" and the hard-coded fallback "Zetwerk Manufacturing" string in `Navigation.tsx` are removed (the fallback org name is a hard-coded string, not data `[V]`). |

Role visibility `[UX]`, enforced additionally by the server `[V]`:

| Item | Associate | Lead | Controller | Admin | Auditor |
|---|---|---|---|---|---|
| Today, Invoices, Audit | ✔ | ✔ | ✔ | ✔ | ✔ (read-only) |
| Approvals | ✔ | ✔ | ✔ | ✔ | hidden |
| Settings ▸ Connections | view | view + connect | view + connect | view + connect | view |
| Settings ▸ Reference data | ✔ | ✔ | ✔ | ✔ | ✔ |
| Settings ▸ Team & access | hidden | invite only | ✔ | ✔ | hidden |

## 3.2 URL map (introduce a real router — **P0, FE**)

Current routing is `useState` + `location.hash`; navigating clears `selectedInvoiceId`, and filters/page are lost on every back-navigation `[V App.tsx]`. Use `react-router` (or equivalent) with path routes:

| Route | Screen | Query/params kept in URL |
|---|---|---|
| `/` → redirect | Today | — |
| `/today` | Today | — |
| `/invoices` | Invoices | `tab`, `q`, `page`, `sort` |
| `/invoices/:id` | Review workspace | `tab`, `from` (list URL to return to) |
| `/approvals` | Approvals (P1) | `page` |
| `/audit` | Audit | `invoice`, `actor`, `action`, `from`, `to`, `page` |
| `/settings/connections` | Connections | `gmail=connected\|error`, `mailbox` (**read this — F-08**) |
| `/settings/reference-data` | Reference data | `tab`, `q` |
| `/settings/team` | Team & access | `tab` |
| `/setup` | Onboarding wizard | `step` |
| `/accept-invite?token=` | Invite acceptance (P1) | `token` |
| `/signin` | Sign-in & access gating | — |

The server already serves `index.html` for unknown paths (`backend/main.py` L87 catch-all `[V]`), and the Gmail callback already redirects to a **path** URL (`/connections?gmail=connected…`), so path routing is compatible. Keep `/connections` as an alias redirecting to `/settings/connections` **preserving the query string**.

## 3.3 The one status vocabulary (P0, FE — mapping; BE normalisation is B-04)

The data contains these values `[V]` — the UI must map **all** of them. Never display a raw enum as a label.

| Stage → Decision (as stored) | Source | **User-facing status** | Chip colour/icon | One-line reason shown |
|---|---|---|---|---|
| `RECEIVED` / `NEEDS_REVIEW` (upload, Gmail) | `documents.py`, `gmail.py` | **Received** — *not yet extracted* | grey, ⏳ | "File received. Waiting for extraction." (Truthful until B-01.) |
| `VALIDATING`, `PARSING`, `EXTRACTED`, `MATCHING` | Offered by UI filters and dashboard; **no code in `backend/` or the seeder ever writes them `[V]`** (only B-01 would) | **Processing** | blue, ◌ | "Reading and checking the invoice…" |
| `PENDING_APPROVAL` / `MATCH_CANDIDATE` | seeder | **Ready to approve** | green, ✓ | "All checks passed. Needs your approval." |
| `ACTION_REQUIRED` / `FLAGGED_EXCEPTION` | seeder | **Needs attention** | amber, ⚠ | Blocking gate name + note |
| `ACTION_REQUIRED` / `FLAGGED_HITL_REVIEW` | seeder | **Needs attention — check scan** | amber, ⚠ | "Scan is hard to read. Verify details against the document." |
| `ACTION_REQUIRED` after Hold / Correction / Escalate / Debit note | `invoices.py` | **On hold** / **Waiting for supplier** / **Escalated** (derive from `decision_reason` prefix until **B-03**) | amber-outline | Reason text as entered |
| `ACTION_REQUIRED` + `ApprovalRequest.status = PENDING_SECOND_APPROVAL` | `invoices.py` | **Waiting for second approval** | purple, ⏸ | "First approved by {name}. Needs a different approver." |
| `INTERNAL_APPROVAL_COMPLETE` / `MANUALLY_APPROVED` | `invoices.py` | **Approved** | green solid | "Internal review complete. Not yet paid or posted." |
| `…` / `AUTO_APPROVED` | read by dashboard/inbox only; **never written `[V]`** → `touchless_rate_pct` is always `null` today | **Approved (automatic)** | green solid | same |
| `…` / `REJECTED` | read by dashboard/inbox only; **never written for invoices `[V]`** (only access-requests use the word) | **Rejected** | red | Reason |
| `QUARANTINED` / `QUARANTINED` (invoice via action) | `invoices.py` | **Not an invoice / set aside** | grey-purple | Reason |
| *(no Invoice row)* `QuarantinedDocument` | seeder, Gmail | **Not an invoice** (file) | grey-purple | `quarantine_reason` mapped: `COMMERCIAL_NON_PAYABLE_RECEIPT` → "Payment receipt"; `MALFORMED_PDF` → "File is damaged"; `FILE_TOO_LARGE` → "File too large"; `EMPTY_FILE` → "File is empty" |

Implementation: a single `statusFor(invoice, approval?) → {key, label, tone, icon, reason}` pure function, unit-tested over every row above, plus a fallback `Unrecognised status` (neutral chip + raw value in tooltip) so a new backend value never renders as a mystery purple badge (F-06).

## 3.4 Terminology (replace everywhere)

| Current | Use |
|---|---|
| Pane 1/2/3 | Document · Matching · Decision (workspace section names) |
| Gate #6 PO Price & Quantity Tolerance | "Price and quantity match the PO" (keep gate number in Details) |
| HITL | "Needs a person to check" |
| Quarantine | "Set aside (not an invoice)" |
| AOP Match engine / Deterministic Policy Gates | "Automatic checks" |
| Exposure Held / Blocked Value | "Value waiting on you" |
| MSME Statutory Due | "Payment due by law" (tooltip: MSMED Act; **wording subject to finance/legal review**) |
| Tenant / org_id / pillar | Workspace / — / — |
| Operational Justification (Mandatory) | "Reason (kept in the audit trail)" |


---

# 4. Onboarding Specification

## 4.0 Principles and hard constraints

**Principles:** one decision per screen; always show progress; every step has a *Skip for now* except sign-in; every failure has a plain-language cause and a retry; nothing is claimed that did not happen.

**Constraints that shape the design `[V]`:**

| # | Constraint | Consequence for onboarding |
|---|---|---|
| C-1 | There is **no API to create or rename an organisation** (`Organisation(` is constructed only in `domain.py` and seed/test code). A user joins an existing org by **invitation** or **access request** | "Workspace setup" cannot create a workspace today. Step 2 is **confirm workspace + invite team**; workspace create/rename is **B-14 (P1)** |
| C-2 | Gmail connect (`GET /integrations/gmail/authorize`) is limited to **SYSTEM_ADMIN / CONTROLLER / AP_LEAD** | Associates/Auditors see Step 3 as "Ask an admin to connect Gmail" with a copyable message |
| C-3 | ERP "connection" is **environment variables only**; there is **no ERP sync endpoint** and no code fills PO/GRN/QC tables | Step 4 cannot connect anything. It shows status + explicit **Skip**, and explains consequence (matching evidence will be missing) |
| C-4 | Uploads are **PDF only**, ≤ 50 MB (`MAX_UPLOAD_FILE_SIZE_BYTES`), verified by `%PDF-` header; duplicates (SHA-256) return **HTTP 409** | Step 5 copy: "PDF files up to 50 MB". Duplicate is a *success-like* state with a link, not an error |
| C-5 | After upload/sync the invoice stays **Received** until **B-01** exists | Steps 5-6 must handle "not yet extracted" honestly. In a non-seeded workspace Step 6 (guided review) is **unavailable until B-01** and is replaced by a **"Preview with demo data"** option |
| C-6 | No onboarding-state endpoint exists | Completion is **derived** from real data (see §4.9); "skipped" is stored in `localStorage` (P0) and persisted server-side later (B-14, P2) |
| C-7 | Gmail sync from the UI uses `max_messages=15` (API allows 1-50) and runs **synchronously** under a 120-s lease | Show a bounded spinner with elapsed time; handle HTTP 409 "already in progress" |

## 4.1 Flow overview

```
 Sign in ─► [Not provisioned?] ─► Join a workspace (invite / request) ──┐
    │                                                                    ▼
    └────────────────────────────────────────────────► 1 Welcome
                                                        2 Your workspace & team
                                                        3 Connect Gmail          (skippable)
                                                        4 Connect ERP            (skippable)
                                                        5 Bring in your first invoice
                                                        6 Review it together     (guided; needs B-01 or demo data)
                                                        7 You're set up → Today
```

Entry rules: wizard opens automatically for `SYSTEM_ADMIN`/`CONTROLLER`/`AP_LEAD` on first sign-in to a workspace with **0 invoices and 0 documents**. For other roles it is replaced by a one-screen welcome + "Take the 2-minute tour" (§4.8). Re-openable from the sidebar checklist at any time (`/setup`). **Auditors never see it.**

## 4.2 Step-by-step

Each step lists: **Shows · User does · Then · States.** States use the canonical set: *Empty/Initial · Loading · Success · Failure · Disconnected/Unavailable · Permission-restricted*.

### Step 0 — Sign-in and joining (existing `AuthScreen`, simplified)

| | |
|---|---|
| **Shows** | Product name, one-line promise ("Get invoices in, see what needs a decision, approve with a clear record."), **Continue with Google** (Supabase). In non-production builds only (`!import.meta.env.PROD` `[V]`), a collapsed "Developer sign-in" with the seeded quick-logins |
| **User does** | Click Continue with Google |
| **Then** | `GET /auth/me`. If `is_provisioned` → Step 1 (or Today if setup already complete). If not → "Join a workspace" |
| **Join a workspace** | Two cards. **"I have an invitation"**: pasted token field *or* arrives via `/accept-invite?token=…` (P1) pre-filled. **"Request access"**: replaces the free-typed Org ID with (a) a field labelled "Workspace code" with example and help "Ask your administrator" (P0, FE); (b) a workspace lookup by code (**B-14, P1**). Keep reason + requested role |
| **States** | *Loading* skeleton on `/auth/me`. *Failure* "We couldn't verify your session" + Try again + Sign out (today's `authError`). *Pending request* shows request status from `GET /auth/access-requests/my` (PENDING/APPROVED/REJECTED with reviewer's reason) with a "Check again" button. *Invitation errors* map server `detail` text to plain language (wrong email, expired, used) |

### Step 1 — Welcome

| | |
|---|---|
| **Shows** | "Welcome, {first name}." A 4-node diagram: **Invoices arrive → We read & check them → You decide → Everything is recorded**. Three honest bullets: "Reads PDF invoices from email or upload", "Checks them against purchase orders, receipts, GST maths and duplicates", "Never pays or posts to your ERP — approval is an internal AP decision". Button **Get started**; link "Skip setup" (goes to Today with checklist visible) |
| **User does** | Press Get started |
| **Then** | Step 2 |
| **States** | None needed (static). If not admin-level role: replace body with role-appropriate tour (§4.8) |
| **Copy rule** | The third bullet is mandatory — it prevents the most dangerous misunderstanding |

### Step 2 — Your workspace and team

| | |
|---|---|
| **Shows** | Workspace name (read-only, from `org_name`), your role chip, a mini roster ("You" only for now), and an **Invite a teammate** inline form: email + role (plain-language role descriptions, §Team page). SYSTEM_ADMIN option appears only for SYSTEM_ADMIN `[V]`. Link "I'll do this later" |
| **User does** | Optionally invite 0-3 people. Each submit calls `POST /auth/invitations` (7-day token `[V]`) |
| **Then** | Each invite shows a **Copy invite link** row (`{origin}/accept-invite?token=…`, P1; token string in P0). Text: "We don't send emails yet — share this link yourself." (`[V]` no email sending exists) |
| **States** | *Failure* mapped: 403 → "Only admins, controllers and AP leads can invite"; privilege-escalation message from server shown verbatim in plain form. *Success* inline row + toast. *Permission-restricted* for Associates: step shown read-only with "Ask an admin to invite colleagues" |
| **Gap** | Cannot rename workspace or see existing members (**B-14, B-11**) — do not show disabled controls for them; omit |

### Step 3 — Connect Gmail (skippable)

Uses the **tenant-level** `GET /integrations/gmail/status` (not `/connections`) — F-08.

| State (from `status`, `initial_sync_pending`, `last_synced_at`) | Shows | Primary action |
|---|---|---|
| **Not available** — `NOT_CONFIGURED` and server lacks `GMAIL_CLIENT_ID` (authorize returns 503 `[V]`) | "Email import isn't set up on this server. An administrator needs to add Google credentials." + What to tell them (copyable list of required env names from `required_env`) | **Skip for now** |
| **Ready to connect** — configured, no authorised account | Plain explanation: "We read invoice PDFs from one dedicated mailbox. We request **read-only** access (Gmail `readonly` scope). We never send or delete mail." Mailbox suggestion: "Use a shared address like ap@yourcompany" | **Connect Gmail** → `GET /gmail/authorize` → `window.location = authorization_url` |
| **Waiting for Google** (returning from OAuth) | Spinner: "Finishing connection…" | auto |
| **Connected, not synced** — `CONNECTED` and `initial_sync_pending` | ✔ "Connected as {mailbox}" "Nothing imported yet." | **Import recent invoices** → `POST /gmail/sync?max_messages=15` |
| **Syncing** | Progress with elapsed seconds; "This can take up to a minute." Button disabled | — |
| **Synced** | Result sentence from response: "{ingested_count} invoice(s) received, {duplicates_skipped} already had, {quarantined_count} set aside." + mode (`INCREMENTAL_HISTORY`/`FULL_QUERY`) hidden in Details | **Continue** |
| **Failed — expired** (`DEGRADED`) | "Google access expired. Reconnect to keep importing." | **Reconnect** |
| **Failed — revoked** (`REVOKED`) | "This mailbox was disconnected." | **Connect again** |
| **Failed — OAuth error** (`?gmail=error&detail=…` on return `[V]`) | Plain message + Try again; raw detail in Details | **Try again** |
| **Failed — sync lock** (HTTP 409 `[V]`) | "An import is already running. Try again in a minute." | Retry |
| **Failed — Google unreachable** (HTTP 502 `[V]`) | "We couldn't reach Gmail." | Retry |
| **Permission-restricted** (Associate/Auditor) | "Only admins, controllers and AP leads can connect email." + Copy request message | Skip |

*Return handling (**P0, FE**):* on load of `/settings/connections` or `/setup`, read `?gmail=connected&mailbox=…` / `?gmail=error&detail=…`, show a toast/banner, refetch status, then strip the query string. **Automatic polling is not available** (`scheduling.*.status = NOT_CONFIGURED` `[V]`); copy must say "Import runs when you press Import" — never "automatically".

### Step 4 — Connect your ERP (skippable, honest)

| | |
|---|---|
| **Shows** | Heading "Connect your ERP (optional for now)". Explains: "Matching checks invoices against purchase orders, goods receipts and quality records. Without ERP data those checks can't pass." Status from `GET /connections` → `pillars.sap_erp`: `NOT_CONFIGURED` / `CONNECTED` |
| **User does** | Either **Skip — I'll do this later** (default) or, if `CONNECTED`, **Continue** |
| **Then** | Step 5. Skip stores `onboarding.erp = "skipped"` locally; sidebar checklist keeps "Connect ERP" as an open optional item |
| **States** | *Unavailable* (always, until B-21): "SAP connection is set up by your administrator in the server settings. There is no sign-in form here yet." `CONNECTED` here means **configuration present**, not "data synced" `[V: is_erp_configured()]` — label it "Configured". *Empty reference data* (always today `[V]` F-10): "No purchase-order data has been loaded." — shown beside status |
| **Do not build** | A fake connect form, OData URL fields, "Test connection" buttons — none can work |

### Step 5 — Bring in your first invoice

Two equal choices (cards) + one demo link.

| Option | Shows | User does | System `[V]` | Result states |
|---|---|---|---|---|
| **Upload a PDF** | Drop zone: "Drop a PDF invoice (up to 50 MB)". Client checks `.pdf` extension and size (mirrors server `[V]`) | Drops/selects file | `POST /documents/upload` | **Received** (`status: QUEUED`, ids returned) → "We've got it" + **Open invoice**; **Duplicate** (409) → "You've already uploaded this file (`{filename}`)" + **Open existing** (uses returned `invoice_id`); **Wrong type/size/corrupt** (400 `detail`) → plain message; **Storage down** (503) → "Secure storage is unavailable. Nothing was saved." |
| **Import from Gmail** | Available only if Step 3 connected | Press Import | `POST /gmail/sync` | as above |
| **See it with demo data** (workspace is **not** a demo workspace) | Link: "Not ready? Preview a sample invoice" → opens a **read-only static sample** in the guided review (FE-bundled JSON, synthetic, clearly labelled) | Click | none (no backend call) | Always works; **P1, FE** |

**Honest "what happens next" panel** shown after a successful receipt:
- *If B-01 is live:* progress stages "Received → Reading → Checking → Ready" driven by polling `GET /invoices/{id}` every 3 s (max 90 s), then **Review it**.
- *Until B-01 (today `[V]`):* "Received. This invoice is waiting for extraction, which isn't running yet on this server." + **Open invoice** (shows empty extraction with explanation) + **Try demo invoice**. **Do not** show a fake progress bar.

### Step 6 — Review your first invoice (guided)

Runs the **workspace tour** (§5.4 / WF-4) on the first invoice whose status is *Ready to approve* or *Needs attention*; if none exists, on the sample (Step 5). Six coach-marks, each dismissible, keyboard-operable (←/→/Esc):

1. **Verdict banner** — "Start here: the system's summary of this invoice."
2. **Document** — "The original file. Click a field to find it" (P2; plain "this is the original" until bounding boxes exist — B-16).
3. **Matching** — "How this invoice compares with the purchase order and receipt."
4. **Checks** — "Each automatic check, pass or fail, with the evidence."
5. **Your decision** — "Pick what to do and say why. The reason is saved for audit."
6. **History** — "Every action on this invoice is recorded."

In a **real** workspace the tour is read-only ("practice mode" — buttons are inert, label "Practice"). Only in the **demo workspace** may the user perform a real action.

### Step 7 — You're set up

| | |
|---|---|
| **Shows** | Checklist with ticks derived from data (§4.9); "What your day looks like": *Today* shows what needs you; *Invoices* is the list; *Approvals* shows what's waiting on a second person. Keyboard-shortcut card ("Press `?` anywhere") |
| **User does** | **Go to Today** |
| **Then** | `/today`; sidebar checklist collapses to a "Setup complete" chip after 7 days or on dismiss |

## 4.3 Empty, loading, success, failure, disconnected — screen-level catalogue

| Condition | Where | Treatment |
|---|---|---|
| Brand-new workspace, 0 invoices | Today, Invoices | Hero empty-state: "No invoices yet" + two buttons (Upload PDF · Import from Gmail) + link to setup. **Never** shows zero-filled KPI tiles |
| API unreachable / 5xx | Any page | Inline banner (not toast) "Couldn't load {thing}" + **Retry** + collapsed technical detail. Keep stale data visible if any (dim, not blank). **No silent `console.error`** (F-06, F-13) |
| 401 | Any | Redirect to `/signin` with "Your session expired. Sign in again." |
| 403 | Action | Inline message under the action: "Your role (Auditor) can view but not change invoices." Buttons for forbidden actions are **hidden**, not disabled-then-error |
| Database not connected (`status: unavailable`, `message`) `[V]` | Today/Invoices | "Data service is unavailable." with `reason` in Details |
| Gmail disconnected/expired | Connections, Invoices "Add invoices" menu | Menu item replaced by "Reconnect Gmail" |
| Storage unhealthy (`object_storage` != CONNECTED) | Upload | Disable upload with reason |

## 4.4 Role variants

| Role | Wizard | Difference |
|---|---|---|
| Admin/Controller/AP Lead | Full 7 steps | — |
| Associate | Steps 0, 1, then **tour** → Step 5 (upload only) | Steps 2-4 become "Ask an admin" cards |
| Auditor | Step 0, welcome, → Audit | No wizard, no upload |

## 4.5 Demo workspace onboarding

If the workspace is a **demo workspace** (§7.1): skip Steps 2-5, open Step 6 immediately on the Scenario-1 invoice, show the persistent **Demo banner** and the **Demo guide** panel (§7.2).

## 4.6 Telemetry for onboarding (P2, FE+BE)

`setup_step_viewed`, `setup_step_completed`, `setup_step_skipped`, `first_invoice_received`, `first_review_opened`, `first_decision_recorded` — to measure §11 acceptance criteria. No endpoint exists today `[V]`; until then compute from audit events (`DOCUMENT_UPLOADED`, action events).

## 4.7 Persistence

| Data | Where today | Spec |
|---|---|---|
| ERP skipped / tour seen / checklist dismissed | — | `localStorage` key `ap.onboarding.{user_id}.{org_id}` (P0). Server persistence in B-14 (P2) |
| Auth token | `localStorage` `ap_command_center_auth_token` `[V client.ts]` | Keep for now; flag XSS exposure to security owner `[?]`; do not widen use |

## 4.8 Short tour for non-admin first sign-in (P1)

Three coach-marks: sidebar (Today / Invoices), the status chip legend (what each colour means), the keyboard help (`?`). Dismissible; never repeats.

## 4.9 Setup checklist — derived, not stored (P0, FE)

| Item | Ticks when (existing endpoint) | Required? |
|---|---|---|
| Sign in | `/auth/me.is_provisioned` | — |
| Invite your team | (cannot detect; ticks when user submits ≥1 invite in this session or dismisses) | optional |
| Connect Gmail | `GET /integrations/gmail/status`: `status == "CONNECTED"` | optional |
| Connect ERP | `GET /connections` `pillars.sap_erp.status == "CONNECTED"` **or** `onboarding.erp == "skipped"` | optional |
| Receive an invoice | `GET /inbox` `total_count ≥ 1` | **required** |
| Make a first decision | `GET /audit?action=APPROVE_AP_REVIEW` (or any action) by current user `≥ 1` | **required** for "complete" |


---

# 5. Page-by-Page Implementation Specifications

Every page uses the same eight headings. "Data requirements" lists the **actual** endpoint and whether it is `[V]` available, `[BX]` available-but-unused, or `[BM]` missing (cross-referenced to §9). Wireframes are in §6 (WF-n).

## 5.1 Application shell (global)

| | |
|---|---|
| **Purpose** | Orient the user, keep navigation constant, surface global truth (demo, health, role) without clutter |
| **User intention** | "Where am I, is everything working, what needs me?" |
| **Hierarchy** | 1 Navigation · 2 Page content · 3 Global banners (Demo / degraded) · 4 User menu · 5 Health pill |
| **Layout** | Fixed left sidebar 240 px (collapses to 64 px icons < 1280 px, drawer < 768 px). Top strip 48 px only for page title, search (P1) and primary page action. Content max-width 1440 px, 24 px gutters. **Remove the footer legal string** `[V App.tsx L133]` |
| **Interactions** | Sidebar items are links (real `<a>`), `g` then `t/i/a/u` go-to shortcuts (P1), `?` opens shortcut help, `/` focuses search (P1). Health pill opens popover listing `health.subsystems` (database, object_storage, identity_provider, gmail_ingestion, sap_erp) with plain language + link to Connections |
| **States** | *Health unknown*: grey "Checking…". *DEGRADED/BLOCKED*: amber/red pill + one-line cause. *Demo workspace*: sticky top banner (§7.1). *Offline*: banner "You're offline" |
| **Data** | `GET /health` `[V]` (`overall_status`: READY / SETUP_REQUIRED / BLOCKED; note the **type** also allows per-subsystem `DEGRADED`/`ERROR`), `GET /auth/me` `[V]` |
| **Simplification** | Remove the two-row header, "Co. Code 1000" chip, the "Zetwerk Manufacturing" fallback string, "System: CHECKING…" jargon, "IdP Sign-In Setup Required" top-bar link for signed-out users (replace with the sign-in page) |
| **Priority** | P0 FE |

## 5.2 Today (replaces Dashboard)

| | |
|---|---|
| **Purpose** | Answer "what needs me, in what order" in under 5 seconds, and show the pipeline at a glance |
| **User intention** | Start the shift; decide what to open first |
| **Information hierarchy** | **1** "Needs attention" next-up list (top 5 by due date then value) · **2** Three outcome tiles: *Needs attention*, *Ready to approve*, *Waiting for second approval* · **3** Pipeline strip (Received → Needs attention → Ready → Approved) · **4** Setup checklist (until done) · **5** Recent activity (last 5 audit events). **Not shown today:** touchless rate (always null `[V]`), stage/decision enum lists, "Production Truth Protocol" banner |
| **Layout** | See **WF-2**. 12-col grid: row 1 greeting + date + "Add invoices" button; row 2 three tiles (4 cols each); row 3 left 8 cols "Next up" table, right 4 cols checklist or "Recent activity"; row 4 pipeline strip |
| **Interactions** | Tile click → `/invoices?tab=…`. "Review" on a row → `/invoices/:id?from=/today`. "Add invoices" menu (Upload PDF / Import from Gmail). Refresh icon + "Updated 10:42" timestamp (no auto-poll in P0; 60 s poll P2) |
| **States** | *Loading*: skeleton tiles + 5 skeleton rows. *Empty (0 invoices)*: onboarding hero (§4.3). *All clear* (invoices exist, none need attention): "Nothing needs you right now" + last approved item. *Error*: banner + Retry, keep last numbers dimmed. *Metrics `status:"unavailable"`* `[V]`: show `reason` in banner, hide tiles. *Auditor*: tiles read-only; "Review" label becomes "View" |
| **Data** | Tiles: `GET /dashboard/metrics` `[V]` gives `stages{}` and `decisions{}` **separately** (no cross-tab) → counts for *Ready to approve* = `decisions.MATCH_CANDIDATE`; *Needs attention* = `summary.open_exceptions` (but wrong after actions — **B-02**); *Waiting for second approval* **cannot be computed** → **B-10**. Next up: `GET /exceptions` `[V]`. Recent activity: `GET /audit?limit=5` `[V]`. **Recommended:** `GET /inbox/summary` returning counts per user-facing status + due-in-7-days count (**B-09, P1**); until then tiles may be approximated from metrics and labelled accordingly |
| **Simplification** | Delete raw stage list, raw decision list, "Blocked Value (Held)" jargon (→ "Value waiting on you" shown inside the *Needs attention* tile as secondary text from `summary.blocked_value_inr`, formatted ₹ en-IN), the MSME tile (fold into row-level "Due" column; its backend definition counts `NEEDS_REVIEW` with a deadline, which does not match its label `[V dashboard.py L74-79]`) |
| **Priority** | P0 FE (+ P0 BE B-02 for truthful counts) |

## 5.3 Invoices (replaces Inbox, Exceptions, Quarantine, upload)

| | |
|---|---|
| **Purpose** | The single list of everything that has arrived, with a tab per working state |
| **User intention** | Find an invoice; work a queue; add new invoices |
| **Hierarchy** | 1 Tabs with counts · 2 Search · 3 Table (status, reason, amount, due) · 4 "Add invoices" action |
| **Layout** | See **WF-3**. Tabs: **Needs attention** (default if any, else All) · **Ready to approve** · **Waiting** (on hold / supplier / second approval) · **Approved** · **Received** (not yet processed) · **Not invoices** · **All** |
| **Columns** | Supplier (name; GSTIN under it in muted small, from `vendor_gstin`) · Invoice no. + PO ref stacked · **Amount** (right-aligned, ₹ en-IN, tabular) · **Status chip + reason line** (§3.3) · **Pay by** (statutory deadline; "—" shown as "No legal deadline set", never "Unestablished") · **Received** (relative; absolute in tooltip) · row chevron. **Needs attention** tab additionally: *Blocked by* (gate name, plain-language), *Owner*, *Value waiting* |
| **Interactions** | Click row or press Enter → workspace with `from` URL. `J/K` move selection, `Enter` open, `/` search (P1). **Pagination controls (First/Prev/Page n of N/Next/Last + page-size 25/50/100)** — **P0 bug fix F-06** using `total_pages`, `page_size ≤ 100` `[V]`. Sort by Pay-by, Amount, Received (client-side within page in P0; server `sort` param is B-09). "Add invoices ▾": *Upload PDF(s)*, *Import from Gmail* (hidden/disabled with reason if not connected), *Drag files anywhere on the page* (overlay "Drop PDFs to add") |
| **Tab → query mapping (P0, single-value filters only)** | Needs attention → **`GET /exceptions`** (different endpoint, `[V]`) · Ready to approve → `decision=MATCH_CANDIDATE` · Approved → `stage=INTERNAL_APPROVAL_COMPLETE` · Received → `stage=RECEIVED` · All → none · Waiting / Not invoices → **need `status_group` filter (B-09)**; Not invoices additionally needs a quarantine list endpoint (B-19). Until B-09/B-19: **hide** tabs that cannot be populated rather than showing empty ones |
| **Search** | P0: text box bound to `vendor=` (`ilike`, `[V] inbox.py`). P1: invoice no., PO, amount (B-09) |
| **Upload behaviour** | Multi-file queue, sequential `POST /documents/upload`. Each file row: name · size · **Waiting → Uploading → Received / Already uploaded / Failed** with reason. Client pre-checks `.pdf` and 50 MB. Duplicate rows link to `invoice_id` from the 409 body `[V]`. Replace the current fake lifecycle (`Processing` is set *before* the request starts `[V ConnectionsPage L97-99]`). After last file: summary toast + list refetch |
| **Gmail import** | `POST /gmail/sync?max_messages=15`. Result sentence from response. 409/502/404 mapped (§4.2 Step 3). **Hide for roles that cannot connect only the *connect* action — import itself is allowed by the server for any member `[V]` but should be limited to non-Auditors in the UI and fixed server-side (B-13)** |
| **States** | *Loading*: 8 skeleton rows. *Empty tab*: tab-specific copy ("No invoices need attention. Nice."). *Empty workspace*: onboarding hero. *No search results*: "No invoices match “{q}”" + Clear. *Error*: banner + Retry (never swallow) `[V F-06]`. *Auditor*: "Add invoices" hidden |
| **Data** | `GET /inbox?page&page_size&stage&decision&vendor` `[V]` returns `id, invoice_number, vendor_name, vendor_gstin, po_reference, total_amount, currency, stage, decision, decision_reason, msme_*, created_at, updated_at`. **Missing:** `source_channel`, owner name, approval status, blocking-gate summary, counts per tab (**B-09**) |
| **Bulk actions (P2, FE+BE)** | Row checkboxes only on **Ready to approve**, only for rows `< threshold`, only for roles that may approve; one shared reason; shows confirmation listing every invoice and total value. Requires `POST /invoices/bulk-actions` that writes one audit event per invoice (**B-17**). **Do not build client-side loops of single approvals** (partial failure, no atomicity) |
| **Simplification** | Remove the "Server-paginated operational ledger of genuine supplier invoices" subtitle, "In accordance with production truth rules, zero fake records exist" empty-state text, MSME column header jargon, raw enum filters |
| **Priority** | P0 FE (pagination, search, status mapping, error surfacing, upload queue, tabs that work today); P1 BE (B-09) |


## 5.4 Invoice Review Workspace (replaces Invoice Detail) — **the most important page**

| | |
|---|---|
| **Purpose** | Let a person understand an invoice and record a defensible decision in under 60 seconds for clean items and under 5 minutes for exceptions |
| **User intention** | "What is this? Is it right? If not, why not? What do I do, and what happens when I do it?" |
| **Design rule** | Answer in this order: **Verdict → Evidence → Decision.** The document is always one glance away; the three "panes" of today become **one document panel + one tabbed analysis panel + one sticky decision bar** |

### 5.4.1 Information hierarchy

1. **Header**: invoice no., supplier, amount (₹ en-IN), status chip, Pay-by date, position in queue ("3 of 12"), Prev / Next, Back to list (uses `from`).
2. **Verdict card** (top of analysis panel) — one sentence + the blocking reason + the recommended next action. Examples built from real fields:
   - *Ready:* "All 7 automatic checks passed. Approve to complete internal review."
   - *Blocked:* "Blocked at **Price and quantity match the PO** — {gate.notes}. Suggested: **Ask supplier to correct** or **Hold**."
   - *Scan:* "This looks like a poor scan; extracted values may be wrong. Verify against the document before approving."
   - *Waiting second approval:* "{first approver name} approved on {date}. A different person must approve."
   - *Not extracted yet (today's real state `[V F-01]`):* "This invoice was received but hasn't been read yet. There are no extracted fields or checks to review."
3. **Analysis tabs** (default **Matching**): **Matching · Checks · Details · History**.
4. **Document panel** (left, ~55 %, collapsible).
5. **Decision bar** (sticky bottom).

### 5.4.2 Layout

See **WF-4** (≥ 1280 px), **WF-4b** (1024-1279), **WF-4c** (< 1024). Replace fixed `h-[750px]` panes `[V]` with viewport-height layout (`height: calc(100vh - header)`); panels scroll independently.

### 5.4.3 Document panel

| Capability | Spec | Data | Priority |
|---|---|---|---|
| Show the original PDF | Embedded viewer fed by `document.preview_url` (signed, 900 s TTL `[V invoices.py L64-72]`). P0: `<iframe>`/`<object>` with page controls from the browser; **on `403/expired` re-request** a URL (`GET /documents/{id}/signed-url`, `[V]` max 300 s) and retry once | `document.preview_url` `[V]` | **P0 FE** |
| Download / open in new tab | "Open original" and "Download" (existing `GET /documents/{id}/download` `[V]`) in a ⋯ menu | `document_id` `[V]` | P0 FE |
| File facts | Filename, size, **SHA-256 (first 12 chars, copy full)**, received date, source (upload/Gmail — **needs `source_channel` in detail, B-09**) in a collapsed "File details" | `[V]` | P0 FE |
| Click a field → highlight on page | Needs `bounding_box` (API returns it `[V]`) **and** the extractor to populate it. The seeder does **not** (`source_page=1`, bbox null `[V sme_eval_setup.py L404-420]`) | **B-16** | **P2** |
| Zoom / fit width / rotate / page thumbnails | Via `pdf.js` | — | P2 |
| Degraded-scan hint | When status = *Needs attention — check scan*, overlay chip "Poor scan — verify values here" | derived (§3.3) | P1 FE |
| Unavailable | If `document` is null or URL generation failed (API swallows and returns `preview_url: null` `[V L67-70]`): "Original file isn't available" + reason + Retry | `[V]` | P0 FE |

### 5.4.4 Tab: Matching (evidence, not decoration)

Goal: put the invoice and what it was compared against **side by side**.

| Block | Content | Data today | Dependency |
|---|---|---|---|
| **Header facts** (2-column key/value) | Supplier (name, GSTIN), invoice no./date, PO ref, currency, Subtotal, GST, **Total payable** — `net_payable` falls back to `total_amount` as today `[V]` | `invoice.*` `[V]` | — |
| **Lines table** | Columns: # · Description (wraps, no truncation) · Qty · Rate · Line total. Row expander for long text | `lines[]` `[V]` | — (P0) |
| **PO comparison columns** (added to the same table) | PO qty · PO rate · Received qty (GRN) · QC status · **Variance %** with red/amber where outside tolerance; footer: PO balance remaining | **Not returned `[V]`**. Schema has `erp_po_lines` (`authorized_quantity`, `contracted_unit_rate`) and GRN line tables but **no population code and no API** | **B-05 + B-06 (P0)** |
| **Tax summary** | Taxable value, CGST/SGST **or** IGST, total tax, rounding, "Reconciled ✓ / Does not reconcile — calculated ₹X vs billed ₹Y" | `subtotal`, `tax_amount` only `[V]`; split not returned | B-05 (P1) |
| **Until B-05** | Show the lines table, then an honest inline note: "PO and receipt comparison isn't available for this invoice yet." Do **not** render empty PO columns | — | P0 FE |

### 5.4.5 Tab: Checks

One row per gate from `match_gates[]` `[V]` (`gate_number`, `gate_name`, `status`, `evidence_source_id`, `notes`, `checked_at`):

| Cell | Spec |
|---|---|
| Icon + plain-language name | Map known names `[V seeder L441-449]`: *Vendor Identity Registered* → "Supplier is registered"; *PO Authorization Valid* → "Purchase order found and valid"; *GRN Receipt Confirmed* → "Goods receipt found"; *QC Inspection Accepted* → "Quality check passed"; *GST Arithmetic Reconciled* → "GST adds up"; *PO Price & Quantity Tolerance* → "Price and quantity match the PO (±1.5 %)" `[tolerance quoted from README, `[?]` in engine config]`; *Duplicate Invoice Check* → "Not a duplicate". Unknown names render as given |
| Status | PASS ✓ green · FAIL ✗ red · anything else (e.g. `WARN`, `SKIPPED`) ⚠ amber with raw value in tooltip `[?]` other values not seen in code |
| Evidence | `notes` shown as the explanation (e.g. "Variance: 4.2%"); `evidence_source_id` as a muted "Source: …" with copy (**today these two fields are returned and never displayed `[V]`** — free P0 win) |
| Order | Failed first, then passed; keep gate number visible ("Check 6 of 7") |
| Row expand | Raw gate name, `checked_at` (org timezone) |
| Header | "5 of 7 checks passed" progress bar; **no "17 gates"/"5-way" wording** |

> **Known data-quality caveat `[V F-02]`:** in the seeded tenant, gate 6 is PASS/FAIL by scenario label, and the exception's blocking gate for degraded scans is named "OCR Readability Inspection" with gate **#1**, which collides with real gate #1 ("Vendor Identity Registered"). The UI must show the **exception's** `blocking_gate_name` in the Verdict card and the **gate list** in Checks without trying to reconcile them; flag to backend owners (B-01).

### 5.4.6 Tab: Details (extracted fields)

- Table: Field (humanised: `supplier_gstin` → "Supplier GSTIN") · Value · Source (page n) — **no confidence column in P0**. Seeded confidence values are constants (0.99/0.95) so showing "99% conf" would be misleading `[V F-02]`. Show a confidence indicator **only** when `ExtractionRun.parser_version` indicates real per-field scoring (`[?]`; B-16).
- Banner when `fields` is empty: "Nothing has been extracted from this file." (replaces "Zero extracted fields. Extraction pipeline pending.").
- Manual correction of a field is **not possible** — no endpoint (**B-20, P1**). Do not render edit pencils.

### 5.4.7 Tab: History

Timeline from `timeline[]` `[V]` (already newest-first): action label (humanised), actor name (needs name — **B-11/B-15**; show ID until then), role chip, local time, reason. Expand: before → after (needs `before_state/after_state`, which the *detail* API omits though the audit API returns it `[V]` → call `GET /audit?invoice_id=` for the expanded view or extend detail **B-15**). Link "Open in Audit".

### 5.4.8 Decision bar — actions

Show **only** actions valid for **role + state**; hide the rest. The primary button reflects the recommendation.

| Action (user label) | API `action` | Exists in UI today | Backend | Role | Effect on state `[V invoices.py]` | Needs |
|---|---|---|---|---|---|---|
| **Approve** | `APPROVE_AP_REVIEW` | yes ("Approve Review") | ✔ | not Auditor | `< ₹5L`: stage `INTERNAL_APPROVAL_COMPLETE`, decision `MANUALLY_APPROVED`. `≥ ₹5L`: creates `ApprovalRequest`, stage `ACTION_REQUIRED` (first approval) → later distinct user completes | — |
| **Approve undisputed amount** | `APPROVE_UNDISPUTED` | **no** `[BX]` | ✔ takes `undisputed_amount` (**stored nowhere** — the handler never reads it `[V]`) | not Auditor | same as Approve | **B-07 to persist amount**; P1 |
| **Hold for evidence** | `HOLD_PENDING_EVIDENCE` | yes | ✔ | not Auditor | stage `ACTION_REQUIRED`, reason prefix "Hold placed:" | B-03 to give it its own state |
| **Ask supplier to correct** | `REQUEST_SUPPLIER_CORRECTION` | yes | ✔ (records only; **no email is sent** — Gmail scope is read-only `[V]`) | not Auditor | stage `ACTION_REQUIRED`; reason prefixed | UI offers "Copy message to supplier" (P1 FE) |
| **Raise debit note** | `RAISE_DEBIT_NOTE` | **no** `[BX]` | ✔ (records only) | not Auditor | as above | P1 FE |
| **Escalate** | `ESCALATE` | **no** `[BX]` | ✔ (records only; no routing) | not Auditor | as above | P1 FE; **B-03** for visible escalated state |
| **Set aside (not an invoice)** | `QUARANTINE` | yes ("Quarantine File") | ✔ | not Auditor | stage+decision `QUARANTINED` | — |
| **Reject** | `REJECT_INVOICE` (proposed) | **no** | **missing** `[V grep 0 hits]` | Lead/Controller (proposed) | decision `REJECTED` | **B-07 (P0)** |

**Behaviour rules**

| Rule | Spec |
|---|---|
| Confirm panel, not browser dialogs | Every action opens an inline confirm panel (not `alert`/`confirm`, F-13) anchored above the bar: **summary** ("Approve AP-26-001 · ₹26,196.00 · Asterion Precision Components"), **reason field** (server minimum 3 characters `[V ActionPayload.min_length=3]`; UI recommends ≥ 10), **reason templates** (chips), consequence line, **Confirm** (primary) / Cancel |
| Reason templates (P0 FE) | Context-sensitive chips that pre-fill an editable reason. Approve: "All checks passed; verified against original." · "Variance within agreed tolerance; reviewed." · Hold: "Awaiting goods receipt for {PO}." · "Awaiting QC certificate." · "PO balance insufficient; awaiting amendment." · Correct: "Unit rate exceeds PO rate by {variance}; supplier to issue corrected invoice." · "GST amount does not reconcile." · Set aside: "Payment receipt, not a payable." · "Duplicate of {inv}." Placeholders filled from gate `notes`/invoice fields |
| Approving over a failed check | If any gate is `FAIL`, **Approve** becomes **"Approve anyway…"** (secondary style) and the confirm panel requires (a) ticking "I have reviewed the failed check(s): {names}" and (b) a reason. The server **does not** check gates today `[V]` — enforcement is **B-08 (P1)**; UI guard is **P0 FE** |
| Dual control | If `total ≥ threshold` (threshold is **not exposed** to the UI `[V]` — **B-05/B-14** add `requires_dual_approval` + threshold to detail; until then show the banner only once an `approval` object exists): confirm panel shows "This invoice needs **two different approvers**. After you approve, {role} must approve." After first approval: Approve is **disabled for the first approver** with reason "You approved this first; a different person must approve" (server returns 400 "Dual control violation" `[V]`; the UI prevents it) |
| Idempotency | Server returns `status: "ALREADY_APPROVED"` `[V]` → show info toast "Already approved", not an error |
| After success | Toast "Approved. Recorded in the audit trail." Refetch; **auto-advance** to next item of the same tab (`from`) after 1.2 s with Undo-less message; if queue empty, return to list with "All done" |
| Failure | Inline error in the confirm panel using server `detail`; keep the typed reason |
| Role handling | Auditor: bar replaced by read-only notice "You have read-only access." |
| Approved-state copy | Banner: "Internal review complete. This does **not** mean paid or posted to your ERP." |
| Statutory deadline | Header chip "Pay by {date} · {n} days" turns amber ≤ 7 days, red when overdue; tooltip states holds do not move the legal deadline (existing exceptions-page invariant `[V]`) — **wording for legal review** |

**Keyboard (P1 FE)** — disabled while focus is in any text input/textarea:

| Key | Action |
|---|---|
| `J` / `K` | Next / previous invoice in queue |
| `A` | Open Approve confirm panel (never submits directly) |
| `H` | Open Hold panel |
| `C` | Open Ask-supplier panel |
| `S` | Open Set-aside panel |
| `1`-`4` | Switch tabs Matching/Checks/Details/History |
| `D` | Toggle document panel |
| `Ctrl/⌘ + Enter` | Confirm (when reason valid) |
| `Esc` | Close panel / return to list |
| `?` | Shortcut help |

### 5.4.9 States

| State | Treatment |
|---|---|
| Loading | Header skeleton + two panel skeletons (replaces centered spinner text "Retrieving authoritative 3-pane…") |
| Not found (404) | "This invoice doesn't exist or you don't have access." + Back to list |
| API error | Banner + Retry |
| No document | Panel shows "No original file attached" |
| Not yet extracted | Verdict card message (above); Matching/Checks/Details tabs show explanatory empty states, History works |
| Quarantined/Approved | Decision bar reduced to the actions still allowed (e.g. none for Approved; **no reopen exists** — B-22 P2) |
| Permission-restricted | See Role handling |
| Concurrent change | On 4xx/409 after another user acted, refetch and show "This invoice changed while you were viewing it" |

### 5.4.10 Data requirements

`GET /invoices/{id}` `[V]` → `invoice, document, extracted_fields, lines, match_gates, approval, timeline`. **Additions requested (B-05):** `po_comparison[]`, `tax_breakdown`, `requires_dual_approval`, `dual_approval_threshold`, `source_channel`, `owner_name`, `workflow_state` (B-03), `can_act: {approve, hold, …}` for the current user, per-action `disabled_reason`. `POST /invoices/{id}/actions` `[V]`.

### 5.4.11 Simplification

Remove: "Pane 1/2/3" labels; "Net Payable Waterfall" jargon (→ "Totals"); in-pane audit list (→ History tab); duplicate stage/decision chips (→ one status chip); `alert()`; fixed heights; monospace for prose; mandatory justification box visible at all times (→ appears in confirm panel).

**Priority:** P0 FE (layout, verdict, document embed, checks with notes, confirm panel, templates, failed-gate guard, role handling, auto-advance); P0 BE (B-05 for matching evidence, B-07 reject, B-02); P1 (keyboard, extra actions, history diff); P2 (bbox highlighting, pdf.js).

## 5.5 Needs attention (the former Exceptions Queue, as a tab of Invoices)

| | |
|---|---|
| **Purpose** | The ordered work queue of blocked invoices |
| **User intention** | "What do I tackle first, and who owns it?" |
| **Hierarchy** | Due date → value → blocking reason → owner |
| **Layout** | Same table frame as Invoices; sort default **Pay by ↑, Value ↓** (mirrors server `ORDER BY msme_statutory_deadline NULLS LAST, exposure DESC` `[V exceptions.py L48-51]`); sort control shows the rule in words: "Sorted by legal due date, then value" |
| **Columns** | Pay by · Value waiting · Supplier + invoice no. · Blocked by (plain-language gate) · Owner · Age · **Review** |
| **Interactions** | Review → workspace. **Assign to me** (calls `POST /exceptions/{id}/reassign` with own user id `[V]`, reason defaulted "Taking ownership"). **Reassign…** needs a member picker (**B-11**) so hide until then. Filters: *Mine / Unassigned / All*, *Due in 7 days* |
| **States** | Empty: "No invoices need attention." Error/Loading as Invoices. **Truthfulness warning:** because exceptions are never closed (F-05) the list will show invoices that were already approved/set aside until **B-02**; until then **P0 FE mitigation**: join each row to `GET /invoices/{id}` lazily and hide rows whose status is Approved/Set aside, with a dev-visible console note. Do not rely on this long-term |
| **Data** | `GET /exceptions` `[V]` (OPEN only; `exception_id, invoice_id, invoice_number, vendor_name, blocking_gate_number/name, exposure_amount_inr, msme_statutory_deadline, assigned_user_id, created_at`) · `POST /exceptions/{id}/reassign` `[BX]` (server lacks tenant/role checks — B-13) |
| **MSME note `[V]`** | In the seeded data no invoice or exception has a deadline set (seeder never fills `msme_statutory_deadline`; INTEGRATION_BLOCKERS lists Udyam verification as not provisioned). The deadline-first sort is therefore inert in the demo; copy must not promise it |
| **Simplification** | Remove the "Statutory Urgency Invariant" banner (move to a ⓘ tooltip on the Pay-by header); replace "Unestablished" and "Unassigned" jargon |
| **Priority** | P0 FE (merge + mitigation), P0 BE (B-02) |

## 5.6 Approvals (new) — **P1**

| | |
|---|---|
| **Purpose** | Make the enforced dual-control rule a visible, workable queue |
| **User intention** | "What is waiting on a second approver, and can I be that approver?" |
| **Hierarchy** | Value → age → first approver → can-I-approve |
| **Layout** | **WF-5.** Tabs: **Waiting for me** · **Waiting for others** · **Completed (30 days)** |
| **Columns** | Invoice · Supplier · Amount · First approved by + when · Age · Status · action |
| **Interactions** | Open workspace (same confirm panel with dual-control framing). Disabled row action for own first approvals with reason. No separate approve button in the list (a reviewer should see the evidence) |
| **States** | Empty: "No approvals are waiting." Permission: hidden for Auditor |
| **Data** | **No list endpoint `[V]`** — `ApprovalRequest` is read only per-invoice. Needs **B-10** `GET /approvals?status=&mine=`. **Do not fake with client-side loops** |
| **Policy question for owner** | Should the second approver be required to be `CONTROLLER`? README says yes; server allows any distinct user `[V]`. UI states the rule the server enforces until B-08 changes it |
| **Priority** | P1 (BE-led) |

## 5.7 Connections (Settings)

| | |
|---|---|
| **Purpose** | Show and manage how invoices get in and whether systems are healthy |
| **User intention** | "Is email import working? Do I need to reconnect something?" |
| **Hierarchy** | **Invoice sources** (Gmail) → ERP → System health (collapsed) |
| **Layout** | **WF-6.** Three stacked sections; no document table, no upload, no quarantine table (moved, §3.1) |
| **Gmail card** | States and actions exactly as §4.2 Step 3, sourced from **`GET /integrations/gmail/status`** `[V]` (fixes F-08). Show: mailbox, **last import** time (org tz), "Automatic import: Not enabled — imports run when someone presses Import" (derived from `scheduling.*.status == NOT_CONFIGURED`, `[V]`), watch status/expiry in Details. Buttons: **Import now** · **Reconnect** · **Disconnect** (confirm dialog with consequence, Admin/Controller/Lead only; **disconnect's server role check not verified `[?]`**) |
| **ERP card** | `pillars.sap_erp` `[V]`: "Configured / Not configured" + "No reference data loaded" + link to Reference data. Instructions for admin (env names) in a collapsible "For administrators". No connect form (§4.2 Step 4) |
| **System health** | Collapsed list of `identity`, `database`, `object_storage` with plain-language message; "Run health check" button (re-fetch) |
| **Compliance note** | Backend states Gmail production verification and CASA assessment are **pending** (`compliance_status`) `[V]`. Show to admins as an informational note "Using a test mailbox until Google verification is complete" — do not hide it |
| **States** | Per-card loading/error; each card fails independently |
| **Data** | `GET /connections`, `GET /integrations/gmail/status`, `GET /health` `[V]` |
| **Simplification** | Remove: `Fernet (AES-128-CBC + HMAC-SHA256)`, `users.history.list`, `Path: org_{org_id}/invoices/…`, "Supabase Free plan compliant", redirect URIs and scopes from the main view (keep behind **Technical details** for admins) |
| **Priority** | P0 FE (status source fix, OAuth return handling, role gating); P1 (health popover) |

## 5.8 Reference data (ERP source records, Settings)

| | |
|---|---|
| **Purpose** | Look up supplier, PO, receipt and QC records the checks rely on |
| **User intention** | "What does the ERP say about PO-26-1001?" — usually reached **from an invoice** |
| **Layout** | **WF-7.** Tabs: Suppliers · Purchase orders · Goods receipts · Quality records; search per tab; PO row opens a right drawer with **lines** (`erp_po_lines`) and linked GRNs |
| **Interactions** | Search; click PO → drawer; from the invoice workspace, the PO reference is a link that opens this drawer (P1) |
| **States** | **Empty is the normal state today** `[V F-10]`: "No ERP data has been loaded into this workspace. ERP sync isn't available yet." + link to Connections. Header shows `Source: {origin_system}` **and** "Last retrieved {max(retrieved_at)}"; if no rows, omit the "SAP S/4HANA" claim (the API hard-codes it) |
| **Data** | `GET /source-records` `[V]` (limit 50 each, **no pagination, no explicit org filter in query** → B-13). PO lines & GRN lines **[BX in schema, not in API]** → **B-05/B-06** |
| **Simplification** | Remove the "Read-Only Isolation Boundary" banner (replace with "Read-only" chip); remove PAN/bank-verified columns unless users ask `[?]` |
| **Priority** | P1 FE; BE B-06 decides whether it is ever non-empty |

## 5.9 Audit

| | |
|---|---|
| **Purpose** | Answer "who did what, when, why, and what changed" |
| **User intention** | Auditor/controller investigation and evidence export |
| **Layout** | **WF-8.** Filter bar → table → right-hand detail drawer |
| **Filters** | Invoice (search by invoice no./supplier, resolving to id — **typeahead needs B-09**; P0 keeps ID text but labelled "Invoice ID"), **Person** (needs member list — B-11; P0: free text actor id), **Action** (dropdown of known actions, `action=` param `[BX]`), **Date range** (**B-15**), Correlation ID (advanced) `[BX]` |
| **Columns** | Time (org tz, relative on hover) · **Event** (human label: `APPROVE_AP_REVIEW` → "Approved", `DOCUMENT_UPLOADED` → "File uploaded", `DOCUMENT_QUARANTINED` → "Set aside as non-invoice", `EXCEPTION_REASSIGNED` → "Reassigned", `AUDIT_TRAIL_EXPORTED` → "Audit exported") · Person (name; ID in tooltip) · Role · Invoice (link) · Reason (2-line clamp, full in drawer) |
| **Detail drawer** | Reason in full; **Before → After** diff of `before_state`/`after_state` (stage, decision, net_payable, assigned_user_id `[V]`); `source_reference` (storage key or evidence ref); correlation id; event id (copy) |
| **Interactions** | Row click → drawer; Export CSV button **only for Auditor/Controller/Admin** (server rule `[V audit.py L82-84]`); after export show toast "Export recorded in the audit trail" (the server writes `AUDIT_TRAIL_EXPORTED` `[V]`). Pagination controls — API caps `limit ≤ 200` with **no offset** `[V]` → **B-15 (P1)**; P0: "Load more" is impossible, so show "Showing latest {n}" honestly |
| **States** | Empty, loading, error, filtered-empty ("No events match") |
| **Data** | `GET /audit` `[V]`, `GET /audit/export` `[V]` (CSV omits state diff and `source_reference` `[V]` → B-15) |
| **Simplification** | Replace the long immutability banner with a small "Append-only" chip + tooltip; drop "Compliance Ledger" title |
| **Priority** | P0 FE (labels, role-gated export, detail drawer using existing fields, action filter); P1 BE |

## 5.10 Team & access (Settings)

| | |
|---|---|
| **Purpose** | Get colleagues in with the right role; see who has access |
| **User intention** | Invite, approve requests, change role, remove |
| **Layout** | **WF-9.** Tabs: **Members** (P1) · **Requests** · **Invite** |
| **Members** | Name, email, role, status, last active `[?]`, ⋯ menu: **Change role** (`PATCH /auth/users/{id}/role`, reason required `[BX]`), **Deactivate** (`POST …/deactivate` `[BX]`). **No list endpoint `[V]` → B-11.** Until then this tab is omitted (do not show an empty roster) |
| **Requests** | Existing list/review (`GET /auth/access-requests`, `POST …/{id}/review`) `[V]`; review dialog shows requested role with permission summary; Admin/Controller only |
| **Invite** | Email + role with **plain-language role descriptions** (below). On success show **invite link** (P1) / token (P0) with Copy + expiry date "Expires in 7 days"; "We don't email this — send it yourself." Pending invitations list needs **B-11** |
| **Role descriptions (shown in selectors)** | Associate — "Upload, triage and resolve invoices." Lead — "Everything an Associate can, plus connect email, invite people and approve." Controller — "Second approval, access review and audit export." Auditor — "Read-only: view invoices and audit trail." Admin — "Full workspace control." Category Manager — "Commercial review (behaviour to be defined)" `[?]` |
| **States** | Loading, empty ("No pending requests"), permission-restricted (AP Lead sees Invite only), error |
| **Simplification** | Remove "enforce strict role boundaries" copy; fix nav so AP Lead does not land on a page where main actions are hidden |
| **Priority** | P0 FE (copy/UX of existing flows), P1 (Members — B-11) |

## 5.11 Sign-in & access gating (AuthScreen)

| | |
|---|---|
| **Purpose** | Get a person to the right place: signed-in, joined, or waiting |
| **Spec** | Single centered card (WF-1). States: signed-out; signing-in; session error; **no workspace** (Join); **request pending/approved/rejected** (with reviewer reason `[V review_reason]`); **invitation accepted → continue**. Dev quick-login group appears only when `!import.meta.env.PROD` **and** the server returns 200 for dev-session; label it "Developer sign-in (not available in production)". Remove the `test_token:*` message copy `[V AuthScreen L75]` |
| **Data** | `/auth/me`, `/auth/invitations/accept`, `/auth/access-requests`, `/auth/access-requests/my` `[V]` |
| **Priority** | P0 FE (copy, workspace code field), P1 (invite link route) |

