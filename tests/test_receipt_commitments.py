"""Disposable regression for cumulative accepted-receipt consumption."""
from sqlalchemy import select
from backend.api.v1.invoices import reevaluate_match_gates
from backend.models.domain import InvoiceLine, MatchGateCheck, WorkOrderSnapshot
from tests.test_production_inspection import db, invoice, reference_data


def test_previous_approved_quantity_reduces_available_receipt(db):
    reference_data(db)
    po=db.get(WorkOrderSnapshot,'po');po.total_authorized_amount=10000;po.remaining_balance=10000
    invoice(db,id='previous',invoice_number='PREVIOUS',stage='INTERNAL_APPROVAL_COMPLETE',total_amount=708,net_payable_amount=708)
    current=invoice(db,id='current',invoice_number='CURRENT',total_amount=708,subtotal_amount=600,tax_amount=108,net_payable_amount=708)
    for key in ('previous','current'):
        db.add(InvoiceLine(id='line-'+key,org_id='a',invoice_id=key,line_number=1,description='Widget',billed_quantity=6,billed_unit_rate=100,billed_line_total=600))
    db.flush()
    run=reevaluate_match_gates(db,current,'a');db.flush()
    checks={x.gate_number:x for x in db.scalars(select(MatchGateCheck).where(MatchGateCheck.match_run_id==run.id)).all()}
    assert checks[3].status=='FAIL'
    assert checks[6].status=='FAIL'
    assert 'receipt quantity' in checks[6].evidence_notes
