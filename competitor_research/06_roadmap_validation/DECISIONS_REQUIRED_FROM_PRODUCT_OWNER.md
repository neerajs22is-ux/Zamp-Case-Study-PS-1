# Decisions Required from Product Owner
## Essential Policy & Architecture Decisions for Roadmap Execution

**Artifact ID:** `DECISIONS_REQUIRED_FROM_PRODUCT_OWNER.md`  
**Target Repository:** `C:\Zamp Casse Study`  
**Audience:** Product Owner, Lead AP Architect & Engineering Lead  
**Date of Synthesis:** November 03, 2026  
**Status:** Certified Decision Request  

---

## 1. Governance & Boundary Notice

In strict accordance with Mission 08 guidelines, this document raises **only** those architectural and policy decisions that genuinely cannot be deduced from the existing codebase or locked invariants.

Locked invariants that **do not require decisions** and remain permanently active:
- 7 Deterministic Policy Gates remain authoritative.
- Failed gates cannot be overridden.
- Tolerances remain 0.00% quantity and $\pm 1.50\%$ rate.
- Dual approval threshold remains ₹5,00,000.
- Self-approval is strictly prohibited.
- Audit trail remains append-only and cryptographically verified.
- Product scope is pre-payment verification, not general ledger accounting or bank payment execution.

---

## 2. Key Decisions for Review

---

### Decision 01: Line Item Correction Authority (Role Delegation)

- **Context:**
  When an OCR extraction misreads a unit rate or quantity, an in-place correction is required (`OPP-01`). We must decide which user roles are authorized to modify active line numbers.
- **Option A (Recommended):** **Permit `AP_ASSOCIATE`, `AP_LEAD`, and `CONTROLLER`.**
  - *Mechanism:* AP Associates can correct typographical OCR errors during initial document intake. Every edit is immutably logged with their user ID, old value, new value, timestamp, and justification.
  - *Trade-off:* Maximizes operational velocity; eliminates bottlenecks. Guarded by the fact that invoices $\ge \text{₹5,00,000}$ still mandate independent Controller sign-off.
- **Option B (Strict Control):** **Restrict Line Corrections to `AP_LEAD` and above.**
  - *Mechanism:* AP Associates can only flag discrepancies; only an AP Lead or Controller can modify numbers.
  - *Trade-off:* Enhances segregation of duties, but increases review queue latency and forces senior leads to perform routine clerical data entry.
- **Consequence of Indecision:** Backend will default to **Option A** (`AP_ASSOCIATE` permitted with mandatory audit logging).

---

### Decision 02: Stale Approval Invalidation Granularity

- **Context:**
  An invoice $\ge \text{₹5,00,000}$ has already received Step 1 approval from an AP Lead and is sitting in the queue awaiting Step 2 sign-off from the Financial Controller. A reviewer then notices an error on Line 2 and corrects the rate.
- **Option A (Recommended — Zero-Trust):** **Complete Invalidation of Existing Approval.**
  - *Mechanism:* Any modification to billed quantity or unit rate automatically revokes Step 1 approval (`ApprovalRequest.status = "REVOKED_CORRECTION"`). The invoice resets to `ACTION_REQUIRED` and must undergo fresh Step 1 review.
  - *Trade-off:* Completely prevents altered financial facts from slipping past the initial reviewer. Requires the AP Lead to re-sign.
- **Option B (Threshold-Based):** **Preserve Step 1 if Net Amount Delta is $\le \text{₹500.00}$.**
  - *Mechanism:* Minor rounding corrections do not wipe Step 1 approval, but trigger an inline warning badge visible to the Financial Controller.
  - *Trade-off:* Reduces rework for trivial rounding adjustments, but introduces discretionary threshold logic into a zero-trust governance model.
- **Consequence of Indecision:** Backend will default to **Option A** (Complete Invalidation on any financial mutation).

---

### Decision 03: Operational Aging vs Statutory MSME Labeling

- **Context:**
  Our source-code audit proved that `backend/core/pipeline.py` does not calculate statutory MSMED deadlines during upload, and MSMED is not evaluated as a deterministic gate. Furthermore, many suppliers lack verified Udyam registration numbers in the database.
- **Option A (Recommended):** **Dual-Labeling Architecture.**
  - *Mechanism:* If a supplier has a verified `Vendor.udyam_number` and MSME status in `vendors`, render the explicit statutory countdown: `[MSMED §15 Statutory Due: X Days]`. If Udyam is missing or unverified, render standard operational aging: `[Payable Aging: X Days]`.
  - *Trade-off:* Accurately reflects legal reality; protects the enterprise from falsely claiming statutory compliance on unverified suppliers.
- **Option B (Blanket Operational Aging):** **Label All Invoices as Operational Aging.**
  - *Mechanism:* Completely remove the statutory MSME badge from the invoice header until a formal Udyam verification API is integrated.
  - *Trade-off:* Extremely safe legally, but removes a prominent compliance feature highlighted in demo workflows.
- **Consequence of Indecision:** Frontend will default to **Option A** (distinguishing verified MSME from general operational aging).

---

### Decision 04: PDF Viewer Migration Approval for Phase B

- **Context:**
  Our audit revealed that `InvoiceDetailPage.tsx` embeds an HTML `<iframe src={previewUrl} />`. A native browser iframe **technically bars** rendering an SVG vector coordinate layer on top of PDF text, making `OPP-02` (PDF-to-field coordinate pulsing) impossible.
- **Option A (Recommended):** **Approve Migration to `pdfjs-dist` in Phase B.**
  - *Mechanism:* In Phase B, replace the iframe with Mozilla's `pdfjs-dist` HTML5 canvas renderer.
  - *Trade-off:* Adds ~280 KB to the frontend bundle and requires 4 engineering days, but unlocks 60 FPS vector coordinate bounding box overlays, point-and-click text capture, and in-viewer search (`Ctrl+F`).
- **Option B (Retain Iframe):** **Reject Canvas Migration; Drop Bounding Boxes.**
  - *Mechanism:* Keep the browser iframe permanently. Drop `OPP-02` (bounding boxes) and `OPP-15` (in-viewer find) from the product roadmap.
  - *Trade-off:* Zero bundle overhead, but permanently surrenders the primary reviewer ergonomic advantage demonstrated by Rossum and FinBooks.
- **Consequence of Indecision:** Engineering will defer canvas migration until Phase B and exclude `OPP-02` from Phase A.
