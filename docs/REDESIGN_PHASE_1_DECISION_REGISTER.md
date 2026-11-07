# Phase 1 — decision register

Proposals require approval. Evidence labels: **S** observed screenshot; **R** original research claim; **C** current source; **P** recommendation. Screenshot IDs and caveats are in [the analysis](REDESIGN_PHASE_1_SCREENSHOT_ANALYSIS.md).

| ID | Decision and evidence | Status / consequence |
|---|---|---|
| D01 | **P:** Use FinBooks' light, quiet palette and typographic hierarchy. **S:** dashboard, bills and sidebar captures show pale canvas, white panels, dark text and green cues. **R:** FinBooks analysis calls the product dark-first; that conflicts with captured light views. | Proposed; light is the evidence-backed reference, not a claim about default theme. Dark theme needs separate design. |
| D02 | **P:** Combine source and review evidence. **S:** Rossum review screenshots show document beside fields. **R:** FinBooks research reports mutually exclusive edit and preview overlays. **C:** AP already provides a split view. | Preserve and refine current pattern; do not claim OCR highlighting is already supported. |
| D03 | **P:** No carousel for essential AP KPIs. **R:** FinBooks dashboard analysis identifies metrics hidden behind carousel controls; **S:** dashboard captures show a constrained KPI arrangement. | Proposed; choose a small set with definitions and direct destinations. |
| D04 | **P:** Surface exceptions as a work queue/filter and keep exact failed checks in context. **C:** separate exceptions route exists without sidebar item; matching is embedded in invoice detail. | IA decision pending usage and permissions; don't claim this is a new route. |
| D05 | **P:** Retain original, corrected value, reason, actor, policy and audit event. **S:** AP correction and timeline examples; **C:** current review and audit surfaces. | Governance invariant, not a cosmetic simplification. Verify backend guarantees separately. |
| D06 | **P:** Keep approval controls role-aware and blocked decisions explainable. **C:** approval queue, auditor conditions and failed gate messaging exist. **S:** older captures include an override and later ones show a disabled action. | Treat screenshots as historical; do not infer today's override rules from them. Confirm active policy and permissions. |
| D07 | **P:** Put hashes and technical metadata in accessible details with copy while leaving blocking evidence visible. **C:** source viewer includes hash and copy; audit exposes event details. | Proposed density change; never discard provenance or evidence. |
| D08 | **P:** Keep period filtering secondary to action state in the inbox. **S:** Flick purchase file view uses period grouping; AP has fiscal-year/month filters. | Proposed; confirm which periods operators actually need. Flick's sales invoice builder is not an AP workflow. |
| D09 | **P:** Use selected tokens and contrast targets from [visual direction](REDESIGN_PHASE_1_VISUAL_DIRECTION.md). **S:** FinBooks hierarchy inspires the palette; exact hex values are ours. | Proposed; validate every state, actual typography and accessibility during implementation. |
| D10 | **P:** Defer bounding-box synchronization, bulk actions and live ERP additions. **R:** Rossum research discusses field/document linkage; **C:** source preview is an iframe/image and SAP configuration is described as unavailable. | These are capability questions, not assumptions or visual requirements. |

## Unresolved questions before implementation

1. Which exact AP roles use exceptions versus the invoice inbox, and should the existing exception route be added to navigation or represented by a filtered inbox? Confirm counts, saved views and access.
2. Which policy rules govern approvals, thresholds, overrides, required reasons and reassignment in each deployment? Read authoritative configuration and test role permutations; don't import stale screenshot values.
3. Are invoice line details, document positions, source files and audit payloads consistently available from current APIs? Which evidence can be displayed without adding backend capabilities?
4. What widths, zoom, screen-reader workflows, languages and real-world invoice volumes must be supported? Validate fixed versus adjustable review panes with actual users.
5. Is Inter available for local distribution, and is a dark mode a committed product requirement? Define and test a separate dark token set before changing it.
6. What are the authoritative definitions, freshness and destinations for each dashboard metric and queue count? Avoid adding KPIs without reliable data.
7. Which integrations and onboarding steps are actually configured per environment, and what is the safe demonstration-data labeling?

**Evidence limitation:** screenshot observations are still images, not proof of every click, backend guarantee or present-day product state. File captions and REA claims are checked against visible content; disagreements and inaccessible states are recorded in the screenshot analysis. Current application assessment is source-level plus historical captures, not a newly authenticated runtime audit.

## Inbox pilot evidence correction

The initial FinBooks vendor-bills screenshot and its approval-badges duplicate show an empty state, not populated rows or badges. The after-upload screenshot contains one partially visible bill. Inbox-wide tab counts, owner filtering/column, general due date and a complete blocker column remain unverified proposals; preserve existing fields and query behavior in the visual pilot.
