# Category 06: Approval Workflows & Governance Controls

## 1. Directory Inventory

| File | Source Product | Original Path | Visual Description & Scope |
|---|---|---|---|
| `ap_cc_approvals_queue.png` | AP Command Center | `test-artifacts/visual-ux-audit/approvals_queue.png` | Work queue dedicated to invoices pending senior manager or controller sign-off. |
| `ap_cc_approve_modal_standard.png` | AP Command Center | `test-artifacts/visual-ux-audit/approve_modal_standard.png` | Current 600-word approval dialog containing policy disclosures, checklist repeats, and warning boxes. |
| `ap_cc_approved_state.png` | AP Command Center | `test-artifacts/visual-ux-audit/approved_state.png` | Visual state post-approval showing cryptographic sign-off badge, approval timestamp, and reviewer ID. |
| `ap_cc_auditor_read_only.png` | AP Command Center | `test-artifacts/visual-ux-audit/auditor_read_only.png` | Auditor role view with disabled action buttons and read-only compliance indicator. |
| `finbooks_bills_approval_badges.png` | FinBooks | `competitor_research/01_finbooks/screenshots/bills_approval_badges.png` | Status chips indicating approval stages: Draft -> Approved -> Paid. |
| `flickai_11_team_management.png` | Flick AI | `competitor_research/03_flickai/screenshots/11_team_management.png` | Role-based access control table configuring Approver, Viewer, Admin permissions. |
| `rossum_03_confirm_blocked_modal.png` | Rossum | `competitor_research/02_rossum/screenshots/03_confirm_blocked_modal.png` | Clean confirmation modal warning user about unconfirmed fields before final sign-off. |
| `rossum_users_and_roles.png` | Rossum | `competitor_research/02_rossum/screenshots/users_and_roles.png` | Enterprise user governance screen separating document reviewers from queue supervisors. |

---

## 2. Visual Comparison: Competitor Benchmarks vs. AP Command Center

```
+----------------------------------------------------------------------------------------------------+
| APPROVAL WORKFLOW & DIALOG VISUAL COMPARISON                                                       |
+------------------------------------+---------------------------------------------------------------+
| AP Command Center (Current)        | Approval modal contains ~600 words of text across 4 sections: |
|                                    | "Governance Attestation", "Tolerance Summary", "Audit Note",  |
|                                    | and a yellow cautionary box. Non-technical buyers experience  |
|                                    | cognitive overload and hesitation before confirming.          |
+------------------------------------+---------------------------------------------------------------+
| Rossum (Gold Standard: Speed)      | Single-click "Confirm" button in bottom bar. If errors exist, |
|                                    | a 25-word alert modal confirms override intent. Fast & clear. |
+------------------------------------+---------------------------------------------------------------+
| Flick AI (Gold Standard: Clarity)  | Clean approval drawer: 3 summary bullets (Vendor, Amount,     |
|                                    | Match status) + 1 required comment field + "Approve" button.  |
+------------------------------------+---------------------------------------------------------------+
| FinBooks (Reference: Badges)       | Status badges update smoothly; however, approval rules are     |
|                                    | implicit rather than enforcing strict dual-control limits.    |
+------------------------------------+---------------------------------------------------------------+
```

### Key Visual Strengths from Competitors
1. **Rossum Lean Confirmation (`rossum_03_confirm_blocked_modal.png`):**
   - High decision velocity: If all checks pass, clicking `Confirm` takes exactly 1 click with zero modal popup.
   - If warnings exist, the confirmation modal is concise (under 30 words), stating clearly: *"There are 2 unverified fields. Do you want to confirm anyway?"*
2. **Flick AI Role Transparency (`flickai_11_team_management.png`):**
   - Visual role badges (Admin, Approver, Viewer) clarify who can authorize payments without confusing technical permission terminology.

### Current AP Command Center Deficiencies (`ap_cc_approve_modal_standard.png`)
1. **Wall of Text Modal:** The modal forces the user to read through multiple paragraphs of repetitive policy statements that they already saw on the review screen.
2. **High Interaction Friction:** Requires multiple checkboxes, an optional note, and a confirmation button, creating unnecessary friction for routine 100% clean matched invoices.
3. **Threshold Opacity:** Dual-approval threshold ($\ge ₹5,00,000$) is not visually highlighted as a progressive step before opening the modal.

---

## 3. Recommended Pattern Adaptations

### What to Adopt
- **The 45-Word / 3-Click Approval Dialog:**
  - For clean, matched invoices:
    - **Header:** `Approve Invoice INV-2024-001`
    - **Summary Card:** `Vendor: Bharat Electricals | Amount: ₹1,45,000 | Match: 100% Clean`
    - **Governance Notice:** `Dual-approval required for amounts ≥ ₹5,00,000 (Current: Standard Approval).`
    - **Action Buttons:** `[Cancel]` and `[Approve & Queue for Payment]`.
- **Progressive Dual-Approval Indicator:**
  - For invoices $\ge ₹5,00,000$, show a clear 2-step stepper in the workspace:
    - Step 1: `Primary Reviewer Sign-Off [Completed by Rahul]`
    - Step 2: `Controller Approval [Awaiting Your Sign-Off]`
- **Auditor Read-Only Banner:**
  - When logged in as Auditor, keep existing read-only protection (`ap_cc_auditor_read_only.png`), but present a clean top banner: *"Viewing in Read-Only Audit Mode — Actions are disabled."*

### What NOT to Copy
- Do not remove the strict governance invariants (anti-self-approval and dual approval must remain strictly enforced in the backend).
- Avoid Rossum's blanket single-click bypass when dealing with high-value invoices $> ₹5,00,000$.
