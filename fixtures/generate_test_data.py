"""Generates realistic enterprise PDF invoices and JSON payloads for PS-1 test cases.

Produces:
1. HP-01: Happy Path (Apex Cloud, PO-1042, $5,425.00) -> AUTO_APPROVED
2. EC-01: Split PO Overrun (Apex Cloud, PO-1042-SPLIT, $6,500.00) -> FLAGGED_HITL_REVIEW
3. EC-02: Duplicate Submission (Apex Cloud, INV-2026-089) -> REJECTED
4. EC-03: Price Spike (+35% on Global Logistics, PO-2090) -> FLAGGED_HITL_REVIEW
5. EC-04: Low-Res Scan / Missing PO (Valley Hardware, $1,280.00) -> FLAGGED_HITL_REVIEW
"""

import json
import os
from datetime import date
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "data")


def create_pdf(
    file_path: str,
    vendor_name: str,
    vendor_tax_id: str,
    invoice_number: str,
    invoice_date: str,
    po_reference: str,
    lines: list,
    subtotal: float,
    tax: float,
    total: float,
    is_scanned: bool = False,
):
    """Generate a clean, professional PDF invoice using ReportLab."""
    c = canvas.Canvas(file_path, pagesize=letter)
    width, height = letter

    # Header
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, height - 60, vendor_name)

    c.setFont("Helvetica", 10)
    c.drawString(50, height - 78, f"Tax ID: {vendor_tax_id}")
    c.drawString(50, height - 92, "100 Tech Enterprise Blvd, Suite 400")

    # Invoice Details Block
    c.setFont("Helvetica-Bold", 12)
    c.drawString(400, height - 60, "INVOICE")
    c.setFont("Helvetica", 10)
    c.drawString(400, height - 78, f"Invoice #: {invoice_number}")
    c.drawString(400, height - 92, f"Date: {invoice_date}")
    if po_reference:
        c.drawString(400, height - 106, f"PO Ref: {po_reference}")

    # Separator Line
    c.setLineWidth(1)
    c.line(50, height - 120, width - 50, height - 120)

    # Line Items Header
    y = height - 145
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "#")
    c.drawString(80, y, "Description")
    c.drawString(320, y, "Qty")
    c.drawString(400, y, "Unit Price")
    c.drawString(480, y, "Total")

    c.line(50, y - 5, width - 50, y - 5)

    # Line Items
    y -= 25
    c.setFont("Helvetica", 10)
    for idx, item in enumerate(lines, start=1):
        desc, qty, unit_price, line_total = item
        c.drawString(50, y, str(idx))
        c.drawString(80, y, str(desc))
        c.drawString(320, y, f"{qty:.1f}")
        c.drawString(400, y, f"${unit_price:,.2f}")
        c.drawString(480, y, f"${line_total:,.2f}")
        y -= 20

    # Totals Block
    y -= 20
    c.line(320, y + 10, width - 50, y + 10)
    c.drawString(320, y - 5, "Subtotal:")
    c.drawRightString(width - 50, y - 5, f"${subtotal:,.2f}")

    c.drawString(320, y - 22, "Tax:")
    c.drawRightString(width - 50, y - 22, f"${tax:,.2f}")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(320, y - 42, "Grand Total:")
    c.drawRightString(width - 50, y - 42, f"${total:,.2f}")

    if is_scanned:
        # Realistic scanned copy stamp and watermark
        c.saveState()
        c.setFont("Helvetica-Bold", 32)
        c.setFillColorRGB(0.88, 0.88, 0.88)
        c.drawString(180, 520, "SCANNED COPY")
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.drawString(50, 40, "[SCANNED DOCUMENT - MOBILE INVOICE CAPTURE]")
        c.restoreState()

    c.save()


def generate_all_fixtures():
    """Build all 5 JSON test fixtures and PDF invoices."""
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    today_str = "2026-10-29"

    scenarios = [
        # HP-01: Happy Path
        {
            "id": "HP-01-Happy-Path",
            "pdf_name": "HP-01-Happy-Path.pdf",
            "json_name": "HP-01-Happy-Path.json",
            "vendor_name": "Apex Cloud Technologies Inc.",
            "vendor_tax_id": "US-EIN-94-3829102",
            "invoice_number": "INV-2026-101",
            "invoice_date": today_str,
            "po_reference": "PO-1042",
            "lines": [
                ("Enterprise API Compute Tier 3", 10.0, 500.00, 5000.00)
            ],
            "subtotal": 5000.00,
            "tax": 425.00,
            "total": 5425.00,
            "document_type": "DIGITAL_PDF",
            "confidence": 0.98,
        },
        # EC-01: Split PO Overrun
        {
            "id": "EC-01-Split-PO-Overrun",
            "pdf_name": "EC-01-Split-PO-Overrun.pdf",
            "json_name": "EC-01-Split-PO-Overrun.json",
            "vendor_name": "Apex Cloud Technologies Inc.",
            "vendor_tax_id": "US-EIN-94-3829102",
            "invoice_number": "INV-2026-102",
            "invoice_date": today_str,
            "po_reference": "PO-1042-SPLIT",
            "lines": [
                ("Enterprise API Compute Tier 3", 12.0, 500.00, 6000.00)
            ],
            "subtotal": 6000.00,
            "tax": 500.00,
            "total": 6500.00,
            "document_type": "DIGITAL_PDF",
            "confidence": 0.97,
        },
        # EC-02: Duplicate Submission (exact $3,250.00 matching seeded historical ERP invoice)
        {
            "id": "EC-02-Duplicate-Submission",
            "pdf_name": "EC-02-Duplicate-Submission.pdf",
            "json_name": "EC-02-Duplicate-Submission.json",
            "vendor_name": "Apex Cloud Technologies Inc.",
            "vendor_tax_id": "US-EIN-94-3829102",
            "invoice_number": "INV-2026-089",  # Matches seeded historical invoice
            "invoice_date": today_str,
            "po_reference": "PO-1042",
            "lines": [
                ("Enterprise API Compute Tier 3 (Partial)", 5.0, 600.00, 3000.00)
            ],
            "subtotal": 3000.00,
            "tax": 250.00,
            "total": 3250.00,
            "document_type": "DIGITAL_PDF",
            "confidence": 0.99,
        },
        # EC-03: Price Spike Variance (+35%)
        {
            "id": "EC-03-Price-Spike-Variance",
            "pdf_name": "EC-03-Price-Spike-Variance.pdf",
            "json_name": "EC-03-Price-Spike-Variance.json",
            "vendor_name": "Global Logistics Partners LLC",
            "vendor_tax_id": "US-EIN-12-8492019",
            "invoice_number": "INV-2026-303",
            "invoice_date": today_str,
            "po_reference": "PO-2090",
            "lines": [
                ("Dedicated Freight Coordination", 40.0, 135.00, 5400.00)
            ],
            "subtotal": 5400.00,
            "tax": 0.00,
            "total": 5400.00,
            "document_type": "DIGITAL_PDF",
            "confidence": 0.96,
        },
        # EC-04: Low-Res Scan / Missing PO
        {
            "id": "EC-04-Low-Res-Missing-PO",
            "pdf_name": "EC-04-Low-Res-Missing-PO.pdf",
            "json_name": "EC-04-Low-Res-Missing-PO.json",
            "vendor_name": "Valley Hardware & Tools",
            "vendor_tax_id": "US-EIN-55-9018273",
            "invoice_number": "INV-2026-404",
            "invoice_date": today_str,
            "po_reference": None,  # Intentionally missing PO
            "lines": [
                ("Industrial Precision Metric Tool Set", 2.0, 640.00, 1280.00)
            ],
            "subtotal": 1280.00,
            "tax": 0.00,
            "total": 1280.00,
            "document_type": "SCANNED_IMAGE",
            "confidence": 0.62,  # Below 75% threshold
        },
    ]

    for sc in scenarios:
        pdf_path = os.path.join(FIXTURES_DIR, sc["pdf_name"])
        create_pdf(
            file_path=pdf_path,
            vendor_name=sc["vendor_name"],
            vendor_tax_id=sc["vendor_tax_id"],
            invoice_number=sc["invoice_number"],
            invoice_date=sc["invoice_date"],
            po_reference=sc["po_reference"],
            lines=sc["lines"],
            subtotal=sc["subtotal"],
            tax=sc["tax"],
            total=sc["total"],
            is_scanned=(sc["document_type"] == "SCANNED_IMAGE"),
        )

        # Generate accompanying JSON payload
        json_path = os.path.join(FIXTURES_DIR, sc["json_name"])
        json_data = {
            "invoice_number": sc["invoice_number"],
            "invoice_date": sc["invoice_date"],
            "vendor": {
                "name": sc["vendor_name"],
                "tax_id": sc["vendor_tax_id"],
                "remit_address": "100 Tech Enterprise Blvd, Suite 400",
                "contact_email": "accounts@vendor.com",
            },
            "po_reference": sc["po_reference"],
            "line_items": [
                {
                    "line_number": idx + 1,
                    "description": l[0],
                    "quantity": l[1],
                    "unit_price": l[2],
                    "total": l[3],
                }
                for idx, l in enumerate(sc["lines"])
            ],
            "subtotal": sc["subtotal"],
            "tax_amount": sc["tax"],
            "total_amount": sc["total"],
            "currency": "USD",
            "document_type": sc["document_type"],
            "confidence_scores": {
                "overall": sc["confidence"],
                "invoice_number": 0.98 if sc["confidence"] > 0.75 else 0.65,
                "total_amount": 0.99 if sc["confidence"] > 0.75 else 0.70,
                "po_reference": 0.95 if sc["po_reference"] else 0.0,
            },
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)

    print(f"Successfully generated {len(scenarios)} PDF and JSON test fixtures in {FIXTURES_DIR}")


if __name__ == "__main__":
    generate_all_fixtures()
