# Phase 1 — visual direction

**Status:** proposal for approval; no implementation. Read with the screenshot analysis, screen blueprints and decision register.

## Art direction

**Observed:** FinBooks' light captures combine a pale canvas, white navigation and panels, ink-dark headings, restrained green, slim outlines and consistent corner radii. Whitespace and weight create hierarchy; scarce action colour, aligned figures and calm surfaces make the interface feel financially trustworthy. Its green is a cue, not a requirement to reproduce its brand. The light captures conflict with its REA document's dark-first description; this proposal follows the visible light captures. **REA:** its review modal and source drawer are mutually exclusive, and vendor table headers can collide. **Recommendation:** borrow the visual restraint, not those workflow defects or its carousel for key metrics.

## Tokens and contrast

These are proposed tokens, not competitor measurements.

| Token | HEX | Use |
|---|---|---|
| Canvas | `#F5F7F4` | Page background |
| Surface | `#FFFFFF` | Sidebar, panels, menus |
| Surface subtle | `#EDF2ED` | Inset region |
| Primary text | `#152B25` | Titles, values, content |
| Secondary text | `#52665F` | Labels, dates, support copy |
| Border / strong | `#D6E0D8` / `#9BAFA2` | Dividers / inputs |
| Brand / hover | `#126B46` / `#0D5538` | Primary action, links |
| Selected | `#E3F2E8` | Selected row or navigation |
| Focus | `#135DB2` | 2px ring and 2px offset |
| Success | `#126B46` on `#E3F2E8` | Passed / completed |
| Warning | `#8A4B08` on `#FFF4DD` | Pending / attention |
| Danger | `#A42732` on `#FDEDEE` | Failed / blocked |
| Info | `#135DB2` on `#EAF2FF` | Informational |
| Inverse text | `#FFFFFF` | Dark buttons |

Calculated WCAG contrast: primary/white **14.96:1**; secondary/white **6.13:1**; brand/white **6.53:1**; brand/canvas **6.06:1**; warning pair **6.22:1**; danger pair **6.36:1**; focus/white **6.49:1**. Verify all actual combinations and focus rings against adjoining surfaces at implementation; aim for 4.5:1 normal text, 3:1 large text and meaningful non-text boundaries. Disabled controls need a readable reason nearby. Pair state colour with a word and, where useful, an icon.

## Type

Use **Inter**, locally bundled where licensing permits, with `system-ui, -apple-system, Segoe UI, sans-serif` fallback. Use tabular numerals for money and dates; reserve `ui-monospace, SFMono-Regular, Consolas, monospace` for hashes and long technical identifiers. Proposed scale: page title 26/32px 650; section 18/24 600; card title 15/22 600; body and table rows 14/20 400–500; controls 14/20 600; metadata 12/18 400–500; KPI 28/34 650. Avoid 10–11px essential text and tracked uppercase micro-labels. Use the nearest available static weight if variable fonts are unavailable.

## Shell, spacing and responsive rules

At 1440px: sidebar **240px**, top bar **64px**, page padding **32px**, ordinary content maximum **1440px**, left aligned. Use an 8px spacing system: 4 for micro gaps, 8 for icon/label, 12 for compact groups, 16 inside rows/cards, 24 between sections and 32 at page edges. Sidebar rows at least 40px with 14px labels, light-green selection and a leading marker; show workload counts only when accurate. Keep organization and account context in the top bar. Avoid unnecessary nested frames. Review may use available width; at ≥1200px show document and evidence side by side, starting around 45/55, with an adjustable divider if feasible. At <1200px provide explicit Document/Evidence views with preserved state, and at narrow widths stack. Do not hide checks or source access. Tables scroll within their container, retaining the identifying column where practical. Size the document viewer to the available viewport instead of universally fixing it at 650px.

## Components

- **Tables:** 14px text, 48–56px rows, 12px semibold headers, 16px horizontal padding; left-align names and IDs, right-align amounts with tabular figures. One subtle divider per row, clear hover and keyboard focus; column minimums and horizontal scrolling prevent collisions. Prioritize vendor, invoice, due date, amount, state and next action.
- **Buttons:** 40px minimum height (44px preferred on touch), 8px radius; one solid green primary per decision area; secondary white outlined, tertiary text. Destructive decisions require distinct confirmation and a reason when policy requires it. Provide visible focus, hover and disabled explanations; respect role permissions.
- **Cards:** white, 1px border, 10–12px radius, 20–24px padding; shadow only for overlays. KPI cards wrap rather than using a carousel.
- **Inputs:** 40–44px height, 8px radius, persistent 13–14px label, associated inline error and help. Placeholder is not a label. Retain entered values after errors.
- **Badges:** 12px semibold, subtle semantic fill, plain-language status. Gate counts supplement the verdict; they do not replace it.
- **Dialogs/drawers:** 480–640px dialogs for confirmation, wider only for evidence; title, factual consequence, primary action and cancel, visible close, focus trap and focus return. Correction shows original value, new value, reason and resulting checks. Use a drawer for reference material needed alongside review.

## Density and evidence

Show decision, supplier, amount, due date, blocker, next action and owner by default. Keep PO/receipt/inspection and line variances visible in reconciliation; place full source identifiers, SHA-256, correlation IDs, payloads, policy version and timestamps behind clearly named details or audit expansion, preserving copy/export and role access. Do not hide a failed gate, variance or approval prerequisite to achieve a clean surface. Explain rules next to affected values and move repeated technical explanations to contextual help. Do not promise OCR bounding-box linking or bulk actions until verified.

**Inbox qualification:** A general due date, owner and dedicated blocker field are not established by the existing inbox response. These are unverified proposals, not fields to add in the visual pilot. The available MSME statutory deadline is not a general due date.
