# Production inspection — 6 November 2026

**Full provider acceptance:** [Five prepared PS-1 cases passed](PS1_LIVE_ACCEPTANCE_RESULTS.md) using a new isolated Supabase/Mantle environment and dedicated IAM credential. Records include real extraction/grounding/matching/events, usage, fixes and verified cloud cleanup. This is bounded synthetic acceptance evidence, not production readiness; the report discloses retention and local-cleanup limitations.

**Disposable provider setup:** [Real provider environment acceptance subset](PROVIDER_ENVIRONMENT_ACCEPTANCE.md) records a newly created/deleted isolated Supabase project, real identity/storage/PostgreSQL/intake/tenant checks, and measured latency. No inference was run: AWS sessions blocked provisioning isolated extraction credentials. Full PS-1 acceptance remains incomplete.

**Provider acceptance attempt:** [Prepared PS-1 inputs and blocked live acceptance](PROVIDER_ACCEPTANCE.md). The user confirmed no designated disposable target. No providers were called; only synthetic local preparation/read-only checks ran. This does not establish live-demo readiness.

**Lease/recovery follow-up:** [Authenticated live-run reliability](LIVE_RUN_RELIABILITY.md) adds bounded provider keepalive, expired-lease denial, observed recovery and Gmail intake checkpoints, with disposable slow-call/process-loss/PostgreSQL checks. Provider/browser and production-readiness limitations remain.

**Live-run follow-up:** [PS-1 persisted processing view](PS1_LIVE_RUN_VIEW.md) adds authenticated, ordered audit checkpoints and a polling invoice-detail view, with disposable retry/failure/RLS tests. It supersedes the absence-of-stage-view statement below; historical baseline evidence is retained. Live-provider/browser demonstration remains unverified.

**Follow-up:** [Disposable offline/PostgreSQL verification](OFFLINE_POSTGRES_VERIFICATION.md) supersedes the earlier red broad-suite result and PostgreSQL-testing blocker below. Final follow-up: 320 broad passes (26 explicit offline skips), 95 focused passes, and 36 passes in the disposable PostgreSQL selection. Migration 012 and an invitation identity-conflict safeguard were added. Remaining readiness limits and the harness/cleanup exceptions are documented in the follow-up. The original baseline and historical evidence below are retained.

## Scope and baseline protocol (defined before application changes)

Preserve existing dirty identity/membership and frontend work. No browser, application server, deployment, production data access or external service testing. No separate attached case-study guide was available in this chat/workspace inventory; `specs/PS1_INVOICE_PROCESSING_SPEC.md` is the available PS-1 reference, not proof of delivered functionality.

Baseline and final use `python scripts/inspect_offline.py tests -q`, frontend `npm run build`, `npm run lint`, and read-only dependency advisory checks. The runner disables dotenv and inherited integration credentials, uses in-memory SQLite and blocks socket connections. Tests using stubbed providers verify contracts, not live extraction quality, storage policies or PostgreSQL RLS. Tests requiring a server/browser or explicit live database are excluded. Record the exact exclusions with each run.

Targets: all applicable offline regressions pass; build and lint exit zero; no cross-tenant reads or unauthorized role mutations in exercised ASGI routes; no approval on failed grounding/nonfinite financial input; damaged document preview denied; rejected uploads cause no storage writes; failed processing remains visibly failed. Added adversarial regressions run unchanged before and after fixes. Financial cases: clean candidate, cumulative PO overrun, duplicate, price variance and missing/low-quality evidence. No invented latency/accuracy target for a live model that is not being called. Track test counts, duration and failures; these are regression metrics, not throughput benchmarks.

## Outcome

Security and financial controls improved, but **release and fully live PS-1 demonstration are not signed off**. The final broad offline run has 291 passing tests, 19 failures, 10 fixture errors and 14 skips. The failures are disclosed below, not excluded from that result. No application server or browser was started, no configured service was called, no migration was applied, and no existing financial/user data was changed.

The original 22 adversarial checks improved from 16 failures / 6 passes to all passing. The expanded focused suite also passes. These are deliberately small regression workloads, not claims about model accuracy, compliance or production throughput.

## Observed workflow and capability boundaries

| Step | Current implementation and evidence | Limits / dead or incomplete paths |
|---|---|---|
| Identity | `backend/core/auth.py`: HS256 configured secret or RS256/ES256 JWKS, expected issuer/audience, required expiry; server-side membership and role lookup | Access token stored in browser localStorage. No complete refresh/revocation flow. Developer sessions are local/test only. Generic OIDC settings are not a complete alternate IdP implementation. |
| Workspace | Identity bindings, legacy subject matching, active user and assigned role; `X-Tenant-ID` checked against memberships; role lookup failure returns 503 | Existing unfinished migration 010 is preserved. Multi-membership selection is reported by backend but the frontend has no finished selector. Invitation/access-request paths are not completed multi-workspace onboarding; verified-email binding needs review. No email-only membership fallback was restored. |
| Intake | `/connections/upload` delegates to `/documents/upload`; PDF bytes, filename/type/size, bounded structural extraction, tenant hash check, storage, invoice/job/audit transaction | Images are not supported by this route. Gmail has OAuth, encrypted refresh tokens, sync/history/PubSub recovery and separate ingestion code. It does not automatically prove live mailbox authorization from presence of configuration. Gmail-specific intake limits/parser parity remain incomplete. |
| Extraction | `HybridAPExtractor` reads PDF pages in a child process; text-bearing PDFs call Mantle; typed output and source occurrence checked; failures remain errors | No live model was called. Textless scans route to human review. OCR and optional Palmyra adapters exist, but are not a verified integrated production route. The regex extractor and CSV rule-engine defaults are evaluation utilities. |
| Matching | Persisted lines use **before-tax** amounts. The v1 pipeline now uses tenant database vendor, PO, GRN and QC snapshots through `reevaluate_match_gates`; local duplicate checks and PO commitments are included | No implemented live SAP synchronization was found. Credentials do not make snapshots verified/live. Rate contracts/milestones in the CSV evaluator are not equivalent to supported v1 database policies. General GST jurisdiction, complex tax cases, currency conversion and cumulative receipt-quantity consumption remain incomplete. |
| Decision | Complete passed checks required; extraction/document blocker retained separately; non-payable documents rejected; INR policy; source/PO commitments rechecked under PO lock; lead/controller/admin authority and distinct second approver | A candidate is not automatic approval. Human approval is internal review, not an ERP posting/payment. Extraction blockers survive line corrections; correcting all extraction fields is not implemented, so re-ingestion/manual investigation may be needed. |
| Evidence | Tenant authorization precedes metadata/URL/download/preview; signed URL TTL is capped at 300s; download and API preview verify SHA-256; PDF filenames are encoded in headers | Signed URLs are bearer access until expiry. Direct signed storage rendering does not itself rehash content. Browser PDF rendering, private bucket policy and S3 configuration were not tested live. A source occurrence/page is evidence, not semantic proof of correctness. |
| History | Extraction runs/fields, lines, match runs/checks, exceptions, audit actors and decisions stored transactionally; repeated approval returns existing result | PostgreSQL append-only triggers and restricted runtime role were not exercised. Source page is saved only when found; invented 95–99% confidence values were removed. No new confidence calibration is claimed. |
| UI | Inbox queue polling; detail polls actual queued/processing status every three seconds; explicit queue resume; evidence/check/history views and real action errors | No stage-by-stage SSE stream in the authenticated app. Queue polling is not a five-stage live execution inspector. No visual/accessibility/browser verification in this run. |

`engine.server` / `run.py --legacy` is a **separate, unauthenticated, in-memory mock ERP demonstration**. Its routes remain used by evaluation tests, so they were not deleted. They are not mounted by the v1 application and must not be deployed as the protected AP product. Its mock vouchers and email drafts do not represent external operations.

## Reproducible baseline and final results

Windows PowerShell; Python 3.12.10; Node v26.7.0; npm 11.19.0. Python baseline used installed packages; final used `.venv-inspection` with system-site packages and explicit patched packages. This is credential/network isolation, **not a clean dependency-install certification**. The initial package upgrade was moved into that venv and the four changed host packages were restored to their original versions. The host's unrelated Streamlit/Pillow conflict is not an application requirement.

Observed Python application/test versions include FastAPI 0.141.1, Starlette 1.7.0, Pydantic 2.13.4, SQLAlchemy 2.0.45, pytest 9.0.3, psycopg 3.3.5 and pandas 3.0.5. Frontend uses React 19.3.1, Vite 8.3.5, TypeScript 7.0.2 and oxlint 1.89.0 according to its manifest/lock and build tools. Full advisory/version snapshots are linked in the research report.

| Check | Baseline | Final / interpretation |
|---|---|---|
| Broad offline suite, same selection | 239 passed, 25 failed, 10 errors, 14 skipped; 12.77s | 291 passed, 19 failed, 10 errors, 14 skipped; 19.49s. Added tests and corrected fixtures change the denominator. This is **not** a green full-suite result. |
| Original adversarial set | 6 passed, 16 failed; 1.71s | All original checks pass. Expanded set covers signed identity, malformed/active/encrypted/over-page-limit PDFs, quota, stale PO commitments, approval history, public buckets, DER/HMAC separation and JWKS failure/expiry. |
| Focused workflow/security suite | Not separately measured before changes | 95 passed in 7.92s; exact results in `inspection-evidence/focused_checks.txt`. Includes genuine PDF intake, mock storage, signed test JWTs and disposable SQLite. |
| Frontend build | Exit 0; 691.44 kB JS / 176.75 kB gzip | Exit 0; exact final size in `inspection-evidence/final_build.txt`. Large-chunk warning remains. |
| Frontend lint | Exit 0, 28 warnings | Exit 0, 28 warnings. Existing hook/memoization/fast-refresh warnings remain. |
| UI mechanical detector | Not measured | `[]` for changed inbox/detail targets. This is not rendered UI verification. |
| npm audit | 0 known advisories; 133 dependencies reported | Lockfile unchanged; repeat snapshot saved separately. Zero known advisories is not a security guarantee. |
| Python advisories | Material installed advisories, including pypdf 6.11.0 | Patched pypdf 6.21.4, multipart 0.0.33, cryptography 50.0.2, Pillow 13.0.0, pydantic-settings 2.14.2. python-jose 3.5.0 retains one advisory represented by two alias entries. |
| Migration graph / compile | Not separately measured | Python compilation succeeds; one Alembic head `011_require_assigned_roles`. PostgreSQL SQL execution remains untested. |
| Secret hygiene | `.env` excluded; no workspace credential values printed | Narrow tracked-file pattern scan found no AWS access-key/private-key/Supabase-secret candidates. No gitleaks/history/entropy scan; do not interpret this as proof of no secrets. |

Commands (from repo root unless noted):

```powershell
python scripts/inspect_offline.py tests -q --ignore=tests/phase_b/test_stage9_live_supabase_verification.py
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests -q --ignore=tests/phase_b/test_stage9_live_supabase_verification.py --tb=short
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests/test_production_inspection.py tests/phase_b/test_stage3_storage_ingestion.py tests/phase_d/test_phase_d2_tenant_security.py tests/phase_d/test_phase_d3_e2e_workflow.py tests/phase_d/test_phase_d4_reliability_recovery.py tests/phase_e/test_security_and_financial_controls.py tests/phase_a/test_auth_and_rbac.py tests/test_indian_ap_and_mantle.py -q --tb=short
.\.venv-inspection\Scripts\python.exe scripts/benchmark_ps1_offline.py
.\.venv-inspection\Scripts\python.exe research/audit_production_dependencies.py
# frontend directory:
npm run build
npm run lint
npm audit --json --ignore-scripts
```

The runner disables dotenv and inherited integration settings before imports, uses an in-memory database, and rejects non-loopback socket connections. Windows asyncio requires internal loopback socketpairs; no listening application server is started. The explicit live Supabase test module is excluded; PostgreSQL opt-in tests skip without `TEST_POSTGRES_URL`. Docker CLI is installed, but `docker info` fails because the local engine pipe is unavailable. No external database was substituted.

### Full-suite failures retained

The remaining 19 failures and 10 errors are listed verbatim in `inspection-evidence/final_tests.txt`. Eighteen failures and all ten setup errors depend on an existing seeded `org_sme_eval`/global application database, including hard-coded historical invoice IDs. That database is deliberately absent from the disposable runner. One source-string UI test expects wording removed by the pre-existing unfinished redesign. These failures existed in the baseline; they were not converted to passes/skips or hidden. Those older suites need explicit disposable fixtures and updated behavioral assertions before a green repository-wide release gate exists.

Tests materially affected by stricter controls now use real PDF fixture bytes, actual supported role names, actual tenant procurement evidence, and request rollback behavior. Tests no longer pretend that a `%PDF-` string with no pages is valid, or that a candidate with no checks is approvable. Positive financial tests seed source records explicitly in test code and call real matching; the application does not synthesize those records.

## Findings and changes

Severity describes potential impact, not a claim of observed production exploitation.

| ID | Severity | Verified evidence | Resolution / remaining proof |
|---|---|---|---|
| F01 | High | Pipeline replaced rejection/review with candidate when coarse gates passed; both orchestration probes failed at baseline | Preserve payable-document/extraction restriction as an additional check; reject non-payable inputs, retain reasons, preserve blocker on correction. Regression passes. |
| F02 | High | No match run and `NOT_EVALUATED` checks accepted by approval route; terminal rejection could be approved | Require seven passed base checks and all additional checks, passed match run, valid currency and current procurement evidence; terminal states blocked. Regression passes. |
| F03 | High | Initial v1 processing used bundled CSV references; vendor check only tested whether GSTIN existed; received quantity and PO balance omitted | Use tenant source records, registered supplier/PO vendor/currency/status, accepted receipt quantity, cumulative local amount commitments, and fresh approval checks. PostgreSQL locks added, but real concurrency remains unverified. |
| F04 | High | 123.99 could be grounded by 123.00 or a substring of an unrelated number; model-supplied verification flags and guessed page 1 survived | Full signed numeric tokens compared with Decimal; identity/date/nonzero amounts/line fields checked; source pages located; flags recomputed. Missing evidence blocks. Occurrence is still weaker than semantic/layout verification. |
| F05 | High | Infinity accepted in financial extraction; tax-type error did not affect `is_valid`; tax-inclusive line totals could be taxed twice at persistence | Reject nonfinite financial values, include tax-type validity, persist before-tax line amounts, verify line arithmetic with decimal values. General tax-law coverage is not claimed. |
| F06 | High | Installed pypdf affected by maintained parser DoS advisories; input accepted on magic prefix only | Patched parser; child timeout 10s, <=100 pages, <=200k text characters, <=50MB, reject encryption and common active/embedded document features. Not malware certification or a process memory limit. |
| F07 | High | Public Supabase bucket returned `readiness=True` and could be used by save/sign operations | Public bucket is not ready; operations fail closed through existing health gate. Mocked provider regression passes; deployed bucket policy unverified. |
| F08 | Medium | Preview omitted integrity comparison; no-DB upload could write storage and report queued; dispatch failure after commit could delete accepted object | Preview/download integrity; no-DB 503 before write; dispatch moved after persistence cleanup scope. Display names use encoded headers; object names exclude URL metacharacters. |
| F09 | High | Source verified: missing legacy RoleAssignment defaulted to write-capable AP Associate; known JWKS key bypassed TTL; empty/failed JWKS fetch not debounced | Explicit role required; migration 011 replaces lookup only, no data rewrite. JWKS refresh obeys TTL, serializes/debounces failed attempts, rejects stale keys. SQLite/mock regressions pass; migration not applied. |
| F10 | Medium | Queue/cost controls incomplete; budget checked only after model billing | Tenant pending-upload cap 10 (configurable), preflight byte/output-token cost ceiling, bounded worker retries and tenant context, queue resume endpoint. Global request-rate/distributed monthly spending limits remain a deployment/application gap. |
| F11 | Medium | Synthetic confidence/page values persisted; UI advertised unsupported image intake; settings alone claimed verified live integrations | Confidence unknown unless measured; only located page saved. PDF-only copy/input, actual polling and queue resume, config-unverified integration status and unverified snapshot provenance. Live stage stream remains missing. |
| F12 | Medium | Provider error bodies could enter extraction/upload responses; authenticated API responses had no explicit cache prohibition | Generic errors on touched model/upload/document paths and API `no-store`. Comprehensive logging/error redaction across Gmail/backup/provider paths remains incomplete. |

## Case-study readiness and demonstration limits

Two different evaluation contexts must be explained to an interviewer:

1. **Authenticated v1 workflow:** disposable tests exercise valid PDF intake, real signed test identity, tenant/role checks, source-backed matching, human approval, replay protection and history. Providers are mocked; this is not a live hosted acceptance test. For an actual recording, use a reviewed workspace with trusted vendor/PO/receipt/QC snapshots and real private storage/model access. Follow the PDF from inbox to source evidence, check reasons, action, audit history and dashboard. Show queued/processing/failed state honestly. Current live-run visibility is polling and recorded results, not a five-stage stream.
2. **Original five PS-1 fixture PDFs:** `scripts/benchmark_ps1_offline.py` reads each real PDF through the legacy deterministic parser and fresh mock ERP. All five expected decisions pass; recorded in `inspection-evidence/ps1_pdf_benchmark.json`. Observed single-run parser times were 2.19–4.14 ms and exclude auth, network, storage, model and database. They are not application latency benchmarks.

| Scenario | Observed evaluation result | Interview explanation |
|---|---|---|
| Happy path | Original PDF: mock `AUTO_APPROVED`; v1 test: candidate then authorized human sign-off | No real ERP voucher or payment. Do not describe mock voucher IDs as production integration. |
| Split PO overrun | Legacy actual fixture has 8,000 previously billed, 2,000 remaining, 6,500 invoice: **4,500 deficit**. v1 stale-commitment/balance regressions block approval | The blueprint's 1,925 deficit describes different starting data. Use displayed evidence, not the old script. |
| Duplicate | Legacy fixture rejected against mock history; v1 byte duplicate gets 409, tenant semantic duplicate check fails | Duplicate handling differs by intake/matching stage. Historical records are retained. |
| Price spike | 135 vs 100 = +35%; flagged; v1 source-record price regression also fails | Show line amount/rate and contract evidence; no email is automatically sent. |
| Low-quality/missing PO | Legacy PDF fixture flags review; v1 missing/ungrounded evidence blocks through extraction/source checks | Legacy fixture contains an OCR-confidence marker; it is not a measured real OCR benchmark. Actual OCR quality and live scanned-document processing remain unverified. |

The guide's automated email sending, ERP posting, universally accurate extraction and finished live inspector must not be claimed. The original guide itself was not attached/available; this inspection used the repository PS-1 specification and checked relevant rehearsal/capability documentation against source.

## Unresolved risks and untested areas

- **High / release blocker:** PostgreSQL migrations 010/011, RLS under `ap_app_user`, SECURITY DEFINER ownership/ACL, transaction-pool tenant reset, simultaneous approvals/uploads and receipt/PO contention have not run on a disposable PostgreSQL instance. SQLite cannot prove these properties.
- **High / release blocker:** live authentication/storage/model/Gmail and full browser workflow are unverified; deployment configuration/secrets deliberately not used. No active security test targeted an external service.
- **High functional limitation:** multi-workspace onboarding/selection remains unfinished. General GST validation, non-INR approval/display/INR exposure aggregation, credit-note semantics, cumulative per-line received-quantity consumption, upstream ERP freshness and broad extraction correction/revalidation require further work. Foreign-currency amounts must not be presented as INR-equivalent exposure; restrict the current demonstration to INR records. No compliance certification.
- **Medium:** python-jose CVE-2026-85394 remains without a patched release in the checked feed. Current key/algorithm separation rejects the demonstrated DER/HMAC prerequisite; this is not dismissal of the component advisory. A maintained replacement or vendor fix should be evaluated before release.
- **Medium:** localStorage tokens and absent end-to-end refresh/logout revocation; global traffic/cost quota and durable worker scheduling/automatic retry service; Gmail ingestion parity; broad exception-body/log redaction; PDF sandbox memory/CPU/container limits, malware scanning and safe browser rendering.
- **Medium:** broad test suite still red and visual interaction untested. Existing frontend lint warnings and large bundle remain. No penetration-test, sustained-load, recovery RPO/RTO or accessibility conformance claim.
- **Untested:** S3/IAM/KMS, deployed signed URL expiry/revocation, backup/restore against actual restricted PostgreSQL, service-account scheduler/PubSub validation against real providers, new dependency installation in a clean production image and full transitive Python advisory coverage.

## Changed files and deployment prerequisites

Changes from this inspection (other dirty files were already present):

- Application: `backend/api/v1/{documents,invoices,connections,health,source_records,system}.py`, `backend/core/{auth,config,database,pipeline,storage}.py`, `backend/main.py`; `engine/{grounding,schemas,hybrid_extractor,indian_tax_rules,mantle_client,pdf_safety}.py`.
- UI: `frontend/src/pages/{InboxPage,InvoiceDetailPage}.tsx`, `frontend/src/api/client.ts`, `frontend/src/types/index.ts`. Existing design/workspace work preserved.
- Migration/config: new `backend/migrations/versions/011_require_assigned_roles.py`, `requirements.txt`, `.env.example`, `.gitignore`. Existing migration 010 was not rewritten. Standard psycopg2 URLs no longer receive psycopg3-only `prepare_threshold`; psycopg3/pandas imports are declared.
- Tests: new root `tests/conftest.py` and `tests/test_production_inspection.py`; updated actual PDF/role/approval fixtures in stage3 ingestion, phase-D tenant/workflow/recovery, phase-E controls, phase-A auth/conftest and Indian extraction tests.
- Evidence/tooling: this report, `docs/inspection-evidence/`, primary-source/advisory research files, `scripts/inspect_offline.py`, `scripts/benchmark_ps1_offline.py`; README readiness claims corrected.

Before release: test migration 010 identity reconciliation and migration 011 with the reviewed privileged migration owner on a disposable database, then verify restricted-role behavior and existing access. Users with no assigned role now fail closed; inventory and legitimately assign roles rather than relying on an implicit default. Preserve existing identity/user/audit IDs. Review the existing `PLATFORM_OPERATOR_SUBJECTS` rollout instructions. Install patched requirements in a clean image; run full dependency/secret checks and regression fixtures there. Configure private storage, trusted issuer and appropriate service credentials outside frontend variables. Apply request/body/CPU/memory/worker limits and a durable quota/scheduling policy. `MAX_PENDING_UPLOADS_PER_TENANT` defaults to 10. Monthly Mantle budget remains planning metadata, not an enforced monthly cap. Verify real source records and the browser/live demo before making a readiness assertion.

No deployment, infrastructure change, production account modification or destructive operation is part of this handoff.

## Sources and skills

Primary sources, exact advisory IDs, observed package versions and applicability distinctions are in [the research report](../research/production_hardening_primary_sources.md), [baseline Python advisory snapshot](../research/production_hardening_pypi_advisories.json), [final installed-package snapshot](../research/production_hardening_pypi_final.json) and npm audit evidence. References include [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/), [file upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html), [prompt-injection guidance](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html), [PostgreSQL RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html), [Supabase JWT](https://supabase.com/docs/guides/auth/jwts), [private storage](https://supabase.com/docs/guides/storage/security/access-control), [AWS Mantle quotas](https://docs.aws.amazon.com/bedrock/latest/userguide/quotas-mantle.html) and maintained package advisory feeds. Latest version/known-advisory checks are dated to this inspection, not permanent guarantees.

Skills read/applied: using-superpowers (skill workflow), research (primary-source investigation, delegated as its instructions require), Karpathy guidelines (focused verified changes), Graphify (existing-graph vocabulary/navigation only; current source/tests determined findings), Impeccable harden/craft-floor (small truthful UI changes; mechanical detector only, no visual sign-off).
