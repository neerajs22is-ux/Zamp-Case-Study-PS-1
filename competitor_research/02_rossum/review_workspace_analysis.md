# Rossum Document Review Workspace: Deep Technical & Interaction Analysis

**Target Route:** `https://svit.rossum.app/document/<document_id>`  
**Evidence Artifacts:** `EV-005`, `EV-008`, `EV-009`, `EV-010`, `EV-011`, `EV-012`, `EV-016`, `EV-017`, `EV-019`, `EV-020`  
**Investigation Framework:** Chrome DevTools Protocol DOM & Canvas Inspection  
**Audit Date:** November 03, 2026  

---

## 1. Interaction Architecture & Layout Model

The Rossum Document Review Workspace is an engineered, two-column interactive environment designed to minimize reviewer eye saccades and cognitive switching costs.

```text
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [Doc Name: [SAMPLE]_tax_invoice_us_2.pdf]  [Page: 1/1]      [Zoom Tools]  [Search] [Info] [Notes] [1 Err] [CONFIRM] │
├─────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────┤
│  DOCUMENT VIEWER CANVAS                         │  STRUCTURED EXTRACTION PANEL                                │
│                                                 │                                                             │
│  ┌───────────────────────────────────────────┐  │  ▼ BASIC INFORMATION                                        │
│  │ Tree gardening                            │  │    Document ID       [ INV-2026-US-8841 ]  (Required [?])   │
│  │ 567 Parsongate Street                     │  │    Order Number      [ Fancygarden      ]                   │
│  │ Brooklyn, NY 112 06                       │  │    Issue Date        [ 5/6/2021         ]                   │
│  │                                           │  │    Due Date          [ 9/30/2021        ]                   │
│  │ TAX INVOICE                               │  │    Document Type     [ Tax Invoice      ]                   │
│  │                                           │  │                                                             │
│  │ Invoice #: [INV-2026-US-8841]  <─────┐    │  │  ▼ TOTALS AND SUBTOTALS                                     │
│  │                                      │    │  │    Subtotal          [ 4,938.71         ]                   │
│  │ ┌──────────────────────────────────┐ │    │  │    Total Tax         [ 200.00           ]                   │
│  │ │ SVG BOUNDING BOX RECT            │ │    │  │    Amount Due        [ 5,138.71         ]                   │
│  │ │ x="935" y="247" width="124" h="28" │ │    │  │    Currency          [ USD              ]                   │
│  │ └──────────────────────────────────┘ │    │  │                                                             │
│  │                                      │    │  │  ▼ VENDOR & CUSTOMER                                        │
│  │                                      └────┼──┼──> Vendor Name       [ Tree gardening   ]                   │
│  │                                           │  │    Vendor Address    [ 567 Parsongate... ]                  │
│  │                                           │  │                                                             │
│  │                                           │  │  ▼ LINE ITEMS (4 items)                                     │
│  │                                           │  │    # | Description        | Qty | Rate    | Tax | Total     │
│  │                                           │  │    1 | Garden Pruners     | 10  | 45.00   | 0%  | 450.00    │
│  │                                           │  │    2 | Organic Fertilizer | 25  | 120.00  | 0%  | 3000.00   │
│  │                                           │  │    3 | Soil Hydration Mix | 8   | 185.00  | 0%  | 1480.00   │
│  └───────────────────────────────────────────┘  │    4 | Delivery & Freight | 1   | 8.71    | 0%  | 8.71      │
└─────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────┘
```

---

## 2. Document Viewer Engine

### Rendering Pipeline
- **Canvas / Text Coordinate Mesh:** Documents are converted server-side into multi-resolution tiled images paired with an OCR coordinate metadata payload.
- **Dynamic SVG Overlay Layer (`basepageContainerLayout`):** Overlaid directly above the rendered image is an SVG container matching the document's native aspect ratio (e.g., `width="1240" height="1605"`).
- **Coordinate-Addressed Rectangles:** The inspection of `[SAMPLE]_credit-note.pdf` verified **51 discrete `<rect>` elements** pre-populated with exact document coordinates:
  ```xml
  <rect class="MuiBox-root css-1g4gskc" x="935" y="247" width="124" height="28" />
  <rect class="MuiBox-root css-ts4dy1" x="974" y="247" width="85" height="28" />
  <rect class="MuiBox-root css-136bvrh" x="930" y="275" width="140" height="26" />
  ```
- **Performance:** Because bounding boxes are rendered as pure vector SVG geometry, zooming and panning occur at 60 FPS without bitmap pixelation or re-rendering lags.

### Viewer Controls & Tools
1. **Interactive Zoom Controls:** Bottom-left floating toolbar providing `Zoom In (+)` , `Zoom Out (-)`, and `Reset Zoom (100%)`.
2. **In-Viewer Text Search:** Clicking `Find in document` (`EV-012`) opens an inline search query input. As the reviewer types, matching words on the canvas highlight in yellow, allowing rapid navigation across long multi-page contracts.
3. **Real-time OCR Translation (`Ctrl+T`):** Reviewers working with multi-national vendors can press `Ctrl+T` to translate foreign language invoice text into English directly on screen.

---

## 3. Structured Extraction Panel

The right panel organizes extracted invoice entities into distinct, collapsable semantic cards:

### Section Taxonomy
1. **Basic Information:**
   - `Document ID` (Invoice Number) — Mandatory field.
   - `Order Number` (Purchase Order Reference).
   - `Issue Date` — Date formatted (`MM/DD/YYYY`).
   - `Due Date` — Payment deadline.
   - `Document Type` — Classified type (`Tax Invoice`, `Credit Note`).
   - `Document Language` — Detected language (`English`, `German`).
2. **Totals and Subtotals:**
   - `Subtotal` (Net Amount before taxes).
   - `Total Tax` (Cumulative tax).
   - `Amount Due` (Gross invoice total).
   - `Currency` (ISO 4217 currency code: `USD`, `EUR`, `GBP`).
   - `VAT Rates` / Tax breakdown table.
3. **Vendor & Customer:**
   - `Vendor Name` & `Vendor Address`.
   - `Customer Name` & `Customer Address`.
   - `Customer Delivery Name` & `Customer Delivery Address` (Ship-to).
4. **Line Items Grid:**
   - Tabular grid displaying line item description, quantity, unit price, tax rate, and extended amount.
5. **Other / Notes:**
   - Internal reviewer notes and audit metadata.

---

## 4. Two-Way Bounding Box Binding (The Core Magic)

The interaction model connects the PDF canvas to the extraction form bidirectionally:

### 1. Form-to-Canvas Highlighting (Field Focus)
- When a reviewer clicks on or tabs into a field (e.g. `Issue Date`), the application:
  1. Identifies the bounding box coordinate tuple `(x, y, width, height)` associated with the datapoint.
  2. Smoothly pans and auto-scrolls the canvas viewer to center the target bounding box.
  3. Activates the active highlight state on the corresponding SVG `<rect>` element (pulsing blue border with translucent fill).
  4. Verified in live test: Clicking `Issue Date` highlighted `x="690" y="152"`; clicking `Vendor Name` highlighted `x="189" y="295"` (`EV-008`, `EV-009`).

### 2. Canvas-to-Form Highlighting & Point-and-Click Extraction
- If a field is empty or incorrectly extracted:
  1. The reviewer clicks the empty field in the form.
  2. The reviewer hovers over any text block on the PDF canvas.
  3. The canvas highlights words under the cursor using an interactive selection cursor.
  4. The reviewer clicks or drags a box across the desired text.
  5. The underlying OCR text layer immediately extracts the string and injects it into the form field, clearing any validation warnings.

---

## 5. Floating Edit Input Architecture (`editBoxInput`)

Instead of standard static `<input>` elements that force constant context switching, Rossum uses a specialized floating input overlay (`editBoxInput`):

- **DOM Structure:** When a field is activated, Rossum dynamically renders an active textarea (`name="editBoxInput"`) over the focused field (`EV-017`).
- **Focus Trap & Instant Confirmation:** Pressing `Enter` commits the value and advances focus automatically to the next field in the schema.
- **Escape to Cancel:** Pressing `Escape` restores the previous extracted value without corrupting the document state.

---

## 6. How a Frontend Engineer Can Recreate This Model

To recreate Rossum's review workspace in our AP Command Center:

1. **State Store (Zustand or Redux):**
   - Store document state: `{ id, status, fields: Record<FieldKey, FieldState>, svgCoordinates: BBox[] }`.
   - Store active selection: `{ focusedFieldKey: string | null, highlightedBBoxId: string | null }`.
2. **Synchronized Layout:**
   - Use CSS Grid with two equal columns `grid-template-columns: 1fr 1fr;`.
3. **SVG Overlay Container:**
   - Place an absolute-positioned `<svg viewBox="0 0 1240 1605">` directly over the PDF render canvas.
   - Map OCR coordinate predictions into `<rect>` elements with CSS classes for `:hover` and `.is-active`.
4. **Scroll Synchronization:**
   - When `focusedFieldKey` changes, dispatch an event to the viewer to execute `canvas.scrollTo({ top: bbox.y - 100, behavior: 'smooth' })`.
5. **Keyboard Driver:**
   - Listen for global hotkeys (`Tab` for next field, `Shift+Tab` for prev, `Ctrl+Enter` to Confirm, `Ctrl+T` to translate).
