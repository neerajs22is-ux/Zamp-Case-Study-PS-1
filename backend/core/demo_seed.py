"""Prepared demo examples. No OCR or ingestion job is implied by this seed."""
from decimal import Decimal
from io import BytesIO
import hashlib

from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from sqlalchemy import select

from backend.core.storage import build_tenant_storage_path, storage_adapter
from backend.models.domain import (AuditEvent, Document, ExceptionRecord, GoodsReceiptLineSnapshot,
    GoodsReceiptSnapshot, Invoice, InvoiceLine, QualityControlSnapshot, Vendor,
    VendorGSTIN, WorkOrderLineSnapshot, WorkOrderSnapshot)


def scenario_definitions(org_id, now):
    """One source for the printed document and its structured financial records."""
    suffix = org_id.removeprefix('org_demo_').upper()
    common = dict(vendor='Asterion Precision Components Pvt Ltd', gstin='29SYNTH0001A1Z5',
                  date=now.strftime('%Y-%m-%d'), qty=Decimal('100'), po_rate=Decimal('100'),
                  tax_rate=Decimal('0.18'))
    cases = []
    for number, title, rate, qc in [(1, 'CLEAN MATCH', '100', 'ACCEPTED'),
                                     (2, 'PRICE VARIANCE', '120', 'ACCEPTED'),
                                     (3, 'QC HOLD', '100', 'HOLD')]:
        c = dict(common, number=number, title=title, rate=Decimal(rate), qc=qc,
                 invoice=f'DEMO/{suffix}/{number:03}', po=f'PO-{suffix}-{number:03}',
                 grn=f'GRN-{suffix}-{number:03}', qc_id=f'QC-{suffix}-{number:03}',
                 item='Precision steel components')
        c['subtotal'] = c['qty'] * c['rate']
        c['tax'] = c['subtotal'] * c['tax_rate']
        c['total'] = c['subtotal'] + c['tax']
        cases.append(c)
    cases += [dict(number=4, title='LOW-CONFIDENCE SCAN', date=common['date'], sample_id=suffix),
              dict(number=5, title='NON-PAYABLE RECEIPT', date=common['date'],
                   invoice=f'RCPT/{suffix}/005', vendor='Northstar Logistics',
                   total=Decimal('2500.00'))]
    return cases


def render_pdf(case):
    out = BytesIO()
    pdf = canvas.Canvas(out, pagesize=(612, 792), pageCompression=0)
    if case['number'] == 4:
        # Image-only document: no native text is presented as extracted evidence.
        image = Image.new('RGB', (1224, 1584), 'white')
        draw = ImageDraw.Draw(image)
        draw.text((120, 170), 'FADED SUPPLIER DOCUMENT', fill='#aaaaaa')
        draw.text((120, 230), 'Reference and amount illegible - review original', fill='#bbbbbb')
        draw.text((120, 300), 'PREPARED DEMO SCAN', fill='#aaaaaa')
        draw.text((120, 350), 'Sample ' + case['sample_id'], fill='#aaaaaa')
        pdf.drawImage(ImageReader(image), 0, 0, width=612, height=792)
    else:
        lines = ['PREPARED SYNTHETIC DEMO - ' + case['title'],
                 'PAYMENT RECEIPT - NOT A TAX INVOICE' if case['number'] == 5 else 'TAX INVOICE',
                 'Supplier: ' + case['vendor'], 'Reference: ' + case['invoice'],
                 'Date: ' + case['date']]
        if case['number'] <= 3:
            lines += ['GSTIN: ' + case['gstin'], 'PO: ' + case['po'],
                      f"{case['item']} | Qty {case['qty']} | Unit INR {case['rate']}",
                      f"Subtotal INR {case['subtotal']:.2f}", f"GST 18% INR {case['tax']:.2f}"]
        lines += [f"Total INR {case['total']:.2f}"]
        if case['number'] == 5:
            lines += ['Payment already received. No amount is payable.']
        pdf.setFont('Helvetica', 12)
        for i, line in enumerate(lines):
            pdf.drawString(48, 740 - i * 27, line)
    pdf.showPage()
    pdf.save()
    return out.getvalue()


def seed_demo_examples(db, org_id, user_id, now):
    """Idempotently create all examples; compensate storage on failed provisioning."""
    existing = db.scalars(select(Invoice).where(Invoice.org_id == org_id,
                         Invoice.source_channel == 'DEMO_EXPERIENCE')).all()
    if existing:
        if len(existing) == 5:
            return
        raise RuntimeError('Incomplete demo seed; refusing to create duplicates')
    from backend.api.v1.invoices import reevaluate_match_gates
    stored = []
    try:
        vendor_id = f'vnd_{org_id}'
        vendor_code = f'VEND-{org_id[-8:]}'
        db.add(Vendor(id=vendor_id, org_id=org_id, erp_vendor_code=vendor_code,
                      legal_name='Asterion Precision Components Pvt Ltd',
                      bank_account_verified=True, created_at=now))
        db.flush()
        db.add(VendorGSTIN(id=f'vg_{org_id}', org_id=org_id, vendor_id=vendor_id,
                           gstin='29SYNTH0001A1Z5', state_code='29', status='ACTIVE'))
        db.flush()
        for case in scenario_definitions(org_id, now):
            n = case['number']
            inv_id, doc_id = f'inv_{org_id}_{n}', f'doc_{org_id}_{n}'
            filename = f'{n:02}_{case["title"].lower().replace("-", "_").replace(" ", "_")}.pdf'
            data = render_pdf(case)
            key = build_tenant_storage_path(org_id, doc_id, filename)
            meta = storage_adapter.save_file(content=data, filename=filename,
                                               mime_type='application/pdf', storage_key=key)
            stored.append(meta['storage_key'])
            inv = Invoice(id=inv_id, org_id=org_id, source_channel='DEMO_EXPERIENCE',
                          invoice_number=case.get('invoice'), vendor_name=case.get('vendor'),
                          vendor_gstin=case.get('gstin'), po_reference=case.get('po'),
                          invoice_date=now, currency='INR', subtotal_amount=case.get('subtotal'),
                          tax_amount=case.get('tax'), total_amount=case.get('total'),
                          net_payable_amount=case.get('total') if n <= 3 else (Decimal('0') if n == 5 else None),
                          stage='ACTION_REQUIRED', decision='NEEDS_REVIEW',
                          decision_reason='Prepared scenario; no OCR or processing run was performed.',
                          owner_user_id=user_id, created_at=now)
            db.add(inv)
            db.flush()
            db.add(Document(id=doc_id, org_id=org_id, invoice_id=inv_id, filename=filename,
                            mime_type='application/pdf', file_size_bytes=len(data),
                            sha256_hash=hashlib.sha256(data).hexdigest(),
                            storage_provider=meta['storage_provider'], storage_key=meta['storage_key'],
                            is_original=True, is_deleted=False, uploaded_at=now))
            if n <= 3:
                wo_id, grn_id = f'wo_{org_id}_{n}', f'grn_{org_id}_{n}'
                # PO allows the clean amount; the price case deliberately exceeds its rate and balance.
                authorized = case['qty'] * case['po_rate'] * Decimal('1.18')
                db.add(WorkOrderSnapshot(id=wo_id, org_id=org_id, po_number=case['po'],
                       vendor_code=vendor_code, total_authorized_amount=authorized,
                       remaining_balance=authorized, currency='INR', status='APPROVED', retrieved_at=now))
                db.add(GoodsReceiptSnapshot(id=grn_id, org_id=org_id, grn_number=case['grn'],
                       po_number=case['po'], received_date=now, retrieved_at=now))
                db.flush()
                db.add(WorkOrderLineSnapshot(id=f'wol_{org_id}_{n}', org_id=org_id, po_id=wo_id,
                       line_number=1, item_code='COMP-01', description=case['item'],
                       authorized_quantity=case['qty'], contracted_unit_rate=case['po_rate'],
                       authorized_line_total=case['qty'] * case['po_rate']))
                db.add(GoodsReceiptLineSnapshot(id=f'grl_{org_id}_{n}', org_id=org_id, grn_id=grn_id,
                       po_line_number=1, accepted_quantity=case['qty'], rejected_quantity=0))
                db.add(QualityControlSnapshot(id=f'qc_{org_id}_{n}', org_id=org_id,
                       qc_certificate_number=case['qc_id'], grn_number=case['grn'],
                       overall_status=case['qc'], retrieved_at=now))
                db.add(InvoiceLine(id=f'line_{org_id}_{n}', org_id=org_id, invoice_id=inv_id,
                       line_number=1, description=case['item'], billed_quantity=case['qty'],
                       billed_unit_rate=case['rate'], billed_line_total=case['subtotal']))
                db.flush()
                reevaluate_match_gates(db, inv, org_id)
            elif n == 4:
                inv.decision = 'FLAGGED_HITL_REVIEW'
                inv.decision_reason = 'Prepared degraded raster scan: document evidence is insufficient; human review required.'
            else:
                inv.stage = 'REJECTED'
                inv.decision = 'REJECTED'
                inv.decision_reason = 'Prepared payment receipt: payment already received; not a payable invoice.'
            if n in (2, 3, 4):
                gate, name = {2: (6, 'PO Price & Quantity Tolerance'),
                              3: (4, 'QC Inspection Accepted'),
                              4: (8, 'Document evidence insufficient')}[n]
                db.add(ExceptionRecord(id=f'exc_{org_id}_{n}', org_id=org_id, invoice_id=inv_id,
                       blocking_gate_number=gate, blocking_gate_name=name,
                       exposure_amount_inr=case.get('total', 0), status='OPEN',
                       assigned_user_id=user_id, created_at=now))
            db.add(AuditEvent(id=f'audit_{org_id}_{n}', org_id=org_id, invoice_id=inv_id,
                   actor_id=user_id, actor_role='AP_ASSOCIATE', action='PREPARED_DEMO_SCENARIO',
                   reason=f"Prepared example: {case['title']}. No OCR or ingestion job was run.", timestamp=now))
        db.commit()
    except Exception:
        db.rollback()
        for key in stored:
            try:
                storage_adapter.delete_file(key)
            except Exception:
                pass
        raise
