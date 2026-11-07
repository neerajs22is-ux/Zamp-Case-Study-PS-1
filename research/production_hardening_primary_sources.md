# AP Command Center: primary-source research

Research date: 6 November 2026 (Asia/Calcutta). Scope: current repository source, public official documentation and version-specific package advisory metadata. No browser UI, server startup, configured infrastructure calls, credential reads or live model calls were used. Security guidance below is a benchmark selection, not certification or a claim that every requirement has been tested.

## Observed versions and reproducibility

Windows workspace; Python 3.12.10, Node 26.7.0, npm 11.19.0. Installed Python package metadata: FastAPI 0.141.1, Starlette 1.7.0, Pydantic 2.13.4, pydantic-settings 2.14.1, SQLAlchemy 2.0.45, Alembic 1.20.1, Uvicorn 0.54.0, httpx 0.28.1, pytest 9.0.3, psycopg2-binary 2.9.11, pypdf 6.11.0, pypdfium2 5.14.0, Pillow 12.3.0, python-jose 3.5.0, python-multipart 0.0.29, cryptography 48.0.0. These are baseline environment versions, not a declaration that they remain installed after hardening.

Frontend lockfile: React/React DOM 19.3.1, react-router-dom 7.18.5, Vite 8.3.5, TypeScript 7.0.2, oxlint 1.90.0. Python requirements initially specify only lower bounds, allowing vulnerable older installed versions to satisfy the file. The frontend has an npm lockfile; Python initially has no equivalent complete lock.

Reproduce environment metadata without importing the app:

```powershell
python --version
node --version
npm --version
python -m pip show fastapi starlette pypdf python-jose python-multipart cryptography pillow
cd frontend
npm audit --json --ignore-scripts
```

The npm audit returned exit 0 and zero known advisories across 133 dependencies. Raw snapshot: `research/production_hardening_npm_baseline.json`. It does not prove absence of vulnerabilities or review application behavior. No dependency update or install was performed by the research task.

The official [PyPI JSON API](https://docs.pypi.org/api/json/) supplies a version-specific `vulnerabilities` field. The initial read-only 13-package snapshot is `research/production_hardening_pypi_advisories.json`; counts include aliases and must not be reported as unique issue counts. `python research/audit_production_dependencies.py` repeats the query for all installed declared requirements plus Starlette, writing `research/production_hardening_pypi_final.json`. Missing packages/network errors are recorded, not converted to passes. This is a focused installed-package metadata check, not a complete transitive `pip-audit` scan. `pip-audit`/`uv` were unavailable in the initial shell. [pip-audit's official project](https://pypi.org/project/pip-audit/) documents environment/requirements scanning and its security limitations.

## Relevant advisories and reachability

| Component at baseline | Primary evidence | App-specific assessment / response |
| --- | --- | --- |
| pypdf 6.11.0 | Maintainer advisories [missing-trailer infinite loop](https://github.com/py-pdf/pypdf/security/advisories/GHSA-5849-834g-hvw5), [page-tree memory use](https://github.com/py-pdf/pypdf/security/advisories/GHSA-cggf-277g-3q54), [encrypted page-count resource use](https://github.com/py-pdf/pypdf/security/advisories/GHSA-62m5-6wh8-28x7). First two fixed in 6.21.4; third in 6.21.3. | Untrusted PDFs enter extraction, making parsing a relevant attack surface. Installed version is affected; no destructive DoS reproduction was attempted. Update to at least 6.21.4, the current PyPI release observed, and bound parsing CPU/memory separately. File byte limits do not bound decompressed complexity. |
| python-jose 3.5.0 | [CVE-2026-85394](https://github.com/advisories/GHSA-3qf3-8w2g-rqmx), critical advisory, no patched version at research time. DER public keys can be mistaken for HMAC secrets when algorithm restrictions are absent. | Current `backend/core/auth.py` uses separate JWK and configured-secret branches and passes a one-element algorithm list; Google token decodes pin RS256. A component advisory is verified; an app auth bypass is not. Test forged HS256 with public-key bytes and preserve algorithm/key-type separation. Do not remove legitimate HS256 legacy configuration solely because of this advisory. |
| python-multipart 0.0.29 | [negative Content-Length](https://github.com/advisories/GHSA-v9pg-7xvm-68hf), fixed 0.0.31; [quadratic semicolon parsing](https://github.com/advisories/GHSA-5rvq-cxj2-64vf), [parser differential](https://github.com/advisories/GHSA-6jv3-5f52-599m), fixed 0.0.30. Current PyPI observed 0.0.33. | Maintainer explicitly excludes FastAPI/Starlette from the direct `parse_form()` problem. URL-encoded paths need reachability review; multipart PDF upload alone does not establish that exploit. Update dependency floor while distinguishing package detection from observed exploit. |
| cryptography 48.0.0 | [bundled OpenSSL advisory](https://github.com/advisories/GHSA-537c-gmf6-5ccf), fixed 48.0.1; [PKCS7 oracle](https://github.com/advisories/GHSA-g6cj-pr64-35w5), fixed 50.0.0. Current PyPI observed 50.0.2. | No `pkcs7` or `x509.verification` call found by focused source search in backend/engine; Fernet/JWT usage is not proof of those specific exploit paths. Update wheel dependencies and retain applicability distinctions. |
| Pillow 12.3.0 | Version-specific [PyPI advisory metadata](https://pypi.org/pypi/pillow/12.3.0/json), raw details in snapshot. Listed fixes are 13.0.0, the current release observed. | Rasterized PDF/vision handling uses Pillow. Upgrade and exercise relevant image/OCR tests. Metadata entries include multiple decoder issues and aliases; no claim that each decoder is reachable here. |

## Selected security/platform guidance

1. [OWASP ASVS 5.0.0](https://github.com/OWASP/ASVS/releases/tag/v5.0.0_release) is the stable May 2025 application-verification benchmark observed. Use its authentication, authorization, session, validation, file-handling and configuration requirements to structure evidence. Target representative Level 2 controls for this financial application; do not call partial coverage ASVS compliance.
2. [OWASP authorization guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html) supports per-request, deny-by-default checks. App test matrix: valid user A requests user B's invoice/document/job/evidence/audit; inactive membership fails closed; auditor cannot mutate; associates cannot approve; controller cannot self-second-approve. Include direct IDs, not only UI navigation.
3. [PostgreSQL 15 row security](https://www.postgresql.org/docs/15/ddl-rowsecurity.html) explains owner/superuser/BYPASSRLS exceptions. Test the actual runtime database role and transaction-scoped tenant context. ORM predicates and SQLite tests alone cannot prove deployed PostgreSQL RLS. [Supabase RLS guidance](https://supabase.com/docs/guides/database/postgres/row-level-security) reinforces protecting service credentials and independent authorization for elevated access.
4. [Supabase JWT guidance](https://supabase.com/docs/guides/auth/jwts) describes signing keys, expiration and issuer. Test signature, key ID, expected issuer/audience and expiry separately; decoded claims alone are not authentication. Workspace membership remains server-authoritative and must be checked after identity verification.
5. [Supabase Storage access control](https://supabase.com/docs/guides/storage/security/access-control) says service credentials bypass storage policies. [Asset serving](https://supabase.com/docs/guides/storage/serving/downloads) distinguishes public objects from private authenticated/signed access. Application scoping must precede URL issuance; short-lived URLs are bearer access and cannot substitute for tenant checks. Verify private bucket configuration separately.
6. [OWASP file-upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) calls for layered type/name/size/access/storage defenses. For this app: allowed PDF extension and signature, bounded bytes/pages/render dimensions, safe generated storage names, parsing failure visibility, authorization before persistence. Malware scanning/CDR and process isolation are separate controls; a `%PDF-` prefix is not a full structural or malware verdict.
7. [OWASP prompt-injection guidance](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) supports separating untrusted evidence, validating output, least privilege and adversarial evaluation. Fence-breaking text, fabricated amounts, false evidence-page references, missing fields, numeric sign/decimal changes and image instructions are useful probes. Fencing reduces risk but is not a security boundary; deterministic gates and explicit review must contain model errors.
8. [AWS Chat Completions](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-chat-completions.html) documents Mantle compatibility endpoints and model-specific paths. Existing Mantle integrations remain supported according to [AWS endpoint guidance](https://docs.aws.amazon.com/bedrock/latest/userguide/endpoints.html); switching providers/endpoints is unnecessary without demonstrated need. [Mantle quotas](https://docs.aws.amazon.com/bedrock/latest/userguide/quotas-mantle.html) distinguish input/output token quotas and 429 responses. Provider quotas are not a per-tenant cost budget. Test bounded retries, visible timeout/429 failures, request size/token caps and locally enforceable cost policy.
9. [Python 3.12 Decimal documentation](https://docs.python.org/3.12/library/decimal.html) provides exact decimal arithmetic suited to accounting equality invariants. Evaluate money with decimal-string inputs and explicit rounding; test threshold pennies, cumulative PO consumption and concurrent decisions rather than only integer happy paths.

## Recommended measured benchmarks before fixes

- Five fixture outcomes: HP-01 clean invoice; EC-01 cumulative PO overrun; EC-02 duplicate; EC-03 price variance; EC-04 missing PO/poor scan. Record extraction fields, rule reason codes, evidence availability and final status, using real deterministic extraction where possible. Model mocks test orchestration, not live model accuracy.
- Financial invariants: at/just above tolerance and dual-approval thresholds, currency mismatch, missing evidence and duplicate approval replay. Measure incorrect approval count; target zero for the defined negative cases.
- Tenant/role matrix: each prohibited action returns 401/403/404 as appropriate, with zero cross-tenant content and zero state mutation. Database-specific tests must state their actual database engine/role.
- Adversarial PDF suite: empty, fake signature, malformed/encrypted, oversized, excessive pages, hostile filename and embedded prompt commands. Target bounded rejection/failure, no approval, no raw document/credential leak. Record parser time and worker isolation limits.
- Reliability: repeated upload, concurrent approval/PO update, job retry after failure, expired job recovery and transient upstream errors. Measure one durable decision/audit effect for one accepted action, no duplicate PO consumption.
- UI contract checks/build/lint can verify code paths without a browser. Pixel layout, focus, document rendering and live-run interaction remain untested under the user's browser/server restriction.

## Code observations requiring independent verification

`engine/grounding.py` initially grounds only invoice number, supplier GSTIN, PO reference and grand total. Its grand-total check includes integer substring candidates, so presence of an unrelated integer can falsely ground cents; empty invoice numbers are treated as verified. It creates page-1 evidence even when another page supplied the match. These are source observations to reproduce with focused tests, not evidence that an invoice was approved incorrectly end to end.

`engine/mantle_client.py` initially checks per-document cost after receiving a billed response, tracks spend only in a client instance and never references the monthly budget setting. Its error strings include raw provider bodies/model JSON fragments. Test whether those details reach persisted/UI errors before assigning data-leak severity. Hard price caps cannot be inferred from telemetry alone.

No source comparison used repository stars or indiscriminate product rankings. Final readiness depends on parent task's actual implementation and repeated tests; this note does not supersede those results.


## Final inspection addendum

The complete declared-installed-package scan also found pydantic-settings 2.14.1 affected by [GHSA-4xgf-cpjx-pc3j](https://github.com/pydantic/pydantic-settings/security/advisories/GHSA-4xgf-cpjx-pc3j). Its prerequisite is opting into nested secret-file loading with attacker-influenced symlinks; that configuration was not found in this app. Version 2.14.2 is pinned and was tested as dependency hygiene, not as a reproduced remote file-read fix. Final results are in `production_hardening_pypi_final.json`. Only the python-jose advisory remains in that direct-installed-package/Starlette snapshot (two alias records for one advisory). The npm final snapshot is `production_hardening_npm_final.json`.

The official [pypdf missing-trailer advisory](https://github.com/py-pdf/pypdf/security/advisories/GHSA-5849-834g-hvw5) was checked directly: affected versions are below 6.21.4 and the patched version is 6.21.4. Child-process limits supplement this upgrade; they do not certify all PDF content safe.
