"""Offline regressions for defects found while preparing real-provider acceptance.

Stub responses here are unit-test evidence only, never provider acceptance results.
"""
import json
import io
from types import SimpleNamespace
from engine.hybrid_extractor import HybridAPExtractor
from engine.indian_tax_rules import IndianAPRuleEngine
from engine.schemas import MantleInvoiceExtraction
from engine.mantle_client import BedrockMantleClient
from backend.core.config import settings

def truth():
    return dict(document_type='INVOICE',supplier_name='Disposable Services',supplier_gstin='29ABCDE1234F1Z5',
        invoice_number='TEST-100',invoice_date='2026-11-06',po_reference='TEST-PO',currency='INR',
        taxable_value=100,cgst_amount=9,sgst_amount=9,total_tax_amount=18,grand_total=118,
        line_items=[dict(item_description='Disposable service',quantity=1,unit_price=100,taxable_amount=100,total_amount=118)])


def test_hybrid_preserves_actual_source_evidence_after_provider_return():
    from reportlab.pdfgen.canvas import Canvas
    output=io.BytesIO();pdf=Canvas(output)
    for index,line in enumerate(['Disposable Services 29ABCDE1234F1Z5','TEST-100 2026-11-06 TEST-PO',
        'Disposable service quantity 1 unit price 100 taxable 100 total 118','CGST 9 SGST 9 total tax 18 grand total 118']):
        pdf.drawString(30,750-index*25,line)
    pdf.save()
    adapter=HybridAPExtractor(mantle_client=SimpleNamespace(extract_document=lambda *args,**kw:MantleInvoiceExtraction(**truth())),rule_engine=IndianAPRuleEngine(load_reference_data=False))
    result=adapter.extract_hybrid(output.getvalue(),'disposable.pdf','disposable')
    assert result.evidence['grand_total'].is_verified
    assert result.evidence['grand_total'].page_number==1
    assert result.grounding_tripwire_passed


def test_mantle_inference_sends_configured_project_header(monkeypatch):
    captured={}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(status_code=200,json=lambda:{'usage':{'prompt_tokens':10,'completion_tokens':10},'choices':[{'message':{'content':json.dumps(truth())}}]})
    monkeypatch.setattr('httpx.Client',Client)
    monkeypatch.setattr(settings,'MANTLE_PROJECT_ID','proj_disposable',raising=False)
    BedrockMantleClient(api_key='disposable-only').extract_document([(1,'grounding is checked independently')])
    assert captured['headers'].get('OpenAI-Project')=='proj_disposable'


def test_missing_fields_are_named_and_held_after_completed_extraction():
    from reportlab.pdfgen.canvas import Canvas
    output = io.BytesIO(); pdf = Canvas(output)
    pdf.drawString(30, 750, 'Disposable Services incomplete invoice')
    pdf.save()
    adapter = HybridAPExtractor(mantle_client=SimpleNamespace(extract_document=lambda *a, **kw:
        MantleInvoiceExtraction(supplier_name='Disposable Services')),
        rule_engine=IndianAPRuleEngine(load_reference_data=False))
    result = adapter.extract_hybrid(output.getvalue(), 'incomplete.pdf', 'incomplete')
    assert result.final_decision == 'FLAGGED_HITL_REVIEW'
    assert {'invoice_number', 'invoice_date', 'grand_total'} <= set(result.unverified_fields)
    assert all(field in ' '.join(result.decision_reasons) for field in ('invoice_number', 'invoice_date', 'grand_total'))


def test_wrong_context_total_reaches_review_in_real_extractor():
    from reportlab.pdfgen.canvas import Canvas
    output = io.BytesIO(); pdf = Canvas(output)
    for i, line in enumerate(['Disposable Services 29ABCDE1234F1Z5', 'TEST-100 2026-11-06 TEST-PO',
        'Disposable service quantity 1 unit price 100 taxable 100 total 185',
        'CGST 9 SGST 9 total tax 18', 'Grand total 185', 'Prior invoice total 999']):
        pdf.drawString(30, 750 - i * 25, line)
    pdf.save()
    values = truth(); values['grand_total'] = 999
    adapter = HybridAPExtractor(mantle_client=SimpleNamespace(extract_document=lambda *a, **kw: MantleInvoiceExtraction(**values)),
        rule_engine=IndianAPRuleEngine(load_reference_data=False))
    result = adapter.extract_hybrid(output.getvalue(), 'mismatch.pdf', 'mismatch')
    assert not result.grounding_tripwire_passed
    assert 'grand_total' in result.unverified_fields
    assert result.final_decision == 'FLAGGED_HITL_REVIEW'


def test_incomplete_provider_line_is_omitted_and_named_without_guessing():
    from pydantic import ValidationError
    import pytest
    raw = truth()
    raw.update(invoice_number=None, invoice_date=None, grand_total=None,
        line_items=[dict(item_description='Disposable service', quantity=1, unit_price=100, taxable_amount=None, total_amount=None)])
    extraction = MantleInvoiceExtraction(**raw)
    assert extraction.line_items == []
    assert 'line_items.0.taxable_amount' in extraction.missing_fields
    from engine.grounding import verify_extracted_evidence
    passed, missing, _ = verify_extracted_evidence(extraction, [(1, 'Disposable Services incomplete invoice')])
    assert not passed and {'invoice_number', 'invoice_date', 'grand_total', 'line_items.0.taxable_amount'} <= set(missing)
    raw['line_items'][0]['taxable_amount'] = 'not a number'
    with pytest.raises(ValidationError):
        MantleInvoiceExtraction(**raw)


def test_labeled_invoice_candidate_requires_unique_explicit_label():
    from engine.grounding import labeled_invoice_number
    assert labeled_invoice_number([(1, 'Invoice number: INV-123\nSupplier: Acme')]) == 'INV-123'
    assert labeled_invoice_number([(1, 'Prior invoice number: INV-123\nPO: INV-234')]) is None
    assert labeled_invoice_number([(1, 'Invoice number: INV-123\nInvoice number: INV-456')]) is None
    assert labeled_invoice_number([(1, 'Reference: INV-123')]) is None
