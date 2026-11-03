# Implementation Dependency & Critical Path Map
## Technical Dependency Topology for Zamp AP Command Center Implementation

**Artifact ID:** `IMPLEMENTATION_DEPENDENCY_MAP.md`  
**Target Repository:** `C:\Zamp Casse Study`  
**Date of Synthesis:** November 03, 2026  
**Status:** Certified Engineering Dependency Map  

---

## 1. Master Architectural Dependency Graph

```mermaid
graph TD
    subgraph Foundation["0. Database & Core Infrastructure Prerequisites"]
        PR_INDEX["PR-01: Index invoices.invoice_date<br/>(PostgreSQL Migration)"]
        PR_REVAL["PR-02: Deterministic Gate Re-evaluation Function<br/>(backend/core/pipeline.py)"]
        PR_PDFJS["PR-03: Integrate pdfjs-dist Canvas Engine<br/>(Replace &lt;iframe /&gt;)"]
        PR_OCR_BOX["PR-04: LayoutLM Normalized Bounding Boxes<br/>(Emit [x1,y1,x2,y2,page])"]
    end

    subgraph PhaseA["1. Phase A: Usability, Trust & In-Place Edit (Sprints 1–2)"]
        A_CORR["OPP-01: Audited Line Correction API<br/>(PATCH /invoices/:id/lines/:id)"]
        A_TABS["OPP-10: Tab Consolidation<br/>(Merge 3-Way Grid + 7 Gates)"]
        A_PERIOD["OPP-04: Period Filter (Year/Month)<br/>(Inbox Query Toolbar)"]
        A_EXPOSURE["OPP-06: AP Exposure Strip<br/>(GET /dashboard/exposure)"]
        A_DEMO["OPP-12: Demo Watermark Banner<br/>(AppShell.tsx)"]
    end

    subgraph PhaseB["2. Phase B: Reviewer Velocity & Document Grounding (Sprints 3–4)"]
        B_LOOP["OPP-03: Continuous Loop & Hotkeys<br/>(Save & Next / Ctrl+Enter)"]
        B_PO_LINK["OPP-09: Contextual PO Search<br/>(PATCH /invoices/:id/link-po)"]
        B_SVG_MESH["OPP-02: PDF-to-Field Coordinate Linking<br/>(SVG Vector Overlay Canvas)"]
        B_SEARCH["OPP-15: In-Viewer Full-Text Search<br/>(pdfjs text layer search)"]
        B_TEMPL["OPP-05: Downloadable CSV Templates<br/>(/public/templates/)"]
    end

    subgraph PhaseC["3. Phase C: Operational Efficiency & Tax (Sprints 5–6)"]
        C_GST["OPP-07: Indian GST Auto-Split Preview<br/>(PoS + State Code Comparison)"]
        C_QUOTA["OPP-11: Monthly Volume Quota Gauge<br/>(GET /system/usage)"]
        C_PREVIEW["OPP-13: ERP Payload Preview Drawer<br/>(GET /invoices/:id/erp-payload)"]
    end

    subgraph PhaseD["4. Phase D: Advanced Assistance & Scale (Sprints 7–8)"]
        D_COPILOT["OPP-08: Ambient 'Ask Zamp' Copilot<br/>(POST /copilot/query)"]
        D_GATEWAY["OPP-14: Gateway Fee Reconciliation<br/>(Razorpay CSV Matcher)"]
    end

    %% Dependency Connections
    PR_REVAL --> A_CORR
    PR_INDEX --> A_PERIOD
    A_CORR --> A_TABS
    A_TABS --> B_LOOP
    A_CORR --> B_PO_LINK
    
    PR_PDFJS --> B_SVG_MESH
    PR_OCR_BOX --> B_SVG_MESH
    PR_PDFJS --> B_SEARCH

    A_PERIOD --> B_TEMPL
    A_EXPOSURE --> C_QUOTA
    A_CORR --> C_GST
    A_TABS --> C_PREVIEW

    C_PREVIEW --> D_COPILOT
    B_TEMPL --> D_GATEWAY
```

---

## 2. Critical Path Analysis

The critical path represents the minimum sequential chain of technical deliverables that must be executed without slippage:

$$\mathbf{Critical\ Path} = \mathbf{PR\text{-}02} \longrightarrow \mathbf{OPP\text{-}01} \longrightarrow \mathbf{OPP\text{-}10} \longrightarrow \mathbf{OPP\text{-}03} \longrightarrow \mathbf{PR\text{-}03} \longrightarrow \mathbf{OPP\text{-}02}$$

| Sequence Step | Capability / Task | Why it is on the Critical Path | Estimated Effort |
|:---:|:---|:---|:---:|
| **1** | **PR-02: Deterministic Re-evaluator** | Line corrections cannot update gate statuses without an atomic re-evaluation function. | 2 Days |
| **2** | **OPP-01: Audited Line Edit API** | Reviewers cannot fix misread data without this backend patch endpoint. | 3 Days |
| **3** | **OPP-10: Tab Consolidation** | Unifying 3-way matching and policy gates in the UI is necessary to see re-evaluation results. | 2 Days |
| **4** | **OPP-03: Continuous Loop (`Ctrl+Enter`)** | Advancing through invoices requires that in-place corrections and tab layouts are stable. | 2 Days |
| **5** | **PR-03: `pdfjs-dist` Integration** | Replacing the native browser iframe is the prerequisite for coordinate overlays. | 4 Days |
| **6** | **OPP-02: PDF Coordinate Linking** | Renders SVG bounding boxes over canvas tokens; completes reviewer grounding. | 3 Days |

---

## 3. Prerequisite Truth Matrix by Roadmap Phase

### Phase A Prerequisites (Zero External Blockers)
All Phase A features can proceed **immediately**:
- `OPP-01` (Line Edit): Needs `PR-02` (in-repo backend re-evaluator).
- `OPP-10` (Tab Consolidation): In-repo React component refactoring.
- `OPP-04` (Period Filtering): Needs `PR-01` (SQL index migration).
- `OPP-06` (AP Exposure Scorecard): In-repo SQL aggregations.
- `OPP-12` (Demo Watermark): In-repo UI banner.

### Phase B Prerequisites (Requires Viewer Architecture Shift)
- `OPP-02` (Coordinate Linking) & `OPP-15` (Find in Document): **STRICTLY BLOCKED** by `PR-03` (`pdfjs-dist` replacing native iframe) and `PR-04` (OCR pipeline emitting coordinates).
- `OPP-03` (Continuous Review Loop): Blocked by `OPP-01` and `OPP-10`.
- `OPP-09` (Contextual PO Linker): Blocked by `OPP-01` re-evaluation logic.

### Phase C Prerequisites
- `OPP-07` (Indian GST Auto-Split): Requires Place of Supply (PoS) extraction field; cannot rely on GSTIN prefix alone.
- `OPP-13` (ERP Preview Drawer): Requires finalized SAP voucher payload schema.

### Phase D Prerequisites
- `OPP-08` ("Ask Zamp" Copilot): Requires schema-grounded LLM inference service.
- `OPP-14` (Gateway Reconciliation): Requires database migration for `settlement_reconciliations`.
