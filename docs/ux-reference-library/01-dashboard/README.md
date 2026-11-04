# Category 01: Operational Dashboard & Executive Overview

## 1. Directory Inventory

| File | Source Product | Original Path | Visual Description & Scope |
|---|---|---|---|
| `ap_cc_today_light.png` | AP Command Center | `test-artifacts/visual-ux-audit/today_light.png` | Current operational "Today" dashboard with 8 stacked panels (metric counters, evaluation banner, workload breakdowns, recent audits, system health). |
| `ap_cc_02_dashboard_exposure_scorecard.png` | AP Command Center | `competitor_research/03_flickai/screenshots/ui_evidence/02_dashboard_exposure_scorecard.png` | Current financial exposure scorecard displaying blocked cash flow, duplicate invoice liability, and unassigned queues. |
| `finbooks_01_dashboard_full.png` | FinBooks | `competitor_research/01_finbooks/screenshots/01_dashboard_full.png` | Complete accounting dashboard with fiscal year selector (`FY 2024-25`), quick summary KPI cards, and recent vendor activity. |
| `finbooks_02_dashboard_bank_statement_view.png` | FinBooks | `competitor_research/01_finbooks/screenshots/02_dashboard_bank_statement_view.png` | Cash & bank reconciliation status cards with clear color-coded ledger matching states. |
| `flickai_01_main_dashboard_full.png` | Flick AI | `competitor_research/03_flickai/screenshots/01_main_dashboard_full.png` | Clean Material-UI v5 dashboard featuring fiscal period selectors, 3 primary KPI cards, recent activity table, and ambient AI assistant. |
| `flickai_02_dashboard_and_sidebar.png` | Flick AI | `competitor_research/03_flickai/screenshots/02_dashboard_and_sidebar.png` | Navigation drawer with collapsed/expanded states, badges showing urgent tasks, and streamlined header. |
| `rossum_01_statistics_dashboard_full.png` | Rossum | `competitor_research/02_rossum/screenshots/01_statistics_dashboard_full.png` | Executive processing throughput metrics, automation percentage rate, queue volume trends, and document resolution velocity. |

---

## 2. Visual Comparison: Competitor Benchmarks vs. AP Command Center

```
+----------------------------------------------------------------------------------------------------+
| DASHBOARD VISUAL STRUCTURE COMPARISON                                                              |
+------------------------------------+---------------------------------------------------------------+
| AP Command Center (Current)        | 8 vertically stacked widgets spanning 1,450px vertical scroll.|
|                                    | Mixes technical engine status, evaluation reset controls,     |
|                                    | 5 separate queue blocks, and raw JSON-style audit logs.       |
|                                    | First-time non-technical buyer feels overwhelmed immediately. |
+------------------------------------+---------------------------------------------------------------+
| Flick AI (Gold Standard: Clean)    | 3 core KPI metrics above fold: (1) Needs Action, (2) Ready to |
|                                    | Pay, (3) Blocked Risk. Strict period-scoped dropdown filter.  |
|                                    | 1 primary action button: "Upload Invoice". Zero technical jargon.|
+------------------------------------+---------------------------------------------------------------+
| Rossum (Gold Standard: Metrics)    | Single-screen operational queue overview with real-time error |
|                                    | counter (`1 error / 0 warnings`) and live automation rate.    |
+------------------------------------+---------------------------------------------------------------+
| FinBooks (Reference: Accounting)   | Sticky fiscal year header with quick-switch period context.   |
|                                    | Visual cards for pending invoices, but cluttered banking tabs.|
+------------------------------------+---------------------------------------------------------------+
```

### Visual Strengths Identified in Competitors
1. **Flick AI (`flickai_01_main_dashboard_full.png`):**
   - **Visual Restraint:** Only 3 KPI metric tiles above the fold with high typography contrast (32px bold numbers, muted labels).
   - **Period Scoping:** A universal Fiscal Year (`FY 2024-25`) and Month filter in the header prevents historical invoice noise from overwhelming daily operations.
   - **Clear Hierarchy:** Left navigation is 240px clean slate; main content has prominent "Upload / New Invoice" primary button with zero ambiguous actions.
2. **Rossum (`rossum_01_statistics_dashboard_full.png`):**
   - **Throughput & Automation Rate:** Highlights straight-through processing rate (e.g., "82% automated without manual touch") which is the #1 metric CFOs care about.
   - **Action Queue Focus:** Shows active queues with bold count badges instead of displaying all historical closed records.

### Current AP Command Center Deficiencies (`ap_cc_today_light.png`)
1. **Vertical Sprawl:** 8 stacked rectangular containers requiring over 1,400px of vertical scrolling.
2. **Technical Leaks:** Evaluation banner ("Evaluate Scenario 1–6"), test runner status, and token indicators confuse a finance user who just wants to process bills.
3. **Competing Action Centers:** Displays multiple separate buttons ("Run Evaluation", "Reset Demo", "Audit Log", "Filter Inbox") without an unmistakable primary action.

---

## 3. Recommended Pattern Adaptations

### What to Adopt
- **The 3-Zone Executive Dashboard:**
  - **Zone 1: The Daily Triad (Top KPI Bar):** Exactly 3 cards:
    1. *Needs Your Decision* (Amber badge, count, total amount).
    2. *Ready to Pay / Fully Verified* (Emerald badge, count, total amount).
    3. *Blocked / Discrepant* (Rose badge, count, total value at risk).
  - **Zone 2: Action Queue (Center):** Direct table of invoices needing user action right now, sorted by urgency/due date.
  - **Zone 3: Automation Pulse (Right Rail or Collapsible Bottom):** Straight-through processing rate and auto-match percentage.
- **Header Period Scope:** Add clean Fiscal Period selector (inspired by Flick AI & FinBooks) to eliminate overwhelming test-data noise.

### What NOT to Copy
- Do not copy FinBooks' banking tabs or multi-ledger views into AP Command Center (unnecessary cognitive burden for AP invoice verification).
- Do not copy Rossum's deep analytics customization controls (complex widget builders are anti-patterns for non-technical managers).
