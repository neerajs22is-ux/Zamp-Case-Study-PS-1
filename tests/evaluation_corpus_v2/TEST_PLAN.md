# Test plan — Mixed Indian AP corpus v2 (40 PDFs)

## Corpus handling
- `invoices/` contains the only 40 PDFs intended to be emailed to the test Gmail mailbox.
- Do not email or upload ground-truth CSV/JSON, scenario map, supplier master or `reference_data/` as invoice attachments.
- Keep all expected answers and reference fixtures outside the application's document-ingestion path.
- All suppliers, GSTIN-like strings, invoice numbers, PO/GRN references, IRNs and transactions are fictional. GSTIN-like strings and IRN are deliberately invalid placeholders.

## Corrections and coverage in v2
1. PDFs do not print internal scenario names, expected outcomes, document IDs or evaluation labels.
2. Semantic duplicate: APTC-035 repeats supplier V001 + invoice AP-26-001 + date + commercial values from APTC-001, but has a separately rendered PDF and a different SHA-256.
3. E-invoice IRN, acknowledgement number/date and synthetic QR payload are printed in the E-invoice PDF.
4. Reverse-charge statement and recipient-payable tax amount are printed in the relevant freight document.
5. Synthetic reference data includes supplier master, PO, GRN, QC, rate-contract, service-period and milestone records.
6. A dedicated two-page invoice and two scanned-image PDFs are included.
7. Domestic GST split and place-of-supply fields are aligned to a fictional Bengaluru buyer. One exception deliberately has a wrong grand total; another exceeds its linked PO's ordered quantity and taxable value.

## Five-document smoke test
Use APTC-001 (clean GST invoice), APTC-009 (manufacturing invoice), APTC-038 (payment receipt), APTC-030 (PO quantity/value overrun) and APTC-037 (degraded scan).
For semantic duplicate detection, send APTC-001 first and APTC-035 second as a separate paired test.

## Execution
1. Email each selected PDF as a separate message to the connected test mailbox.
2. Run Gmail sync.
3. Verify Gmail message ID and attachment ID, PDF magic bytes, SHA-256, private Storage object, document registration and audit event.
4. Compare extracted fields with ground truth only after processing.
5. Load `reference_data/` only into an isolated test ERP/reference-data area, never as live Zetwerk records.
6. Evaluate PO/GRN/QC/rate/milestone matching against those reference records.
7. Verify semantic duplicate detection using APTC-001 and APTC-035. Their file hashes differ, but supplier + invoice number + date + commercial values match.
8. Repeat sync to verify idempotency.

## Guardrails
- `MATCH_CANDIDATE` is not approval. No synthetic invoice should auto-approve.
- Reference data is synthetic fixture data, not live ERP data.
- GST/RCM/foreign-trade fields are test cases, not legal/tax conclusions.
- This corpus is a functional test set, not an exhaustive benchmark of all Indian GST and manufacturing AP cases.
