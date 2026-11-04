# Category 08: AP Command Center Current UI Baseline Reference

## 1. Directory Inventory & Baseline Captures

This directory catalogues the complete visual state of our application prior to the non-technical buyer simplification initiative. All images captured from `handoff/ap-command-center` at commit `29d3c28`.

| File | Screen Name | Route / Component | Primary Purpose & Observed UX Issue |
|---|---|---|---|
| `01_appshell_eval_mode_banner.png` | Global App Shell | Root Layout (`AppShell.tsx`) | Global header featuring developer evaluation mode banner, role switcher, and environment status. Leaks test harness concepts to business users. |
| `02_dashboard_exposure_scorecard.png` | Exposure Scorecard | `/` (`TodayDashboard.tsx`) | 8-panel vertically stacked dashboard with exposure cards, pipeline health, and unassigned work queue. Too much visual noise. |
| `03_inbox_temporal_filtering.png` | Temporal Inbox | `/inbox` (`InvoiceInbox.tsx`) | Invoice queue with date range picker, multi-facet status chips, and pagination controls. Dense column layout. |
| `04_invoice_review_unified_workspace.png` | Review Workspace | `/inbox/:id` (`InvoiceReviewWorkspace.tsx`) | Split screen with PDF viewer on left and 4 vertically stacked explanation cards on right. Line items buried below the fold. |
| `05_line_item_inline_editing.png` | Line Item Editor | Line Items Table (`LineItemsTable.tsx`) | Interactive inline editable cells for quantities, unit prices, and tax rates with real-time recalculation. |
| `06_line_item_corrected_gate_re-evaluated.png` | Gate Re-evaluation | Gate Engine (`PolicyGates.tsx`) | Reactive recalculation showing gate transitioning from `BLOCKED` to `PASSED` upon line item correction. |
| `07_audit_trail_timeline_event.png` | Audit Event Feed | Timeline (`AuditTrail.tsx`) | Append-only chronological timeline displaying actors, timestamps, action types, and cryptographic hashes. |
| `08_system_demo_reset_feedback.png` | Reset & Demo Controls | Dev Utility (`DemoControls.tsx`) | Evaluation runner and mock data reset triggers. Should be quarantined to a developer drawer. |
| `today_light.png` | Today Dashboard (Light) | `/` (`TodayDashboard.tsx`) | Full page capture of the light-theme operational dashboard displaying the 1,450px vertical scroll stack. |
| `inbox_table.png` | Inbox Table Detail | `/inbox` (`InvoiceInbox.tsx`) | Full resolution capture of the 10-column invoice list with technical status chips. |
| `approvals_queue.png` | Approvals Queue | `/approvals` (`ApprovalsQueue.tsx`) | Filtered inbox specifically showing invoices requiring dual approval or manager sign-off. |
| `approve_modal_standard.png` | Standard Approval Modal | Dialog (`ApproveDialog.tsx`) | Current 600-word confirmation modal with policy disclosures, tolerance summaries, and warning boxes. |
| `audit_ledger.png` | Audit Ledger Grid | `/audit` (`AuditLedger.tsx`) | Formal compliance ledger displaying raw SHA-256 event chains and user session signatures. |
| `exceptions_reassign_modal.png` | Task Reassignment Dialog | Dialog (`ReassignDialog.tsx`) | Exception routing modal allowing reassignment of discrepant invoices to buyers or warehouse clerks. |

---

## 2. Core Baseline Deficiencies to Be Eliminated

1. **Information Architecture (The "Stacked Explanations" Problem):**
   - The workspace currently attempts to educate the user by piling cards on top of cards: `VerdictBanner`, `CaseSummaryCard`, `PolicyChecksGrouped`, `ProcurementVerificationFlow`.
   - **Impact:** Non-technical buyers cannot see the invoice line items without extensive vertical scrolling.
2. **Cognitive Load & Terminology:**
   - Terminology is heavily system-centric: `EVAL_RUN_COMPLETED`, `GATE_FAILED: QTY_TOLERANCE_EXCEEDED`, `SHA-256`, `IDEMPOTENT_LOCK`.
   - **Impact:** First-time finance managers assume the tool is broken or requires specialized IT training.
3. **Modal Friction:**
   - Routine approvals require navigating a 600-word confirmation modal with multiple legalistic checkboxes.
   - **Impact:** Decreases decision velocity and causes user hesitation.
4. **Developer Artifact Sprawl:**
   - Evaluation runner buttons ("Scenario 1-6", "Reset Fixtures") are placed directly in the main user viewport.
   - **Impact:** The application feels like a test harness rather than a production-grade enterprise SaaS product.

---

## 3. Preservation Invariants for Any Subsequent Redesign

When executing the UI simplifications specified in this audit, the following architectural and governance guarantees must remain 100% intact:
1. **Dual Approval Rule:** Any invoice with total amount $\ge ₹5,00,000$ strictly requires Controller dual sign-off.
2. **Anti-Self-Approval:** The user who modified or corrected a line item cannot be the sole approver.
3. **Deterministic Tolerances:** Quantity tolerance is exactly 0.00% (zero tolerance); price tolerance is strictly $\le 1.50\%$.
4. **Auditor Read-Only Boundary:** Auditor role cannot mutate data, approve invoices, or trigger actions (returns HTTP 403).
5. **Immutable Audit Ledger:** All line item mutations, policy evaluations, and approvals must append to the immutable audit event log with SHA-256 cryptographic verification.
6. **Zero Direct Disbursement:** AP Command Center prepares, reconciles, and authorizes invoices for payment, but does NOT execute direct banking or GL ledger disbursement.
