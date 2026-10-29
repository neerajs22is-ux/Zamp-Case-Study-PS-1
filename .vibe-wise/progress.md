# Learning Progress

## Topic: Forward Deployed Engineering (FDE) & PS-1 Architecture
### Introduced
- **The FDE Mental Model:** How an FDE bridges the gap between raw engineering and executive buyers (Controllers/CFOs). An FDE frames workflows through **Risk, Latency, Tolerance, and Auditability**.
- **The Pace Paradigm:** Structuring invoice processing as an autonomous **Digital Employee** running an **Agent Operating Procedure (AOP)** with a **Plan-Execute-Validate (PEV)** loop.

### Demonstrated Understanding & Hardening Milestones
- **Deterministic PDF Ingestion:** Labeled totals and tabular line-item parsing preventing subtotal/total collisions.
- **Fail-Soft Exception Handling:** Graceful degradation on unparseable bytes to `FLAGGED_HITL_REVIEW` with `extraction_failed` metadata (zero 500 crashes).
- **AOP Tolerance Discipline:** Implemented "whichever is lower" evaluation between percentage ($\le 1.5\%$) and dollar amount ($\le \$20.00$) limits.
- **Reconciled Duplicate Ledger Policy:** Reconciled spec §3 and `AOPPolicyConfig` so amount-only duplicate detection defaults to same-day (`duplicate_window_days=0`), preserving legitimate recurring monthly SaaS subscriptions while keeping invoice-number and content-hash collisions absolute.
- **Idempotent Scenario Runs:** Seeded ERP resets per scenario run for clean, repeatable live demo presentations.
- **Streaming Reliability:** Pydantic JSON mode serialization for SSE events ensuring zero serialization crashes.
- **Full Test Suite:** 31/31 unit, integration, and regression tests passing in 3.0s.

## Status
Engine, API, UI, Spec, and Tests are fully hardened and reconciled. Ready for demo recording and interview walkthrough.
