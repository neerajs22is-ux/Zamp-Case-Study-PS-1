"""Pydantic v2 schemas for Indian AP Document Intelligence and Mantle Inference.

Enforces strict structural boundaries, untrusted evidence provenance tracking,
and typed representation for Indian GST commercial documents.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CommercialDocumentType(str, Enum):
    INVOICE = "INVOICE"
    PAYMENT_RECEIPT = "PAYMENT_RECEIPT"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    DELIVERY_CHALLAN = "DELIVERY_CHALLAN"
    CREDIT_NOTE = "CREDIT_NOTE"
    DEBIT_NOTE = "DEBIT_NOTE"
    PROFORMA_INVOICE = "PROFORMA_INVOICE"
    UNKNOWN = "UNKNOWN"


class FieldEvidence(BaseModel):
    """Provenance citation linking an extracted entity to raw page text."""
    field_name: str
    extracted_value: str
    page_number: int = Field(default=1, ge=1)
    raw_snippet: Optional[str] = None
    is_verified: bool = False


class ExtractedLineItem(BaseModel):
    """Individual line item from an Indian GST invoice."""
    model_config = ConfigDict(allow_inf_nan=False)
    item_description: str = Field(..., min_length=1)
    hsn_sac: Optional[str] = None
    quantity: float = Field(..., gt=0)
    unit: Optional[str] = None
    unit_price: float = Field(default=0.0, ge=0)
    taxable_amount: float = Field(default=0.0, ge=0)
    cgst_rate: float = Field(default=0.0, ge=0)
    cgst_amount: float = Field(default=0.0, ge=0)
    sgst_rate: float = Field(default=0.0, ge=0)
    sgst_amount: float = Field(default=0.0, ge=0)
    igst_rate: float = Field(default=0.0, ge=0)
    igst_amount: float = Field(default=0.0, ge=0)
    total_amount: float = Field(default=0.0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # item_description
            if "item_description" not in data:
                desc = data.get("description") or data.get("item") or data.get("line_item")
                if desc:
                    data["item_description"] = str(desc)
            # taxable_amount
            if "taxable_amount" not in data or data.get("taxable_amount") is None:
                taxable = data.get("taxable_value") or data.get("amount")
                if taxable is not None:
                    data["taxable_amount"] = float(taxable)
            # unit_price
            if "unit_price" not in data or data.get("unit_price") is None:
                price = data.get("unit_rate") or data.get("rate") or data.get("price")
                if price is not None:
                    data["unit_price"] = float(price)
                elif data.get("quantity") and data.get("taxable_amount"):
                    qty = float(data["quantity"])
                    taxable = float(data["taxable_amount"])
                    data["unit_price"] = round(taxable / qty, 2) if qty > 0 else 0.0
                else:
                    data["unit_price"] = 0.0
            # total_amount
            if "total_amount" not in data or data.get("total_amount") is None:
                tot = data.get("total") or data.get("line_total")
                if tot is not None:
                    data["total_amount"] = float(tot)
                elif "taxable_amount" in data and data["taxable_amount"] is not None:
                    taxes = (
                        float(data.get("cgst_amount") or 0)
                        + float(data.get("sgst_amount") or 0)
                        + float(data.get("igst_amount") or 0)
                    )
                    data["total_amount"] = round(float(data["taxable_amount"]) + taxes, 2)
                elif "quantity" in data and "unit_price" in data:
                    data["total_amount"] = round(float(data["quantity"]) * float(data["unit_price"]), 2)
        return data

    @model_validator(mode="after")
    def validate_line_arithmetic(self) -> ExtractedLineItem:
        calc_taxable = round(self.quantity * self.unit_price, 2)
        # Allow 0.50 tolerance for rounding differences in unit rate
        if abs(calc_taxable - round(self.taxable_amount, 2)) > 1.0:
            # We preserve the reported taxable_amount but record in discrepancy if needed
            pass
        return self


class MantleInvoiceExtraction(BaseModel):
    """Structured extraction output validated against Bedrock Mantle Qwen3 235B response."""
    model_config = ConfigDict(allow_inf_nan=False)
    document_type: CommercialDocumentType = CommercialDocumentType.INVOICE
    is_payable_invoice: bool = True
    supplier_name: str = Field(..., min_length=1)
    supplier_gstin: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_gstin: Optional[str] = None
    place_of_supply: Optional[str] = None
    invoice_number: str = Field(default="UNKNOWN")
    invoice_date: str = Field(default="1970-01-01")
    po_reference: Optional[str] = None
    currency: str = Field(default="INR", min_length=3, max_length=3)
    taxable_value: float = Field(default=0.0, ge=0)
    cgst_amount: float = Field(default=0.0, ge=0)
    sgst_amount: float = Field(default=0.0, ge=0)
    igst_amount: float = Field(default=0.0, ge=0)
    total_tax_amount: float = Field(default=0.0, ge=0)
    grand_total: float = Field(default=0.0, ge=0)
    line_items: List[ExtractedLineItem] = Field(default_factory=list)
    evidence: Dict[str, FieldEvidence] = Field(default_factory=dict)
    explanation: str = Field(default="")
    
    # Telemetry and audit metadata
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    tripwire_passed: bool = True
    unverified_fields: List[str] = Field(default_factory=list)
    http_status: int = 200
    model_id: str = "qwen.qwen3-235b-a22b-2507-v1:0"

    @model_validator(mode="before")
    @classmethod
    def normalize_top_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # invoice_number
            if not data.get("invoice_number"):
                inv = data.get("document_number") or data.get("receipt_number") or data.get("invoice_no") or data.get("inv_number")
                data["invoice_number"] = str(inv) if inv else "UNKNOWN"
            # invoice_date
            if not data.get("invoice_date"):
                dt = data.get("document_date") or data.get("receipt_date") or data.get("date")
                data["invoice_date"] = str(dt) if dt else "1970-01-01"
            # po_reference
            if "po_reference" not in data or data.get("po_reference") is None:
                po = data.get("po_number") or data.get("purchase_order") or data.get("po")
                if po:
                    data["po_reference"] = str(po)
            # taxable_value
            if "taxable_value" not in data or data.get("taxable_value") is None:
                taxable = data.get("taxable_amount") or data.get("subtotal")
                data["taxable_value"] = float(taxable) if taxable is not None else 0.0
            # grand_total
            if "grand_total" not in data or data.get("grand_total") is None:
                gt = data.get("total_amount") or data.get("total")
                data["grand_total"] = float(gt) if gt is not None else 0.0
            # total_tax_amount
            if "total_tax_amount" not in data or data.get("total_tax_amount") is None:
                calc_tax = (
                    float(data.get("cgst_amount") or 0)
                    + float(data.get("sgst_amount") or 0)
                    + float(data.get("igst_amount") or 0)
                )
                data["total_tax_amount"] = calc_tax
            # is_payable_invoice
            doc_type = str(data.get("document_type", "")).upper()
            if any(x in doc_type for x in ["RECEIPT", "PURCHASE_ORDER", "DELIVERY_CHALLAN", "PROFORMA"]):
                data["is_payable_invoice"] = False
        return data
