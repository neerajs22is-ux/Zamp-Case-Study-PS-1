"""Five real fixture PDFs through the legacy deterministic engine, no server.

Mock ERP and in-memory vouchers are evaluation artifacts, never payment/ERP
operations. This is explicitly separate from the authenticated v1 application.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.pipeline import InvoiceProcessingPipeline
from engine.mock_erp import MockERPDatabase

expected = {
    'HP-01-Happy-Path': 'AUTO_APPROVED',
    'EC-01-Split-PO-Overrun': 'FLAGGED_HITL_REVIEW',
    'EC-02-Duplicate-Submission': 'REJECTED',
    'EC-03-Price-Spike-Variance': 'FLAGGED_HITL_REVIEW',
    'EC-04-Low-Res-Missing-PO': 'FLAGGED_HITL_REVIEW',
}
rows = []
for name, outcome in expected.items():
    path = ROOT / 'fixtures/data' / f'{name}.pdf'
    result = InvoiceProcessingPipeline(erp=MockERPDatabase()).process(path.read_bytes(), filename=path.name)
    rows.append(dict(scenario=name, source=str(path.relative_to(ROOT)),
        expected=outcome, decision=result.decision.value, passed=result.decision.value == outcome,
        reasons=result.reasons, elapsed_ms=result.total_latency_ms,
        discrepancies=result.discrepancy_details))
output = ROOT / 'docs/inspection-evidence/ps1_pdf_benchmark.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(dict(mode='legacy deterministic parser + mock ERP, not v1/live model', results=rows), indent=2), encoding='utf-8')
for row in rows:
    print(row['scenario'], row['decision'], row['passed'], row['elapsed_ms'])
raise SystemExit(0 if all(row['passed'] for row in rows) else 1)
