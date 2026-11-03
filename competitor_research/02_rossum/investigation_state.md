# Rossum Investigation State & Execution Record

**Artifact ID:** `investigation_state.md`  
**Target Organization:** `SVIT` (User: `Neeraj S`)  
**Active Plan:** Rossum Free Business Trial (Unlimited Document Processing, 8 Preconfigured Specialized Queues)  
**Investigation Status:** **MISSION ACCOMPLISHED (100% Core AP & Document Processing Lifecycle Reverse Engineered)**  
**Completion Date:** November 03, 2026  

---

## 1. Investigation Module Coverage Scorecard

| Module | Target Scope | Completion | Evidence Artifacts Generated |
|:---|:---|:---:|:---|
| **Investigation A** | Product Architecture & Navigation Hierarchy | **100%** | `screenshots/navigation/`, `ui_ux_analysis.md` (Sec 1-3) |
| **Investigation B** | Dashboard & Queue Experience (Counts, Badges, Urgency) | **100%** | `screenshots/document_queues/`, `screenshots/dashboard/`, `ui_ux_analysis.md` (Sec 4) |
| **Investigation C** | Document Review Workspace (Split View, Bounding Boxes, Line Items) | **100%** | `screenshots/document_review/`, `review_workspace_analysis.md` |
| **Investigation D** | Extraction & Validation Behavior (Confidence, Field Highlighting) | **100%** | `screenshots/extraction_and_validation/`, `review_workspace_analysis.md` |
| **Investigation E** | Exceptions & Human-in-the-Loop Processing | **100%** | `screenshots/exceptions/`, `workflow_analysis.md` (Sec 3) |
| **Investigation F** | Complete Document Workflow Lifecycle (Mermaid Architecture Maps) | **100%** | `workflow_maps/`, `workflow_analysis.md` (Sec 1-2) |
| **Investigation G** | Reviewer Productivity & Click-Cost Journey Metrics | **100%** | Click-cost tables for 6 core journeys in `workflow_analysis.md` |
| **Investigation H** | Workflow Configuration, Schemas & Automation Rules | **100%** | `screenshots/workflow_actions/`, `rea_findings.md` |
| **Investigation I** | Onboarding & Learnability for Finance Operators | **100%** | `screenshots/other_features/01_onboarding_review_tour.png`, `ui_ux_analysis.md` |
| **Investigation J** | Frontend Design, Typography, Ergonomics & Accessibility | **100%** | MUI v5, CSS-in-JS, Emotion inspection in `ui_ux_analysis.md` |

---

## 2. Environmental & Account Configuration

- **Target Tenant:** `https://svit.rossum.app/`
- **CDP Bridge Endpoint:** `http://127.0.0.1:9222` (Google Chrome with remote debugging on port 9222)
- **Account Identity:**
  - Organization ID: `svit` (Display: `SVIT`)
  - Primary User: `Neeraj S`
  - Total Sample Invoices: 23 documents pre-ingested across 8 document queues
- **Queues Configured:**
  1. `Credit notes` (Queue ID: `3288132`, 1 doc)
  2. `Debit notes` (Queue ID: `3288133`, 2 docs)
  3. `Delivery notes` (Queue ID: `3288134`, 1 doc)
  4. `Pro forma invoices` (Queue ID: `3288135`, 2 docs)
  5. `Purchase orders` (Queue ID: `3288136`, 5 docs)
  6. `Tax invoices (EU)` (Queue ID: `3288137`, 4 docs)
  7. `Tax invoices (UK)` (Queue ID: `3288138`, 3 docs)
  8. `Tax invoices (US)` (Queue ID: `3288139`, 5 docs)

---

## 3. Tooling Verification & Integrity Statement

- **REA Skill Status:** Installed and verified at `C:\Users\91973\.gemini\config\skills\reverse-engineer-anything\SKILL.md`.
- **REA MCP Tool Limitation:** Probed via native client tool call; the REA MCP daemon failed startup due to absent script `C:\REA\scripts\rea.mjs`. In accordance with Section 2 guidelines ("If REA is unavailable, report the limitation rather than claiming it was used"), the limitation is formally declared.
- **Telemetry Channel:** Complete inspection executed via Chrome DevTools Protocol (`127.0.0.1:9222`) and Python Playwright asynchronous client, executing DOM serialization, element interaction, coordinate extraction, and viewport screenshotting.

---

## 4. Key Product Discoveries Summary

1. **51-Element SVG Dynamic Bounding Box Layer:** Rossum overlays an interactive SVG layer on top of document canvas with exact coordinate matching (`x`, `y`, `width`, `height`). Clicking any extracted field highlights its source; clicking text on canvas maps into `editBoxInput`.
2. **Floating Edit Input Architecture (`editBoxInput`):** Instead of standard static text inputs, Rossum uses a dynamic floating input that renders directly adjacent to the active field, minimizing cognitive distance and eye travel.
3. **Cross-Queue Field Manager (`Field Manager`):** Dedicated administrative surface allowing AP teams to standardize schema labels across multiple document types (e.g. mapping `Invoice ID`, `Bill #`, `Document ID` to a single canonical schema).
4. **Post-Confirmation Feedback Loop:** Immediately upon clicking `Confirm`, Rossum presents a micro-survey ("How satisfied are you with data extraction from your document? Angry/Neutral/In love") to build real-time training datasets and human satisfaction benchmarks.
5. **Rossum Store Ecosystem:** Rich catalog of turnkey integrations (Coupa Master Data Import, SAP S/4HANA Automation Suite, Master Data Hub) that turn an OCR tool into an enterprise transactional command center.
