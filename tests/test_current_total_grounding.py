import pytest
from engine.grounding import verify_extracted_evidence
from engine.schemas import MantleInvoiceExtraction


@pytest.mark.parametrize('text,total,verified', [
    ('Grand total 185.00\nPrior invoice total 999.00', 999, False),
    ('Grand total 185.00\nPrior invoice total 999.00', 185, True),
    ('Prior invoice\nTotal 999.00', 999, False),
    ('Previous invoice: Total 999.00', 999, False),
    ('Invoice total INR 185.00\nGrand total 999.00', 185, False),
    ('Amounts: 185.00 999.00', 185, False),
    ('Widget quantity 1 line total 999.00', 999, False),
    ('Grand total\nINR 185.00', 185, True),
    ('Grand total INR 26,196.00', 26196, True),
    ('Grand total 185.00', 18, False),
])
def test_current_total_requires_unambiguous_label(text, total, verified):
    extraction = MantleInvoiceExtraction(supplier_name='Acme', grand_total=total)
    _, unverified, evidence = verify_extracted_evidence(extraction, [(3, text)])
    assert evidence['grand_total'].is_verified is verified
    assert ('grand_total' not in unverified) is verified
    if verified:
        assert evidence['grand_total'].page_number == 3
