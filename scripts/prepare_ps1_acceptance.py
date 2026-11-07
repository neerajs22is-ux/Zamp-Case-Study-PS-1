"""Prepare synthetic acceptance inputs locally. Never connects to app/providers or reads .env.

This is fixture preparation, not a provider-backed acceptance runner. No target
workspace is selected or created, and expected outcomes are never marked observed.
"""
import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import time

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from pypdf import PdfReader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)  # Never overwrite existing workspace artifacts.
    styles = getSampleStyleSheet()
    supplier = 'PS1 Synthetic Services'
    description = 'Acceptance review service'
    cases = []
    orders = []
    document_checks = []
    for case, number, po, rate, payable, qc in [
        ('happy', 'ACCEPT-HAPPY', 'ACCEPT-PO-HAPPY', 100, True, True),
        ('price_variance', 'ACCEPT-PRICE', 'ACCEPT-PO-PRICE', 120, True, True),
        ('missing_qc', 'ACCEPT-QC', 'ACCEPT-PO-QC', 100, True, False),
        ('payment_receipt', 'ACCEPT-RECEIPT', 'ACCEPT-PO-RECEIPT', 100, False, True),
    ]:
        taxable = Decimal(rate)
        gst = (taxable * Decimal('.09')).quantize(Decimal('.01'))
        total_tax = gst*2
        total = taxable+total_tax
        title = 'TAX INVOICE' if payable else 'PAYMENT RECEIPT'
        path = output/f'{case}.pdf'
        rows = [Paragraph('SYNTHETIC ACCEPTANCE FIXTURE - NO COMMERCIAL VALIDITY', styles['Heading3']),
            Paragraph(title, styles['Title']), Spacer(1,12)]
        for line in [f'Supplier: {supplier}', 'GSTIN: 29ABCDE1234F1Z5 (fictional test registration)',
            'Buyer: PS1 Synthetic Buyer', f'Document number: {number}', 'Document date: 2026-11-06',
            f'Purchase order: {po}', 'Place of supply: Karnataka', 'Currency: INR']:
            rows.append(Paragraph(line,styles['BodyText']))
        if not payable:
            rows.extend([Spacer(1,8),Paragraph('Acknowledges receipt of payment already made. This is not an invoice for payment.',styles['BodyText'])])
        rows.append(Spacer(1,20))
        table = Table([['Description','Qty','Unit rate','Taxable value','Line total incl GST'],
            [description,'1',f'{taxable:.2f}',f'{taxable:.2f}',f'{total:.2f}']],colWidths=[170,30,65,75,110])
        table.setStyle(TableStyle([('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9eef3')),('BOTTOMPADDING',(0,0),(-1,-1),10),
            ('TOPPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,0),.5,colors.grey)]))
        rows.extend([table,Spacer(1,20)])
        for line in [f'Taxable value: INR {taxable:.2f}', f'CGST: INR {gst:.2f}', f'SGST: INR {gst:.2f}',
            'IGST: INR 0.00',f'Total tax amount: INR {total_tax:.2f}',f'Grand total: INR {total:.2f}',
            'All amounts and identities are synthetic. Do not pay or submit approval actions.']:
            rows.append(Paragraph(line,styles['BodyText']))
        SimpleDocTemplate(str(path),pagesize=A4,leftMargin=30,rightMargin=30).build(rows)
        start = time.perf_counter()
        reader = PdfReader(path)
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        assert len(reader.pages)==1 and number in text and po in text and f'{total:.2f}' in text
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        document_checks.append(dict(file=path.name,sha256=digest,pages=len(reader.pages),text_characters=len(text),
            local_parse_ms=round((time.perf_counter()-start)*1000,3),status='LOCAL_SOURCE_CHECK_PASSED'))
        expected_decision = 'MATCH_CANDIDATE' if case=='happy' else 'REJECTED' if not payable else 'FLAGGED_EXCEPTION'
        cases.append(dict(case=case,pdf=path.name,expected=dict(decision=expected_decision,
            stage='PENDING_APPROVAL' if case=='happy' else 'REJECTED' if not payable else 'ACTION_REQUIRED',
            gates='1-7 PASS' if case=='happy' else 'gate 6 FAIL' if case=='price_variance' else 'gate 4 FAIL' if case=='missing_qc' else 'non-payable document rejected'),
            observed=None,execution='NOT_RUN_NO_DISPOSABLE_TARGET',
            ground_truth=dict(document_type='INVOICE' if payable else 'PAYMENT_RECEIPT',is_payable_invoice=payable,
                supplier_name=supplier,supplier_gstin='29ABCDE1234F1Z5',invoice_number=number,invoice_date='2026-11-06',
                po_reference=po,currency='INR',place_of_supply='Karnataka',taxable_value=float(taxable),
                cgst_amount=float(gst),sgst_amount=float(gst),igst_amount=0,total_tax_amount=float(total_tax),grand_total=float(total),
                line_items=[dict(item_description=description,quantity=1,unit_price=rate,taxable_amount=float(taxable),total_amount=float(total))])))
        orders.append(dict(po_number=po,vendor_code='ACCEPT-VENDOR',currency='INR',status='OPEN',
            total_authorized_amount=1000,remaining_balance=1000,
            lines=[dict(line_number=1,description=description,authorized_quantity=10,contracted_unit_rate=100,authorized_line_total=1000)],
            grn_number=f'GRN-{case}',accepted_quantity=10,qc_status='ACCEPTED' if qc else None))
    cases.insert(1,dict(case='identical_duplicate',pdf='happy.pdf',reuse_exact_bytes=True,
        expected=dict(http_status=409,status='DUPLICATE_DETECTED',new_job_count=0,additional_provider_calls=0),
        observed=None,execution='NOT_RUN_NO_DISPOSABLE_TARGET'))
    reference_pdf = output/'synthetic_procurement.pdf'
    rows = [Paragraph('SYNTHETIC PROCUREMENT REFERENCES - NOT AN ERP EXPORT',styles['Heading2']),
        Paragraph('Expected test setup only. These records have NOT been inserted into any workspace.',styles['BodyText']),Spacer(1,18)]
    for order in orders:
        rows.extend([Paragraph(order['po_number'],styles['Heading3']),
            Paragraph(f"Supplier: {supplier}; vendor code ACCEPT-VENDOR; fictional GSTIN 29ABCDE1234F1Z5.",styles['BodyText']),
            Paragraph('INR; OPEN; authorized amount 1000.00; remaining balance 1000.00.',styles['BodyText']),
            Paragraph(f'Line 1: {description}; quantity 10; contracted unit rate 100.00; authorized line total 1000.00.',styles['BodyText']),
            Paragraph(f"Receipt {order['grn_number']}: accepted quantity 10. QC: {order['qc_status'] or 'ABSENT - deliberately do not seed a QC record'}.",styles['BodyText']),Spacer(1,12)])
    SimpleDocTemplate(str(reference_pdf),pagesize=A4,leftMargin=36,rightMargin=36).build(rows)
    assert len(PdfReader(reference_pdf).pages)==1
    manifest=dict(status='PREPARED_NOT_EXECUTED',workspace=None,external_requests=0,provider_usage=None,provider_cost=None,
        blocker='User confirmed no designated disposable test workspace/project/bucket.',
        forbidden_actions=['approvals','payments','ERP posting','deployment','browser use'],
        fixture_vendor=dict(legal_name=supplier,erp_vendor_code='ACCEPT-VENDOR',gstin='29ABCDE1234F1Z5',gstin_status='ACTIVE'),
        procurement=orders,cases=cases,local_document_checks=document_checks,
        source_pdf=dict(file=reference_pdf.name,sha256=hashlib.sha256(reference_pdf.read_bytes()).hexdigest()))
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=manifest['status'],output=str(output),unique_pdfs=5,planned_cases=5,external_requests=0)))


if __name__=='__main__':
    main()
