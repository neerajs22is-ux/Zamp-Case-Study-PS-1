# AI & Document Intelligence Pipeline

This document details the multi-modal document intelligence architecture, foundation model configurations, and extraction guardrails of the Autonomous Accounts Payable (AP) Command Center.

---

## 1. Architectural Philosophy: The Hybrid Processing Engine

The AP Command Center strictly separates probabilistic AI inference from deterministic financial arithmetic:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             PROBABILISTIC AI INFERENCE                           │
│  AWS Bedrock Mantle (Qwen3-235B)  /  Palmyra Vision 7B Adapter                   │
│                                                                                  │
│  • Commercial Document Classification (Invoice vs Receipt vs Delivery Challan)   │
│  • Unstructured PDF Layout & Table Interpretation                                │
│  • Indian Tax Field Extraction (GSTIN, PAN, Invoice Number, Date, Line Items)    │
│  • Bounding-Box Confidence & Source Grounding                                    │
│  • Natural-Language Variance Explanations for AP Controllers                     │
└─────────────────────────────────────────┬────────────────────────────────────────┘
                                          │ Typed Pydantic v2 Invariants
┌─────────────────────────────────────────▼────────────────────────────────────────┐
│                        DETERMINISTIC PYTHON & SQL ENGINE                         │
│                                                                                  │
│  • File Integrity & PDF Pre-Screening (Header Check, Modality Detection)        │
│  • Indian GST Arithmetic Validation (Taxable Amount + CGST + SGST == Total)      │
│  • Interstate vs Intrastate IGST / CGST+SGST Logic Verification                  │
│  • 3-Way Reference Reconciliation (PO Line Items, GRN Receipts, QC Acceptance)  │
│  • Unit Rate & Quantity Tolerance Math (≤ 1.5% and ≤ ₹20.00)                     │
│  • Cryptographic Duplicate Detection (SHA-256 + Vendor/Invoice# Match)           │
│  • State Machine Transitions & Approval Threshold Enforcement                    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Ingestion Modality Classification & Pre-Screening

Before sending any document bytes to an LLM, the pre-screener analyzes the file:

1. **Digital Text vs Scanned Image Detection:**
   - Evaluates machine-readable character density across pages using `pypdf`.
   - If extractable text count is $> 100$ characters, modality is classified as `DIGITAL_TEXT_PDF`. The document is routed directly to Bedrock Mantle Qwen 235B.
   - If extractable text count is $< 100$ characters, modality is classified as `SCANNED_IMAGE`.
2. **Contrast Pre-Screening:**
   - Scanned PDFs are rendered into image frames via `pypdfium2`.
   - Computes grayscale contrast standard deviation ($\sigma$).
   - If $\sigma < 10.0$, the file is marked `DEGRADED_SCAN_POOR_CONTRAST`. Text LLMs are bypassed to prevent hallucination, and the file is immediately routed to human-in-the-loop review (`FLAGGED_HITL_REVIEW`).

---

## 3. Primary LLM: AWS Bedrock Mantle (Qwen3-235B)

- **Model ID:** `qwen.qwen3-235b-a22b-2507-v1:0`
- **Region:** AWS Mumbai (`ap-south-1`)
- **Protocol:** HTTP POST to `/v1/chat/completions` (OpenAI-compatible schema)
- **Parameters:** `temperature: 0.0`, `max_tokens: 2048`, `response_format: {"type": "json_object"}`.
- **Latency Benchmark:** 2.9s to 3.1s per invoice page.
- **Average Cost:** $0.0022 USD per document (within the $0.10 document spend cap).

### Commercial Document Classification
Mantle classifies the commercial role of every ingested file into:
- `TAX_INVOICE`: Standard payable tax invoice.
- `PROFORMA_INVOICE`: Preliminary quotation; non-payable.
- `CREDIT_NOTE`: Adjusts an earlier invoice balance downward.
- `DEBIT_NOTE`: Adjusts an earlier invoice balance upward.
- `PAYMENT_RECEIPT`: Acknowledgment of past cash/bank disbursement. **Non-payable; automatically quarantined.**
- `DELIVERY_CHALLAN`: Goods movement voucher without tax liability.

If classification yields a non-payable document type (such as `PAYMENT_RECEIPT`), the system refuses to create an invoice liability and writes the record to `quarantined_documents` with an immutable audit event.

---

## 4. Multimodal Visual Adapter: AWS Bedrock Palmyra Vision 7B

- **Model ID:** `writer.palmyra-vision-7b`
- **Region:** AWS N. Virginia (`us-east-1`)
- **Role:** Evaluated as a visual OCR pre-fill adapter for degraded raster scans.
- **Status:** **Disabled by default** via `ENABLE_PALMYRA_VISION=false`.

### Evaluation Findings
Evaluated on `APTC-037` (low-contrast, skewed scan):
- Correctly parsed the supplier identity visually (*"Coastal Packaging Solutions"*).
- Exhibited character substitutions on alphanumeric tax strings (`325YSYNTH001001K125` vs ground truth GSTIN).
- Conflated line subtotal with grand total (`₹9,500.00` vs `₹17,696.00`).
- **Safety Rule:** Deterministic GST tax rules caught the mathematical variance and failed closed to HITL review. Zero hallucinated values entered the ledger.

---

## 5. Structured Output & Confidence Grounding

Extracted fields are mapped into typed Pydantic models with field-level confidence scores ($[0.0, 1.0]$):

```python
class ExtractedInvoice(BaseModel):
    invoice_number: str
    invoice_date: date
    vendor_gstin: str
    customer_gstin: str
    taxable_subtotal: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    total_amount: Decimal
    line_items: List[ExtractedLineItem]
    confidence_scores: Dict[str, float]
    bounding_boxes: Optional[Dict[str, List[float]]]
```

If the overall confidence score falls below $0.80$, or if critical fields (Invoice Number, Vendor GSTIN, Net Payable) have confidence $< 0.70$, the pipeline automatically blocks straight-through processing and flags the invoice for manual human review.
