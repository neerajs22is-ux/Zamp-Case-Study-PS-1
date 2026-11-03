# Rossum Workflow Analysis & Reviewer Productivity Audit

**Target Application:** `https://svit.rossum.app/` (Rossum Cloud Platform)  
**Investigation Framework:** Live Interaction Timing & Click-Cost Telemetry  
**Audit Date:** November 03, 2026  
**Trial Organization:** `SVIT` (User: `Neeraj S`)  

---

## 1. End-to-End Observed Document Lifecycle

The end-to-end lifecycle of an invoice processed through Rossum traverses 6 discrete operational stages:

```text
[Document Intake]
       │ (Manual Upload / Dedicated Email Inbox / REST API)
       ▼
[Ingestion & Preprocessing]
       │ (Page Splitting, Deskewing, OCR Coordinate Generation)
       ▼
[Classification & Queue Assignment]
       │ (Routed to Specific Queue: e.g. Tax Invoices US, Credit Notes)
       ▼
[AI Extraction & Rule Validation]
       ├── All Required Fields Present & Confidence >= Threshold ───> [Straight-Through Export]
       └── Missing Required Fields or Rule Error (e.g. Doc ID ?) ───> [To Review Queue]
                                                                             │
[Human-in-the-Loop Review Workspace] <───────────────────────────────────────┘
       ├── Field Verification & SVG Bounding Box Inspection
       ├── Point-and-Click Correction / Floating Keyboard Entry
       └── Decision: [Confirm] | [Postpone] | [Reject] | [Reassign Queue]
                                       │
[Downstream ERP / Export Pipeline] <───┘
```

---

## 2. Decision Points & State Machine

Rossum documents transition through an explicit set of status states:

| Observed Status | State Meaning | Available Operator Actions | Destination |
|:---|:---|:---|:---|
| `Importing` | Document being parsed, OCR'd, and evaluated against schema. | Read-only | Evaluates to `To review` or `Confirmed` |
| `To review` | Extraction completed; validation error or human verification required. | Open in Workspace, Edit fields, Confirm, Postpone, Reject, Move | Review Workspace |
| `Postponed` | Document parked awaiting vendor clarification or missing data. | Un-postpone, Open in Workspace, Reject | Queue `Postpone` tab |
| `Rejected` | Fraudulent, illegible, or duplicate bill marked invalid. | Delete, Reopen, Move to another queue | Archived / Audit trail |
| `Confirmed` | Human operator approved all fields; validation errors cleared. | Export, Move to queue, Re-open | Downstream ERP / Export |
| `Exported` | Document successfully delivered to ERP (SAP, Coupa, NetSuite). | View read-only audit copy | External financial system |

---

## 3. Human-in-the-Loop Exception Handling

Rossum's exception-handling strategy is built on aggressive visual affordances and strict confirmation gates:

### Identification of Problems
- **Field-Level Indicators:** A missing required field renders a prominent red question-mark badge `?` next to the label (`EV-016`).
- **Header Counter:** An action-bar error pill badge (`1 error / 0 warnings`) notifies the reviewer at all times of remaining blockers (`EV-016`).
- **Confirmation Gate:** While Rossum allows clicking `Confirm` on an incomplete invoice, it immediately intercepts the action and demands explicit user confirmation or flags that mandatory data is unverified (`EV-018`).

### Corrective Interaction
- When a reviewer clicks the erroneous field, the system auto-scrolls the viewer canvas to the predicted region.
- The reviewer can resolve the error in **two clicks**:
  1. Click the field.
  2. Click the corresponding text block on the PDF canvas.
- The error pill immediately decrements from `1` to `0`, and the `Confirm` button turns into an enabled primary action state (`EV-019`).

---

## 4. Reviewer Productivity & Click-Cost Analysis

To evaluate operational efficiency, 8 core accounting journeys were traced and measured against actual observed interactions in the live trial:

| Journey # | Operational Reviewer Task | Starting Screen | Action Sequence | Interaction Count (Clicks / Keystrokes) | Context Switch? | Friction / Bottleneck Observed |
|:---:|:---|:---|:---|:---:|:---:|:---|
| **J-01** | Find document requiring review | Global App Shell | Click `Documents` → Click Queue (`Tax invoices US`) → Scan `Reviews` tab | **2 clicks** | No | None; fast queue sidebar navigation. |
| **J-02** | Open document from queue | Queue List View | Click document link or row | **1 click** | No | Instant split-pane transition without page reload. |
| **J-03** | Review extracted header fields | Review Workspace | Scan Basic Information & Totals sections | **0 clicks** (Visual scan) | No | Compact layout allows scanning 6 headers simultaneously. |
| **J-04** | Verify source on PDF canvas | Review Workspace | Click `Vendor Name` field → Viewer auto-scrolls to bounding box | **1 click** | No | Flawless SVG auto-centering (`EV-009`). |
| **J-05** | Correct missing Document ID | Review Workspace | Click `Document ID` → Type `INV-2026-US-8841` → Press `Enter` | **1 click + 18 keystrokes** | No | Floating `editBoxInput` prevents mouse-keyboard switching. |
| **J-06** | Review multi-row line items | Review Workspace | Scroll down to Line Items card → Click to expand table | **1 click** | No | Line items collapsed by default; requires 1 click to view. |
| **J-07** | Confirm & Advance to Next | Review Workspace | Click `Confirm` (or press `Ctrl+Enter`) → Skip feedback survey | **2 clicks** (or hotkey) | No | Feedback survey adds 1 unnecessary click (`EV-018`). |
| **J-08** | Postpone invoice for query | Review Workspace | Click `Postpone` button in top toolbar | **1 click** | No | Instant status transition to Postponed. |

---

## 5. Productivity Bottlenecks & Optimization Opportunities

1. **Feedback Survey Friction:** Every manual confirmation triggers a micro-survey ("How satisfied are you with data extraction?"). While valuable for ML training, in high-volume enterprise AP environments where reviewers process 400 invoices daily, this adds 400 unnecessary dismiss clicks.
2. **Line Items Collapsed by Default:** The Line Items section requires an explicit click to expand. In AP workflows where 3-way line item matching is mandatory, this table should be expanded by default.
3. **Queue Table Metadata Scarcity:** Reviewers cannot see invoice totals or supplier names in the main queue list without opening the document. Adding customizable column headers in the queue would enable faster triage of high-dollar invoices.
