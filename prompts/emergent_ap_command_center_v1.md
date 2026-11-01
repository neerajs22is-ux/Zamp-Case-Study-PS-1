# AP Command Center — build brief for Emergent

> **How to use:** paste from the line below into Emergent as the initial prompt. It is written to be self-contained. Build **Phase 1 only**, then stop.
> **Before you paste:** nothing. Every variable is already decided below. Change the stack line only if you have a reason.

---

You are building a **new application from an empty directory**. There is no existing codebase, schema, pipeline, or repo to extend. Do not assume anything exists. Do not reference an "existing" anything.

Build it in the five phases defined in **Section 16**. After each phase, stop, post the preview, and wait for me to say continue. Do not attempt the whole thing in one pass.

## 1. WHAT THIS IS

An **accounts-payable command centre** for an Indian contract manufacturer. Supplier invoices arrive by email. A background agent ingests them, extracts the fields, reconciles each invoice against a work order, a goods-receipt note, a quality-check result and a rate contract, then decides: auto-approve, send to a human, reject, or quarantine.

The human interface exists for one reason: **show an AP associate only the invoices that need a decision, with the evidence already assembled, sorted by statutory deadline and money at risk.**

Company context: ~7,000 third-party suppliers, multi-state GST, ~4,000 invoices/month, three legal entities. Most suppliers are MSMEs, which makes every delay a statutory liability, not just slow admin.

## 2. THE LOOP THE APP MUST CLOSE

```
Email arrives → attachment stored → fields extracted → duplicate check
→ vendor identified by GSTIN → work order resolved → milestone cap checked
→ GRN qty checked → QC checked → rate contract checked → tax arithmetic checked
→ net-offs computed → MSME deadline computed
→ DECISION (auto-approve | exception | reject | quarantine)
→ evidence stored → human acts (or doesn't) → audit row written
```

Every arrow is real code. Nothing is pre-decided.

## 3. USERS

Five roles, switchable from a header menu. No passwords in Phase 1, but **role checks are enforced server-side on every mutating endpoint**, not just hidden in the UI.

| Role | Job | Lands on |
|---|---|---|
| AP Associate | Clear the exception queue | `/exceptions` |
| AP Lead | Throughput, ageing, ownership | `/inbox` grouped by owner |
| Controller | Cash, MSME exposure, blocked value | `/exceptions` (KPI strip) |
| Category Manager | Close GRN/QC gaps | `/exceptions` filtered to their assignments |
| Auditor | Reconstruct any decision | `/audit` |

## 4. SCOPE — PHASE 1 ONLY

**Build these six routes and nothing else:**

`/connections` · `/inbox` · `/invoices/:id` · `/exceptions` · `/procurement` · `/audit`

**Do not build, not even as a placeholder:** dashboard with charts, vendor master CRUD, rules editor, payment scheduling, WhatsApp, multi-currency, mobile layout, notifications, email sending, exports beyond CSV on `/audit`, settings pages, onboarding tours.

**A dead nav item is worse than an absent one.** If a feature is Phase 2, the only permitted signpost is one line of secondary text in `/connections`.

## 5. STACK

- **Frontend:** React + TypeScript + Tailwind + shadcn/ui. Vite. No component library beyond shadcn.
- **Backend:** FastAPI (Python 3.11) in the same repo, served under `/api`.
- **Database:** SQLAlchemy 2.x models, tables created on startup. Postgres if the platform provisions it; otherwise SQLite at `./storage/app.db`. Never in-memory — state must survive a reload.
- **PDF text extraction:** `pdfplumber` (text layer only). No OCR, no Tesseract, no external OCR service.
- **Realtime:** SSE endpoint `/api/events`. If the preview proxy buffers SSE, fall back to 3-second polling on `/api/invoices/changed-since?ts=` **and say so in `IMPLEMENTATION_NOTES.md`**. Never simulate progress.
- **File storage:** local disk under `./storage/attachments/`, content-addressed by SHA-256. Served only through an authenticated endpoint. Never a public path.

## 6. DATA MODEL

Create these tables. Field lists are the minimum; add indexes on the obvious lookup columns.

```
users            id, name, email, role
entities         id, name, erp_company_code, gstin
vendors          id, name, state_code, msme_registered, msme_udyam_no,
                 bank_verified, bank_last_changed_at, payment_terms_days
vendor_gstins    id, vendor_id, gstin, state_code, is_primary, verified_at
work_orders      id, wo_number, vendor_id, entity_id, total_value, currency,
                 retention_pct, opened_at, status
milestones       id, work_order_id, name, pct, sequence
rate_contracts   id, vendor_id, description, unit_rate, valid_from, valid_to
debit_notes      id, work_order_id, note_number, amount, reason, status, raised_at
grns             id, grn_number, work_order_id, received_at, received_by
grn_lines        id, grn_id, description, qty_received
qcs              id, qc_number, grn_id, inspected_at, status, rejected_qty, reason
invoices         id, source, message_id, attachment_sha256, attachment_path,
                 received_at, vendor_id, invoice_number, invoice_date,
                 invoice_total, subtotal, cgst, sgst, igst, freight,
                 retention, advances, debit_notes, net_payable,
                 stage, decision, blocking_rule, confidence_overall,
                 msme_due_date, owner_id, created_at, updated_at
invoice_lines    id, invoice_id, description, hsn, qty, rate, amount, tax_rate
invoice_wos      id, invoice_id, work_order_id, milestone_id, resolved_by,
                 confidence
match_checks     id, invoice_id, rule, status, evidence, source, checked_at,
                 sequence
audit_events     id, invoice_id, actor_id, actor_role, type, reason,
                 payload_json, before_json, after_json, created_at
quarantine       id, attachment_sha256, filename, reason_code, detail,
                 received_from, created_at, resolved_at
gmail_accounts   id, entity_id, email, refresh_token_encrypted, scopes,
                 history_id, last_synced_at, status
```

`audit_events` is **append-only**. Implement no update or delete path for it anywhere in code.

**State machine:** `RECEIVED → PARSING → IDENTIFIED → MATCHED → DECIDED → ACTIONED → SCHEDULED → PAID`
Terminal branches from `DECIDED`: `AUTO_APPROVED`, `EXCEPTION`, `REJECTED`, `QUARANTINED`.
Every transition writes an `audit_event`.

## 7. THE MATCHING ENGINE — deterministic, ordered, no LLM

Run these gates **in this order**. The first `fail` sets `blocking_rule`. All gates still run and all results are stored, so the UI can show the full trace.

| # | Gate | Passes when |
|---|---|---|
| 1 | Attachment integrity | SHA-256 stored, MIME is pdf/png/jpg, size ≤ 25 MB |
| 2 | Duplicate | No prior invoice with the same `message_id`, the same `attachment_sha256`, the same `(vendor_id, invoice_number, invoice_total)` — including across that vendor's other GSTINs — or the same `(gstin, invoice_number, invoice_total)` |
| 3 | Supplier identity | Printed GSTIN exists in `vendor_gstins`; no fuzzy name matching |
| 4 | GSTIN verified | That row's `verified_at` within 30 days |
| 5 | Classification | Document is an invoice (not credit note, debit note, or statement) |
| 6 | Extraction confidence | `confidence_overall ≥ 0.85` and no required field missing |
| 7 | WO resolution | Exact `wo_number` printed on the invoice, or inferred with confidence ≥ 0.85 |
| 8 | Milestone cap | `sum(invoices against this WO milestone) + this invoice ≤ pct × WO total_value` |
| 9 | GRN quantity | received qty ≥ invoiced qty |
| 10 | QC clearance | `qc.rejected_qty == 0` |
| 11 | Rate contract | invoiced unit rate == active `rate_contracts.unit_rate` for that vendor + description |
| 12 | Tax arithmetic | `sum(line amounts) + freight == subtotal`, `subtotal × tax_rate == cgst+sgst+igst`, `subtotal + taxes == invoice_total`, all to the paisa |
| 13 | Place of supply | IGST iff vendor state ≠ delivery state; CGST+SGST otherwise |
| 14 | TDS | 194C at 2% or 194Q at 0.1% computed and shown as **withheld at payment** — informational, never deducted from `net_payable` |
| 15 | MSME window | `msme_due_date = invoice_date + 45 days` if vendor MSME, else payment terms |
| 16 | Bank detail | No bank-change request attached to this invoice; if one is, the vendor's `bank_verified` must already be true and `bank_last_changed_at` older than the request |
| 17 | Threshold | `net_payable ≤ ₹5,00,000`, otherwise dual control required |

**Decision rule:**
- `REJECTED` — gate 2 fails (the invoice is a duplicate).
- `QUARANTINED` — no invoice record can be created: no text layer, unreadable, or classification says it is not an invoice. The row goes to the `quarantine` table instead.
- `AUTO_APPROVED` — gates 1–16 all pass **and** gate 17 passes.
- `EXCEPTION` — an invoice record exists but at least one gate failed.

A single missing field on an otherwise readable invoice is an `EXCEPTION`, never a quarantine.

**Net payable**, computed as a waterfall, each step stored with its source:

```
invoice_total
− rejected lines (qty × rate, plus tax at the line's rate)
− retention (`work_orders.retention_pct` × accepted pre-tax value)
− open `debit_notes` rows for this work order
− advances already paid against this WO
= net_payable
```

Gate 10 failing and a debit note for rework are **different things**. Never deduct the same units twice.

## 8. EXTRACTION PIPELINE

Strategy chain, in order. Each field records which strategy produced it and a confidence.

1. **Label-anchored regex** on the pdfplumber text layer — invoice number, date, GSTIN, PO/WO number, line items, tax lines, total.
2. **Arithmetic reconciliation** — if line sums and the printed total agree, confidence rises; if they disagree, confidence falls and gate 12 fails.
3. **LLM fallback** only for fields still missing after 1 and 2, using the model integration available in this environment. Any field sourced this way is marked `source: "llm"` and capped at confidence 0.8.

Hard rules:
- No field is ever guessed silently. A missing field is `null`, and gate 6 fails.
- If the PDF has no text layer (image-only scan), the document goes to `quarantine` with `reason_code: no_readable_text`. It does not error, does not 500, and is never silently dropped.
- Store the original attachment byte-for-byte. Never rewrite, re-encode, or normalise it.
- Extraction runs in a background task. The invoice row is created first with `stage: RECEIVED`, so the UI can show it immediately.

## 9. INTAKE

Three channels. All three converge on one function `ingest_attachment(bytes, filename, source, message_id)`.

**A. Gmail (primary).**
OAuth 2.0, scope `https://www.googleapis.com/auth/gmail.readonly` **only** — do not request modify, do not request send. Offline access; refresh token encrypted with AES-GCM using a key from `SECRET_KEY`. Incremental sync on `historyId`, 120-second poll fallback, concurrency cap 4. Ingest messages that have attachments; skip inline images and signature blocks under 60 KB. Retry with exponential backoff, 5 attempts, then quarantine with the exact error string.

If `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` are not set, `/connections` renders a **setup card** listing the exact env vars and the redirect URI to register, with the Connect button disabled. It must never render a fake "Connected" state.

**B. Forwarding address.**
Each entity gets `ap+<entity>@<inbound-domain>`. A `POST /api/inbound/email` endpoint accepts multipart email (or a JSON payload with base64 attachment), verifies an HMAC signature header, and calls the same ingestion function. This is how a supplier who emails the shared inbox gets in without OAuth.

**C. Portal upload.**
Drag-and-drop in `/connections`, accepting `.pdf .png .jpg .eml`, max 25 MB, multiple files. Same ingestion function, `source: "portal"`.

None of these three is a fallback for another in the code — they are peers. The UI says which source each invoice came from.

## 10. SCREENS

### 10.1 `/connections`
Cards, top to bottom: **Gmail** (account, scopes, token expiry, last sync, scanned today, ingested, failed, Sync now / Reconnect / Revoke) · **Forwarding address** (the address per entity, copy button, HMAC secret status, last received) · **Portal upload** (dropzone) · **Quarantine** (list with reason, open original, reclassify, dismiss) · **Health strip** (token state, retry queue depth, last error). One line of secondary text: *"ERP posting and WhatsApp intake are Phase 2."*

### 10.2 `/inbox`
Virtualised table, sticky header, fixed widths:
`Supplier (220) · Invoice # (140) · WO (150) · Amount (130, right, tabular) · GSTIN (160, mono) · MSME due (120) · Stage (140) · Decision (150) · Owner (120) · Updated (110)`

- Overdue MSME rows: 3 px left rule in `destructive`. Due ≤ 7 days: 3 px in `warning`. Never a full-row colour wash.
- Hover reveals a two-line "why it is here".
- Filters: decision, stage, entity, vendor, due window, amount range, owner, `needs me`.
- Saved views: `My queue`, `Due in 7 days`, `Blocked by QC`, `Duplicates`, `Quarantined`.
- Bulk actions enable only when every selected row passes the same gate; if not, the disabled button names the blocking rows.

### 10.3 `/invoices/:id` — the core screen
Three resizable panes, split persisted per user in `localStorage`.

**Left — Document.** The original PDF/image rendered in an `<iframe>` or canvas, page thumbnails, zoom. Hovering an extracted field highlights its region. A `confidence` toggle underlines fields below 0.85 in amber with the raw text on hover.

**Middle — Reconciliation.** One table, no tabs:

| Line | Inv qty | Inv rate | WO qty | WO rate | GRN recv | QC | Delta | Verdict |

Then the net-payable waterfall as rows, each with a source link. Then the GST split and TDS note.

**Right — Decision.**
- Decision pill: `Auto-approved` / `Needs review` / `Rejected` / `Quarantined`.
- **Rule trace:** all 17 gates, numbered, each `rule · pass|fail|unknown · one-line evidence · source · timestamp`. Failing gates expanded by default; passing gates collapsed but present.
- **Actions:** `Approve` · `Approve undisputed portion` · `Raise debit note` · `Hold pending GRN` · `Request vendor correction` · `Escalate`. Each opens an inline panel with a prefilled reason and an editable vendor message. Financial actions confirm with the amount in digits and words.
- **Timeline:** actor, role, timestamp, before → after. Append-only.

Above ₹5,00,000 the Approve button shows *"Second approval required — [approver name] pending"* and the server returns 403 for a single actor.

### 10.4 `/exceptions`
KPI strip (64 px, five cells, each with its period and a link to its rows): `Open exceptions` · `Touchless rate (30d)` · `MSME exposure < 7d` · `Blocked value` · `Median cycle time (30d)`.

Rows sorted by `days_to_msme_deadline ASC, net_payable DESC`, with the sort rule in a tooltip. Each row: supplier, amount, **the single blocking rule**, days to deadline, owner, recommended next step, evidence count. Claim / reassign / snooze (snooze requires a reason and never hides the deadline).

### 10.5 `/procurement` — the system of record
Four tabs: **Work orders** · **GRNs** · **QC results** · **Rate contracts**.

This screen exists because Phase 1 has no ERP connection. It is the system of record, and the UI says so in one line at the top: *"Phase 1 system of record. ERP sync arrives in Phase 2."* Keep it functional, not decorative: list, filter, open a record, edit the fields the matching engine reads (qty received, rejected qty, unit rate, milestone %, WO total).

### 10.6 `/audit`
Filter by invoice, actor, rule, date range. CSV export. Immutable; no edit affordance rendered anywhere.

## 11. METRIC DEFINITIONS — use exactly these, invent no others

| Metric | Definition |
|---|---|
| Open exceptions | count(stage = DECIDED AND decision = EXCEPTION) |
| MSME exposure < 7d | sum(net_payable) where vendor.msme_registered and msme_due_date between now and now+7d and stage ≠ PAID |
| Blocked value | sum(net_payable) where decision = EXCEPTION |
| Median cycle time | median(first_decision_at − received_at) over decided invoices, last 30 days |
| Touchless rate | count(AUTO_APPROVED with no human action) / count(decided), last 30 days |

Every KPI shows its period and links to the rows behind it.

## 12. DESIGN

Operational density, not marketing. Neutral canvas (`#FAFAF9` light / `#0C0A09` dark), single accent `#4F46E5`, semantic colour reserved for state only. One sans for UI, one mono for money, GSTINs, and document numbers. Tabular numerals wherever money aligns.

8-pt grid. 1 px borders. No gradients, no glassmorphism, no shadow above 2 px. Target 1440×900, usable at 1280 with no horizontal scroll on `/inbox`. Visible focus rings, AA contrast, `prefers-reduced-motion` respected.

Keyboard: `J/K` move · `Enter` open · `A` approve · `H` hold · `D` debit note · `Esc` close · `/` search.

Indian money format everywhere: `₹10,39,800.00`. Dates `14 Nov 2026`. Deadlines `due in 6 days` / `overdue by 2 days`.

## 13. BANNED

In UI copy, seed data, and labels — never:

`expected` · `mock` · `demo` · `sample` · `fixture` · `dummy` · `test data` · `lorem`

In code — never in a progress, stage, or streaming path:

`setTimeout` · `sleep()` · any `await new Promise(r => setTimeout(...))`

Never:
- Render a decision before the matching engine has run for that invoice.
- Render a "Connected" state without a real token.
- Leave a `try/except: pass`. Failures go to `quarantine` or the audit log with the exact error.
- `alert()`, `console.log` as UI, or a dead nav item.

## 14. SEED DATA

Seed it as **system-of-record data**, not as answers. No table may carry a `decision`, `expected`, or `status` column that pre-decides an invoice. Outcomes are computed by the engine on first boot.

**Vendors (5):** Shakti Precision Works (GJ, MSME, two GSTINs: 24AABCS4567K1ZP primary and 24AABCS4567K2ZQ branch) · Anand Tooling & Dies (29AACCA1234M1Z9, KA, MSME) · Maharashtra Steel Supply (27AADCM5678N1ZR, MH, not MSME) · Precision Coatings (29AAECP9012Q1Z4, KA, MSME) · Sunrise Logistics (29AAFCS3456R1Z7, KA, MSME). All GSTINs verified within the last 30 days.

**Work orders (4):** ZW-WO-2026-00841 Shakti ₹18,00,000 (30/60/10, retention 5%) · ZW-WO-2026-00902 Anand ₹6,40,000 (40/50/10, retention 0%) · ZW-WO-2026-01033 Maharashtra Steel ₹4,20,000 (0/100/0, retention 0%) · ZW-WO-2026-01117 Precision Coatings ₹9,50,000 (30/60/10, retention 5%).

**Debit notes:** one open note, DN-2026-0311, ₹12,000 against WO-841, reason *rework on 2 units rejected at QC #9921*.

**History (not an answer key):** one prior invoice, Shakti 30% advance ₹5,40,000 against WO-841, ingested 10 days ago and now `PAID`. It exists so the duplicate rule has a real target.

**GRNs and QCs:** one per WO. WO-841 has GRN #4821 (40 of 40 received) and QC #9921 (rejected 2, dimensional deviation 0.4 mm). All others pass clean.

**Rate contracts:** Shakti machined bracket ₹24,000/unit · Anand die insert ₹8,000/unit · Maharashtra MS plate ₹52/kg · Precision powder coat ₹95/sq ft.

**Invoice corpus — 7 new PDFs in seven different layouts, generated as files under `seed/invoices/` and fed through the real intake on first boot.** With the one paid history invoice, `/inbox` shows 8 rows.

| # | Document | Expected outcome — computed, never stored |
|---|---|---|
| 1 | Anand, dispatch milestone 50%, GRN 20/20, QC pass, ₹3,77,600 | `AUTO_APPROVED`, all gates pass |
| 2 | Tally PDF, WO number not printed, vendor + amount unambiguous | `EXCEPTION` at gate 7 — WO inferred at 0.62, associate confirms |
| 3 | Shakti 30% advance, same number and amount as the paid history invoice | `REJECTED` at gate 2, links that prior invoice and its payment |
| 4 | Shakti, 40 units @ ₹24,000, full GRN, QC rejects 2 | `EXCEPTION`, partial approval ₹10,39,800 + debit note |
| 5 | Invoice #4 resubmitted under Shakti's branch GSTIN | `REJECTED` at gate 2, duplicate across GSTINs |
| 6 | Clean invoice + attached bank-detail change request | `EXCEPTION` at gate 16, routed to dual control with a callback log |
| 7 | Image-only scan, no text layer | `QUARANTINED`, `no_readable_text` |

**Invoice #4 is the reference calculation. Match it to the paisa:**

```
40 × ₹24,000                       = ₹9,60,000
+ freight                              ₹18,000
= subtotal                         = ₹9,78,000
+ IGST 18%                            ₹1,76,040
= invoice_total                  = ₹11,54,040.00
− 2 rejected units (₹48,000 + ₹8,640 IGST)  −₹56,640.00   → ₹10,97,400.00
− retention 5% of ₹9,12,000                 −₹45,600.00   → ₹10,51,800.00
− debit note DN-2026-0311 (rework)          −₹12,000.00   → ₹10,39,800.00
```

Recommended action on that invoice: `Approve ₹10,39,800.00 · raise debit note ₹12,000.00 · 2 units rejected at QC`. Above ₹5,00,000, so a second approver is required.

## 15. ACCEPTANCE CRITERIA

Each must be demonstrable in the running preview. Report each as pass or fail — a fail must name what is missing.

1. First boot ingests the 7 new invoices through the real pipeline; `/inbox` shows 8 rows (7 new + 1 paid history) with every decision computed, none stored.
2. Invoice #4 shows `₹10,39,800.00`, and the waterfall, the reconciliation table and the rule trace all agree with it.
3. Invoice #7 is `QUARANTINED` with reason `no readable text`, is clickable, and produced no 5xx in the logs.
4. Invoice #5 is `REJECTED` and links invoice #4 as the prior voucher.
5. Invoice #2 is an `EXCEPTION` on gate 7 with the inference confidence shown.
6. Invoice #6 is an `EXCEPTION` on gate 16 with the callback log visible in its decision pane.
7. Approving invoice #4 as AP Associate returns 403 (above threshold) and writes **no** `APPROVED` audit row; approving as AP Lead then succeeds and writes two audit rows.
8. A Category Manager calling the approve endpoint gets 403.
9. Uploading a duplicate PDF through `/connections` is rejected by the same gate-2 rule and links the original.
10. Hard reload preserves stage, decision, owner and full audit history.
11. `grep -rniE "expected|mock|demo|sample|fixture|dummy" src/` returns nothing outside test files and `IMPLEMENTATION_NOTES.md`.
12. `grep -rn "setTimeout\|sleep(" src/` returns nothing in a progress, stage or streaming path.
13. Keyboard only: `J J Enter A Enter` clears one exception from `/exceptions`.

## 16. BUILD SEQUENCE — STOP AFTER EACH PHASE

Do not attempt this in one pass. After each phase, post the preview link and a one-line status, then **wait for me to say continue**.

**Phase A — skeleton.** DB schema, migrations, state machine, audit writer, 5 seeded users, empty routes for the six screens with real empty states. Seeded vendors, WOs, milestones, GRNs, QCs, rate contracts on `/procurement`.

**Phase B — extraction and matching.** Intake function, portal upload, pdfplumber extraction with per-field confidence, all 17 gates, decision, net-payable waterfall, quarantine. Seeded invoices ingest on boot. `/inbox` and `/invoices/:id` become real.

**Phase C — human loop.** Actions, dual control, role enforcement, `/exceptions` with KPI strip, `/audit`, SSE or polling.

**Phase D — Gmail.** OAuth flow, encrypted refresh token, historyId sync, retry and quarantine, the setup card when credentials are absent.

**Phase E — polish.** Keyboard shortcuts, confidence overlay, saved views, CSV export, the two grep checks, `IMPLEMENTATION_NOTES.md` mapping all 13 acceptance criteria to code and evidence.

## 17. WHEN BLOCKED

Do not invent an integration, and do not fake a state to make a screen look finished.

- Missing Google credentials → render the setup card and continue with Phases A–C.
- `pdfplumber` cannot parse a seeded PDF → regenerate that PDF so it has a text layer, and note it. Do not add OCR.
- SSE does not stream through the preview proxy → switch to polling, note it in `IMPLEMENTATION_NOTES.md`.
- A gate cannot be implemented as specified → implement it as `unknown` with the reason, never as `pass`.

Write `IMPLEMENTATION_NOTES.md` as you go: what was built, what was deferred, every assumption, and the 13-criterion scorecard.
