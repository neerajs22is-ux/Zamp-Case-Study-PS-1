# Mixed Indian AP test corpus v2 — 40 PDFs

See `TEST_PLAN.md` before use.

- `invoices/`: exactly 40 PDF attachments to send through Gmail.
- `ground_truth.csv` / `.json`: expected extracted fields, document classes and routes; keep hidden from application processing.
- `fictional_supplier_master.csv`: synthetic supplier directory.
- `reference_data/`: synthetic PO, GRN, QC, rate-contract, service-period and milestone fixtures for isolated matching tests only.
- `test_scenarios.json`: evaluation-only scenario map.
- `gmail_test_email_manifest.csv`: suggested email subjects and attachment mapping.
- `pdf_integrity_manifest.csv`: PDF sizes and SHA-256 checksums.

All entities and transactions are fictional. GSTIN-like values and IRN are deliberately invalid placeholders. No document is valid for tax filing, accounting, procurement or payment. Do not enable production auto-approval for this corpus.
