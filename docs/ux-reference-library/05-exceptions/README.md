# Category 05: Exceptions, Discrepancies & Resolution Workflows

## 1. Directory Inventory

| File | Source Product | Original Path | Visual Description & Scope |
|---|---|---|---|
| `ap_cc_blocked_checks_tab.png` | AP Command Center | `test-artifacts/visual-ux-audit/blocked_checks_tab.png` | Policy checks tab displaying red blocked gates, missing documents, and hard failure reasons. |
| `ap_cc_blocked_no_override.png` | AP Command Center | `test-artifacts/visual-ux-audit/blocked_no_override.png` | Governance gate UI enforcing zero override without required role elevation or evidence. |
| `ap_cc_reassign_modal.png` | AP Command Center | `test-artifacts/visual-ux-audit/reassign_modal.png` | Task assignment dialog routing exceptions to procurement buyer or warehouse manager. |
| `finbooks_01_exception_handling.png` | FinBooks | `competitor_research/01_finbooks/screenshots/01_exception_handling.png` | Duplicate invoice detection card (`dupCard`) displaying SHA-256 hash collision and vendor conflict. |
| `flickai_01_validation_errors_highlighted.png` | Flick AI | `competitor_research/03_flickai/screenshots/01_validation_errors_highlighted.png` | Field-level error validation in invoice form with red underlines and floating error tooltips. |
| `flickai_02_access_denied_exception.png` | Flick AI | `competitor_research/03_flickai/screenshots/02_access_denied_exception.png` | Role-based permission boundary blocking unauthorized actions with clear contact admin CTA. |
| `rossum_01_missing_required_document_id.png` | Rossum | `competitor_research/02_rossum/screenshots/01_missing_required_document_id.png` | Validation failure badge (`1 error`) indicating mandatory Document ID field is missing from extraction. |
| `rossum_02_document_id_focused_input.png` | Rossum | `competitor_research/02_rossum/screenshots/02_document_id_focused_input.png` | Interactive resolution: clicking error badge directly focuses the missing input field on the right. |
| `rossum_04_document_id_corrected_resolved.png` | Rossum | `competitor_research/02_rossum/screenshots/04_document_id_corrected_resolved.png` | Real-time resolution state: once entered, error badge turns green, enabling the "Confirm" action. |

---

## 2. Visual Comparison: Competitor Benchmarks vs. AP Command Center

```
+----------------------------------------------------------------------------------------------------+
| EXCEPTION VISIBILITY & RESOLUTION FLOW COMPARISON                                                  |
+------------------------------------+---------------------------------------------------------------+
| AP Command Center (Current)        | Stacks multiple long error banners. When an unreadable scan or|
|                                    | OCR failure occurs, it reports 6 false gate failures (missing |
|                                    | PO, missing GRN, missing vendor, tax mismatch) instead of     |
|                                    | diagnosing the root cause: "Scanned document is unreadable".   |
|                                    | Hard blocks show red badges without 1-click resolution actions.|
+------------------------------------+---------------------------------------------------------------+
| Rossum (Gold Standard: 1-Click Fix)| Error counter in header (`1 error`). Clicking jumps user to   |
|                                    | the exact erroneous field. Entering data turns error to green.|
|                                    | No technical jargon or cascading false alerts.                |
+------------------------------------+---------------------------------------------------------------+
| Flick AI (Gold Standard: Clean)    | Highlights field borders in red with contextual micro-copy:   |
|                                    | "GSTIN format invalid (expected 15 characters)".              |
+------------------------------------+---------------------------------------------------------------+
| FinBooks (Reference: Duplication)  | Dedicated duplicate collision card (`dupCard`) showing exact  |
|                                    | existing invoice number, previous payment date, and link.     |
+------------------------------------+---------------------------------------------------------------+
```

### Key Visual Strengths from Competitors
1. **Rossum Guided Error Navigation (`rossum_01_missing_required_document_id.png` -> `rossum_02` -> `rossum_04`):**
   - The user doesn't have to hunt for errors.
   - The top header has a pill: `1 error`. Clicking it takes the cursor right into the missing input.
   - Once resolved, the error count drops to `0 errors`, the top bar turns green, and the `Confirm` button unlocks.
2. **FinBooks Duplicate Detection (`finbooks_01_exception_handling.png`):**
   - High financial risk protection: A big warning card shows: *"This invoice appears to be a duplicate of INV-2024-089 paid on 14 Oct 2024."* Gives a direct link to the original bill.

### Current AP Command Center Deficiencies (`ap_cc_blocked_checks_tab.png`)
1. **Cascading False Failures:** If an invoice scan is blurry or unreadable, the engine runs all 6 governance checks and fails every single one. The user sees 6 alarming red X's instead of 1 root-cause diagnosis: *"We couldn't read this invoice scan. Please upload a clearer PDF or enter details manually."*
2. **Dead Ends:** Red blocked badges indicate `FAILED: HARD_BLOCK`, but do not offer the user a clear choice of what to do next (e.g., *Reassign to Buyer*, *Request Credit Note*, *Reject to Vendor*).

---

## 3. Recommended Pattern Adaptations

### What to Adopt
- **Root-Cause Triage for Unreadable Invoices:**
  - If OCR extraction confidence is $< 40\%$, display a single primary triage card: *"Document Unreadable: OCR could not extract invoice text. [Re-upload Clean Copy] or [Enter Details Manually]"*. Suppress downstream 3-way matching gate failures.
- **Rossum Error Jump-to-Fix Workflow:**
  - Add a sticky badge at top right: `⚠️ 2 Items Need Attention`. Clicking scrolls smoothly to the line item or field requiring correction.
- **Action-Oriented Exception Resolvers:**
  - Every exception card must end with concrete action pills:
    - *Discrepancy in Quantity:* `[Accept Adjusted Quantity]`, `[Ask Buyer to Follow Up]`, `[Reject Bill]`.

### What NOT to Copy
- Do not hide exceptions behind generic server error codes (e.g. 500 or 422).
- Do not copy Flick AI's abrupt "Access Denied" screen without a self-service re-routing workflow.
