# Phase 1 — screen blueprints and current UI audit

**Evidence key:** S = screenshot observation in [analysis](REDESIGN_PHASE_1_SCREENSHOT_ANALYSIS.md); R = research finding; C = current source inspection; P = proposed design. Screenshots of AP are historical, not proof of today's runtime. Source was inspected statically; a fresh authenticated browser session was not verified. Route names below describe source, not a claim that services are running.

## Navigation and shell

**C:** `App.tsx` exposes Today, Invoices, Approvals, Audit, Connections, Procurement Records, Team and Setup; the exceptions route exists but is not in `Sidebar.tsx`; matching lives in invoice detail. The 256px sidebar uses 10–12px labels. **S:** AP captures combine small labels, several colored status chips and stacked explanatory regions; FinBooks uses a calmer light shell and compact grouping. **P:** 240px shell with 14px navigation: Today; Invoices (with Needs attention filter); Approvals; Audit trail; then Settings group containing Connections, Procurement records, Team and Setup. Link exceptions from Today and the inbox; decide whether to expose its existing separate route before changing navigation. Keep current role restrictions, including auditor access, and do not silently remove a route. Use one clear current-page indicator.

## Today / dashboard

**C:** `DashboardPage.tsx` has three large monospace metrics, an operations table and audit feed. **S:** FinBooks has generous spacing but carousels hide metrics; AP's cards and explanation banners compete. **P:** header “Today” with date/context and one upload action; a single row for actionable exposure, blocked invoices and approvals due, each with definition and direct filtered destination. Below, a priority queue with supplier, blocker, amount, age and owner; compact recent activity to the side or below. No decorative greeting, redundant audit feed, carousel or unsupported totals. Preserve currency, period and the meaning of each value.

## Invoice inbox

**C:** `InboxPage.tsx` provides the existing queue tabs and mappings, fiscal-year/month filters, page-local search, sync, upload and a paginated table. **S:** FinBooks' initial bill-list capture is empty; a separate after-upload capture shows one partially visible bill. Flick's purchase file view groups by period, while its supposed invoice-list capture is loading. **P:** improve type, spacing and action hierarchy while preserving the existing labels, filters, actions, fields and mappings. **Unverified / not in this pilot:** accurate counts for every tab, a general due date, owner column or filter, a specific blocker column and complete per-line status coverage. The current inbox API returns only the current query's total and an MSME statutory deadline, which must not be presented as a general due date. Supplier filtering is supported by the API but is not the current UI search behavior. Review error-state behavior separately; do not imply it is already implemented.

## Invoice review

**C:** `InvoiceDetailPage.tsx` shows a fixed-height source viewer, verdict card, matching/history tabs, gate drawer and decision footer; it uses 10–12px metadata. Its source title says “Information Read by AI” although it renders the document. **S:** Rossum's document and structured field panes are visible together; FinBooks' edit dialog is disconnected from its source (R). **P:** breadcrumb; invoice number, supplier, state and total in one compact header; source document on left with correctly named toolbar, zoom/open and unavailable/retry states; right side starts with verdict and named blockers, then tabs Match, Invoice data and History if supported. Keep source visible during correction wherever width allows. Show a short document fingerprint with accessible full copy/details. Bottom decision bar contains the authorized primary action and an “Other actions” menu; keep blocked reasons and role constraints visible. Do not imply source-region linking exists.

## Reconciliation / procurement evidence

**C:** no standalone route; `ProcurementVerificationFlow` is within review, with correction controls and policy values. **S:** AP screenshots show invoice/PO/receipt/inspection evidence and correction dialogs, but some viewers are blank. **P:** summary of matched / needs attention and line grid: description, invoice quantity/rate, PO authorized quantity/rate, received/inspected quantity and variance. Expand a line for source document IDs, tolerances, provenance, missing evidence and correction history; show every failed check and monetary/quantity difference without requiring expansion. Correct via dialog with old/new values, reason, cancel and resulting re-evaluation. Preserve evidence identifiers, timestamps, immutable snapshots and all policy checks. Do not add an independent navigation destination unless a separate work queue is justified.

## Exceptions

**C:** `ExceptionsPage.tsx` has filters, ownership reassignment and a table, but the sidebar does not expose it. **S:** the FinBooks “exception” capture is an edit dialog, not proof of a duplicate workflow; Flick's validation image illustrates inline errors. **R:** FinBooks research describes a duplicate card with an existing-invoice link. **P:** make Needs attention a prominent inbox filter linking to a focused queue; if the existing exception queue is retained, show issue type, supplier/invoice, amount, age, owner and next step, with reassignment as a deliberate action. In review, show exact failed check, compared values, source and resolution; no “approve anyway” unless existing policy explicitly permits it. Keep an audit record of ownership and decisions.

## Approvals

**C:** `ApprovalsPage.tsx` contains a dual-control queue and authorization dialog; `Sidebar.tsx` restricts the navigation for auditor roles. **S:** historical captures show queue and confirmation, while the reference allegedly showing Rossum blocked confirmation is a survey. **P:** show pending items, requester, supplier/invoice, amount, requested time, due/age and required approver; emphasize separation-of-duties and factual eligibility. Detail opens in context with source evidence and checks. Confirmation names the actual decision, actor, total and consequence; show reason and self-approval restriction where applicable. Do not hard-code a threshold from historical screenshots; display the active policy value.

## Audit trail and invoice history

**C:** `AuditPage.tsx` provides filtering and event detail; invoice detail also has a chronological history tab. **S:** historical AP rows are dense and heavily technical. **P:** global ledger: timestamp, actor, action, object, result; filter by date, actor, invoice and event, with searchable event details. Invoice history: human-readable event timeline with actor and exact time, old/new values and reason for changes. Expand to expose policy version, correlation ID, source identifiers and payload when available; retain ordering, integrity indicators and copy/export capabilities. Never replace a complete ledger with a curated summary.

## Connections, settings and procurement records

**C:** `ConnectionsPage.tsx` mixes service health, storage, Gmail, ERP configuration and a detailed technical table; `SourceRecordsPage.tsx` includes reference tables and PO detail. **S:** FinBooks settings uses calm grouped controls; AP integration captures foreground implementation details. **P:** group by task: Intake, Storage, Procurement/ERP, Identity; each shows service, current status, last check, consequence and available authorized action. Put endpoints, environment parameters and raw health in expandable diagnostics. Procurement records retain PO, receipt and inspection source, version, dates and balances, with search and clearly read-only provenance. Do not imply live SAP sync when source says it is not configured.

## Onboarding / help

**C:** `OnboardingPage.tsx` includes a multi-step guide and optional guided live workspace. **S:** FinBooks has a help panel; Rossum has an onboarding tour. **P:** short role-aware checklist: connect intake, verify procurement source, review a sample, understand approvals, inspect history. Each step has purpose, current status and one next action; distinguish demo from live data. Help drawer defines terms in context and links to full instructions. Completion must reflect actual checks, not clicks; preserve the ability to return and skip where existing policy allows.

## Cross-cutting acceptance

All states require readable text, keyboard access, explicit loading/error/empty messages, no clipped financial values, and a route back to work. Keep role gating, failed checks, evidence provenance, reasons, policy values and audit detail intact. Validate the proposed arrangement against real datasets at 1280×800 and 1440×900, narrow viewports, long supplier names and high-volume queues before implementing broadly.
