"""Data models and validation contracts for the PS-1 Invoice Processing Digital Employee.

Enforces strict Pydantic v2 validation and arithmetic invariants to eliminate
LLM calculation hallucinations before any enterprise financial decision is recorded.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class DocumentType(str, Enum):
    DIGITAL_PDF = "DIGITAL_PDF"
    SCANNED_IMAGE = "SCANNED_IMAGE"
    STRUCTURED_JSON = "STRUCTURED_JSON"


class DecisionState(str, Enum):
    AUTO_APPROVED = "AUTO_APPROVED"
    FLAGGED_HITL_REVIEW = "FLAGGED_HITL_REVIEW"
    REJECTED = "REJECTED"


class LineMatchStatus(str, Enum):
    MATCHED = "MATCHED"
    PRICE_VARIANCE = "PRICE_VARIANCE"
    QTY_EXCEEDED = "QTY_EXCEEDED"
    UNMATCHED = "UNMATCHED"


class InvoiceLineItem(BaseModel):
    line_number: int = Field(..., ge=1, description="Sequential line number on invoice")
    description: str = Field(..., min_length=1, description="Line item description")
    quantity: float = Field(..., gt=0, description="Billed quantity")
    unit_price: float = Field(..., ge=0, description="Billed price per unit")
    total: float = Field(..., ge=0, description="Total amount for this line item")

    @model_validator(mode="after")
    def validate_line_math(self) -> InvoiceLineItem:
        calculated_total = round(self.quantity * self.unit_price, 2)
        if abs(calculated_total - round(self.total, 2)) > 0.05:
            # Allow minor cent rounding, but flag discrepancies
            raise ValueError(
                f"Line {self.line_number} calculation mismatch: "
                f"{self.quantity} * {self.unit_price} = {calculated_total}, but line total is {self.total}"
            )
        return self


class VendorInfo(BaseModel):
    name: str = Field(..., min_length=1, description="Legal vendor/supplier name")
    tax_id: Optional[str] = Field(None, description="Tax Identification Number (EIN, GSTIN, VAT)")
    remit_address: Optional[str] = Field(None, description="Billing/remittance address")
    contact_email: Optional[str] = Field(None, description="Vendor accounts receivable email")


class Invoice(BaseModel):
    invoice_number: str = Field(..., min_length=1, description="Vendor invoice number")
    invoice_date: date = Field(..., description="Invoice issue date")
    due_date: Optional[date] = Field(None, description="Payment due date")
    vendor: VendorInfo
    po_reference: Optional[str] = Field(None, description="Purchase Order reference number")
    line_items: List[InvoiceLineItem] = Field(default_factory=list, description="Extracted line items")
    subtotal: float = Field(..., ge=0, description="Sum of line items before tax")
    tax_amount: float = Field(default=0.0, ge=0, description="Taxes and regulatory fees")
    total_amount: float = Field(..., gt=0, description="Grand total payable")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    document_type: DocumentType = DocumentType.DIGITAL_PDF
    raw_text: Optional[str] = Field(None, description="Raw extracted text if applicable")
    confidence_scores: Dict[str, float] = Field(
        default_factory=lambda: {
            "overall": 0.95,
            "invoice_number": 0.99,
            "total_amount": 0.99,
            "po_reference": 0.90,
        }
    )

    @model_validator(mode="after")
    def validate_totals(self) -> Invoice:
        if self.line_items:
            sum_lines = round(sum(item.total for item in self.line_items), 2)
            if abs(sum_lines - round(self.subtotal, 2)) > 0.05:
                raise ValueError(
                    f"Invoice subtotal mismatch: sum of line items ({sum_lines}) "
                    f"does not match subtotal ({self.subtotal})"
                )
        calculated_grand_total = round(self.subtotal + self.tax_amount, 2)
        if abs(calculated_grand_total - round(self.total_amount, 2)) > 0.05:
            raise ValueError(
                f"Invoice grand total mismatch: subtotal ({self.subtotal}) + tax ({self.tax_amount}) = "
                f"{calculated_grand_total}, but total_amount is {self.total_amount}"
            )
        return self


class POLineItem(BaseModel):
    line_number: int = Field(..., ge=1)
    item_code: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    authorized_quantity: float = Field(..., gt=0)
    contracted_unit_price: float = Field(..., ge=0)
    total_amount: float = Field(..., ge=0)
    invoiced_quantity: float = Field(default=0.0, ge=0)
    invoiced_amount: float = Field(default=0.0, ge=0)

    @property
    def remaining_quantity(self) -> float:
        return max(0.0, round(self.authorized_quantity - self.invoiced_quantity, 2))

    @property
    def remaining_amount(self) -> float:
        return max(0.0, round(self.total_amount - self.invoiced_amount, 2))


class PurchaseOrder(BaseModel):
    po_number: str = Field(..., min_length=1)
    vendor_id: str = Field(..., min_length=1)
    vendor_name: str = Field(..., min_length=1)
    authorized_amount: float = Field(..., gt=0)
    invoiced_amount: float = Field(default=0.0, ge=0)
    status: Literal["OPEN", "PARTIALLY_INVOICED", "CLOSED", "EXHAUSTED"] = "OPEN"
    line_items: List[POLineItem] = Field(default_factory=list)

    @property
    def remaining_balance(self) -> float:
        return max(0.0, round(self.authorized_amount - self.invoiced_amount, 2))


class VendorRecord(BaseModel):
    vendor_id: str
    name: str
    tax_id: str
    status: Literal["ACTIVE", "SUSPENDED", "UNAPPROVED"] = "ACTIVE"
    payment_terms: str = "Net 30"
    contact_email: str


class HistoricalInvoiceRecord(BaseModel):
    invoice_id: str
    vendor_id: str
    invoice_number: str
    amount: float
    processed_date: date
    sha256_hash: str
    batch_id: str
    status: DecisionState


class LineMatchResult(BaseModel):
    line_number: int
    matched_po_line: Optional[int] = None
    description: str
    billed_quantity: float
    po_quantity: Optional[float] = None
    billed_unit_price: float
    contracted_unit_price: Optional[float] = None
    price_variance_pct: float = 0.0
    price_variance_amount: float = 0.0
    status: LineMatchStatus
    notes: str


class StageTiming(BaseModel):
    stage_name: str
    latency_ms: float
    status: Literal["SUCCESS", "FAILED", "SKIPPED"] = "SUCCESS"
    details: Dict[str, Any] = Field(default_factory=dict)


class DecisionAudit(BaseModel):
    run_id: str
    invoice_number: str
    vendor_name: str
    po_number: Optional[str] = None
    decision: DecisionState
    overall_confidence: float
    reasons: List[str]
    discrepancy_details: Dict[str, Any] = Field(default_factory=dict)
    line_match_results: List[LineMatchResult] = Field(default_factory=list)
    vendor_email_draft: Optional[str] = None
    erp_voucher_id: Optional[str] = None
    stage_timings: List[StageTiming] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def line_results(self) -> List[LineMatchResult]:
        """Convenience alias for line_match_results."""
        return self.line_match_results
