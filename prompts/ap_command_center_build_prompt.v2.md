# Build Prompt v2 — "AP Command Center" (Zetwerk-shaped)

> Paste everything below the line into a coding agent (Claude Code, Cursor, Codex, Lovable, v0).
> Fill the `<< >>` block first. Do not trim Section 2 (Hard Constraints) or Section 12 (Acceptance) — they are the load-bearing parts.

---

## 0. VARIABLES — fill these before running

| Variable | Value |
|---|---|
| `<<COMPANY>>` | Zetwerk |
| `<<INVOICES_PER_MONTH>>` | 4000 |
| `<<ERP>>` | SAP S/4HANA (confirm on day 1; if unknown, isolate behind an adapter) |
| `<<MAILBOX>>` | ap.invoices@zetwerk.com |
| `<<LEGAL_ENTITIES>>` | 3 (IN-MFG, IN-TRADE, IN-EXPORTS) |
| `<<APPROVAL_THRESHOLD>>` | ₹5,00,000 |
| `<<ACCENT>>` | #4F46E5 |
| `<<STACK>>` | Next.js 15 App Router + TypeScript + Tailwind + Postgres (Prisma) + a Python worker for PDF extraction |

If a variable is unknown, do not guess silently — pick the value, record it in `ASSUMPTIONS.md`, and continue.

---

## 1. ROLE

You are a **forward-deployed engineer and product designer**. You ship production-shaped internal tools for finance operations, not demos.

Your expertise:
- Multi-tenant Next.js apps with server actions and streaming
- PDF/OCR extraction pipelines and confidence scoring
- Accounts-payable domain: 3-way match, GRN, QC, GST/TDS, MSME statutory deadlines
- Dense, keyboard-first operational UI

**Operating rules**
1. Build the working interface first. No slide deck, no wireframe-only deliverables.
2. Every number on screen traces to a database row or a computed function. If it can't, it doesn't ship.
3. Prefer boring, explicit code over clever abstraction. One file per concern.
4. When a requirement is ambiguous, pick the boring option, write it in `ASSUMPTIONS.md`, move on. Do not stop to ask unless you are blocked on a credential.
5. Never stub silently. A stub must be `throw new Error("not implemented: <what> — <why>")`, never a fake success.

---

## 2. HARD CONSTRAINTS

**MUST NOT appear anywhere in the UI or seeded data:**

| Banned | Why |
|---|---|
| `expected`, `Expected:` | The system must not know the answer before it runs |
| `mock`, `demo`, `sample`, `fixture`, `dummy`, `test data` | User-facing copy describes real work |
| `setTimeout`, `sleep`, `await new Promise(r => setTimeout` in any progress path | Progress is measured, never simulated |
| A decision rendered before a pipeline run exists for that invoice | No pre-computed answer keys |
| Dead nav items, `alert()`, `console.log` as UI | Unfinished surface area |

**MUST hold:**

1. Every stage duration is a measured timestamp delta stored in the DB (`started_at`, `ended_at`), rendered as-is — 40 ms shows as 40 ms.
2. Every badge, KPI, or status is a link or button that reveals its evidence, source rows, and the query that produced it.
3. MSME payment deadline is visible on the invoice list row, the detail header, and the KPI strip on `/exceptions`.
4. Approve / Hold / Debit note / Request correction / Escalate are real mutations: they write an audit row and change state.
5. The audit log is append-only. No update or delete path exists in code, not just in UI.
6. Unreadable input goes to Quarantine with a plain-English reason. It never 500s and is never dropped.
7. Above `<<APPROVAL_THRESHOLD>>`, approval requires a second actor. The UI shows who is pending.
8. Empty, loading, error, and permission-denied states exist for every route. No route renders a spinner forever.

---

## 3. PRODUCT TRUTH

`<<COMPANY>>` is a contract manufacturer: **1,802 enterprise customers, ~6,979 third-party suppliers, 26 owned facilities, FY26 revenue ₹15,913 cr**. Supplier invoices settle against a **work order and a milestone** (e.g. 30% advance / 60% dispatch / 10% installation), then reconcile with **GRN + QC + rate contract**, then GST/TDS, then net-offs (debit notes, advances, retention).

Two forces make this urgent and are the reason the interface exists:

- **Statutory clock.** MSMED §15 requires payment within 45 days; §16 charges 3× bank rate interest. Income Tax §43B(h) disallows the expense until an MSME supplier is paid. A slow queue is interest expense plus a deferred deduction.
- **Reconstruction, not extraction.** The associate's day is spent joining work order, GRN, QC report, rate contract, GST portal and bank data by hand. That join is the product.

The interface has one job: **show the associate only what needs a human decision, with the evidence already assembled, sorted by deadline × amount at risk.**

Currency INR, Indian grouping: `₹10,39,800.00`. Dates `14 Nov 2026`. Deadlines `due in 6 days` / `overdue by 2 days`.

---

## 4. USERS

| User | Job | Lands on |
|---|---|---|
| AP Associate (primary) | Clear the exception queue before deadlines | `/exceptions` |
| AP Lead | Throughput, ageing, ownership | `/inbox` grouped by owner |
| Controller | Cash, MSME exposure, leakage | `/exceptions` (KPI strip) |
| Category Manager | Close GRN/QC gaps | `/exceptions` filtered to items assigned to them |
| Auditor | Reconstruct any decision | `/audit` |

No login wall beyond a user switcher for these five roles. Role gates are real (a category manager cannot approve an invoice).

---

## 5. SCOPE FENCE

**Phase 1 — must exist and work end to end:**

`/connections` · `/inbox` · `/invoices/[id]` · `/exceptions` · `/audit`

**Phase 1 — must NOT exist, not even as a placeholder:** Dashboard, Vendors, Rules editor, payment scheduling, WhatsApp, multi-currency, mobile layout. Mid-Phase-1 features are worse than absent ones.

**Allowed Phase 2 signposting:** exactly one `Phase 2` chip in the left nav footer, and one line in `/connections` under "Not yet connected: ERP posting, WhatsApp Business." Nothing else.

---

## 6. INFORMATION ARCHITECTURE

Left rail, 240 px, collapsible to 56 px:
`Exceptions` · `Inbox` · `Audit` · `Connections` — and a `Phase 2` chip.

Top bar, 56 px: global search (`/` opens, searches invoice no, supplier, WO, amount), entity switcher, deadline-breach bell, user switcher.

---

## 7. SCREENS

### 7.1 `/connections`

```
┌ Gmail ───────────────────────────────────────────────┐
│ ap.invoices@zetwerk.com            ● Connected       │
│ Scopes: gmail.readonly   Token expires: 12 Mar 2027  │
│ Last sync 09:41:12 · historyId 8842193               │
│ Scanned today 214 · Ingested 61 · Quarantined 3      │
│ [Sync now]  [Reconnect]  [Revoke]                    │
└──────────────────────────────────────────────────────┘
┌ Ingestion rules ─────────────────────────────────────┐
│ Labels watched · allowed types (pdf,png,jpg) · max 25MB │
│ Sender allow/deny · mailbox → legal entity → ERP code │
└──────────────────────────────────────────────────────┘
┌ Quarantine (3) ──────────────────────────────────────┐
│ 14 Nov 09:22 · "scan_0041.pdf" · no readable text     │
│   [Open original] [Reclassify] [Ask vendor for copy]  │
└──────────────────────────────────────────────────────┘
Health strip: token state · API quota · retry queue depth · last error
```

### 7.2 `/inbox`

Columns, fixed widths, virtualised past 200 rows:
`Supplier (220) · Invoice # (140) · WO (150) · Amount (130, right, tabular) · GSTIN (160, mono) · MSME due (120) · Stage (140) · Decision (150) · Owner (120) · Updated (110)`

- Sticky header; row hover shows a 2-line "why it is here".
- Overdue MSME rows carry a left 3 px rule in `danger`; due ≤ 7 days in `warning`. Never a colour wash.
- Filters: status, entity, supplier, due window, decision, amount range, owner, `needs me`.
- Saved views: `My queue` · `Due in 7 days` · `Blocked by GRN` · `Duplicates` · `Unreadable`.
- Bulk select: actions are enabled only where every selected row passes the same gate; otherwise the disabled button states the blocking row count.

### 7.3 `/invoices/[id]` — the core screen

Three panes, resizable, split persisted per user.

**Left — Document.** Original attachment rendered from a signed URL. Page thumbnails, zoom, rotate. Hovering an extracted field highlights its bounding box. Toggle `confidence` → fields under 0.85 get an amber dotted underline plus the raw value on hover; no red washes.

**Middle — Reconciliation.** One table, no tabs:

| Line | Inv qty | Inv rate | WO qty | WO rate | GRN recv | QC | Delta | Verdict |

Footer waterfall: `Invoice total → - disputed lines → - retention → - debit notes → - advances → Net payable`. Each step is a row with its own source link.

**Right — Decision.**
- Decision pill: `Auto-approved` · `Needs review` · `Rejected` · `Quarantined` · `Paid`.
- Rule trace: numbered, each row `rule · pass|fail|unknown · one-line evidence · source link · checked_at`.
- Actions: `Approve` · `Approve undisputed portion` · `Raise debit note` · `Hold pending GRN` · `Request vendor correction` · `Escalate`. Each opens an inline panel (no modal chain) with a prefilled reason and an editable vendor message.
- Timeline: actor · timestamp · before → after. Append-only.

### 7.4 `/exceptions`

KPI strip, 64 px, four cells, each with its period and a link to its rows:

`Open exceptions (now)` · `MSME exposure < 7d (₹, now)` · `Blocked value (₹, now)` · `Median cycle time (last 30d)`

Dense rows sorted by `days_to_msme_deadline ASC, net_payable DESC` (sort rule stated in a tooltip). Each row: supplier, amount, **the one rule that failed**, days to deadline, owner, recommended next step + evidence count. Claim / reassign / snooze (snooze requires a reason and never hides the deadline).

### 7.5 `/audit`

Filter by invoice, actor, rule, date. Export CSV. Every row immutable; no edit affordance rendered anywhere.

---

## 8. DATA CONTRACTS

```ts
Invoice {
  id, source: 'gmail' | 'upload' | 'portal',
  message_id, attachment_sha256, received_at,
  supplier: { name, gstin, msme_registered, bank_verified },
  invoice_number, invoice_date, currency: 'INR',
  work_orders: [{ wo_number, milestone, milestone_pct }],
  lines: [{ description, hsn, qty, rate, amount, tax_rate }],
  invoice_total,          // as printed on the document
  subtotal, cgst, sgst, igst, freight, retention, advances, debit_notes,
  net_payable,            // null until MATCHED; computed, never extracted
  irn?, eway_bill?,
  stage, decision, confidence: { overall, fields: Record<string, number> },
  msme_due_date, owner_id, created_at, updated_at
}

MatchEvidence {
  invoice_id,
  checks: [{ rule, status: 'pass' | 'fail' | 'unknown', evidence, source, checked_at }],
  grn?: { number, received_qty, date },
  qc?: { status, rejected_qty, reason },
  deltas: [{ line, invoice_value, wo_value, delta, verdict }]
}

AuditEvent { id, invoice_id, actor_id, actor_role, type, reason, payload, before, after, created_at }
```

State machine:
`RECEIVED → PARSING → IDENTIFIED → MATCHED → DECIDED → (AUTO_APPROVED | EXCEPTION | REJECTED | QUARANTINED) → ACTIONED → SCHEDULED → PAID`

Every transition writes an `AuditEvent`. Duplicates terminate at `DECIDED`/`REJECTED`.

### 8.1 Worked example — this is the target output, match it exactly

Input: one email, attachment `INV-ZW-8841.pdf`.

```json
{
  "invoice_number": "INV/2026/8841",
  "invoice_date": "2026-11-14",
  "supplier": { "name": "Shakti Precision Works", "gstin": "24AABCS4567K1ZP", "msme_registered": true },
  "work_orders": [{ "wo_number": "ZW-WO-2026-00841", "milestone": "dispatch", "milestone_pct": 60 }],
  "lines": [{ "description": "Machined bracket, Rev-C", "hsn": "73269099", "qty": 40, "rate": 24000, "amount": 960000, "tax_rate": 18 }],
  "subtotal": 978000, "freight": 18000, "igst": 176040, "invoice_total": 1154040
}
```

Evidence produced:

```json
{
  "checks": [
    { "rule": "GSTIN active on GSTN",        "status": "pass", "evidence": "24AABCS4567K1ZP active, registered 2019-04-02", "source": "gstn", "checked_at": "2026-11-14T09:41:02+05:30" },
    { "rule": "Duplicate (GSTIN, no, amount)", "status": "pass", "evidence": "no prior voucher", "source": "ledger", "checked_at": "2026-11-14T09:41:03+05:30" },
    { "rule": "WO exists + milestone cap",   "status": "pass", "evidence": "ZW-WO-2026-00841, 60% of ₹18,00,000 = ₹10,80,000 cap, ₹9,60,000 invoiced to date", "source": "erp", "checked_at": "2026-11-14T09:41:05+05:30" },
    { "rule": "GRN quantity",                "status": "pass", "evidence": "GRN #4821 received 40 of 40", "source": "grn", "checked_at": "2026-11-14T09:41:06+05:30" },
    { "rule": "QC clearance",                "status": "fail", "evidence": "QC #9921 rejected 2 units — dimensional deviation 0.4 mm", "source": "qc", "checked_at": "2026-11-14T09:41:07+05:30" },
    { "rule": "Rate contract",               "status": "pass", "evidence": "₹24,000/unit matches RC-2026-114", "source": "erp", "checked_at": "2026-11-14T09:41:07+05:30" },
    { "rule": "GST place of supply",         "status": "pass", "evidence": "GJ → KA inter-state, IGST 18% correct", "source": "gstn", "checked_at": "2026-11-14T09:41:08+05:30" },
    { "rule": "TDS 194C",                    "status": "pass", "evidence": "2% on ₹9,12,000 = ₹18,240 withheld at payment, not deducted from payable", "source": "rules", "checked_at": "2026-11-14T09:41:08+05:30" },
    { "rule": "MSME payment window",         "status": "pass", "evidence": "MSME registered, due 2026-12-29, 6 days", "source": "rules", "checked_at": "2026-11-14T09:41:09+05:30" }
  ],
  "deltas": [{ "line": 1, "invoice_value": 960000, "wo_value": 912000, "delta": -48000, "verdict": "2 of 40 units rejected at QC" }]
}
```

Rendered outcome, and the only acceptable one:

- Decision pill: `Needs review`
- Net payable waterfall — each line links to its source:

| Step | Amount | Running |
|---|---|---|
| Invoice total | ₹11,54,040.00 | ₹11,54,040.00 |
| − 2 units rejected at QC #9921 (₹48,000 + ₹8,640 IGST) | −₹56,640.00 | ₹10,97,400.00 |
| − Retention 5% of accepted value ₹9,12,000 | −₹45,600.00 | ₹10,51,800.00 |
| − Debit note DN-2026-0311 (rework, QC #9921) | −₹12,000.00 | **₹10,39,800.00** |

- Recommended action: `Approve ₹10,39,800.00 · raise debit note ₹12,000.00 · 2 units rejected at QC`
- Guardrail: `₹10,39,800.00 > ₹5,00,000.00 → second approval required`

The rejection reduces quantity *and* raises a debit note for a different reason (rework). Doing both for the same two units would double-count — the waterfall above is the only acceptable arithmetic.

Note what the example does *not* contain: an "expected" label, a confidence of 1.0, or a decision computed before the checks ran.

---

## 9. GMAIL INGESTION

- OAuth 2.0 with `gmail.readonly` only. Do not request `gmail.modify` in Phase 1. Offline access; refresh token encrypted at rest (AES-GCM, key from env, never in the repo).
- Incremental sync on `historyId`; fallback poll every 120 s; concurrency cap 4.
- Ingest messages with attachments; skip inline images and signatures (< 60 KB, `Content-Disposition: inline`).
- Dedupe key: `message_id` + `attachment_sha256` + `(gstin, invoice_number, amount)`.
- Classify: invoice · credit note · debit note · statement · non-invoice. Non-invoices → Quarantine with a reason from a closed set: `not an invoice` · `encrypted` · `unsupported type` · `no readable text` · `supplier unknown`.
- Entity routing: mailbox + label → legal entity → ERP company code.
- Retries: exponential backoff, 5 attempts max, then Quarantine carrying the exact error string.
- Store the original attachment byte-for-byte, hash it, never rewrite it. Serve via signed URL, never a public path.
- `/connections` must state retention and PII policy in one sentence a human can read.
- **Sandbox mode:** a `GMAIL_MODE=sandbox` env flag that reads from a local `.eml` directory through the identical ingestion interface. Same code path, no branching inside the parser.

---

## 10. METRIC DEFINITIONS — use these formulas, do not invent others

| Metric | Formula |
|---|---|
| Touchless rate | `count(decision = AUTO_APPROVED AND actor IS NULL) / count(stage >= DECIDED)` over period |
| Open exceptions | `count(stage = DECIDED AND decision = EXCEPTION)` now |
| MSME exposure < 7 days | `sum(net_payable) WHERE msme_registered AND msme_due_date BETWEEN now AND now + 7d AND stage < PAID` |
| Blocked value | `sum(net_payable) WHERE decision = EXCEPTION` |
| Median cycle time | median(`first_decision_at − received_at`) over decided invoices |
| Exception rate by rule | `count(checks[rule].status = 'fail') / count(checks[rule])` |

Each KPI renders its period and source as secondary text, and links to the underlying rows.

---

## 11. INTERACTION AND VISUAL

Keyboard: `J/K` move · `Enter` open · `A` approve · `H` hold · `D` debit note · `C` correction · `Esc` close · `/` search · `?` shortcuts.

- Optimistic UI only for non-financial actions, with 5 s undo. Financial actions confirm with the amount spelled out in words and digits.
- Inline panels, never modal chains; the document stays visible.
- Tables virtualised past 200 rows; interactions under 200 ms on a 4-year-old laptop.
- Errors state what happened, what was preserved, and the next action. Never "Something went wrong."

Visual: neutral canvas (`#FAFAF9` / `#0C0A09`), one accent `<<ACCENT>>`, semantic colour reserved for state only. One sans for UI, one mono for money, GSTINs, WO and invoice numbers. Tabular numerals wherever money aligns. 8-pt grid; 1 px borders; no gradients, no glassmorphism, no drop shadows above 2 px. Target 1440×900, usable at 1280 with no horizontal scroll on the inbox table. Visible focus rings, AA contrast, `prefers-reduced-motion` respected.

---

## 12. ACCEPTANCE CRITERIA — executable, not vibes

Each must be provable by a command or a test file you ship.

1. Drop a `.eml` with a PDF into the sandbox inbox → the invoice appears in `/inbox` via SSE **without a refresh**, with the email's real `received_at`.
2. For any invoice, the PDF, the reconciliation table, and the rule trace agree on `net_payable` — asserted by a test over the seeded corpus.
3. Resubmitting the same attachment → `Rejected`, with the prior invoice number and voucher linked.
4. A text-free PDF → `Quarantined`, reason `no readable text`, row clickable, no 5xx in logs. Test asserts the 200 response and the audit row.
5. GSTIN mismatch → exception showing both GSTINs; the Approve button is disabled and its tooltip names the blocking rule.
6. An MSME invoice due in 3 days appears on the row, in the detail header, and inside the `/exceptions` KPI strip — same number, one source.
7. Approve → stage advances, audit row written with actor and timestamp, page revalidates, all KPIs recompute.
8. Partial approval → debit note row created, waterfall recomputed, `net_payable` equals the sum of the waterfall steps to the paisa.
9. `grep -rniE "expected|mock|demo|sample|fixture|dummy" src/ app/ components/` returns zero hits outside `ASSUMPTIONS.md` and test files.
10. `grep -rn "setTimeout\|sleep(" app/ components/` returns zero hits in any progress, stage, or streaming path.
11. Hard reload → state, queue position, and full audit history survive; no client-only truth.
12. Keyboard only: `J` `J` `Enter` `A` `Enter` clears one exception with a passing test that drives those keys.
13. Above `<<APPROVAL_THRESHOLD>>`, approve by a single actor is refused server-side (not just disabled in UI); the test asserts the 403 and that no `APPROVED` audit row was written.
14. Role gate: a `CATEGORY_MANAGER` calling the approve action gets 403.
15. First paint at 1280×800 shows the inbox table with no horizontal scroll and no layout shift.

---

## 13. SEED CORPUS — seven documents, seven layouts

Build these as real files under `seed/`, each with a matching `.eml`. Each must produce a different, correct outcome — deriving it from the pipeline, not from a column in the seed.

| # | Document | Must produce |
|---|---|---|
| 1 | Tally-style PDF, WO referenced, GRN complete | `AUTO_APPROVED`, full rule trace all pass |
| 2 | Phone photo of an invoice, no WO printed, noisy | `EXCEPTION` — WO inferred with confidence < 0.85, associate confirms |
| 3 | Milestone invoice (30% advance) on a WO already at 30% | `REJECTED` duplicate-milestone, links prior invoice |
| 4 | Full GRN, QC rejects 2 of 40 units | `Needs review`, partial approval + debit note (use the §8.1 arithmetic exactly) |
| 5 | Same invoice resubmitted under a second GSTIN | `REJECTED` duplicate across GSTINs |
| 6 | Clean invoice + bank-detail change request | `EXCEPTION` routed to dual-control review, callback log required |
| 7 | Unreadable scan | `QUARANTINED`, reason `no readable text` |

No seed file may contain a `decision`, `expected`, or `status` column. Outcomes are computed.

---

## 14. BUILD ORDER AND DEFINITION OF DONE

1. Schema + migrations + state machine + audit writer (tests first).
2. Ingestion (sandbox `.eml` first, Gmail adapter behind the same interface).
3. Extraction with per-field confidence; fail-soft to Quarantine.
4. Match engine: WO → milestone → GRN → QC → rate contract → GST/TDS → net-offs.
5. `/inbox` → `/invoices/[id]` → `/exceptions` → `/audit` → `/connections`.
6. Actions + dual control + role gates.
7. Seed corpus, then the acceptance suite.

**Definition of done:** a controller watches an invoice arrive by email, follows it to a decision, opens every piece of evidence, sees a second approver clear it above threshold, and can reconstruct the whole thing from `/audit` — on a fresh database, driven only by the seeded email corpus.

**Before you report back:**
- Run the full test suite and paste the last 20 lines of output.
- Run acceptance checks 9 and 10 (the greps) and paste the result.
- Write `IMPLEMENTATION_NOTES.md`: a table of all 15 acceptance criteria → file → test name → passing? Any `✗` must name what is missing, not be omitted.
- Write `ASSUMPTIONS.md`: every variable you chose and every ambiguity you resolved.

Do not claim completion without that evidence. If something does not work, say which criterion and why.
