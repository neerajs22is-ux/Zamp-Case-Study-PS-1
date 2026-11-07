# PS-1 verification summary

The historical provider-backed acceptance run used a newly created, isolated test identity provider, private object storage, restricted PostgreSQL role and model project with synthetic data. Those resources were removed after the run. It exercised the authenticated application in an in-process ASGI harness, not a browser. The following are historical observations, not a guarantee of current provider access or a re-test of subsequent changes:

| Synthetic scenario | Recorded result |
| --- | --- |
| Matching invoice | Seven matching checks passed; `PENDING_APPROVAL / MATCH_CANDIDATE` |
| Exact-byte duplicate | HTTP 409; no additional processing job or model call |
| Price variance | Price check failed; `ACTION_REQUIRED / FLAGGED_EXCEPTION` |
| Missing QC | QC check failed; `ACTION_REQUIRED / FLAGGED_EXCEPTION` |
| Payment receipt | Classified as non-payable and rejected |

The four unique PDFs used real model extraction and deterministic source occurrence checks. Original and downloaded document hashes matched. A second test tenant was denied access to the first tenant's invoice, run and document endpoints. The test did not submit an approval, pay an invoice, or post to an ERP. The inputs were simple synthetic documents; their results do not establish general model accuracy or semantics. See `scripts/prepare_ps1_acceptance.py` for the fixture definitions and `scripts/acceptance_storage_identity.py` for the harness; running against providers requires a newly authorized disposable environment.

The comprehensive automated offline verification suite (`pytest tests/`) reports 393 passed and 43 skipped across 436 collected tests. A separate disposable PostgreSQL recovery selection reported 3 passed; prior broader PostgreSQL checks reported 52 passed. Suites overlap. Test code and reproducible commands are in the repository. Local raw execution captures are excluded because some contain host paths or provider-resource metadata; this summary retains no credentials or signed URLs.

Follow-up work after the provider acceptance added token revocation, conservative extraction reservations, recovery checks and correction restrictions. The provider-backed cases have not been repeated after those changes. See [`docs/architecture/FREE_TIER_LIMITATIONS.md`](architecture/FREE_TIER_LIMITATIONS.md) and [`SECURITY_NOTES.md`](../SECURITY_NOTES.md) for current operational constraints and prerequisites.
