"""Mock Enterprise Resource Planning (ERP) database for Zamp PS-1.

Provides authoritative vendor master data, open purchase orders, and historical
invoice ledgers to simulate NetSuite / SAP systems-of-record.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from engine.models import (
    DecisionState,
    HistoricalInvoiceRecord,
    POLineItem,
    PurchaseOrder,
    VendorRecord,
)


class MockERPDatabase:
    """In-memory, deterministic ERP database for vendor & PO validation."""

    def __init__(self) -> None:
        self.vendors: Dict[str, VendorRecord] = {}
        self.purchase_orders: Dict[str, PurchaseOrder] = {}
        self.historical_invoices: List[HistoricalInvoiceRecord] = []
        self._seed_database()

    def _seed_database(self) -> None:
        """Seed the ERP with realistic enterprise data."""
        # 1. Vendors
        v1 = VendorRecord(
            vendor_id="VEND-001",
            name="Apex Cloud Technologies Inc.",
            tax_id="US-EIN-94-3829102",
            status="ACTIVE",
            payment_terms="Net 30",
            contact_email="ap-billing@apexcloud.io",
        )
        v2 = VendorRecord(
            vendor_id="VEND-002",
            name="Global Logistics Partners LLC",
            tax_id="US-EIN-12-8492019",
            status="ACTIVE",
            payment_terms="Net 15",
            contact_email="invoices@globallogistics.com",
        )
        v3 = VendorRecord(
            vendor_id="VEND-003",
            name="Valley Hardware & Tools",
            tax_id="US-EIN-55-9018273",
            status="ACTIVE",
            payment_terms="Net 30",
            contact_email="accounts@valleytools.com",
        )
        v_suspended = VendorRecord(
            vendor_id="VEND-999",
            name="Suspended Logistics Inc.",
            tax_id="US-EIN-00-1112233",
            status="SUSPENDED",
            payment_terms="Prepaid Only",
            contact_email="legal@suspendedlogistics.com",
        )

        for v in [v1, v2, v3, v_suspended]:
            self.vendors[v.vendor_id] = v

        # 2. Purchase Orders
        # PO-1042: Clean open PO for Happy Path (HP-01)
        po_1042 = PurchaseOrder(
            po_number="PO-1042",
            vendor_id="VEND-001",
            vendor_name="Apex Cloud Technologies Inc.",
            authorized_amount=10000.00,
            invoiced_amount=0.00,
            status="OPEN",
            line_items=[
                POLineItem(
                    line_number=1,
                    item_code="API-COMPUTE-T3",
                    description="Enterprise API Compute Tier 3",
                    authorized_quantity=20.0,
                    contracted_unit_price=500.00,
                    total_amount=10000.00,
                    invoiced_quantity=0.0,
                    invoiced_amount=0.0,
                )
            ],
        )

        # PO-1042-SPLIT: Pre-invoiced PO for Edge Case 1 (Split PO Budget Overrun)
        # Billed $8,000 previously. Only $2,000 remaining.
        po_1042_split = PurchaseOrder(
            po_number="PO-1042-SPLIT",
            vendor_id="VEND-001",
            vendor_name="Apex Cloud Technologies Inc.",
            authorized_amount=10000.00,
            invoiced_amount=8000.00,
            status="PARTIALLY_INVOICED",
            line_items=[
                POLineItem(
                    line_number=1,
                    item_code="API-COMPUTE-T3",
                    description="Enterprise API Compute Tier 3",
                    authorized_quantity=20.0,
                    contracted_unit_price=500.00,
                    total_amount=10000.00,
                    invoiced_quantity=16.0,
                    invoiced_amount=8000.00,
                )
            ],
        )

        # PO-2090: Open PO for Edge Case 3 (Unit Price Variance)
        po_2090 = PurchaseOrder(
            po_number="PO-2090",
            vendor_id="VEND-002",
            vendor_name="Global Logistics Partners LLC",
            authorized_amount=5000.00,
            invoiced_amount=0.00,
            status="OPEN",
            line_items=[
                POLineItem(
                    line_number=1,
                    item_code="LOG-DEDICATED-HR",
                    description="Dedicated Freight Coordination",
                    authorized_quantity=50.0,
                    contracted_unit_price=100.00,
                    total_amount=5000.00,
                    invoiced_quantity=0.0,
                    invoiced_amount=0.0,
                )
            ],
        )

        # PO-3015: Open PO for Valley Hardware (for EC-04 reference lookup)
        po_3015 = PurchaseOrder(
            po_number="PO-3015",
            vendor_id="VEND-003",
            vendor_name="Valley Hardware & Tools",
            authorized_amount=2500.00,
            invoiced_amount=0.00,
            status="OPEN",
            line_items=[
                POLineItem(
                    line_number=1,
                    item_code="IND-TOOL-SET",
                    description="Industrial Precision Metric Tool Set",
                    authorized_quantity=2.0,
                    contracted_unit_price=640.00,
                    total_amount=1280.00,
                    invoiced_quantity=0.0,
                    invoiced_amount=0.0,
                )
            ],
        )

        for po in [po_1042, po_1042_split, po_2090, po_3015]:
            self.purchase_orders[po.po_number] = po

        # 3. Seeded Historical Invoices (to trigger Duplicate Rejection in EC-02)
        # Invoice INV-2026-089 was already processed 12 days ago
        earlier_date = date.today() - timedelta(days=12)
        historical_invoice = HistoricalInvoiceRecord(
            invoice_id="HIST-INV-9102",
            vendor_id="VEND-001",
            invoice_number="INV-2026-089",
            amount=5425.00,
            processed_date=earlier_date,
            sha256_hash=hashlib.sha256(b"VEND-001:INV-2026-089:5425.00").hexdigest(),
            batch_id="BATCH-2026-10-12A",
            status=DecisionState.AUTO_APPROVED,
        )
        self.historical_invoices.append(historical_invoice)

    # Vendor Lookup Methods
    def get_vendor_by_name(self, name: str) -> Optional[VendorRecord]:
        """Fuzzy/normalized search for vendor by name."""
        clean_target = name.strip().lower()
        for v in self.vendors.values():
            if clean_target in v.name.lower() or v.name.lower() in clean_target:
                return v
        return None

    def get_vendor_by_tax_id(self, tax_id: str) -> Optional[VendorRecord]:
        """Exact lookup by Tax ID."""
        clean_tax = tax_id.replace("-", "").replace(" ", "").upper()
        for v in self.vendors.values():
            if v.tax_id.replace("-", "").replace(" ", "").upper() == clean_tax:
                return v
        return None

    # PO Lookup Methods
    def get_po(self, po_number: str) -> Optional[PurchaseOrder]:
        """Retrieve PO by PO number."""
        clean_po = po_number.strip().upper()
        return self.purchase_orders.get(clean_po)

    def find_open_pos_for_vendor(self, vendor_id: str) -> List[PurchaseOrder]:
        """Find all active POs for a given vendor."""
        return [
            po
            for po in self.purchase_orders.values()
            if po.vendor_id == vendor_id and po.status in ("OPEN", "PARTIALLY_INVOICED")
        ]

    # Duplicate Detection
    def check_duplicate(
        self,
        vendor_id: str,
        invoice_number: str,
        amount: float,
        sha256_hash: Optional[str] = None,
        invoice_date: Optional[date] = None,
        window_days: int = 0,
    ) -> Tuple[bool, Optional[HistoricalInvoiceRecord]]:
        """Check if an invoice has already been submitted or paid.

        Matches on:
        1. Exact vendor_id + invoice_number collision.
        2. Exact sha256_hash collision.
        3. Same vendor_id + amount within the duplicate window (same bill resubmitted under a typo).
        """
        for record in self.historical_invoices:
            # Check 1: Invoice number match
            if record.vendor_id == vendor_id and record.invoice_number.upper() == invoice_number.strip().upper():
                return True, record

            # Check 2: Hash match
            if sha256_hash and record.sha256_hash == sha256_hash:
                return True, record

            # Check 3: Same vendor + amount inside the duplicate window
            if (
                record.vendor_id == vendor_id
                and abs(record.amount - amount) < 0.01
                and invoice_date
                and abs((record.processed_date - invoice_date).days) <= window_days
            ):
                return True, record

        return False, None

    def record_processed_invoice(self, record: HistoricalInvoiceRecord) -> None:
        """Add a processed invoice to the historical ledger."""
        self.historical_invoices.append(record)

    def record_po_drawdown(self, po_number: str, amount: float) -> None:
        """Deduct invoice amount from open PO balance."""
        po = self.get_po(po_number)
        if po:
            po.invoiced_amount = round(po.invoiced_amount + amount, 2)
            if po.remaining_balance <= 0.0:
                po.status = "EXHAUSTED"
            else:
                po.status = "PARTIALLY_INVOICED"

    def record_po_line_usage(
        self, po_number: str, po_line_number: int, quantity: float, amount: float
    ) -> None:
        """Advance the billed quantity/amount on a single PO line after approval."""
        po = self.get_po(po_number)
        if not po:
            return
        for line in po.line_items:
            if line.line_number == po_line_number:
                line.invoiced_quantity = round(line.invoiced_quantity + quantity, 2)
                line.invoiced_amount = round(line.invoiced_amount + amount, 2)
                return

    def reset(self) -> None:
        """Restore the database to its seeded demo state (repeatable scenario runs)."""
        self.vendors.clear()
        self.purchase_orders.clear()
        self.historical_invoices.clear()
        self._seed_database()
