# PS-1 provider-backed acceptance results

**Five prepared cases matched their expected results using the real authenticated pipeline.** Four unique documents made four successful live extraction calls; the duplicate was rejected before processing. This is bounded acceptance evidence, not production-readiness or unrestricted demo sign-off.

Execution: **6 November 2026, 23:55:40–23:56:48 IST** (18:25:40–18:26:48 UTC). Cleanup and handoff continued on **7 November IST**. Resource/evidence names retain the prepared `20261106` label. This supersedes the expired-AWS-session/full-extraction blocker in [the earlier subset report](PROVIDER_ENVIRONMENT_ACCEPTANCE.md); historical evidence is preserved.

## Actual environment and isolation

| Component | Actually exercised |
|---|---|
| Provisioning identity | Renewed AWS CLI identity verified with STS. It was an account-root session; used only for new-resource provisioning, policy checks, cleanup and owned metadata verification, **not application inference**. Credentials were never printed or saved in public evidence |
| AWS test identity | New tagged IAM user `ps1-acceptance-20261106-040e6a53`; no console login/access key or broad managed policy; one service-specific bearer credential expiring after one day, with effective bearer/inference permission expiry after two hours |
| Extraction boundary | New Mumbai Mantle project `proj_otq67vwlewxzfizztrje`; final application policy permits only `CreateInference` for that exact project and configured Qwen model, plus model metadata reads in Mumbai. No project management, unrelated service or production-workload inference authority |
| Model | Requested and provider-reported **`qwen.qwen3-235b-a22b-2507-v1:0`** on `bedrock-mantle.ap-south-1.api.aws`; four responses HTTP **200**. Catalog listed a shorter identifier, but the configured alias was accepted, so it was **not changed** |
| Supabase | New isolated project `swefzrbgkbrhydtjrxbh`, name `ps1-acceptance-20261106-040e6a53`, Mumbai, account's Free plan; existing project excluded by ID and ownership checks |
| Database | Dedicated `ps1_acceptance_040e6a53`, real PostgreSQL **17.11**, actual migrations through **012_invitation_utc_expiry**; administrator only for new schema/source setup, application directly authenticated as non-superuser/non-BYPASSRLS `ap_app_user` |
| Storage | New private PDF-only bucket `ps1-040e6a53`, 1 MiB limit; real `SupabaseStorageAdapter`, new project's credential only |
| Identity/tenants | Two synthetic provider users, real password sign-in and ES256 JWT/JWKS verification; separate synthetic memberships, least-privilege **AP_ASSOCIATE** roles |
| Application | Actual FastAPI routes in an in-process ASGI harness, **staging mode**, local auth/dev sessions disabled, dotenv/inherited production integration credentials excluded. No browser, app server or deployment |

Provisioning temporarily granted the new IAM user only the management operations needed to create/tag/reconcile its new project. These were replaced by the restricted runtime policy **before any inference**. IAM simulation allowed the exact project/model/region and denied default-project, other-model and other-region inference. An actual default-project model-catalog request with the test credential returned **403**. No inference probe was sent to a production/default project. See `extraction-policy.json`, `iam-simulation.json` and `live-default-project-denial.json` in the evidence directory.

The application's new optional `MANTLE_PROJECT_ID` sends `OpenAI-Project` on real model requests. An isolated key alone is insufficient if requests silently use the account default project. The existing shared `.env` inference key was not used for this run.

## Expected versus observed

The source pack and expected outcomes were prepared before provider execution. Model answers were not supplied from the manifest. Only synthetic vendor/PO/receipt/QC data was seeded; the manifest's deliberate QC absence was preserved. No approval, payment or ERP-posting action was submitted.

| Prepared case | Expected | Actual persisted result | Verification |
|---|---|---|---|
| Happy PDF, taxable INR 100, GST 18, gross 118 | Gates 1–7 PASS, candidate awaiting approval | **`PENDING_APPROVAL / MATCH_CANDIDATE`**; all seven gates PASS | **PASS** |
| Exact same happy PDF uploaded again | 409 duplicate, original reference, no new job/model request | **409 `DUPLICATE_DETECTED`**, original invoice ID, unchanged job count; no extra inference | **PASS** |
| Price INR 120 against contracted INR 100; gross 141.60 | Price variance blocks acceptance | Gate **6 FAIL** (+20% rate variance); **`ACTION_REQUIRED / FLAGGED_EXCEPTION`** | **PASS** |
| Valid separate invoice/PO/receipt, QC record deliberately absent | Missing QC blocks acceptance | Gate **4 FAIL**; **`ACTION_REQUIRED / FLAGGED_EXCEPTION`** | **PASS** |
| Payment receipt acknowledging payment already made | Non-payable classification and rejection | Provider classified **`PAYMENT_RECEIPT`**; extraction gate 8 FAIL; **`REJECTED / REJECTED`** | **PASS** |

For all four provider-backed documents, invoice number, date, supplier GSTIN, PO reference, currency, taxable/tax/gross amounts and line quantities/prices/totals matched predefined synthetic source facts. All **16 evaluated evidence fields per document** passed deterministic source occurrence on page 1, with no unverified fields; tax arithmetic passed. This validates these simple documents, not general extraction accuracy or semantic correctness on arbitrary layouts.

Persisted field verification found **44 extracted fields** with unknown confidence retained as `None`; **40 have verified source pages**. Four optional **zero-valued IGST** fields have no saved page because grounding deliberately skips optional zero values. No page/confidence was invented. An initially over-strict post-check requiring a page on every field failed; code/data review established this existing zero-field rule. The corrected check requires pages for required/nonzero fields and explicitly preserves this disclosure (`post-check-correction.json`). Application/security behavior was not weakened to satisfy it.

## Storage, authorization, financial and event checks

- Each original PDF hash matched the uploaded document hash, authenticated download, inline preview and actual signed-download bytes. The provider bucket was private; unsigned public-object requests returned **400**, without the documents. Capability URLs/tokens were not saved as evidence.
- Tenant B's genuine provider JWT received **404** for tenant A's known new invoice detail, run snapshot, document metadata, download, preview and signed-URL minting. Anonymous run inspection returned **401** and a forged workspace-selection header returned **403**. Non-bypass tenant B SQL returned no tenant A invoice/document rows. Both legitimate identity/membership checks passed: **11 grouped auth/isolation checks** in total. Signed URLs are bearer capabilities until expiry; no session-bound guarantee for leaked URLs is claimed.
- Authenticated upload used `/api/v1/connections/upload`. Actual processing used the role-protected `/api/v1/documents/process-next`, which claimed the tenant job and ran the real background pipeline. Polling the real run API during execution observed queued/processing/extraction/matching/outcome checkpoints, with final full snapshots read after completion. Polling can miss short stages; persisted events establish the ordered history.
- Each completed job has **nine ordered checkpoints**: intake queued → claim started → document read started/succeeded → extraction started/succeeded → matching started/succeeded → outcome recorded. Sequence numbers are contiguous; intake is attempt 0 and processing is attempt 1. Each last outcome matches the committed invoice decision/stage. All jobs completed with retry count **0**; no fabricated progress or fallback extraction was used.
- Final database counts: **4 invoices, 4 documents, 4 jobs, 4 extraction runs, 4 match runs, 29 gate checks, 40 audit events, 0 approval requests**. The 40 audits comprise 36 run checkpoints and four existing `DOCUMENT_PROCESSED` audits. Historical rows were not rewritten. A candidate is **not approval, ERP posting or payment**.

The harness instrumented real HTTP responses and decorated the existing extractor only to record its unchanged return value. It did not replace storage, identity, inference responses, matching or financial decisions. Unit-test stubs mentioned below are separate regression evidence.

## Measured latency and usage

One sample per case; local monotonic timers. Provider time is the measured HTTP response round trip, not server-only compute. Processing wall time includes claim, provider work, database matching/persistence and harness polling overhead.

| Case | Upload/duplicate response | Provider HTTP | Processing wall | Provider prompt/output/total tokens |
|---|---:|---:|---:|---:|
| Happy | 1,739.41 ms | 2,337.37 ms | 7,511.21 ms | 535 / 288 / 823 |
| Duplicate | 632.43 ms | No call | No new job | No additional usage |
| Price variance | 1,628.18 ms | 2,736.30 ms | 7,506.43 ms | 536 / 291 / 827 |
| Missing QC | 1,588.03 ms | 2,363.56 ms | 7,551.54 ms | 535 / 291 / 826 |
| Receipt | 2,086.83 ms | 3,094.11 ms | 8,385.34 ms | 558 / 309 / 867 |

Provider-reported totals: **2,164 prompt + 1,179 completion = 3,343 tokens**, four successful generation requests, no inference retries or failed inference responses. At the **configured client rates** of $0.0006/1K input and $0.0024/1K output, the estimate is **$0.004128**. This is **not a billed-cost measurement or verified current price**. No billing API was queried or cost-allocation settings changed.

The measured intake-to-outcome event intervals were **29.275, 31.406, 34.022 and 37.072 seconds**, respectively. They include deliberate queue waiting while the harness uploaded/verified the other fixtures, then processed jobs sequentially. They are retained to expose actual timing, not presented as immediate-upload throughput or compared with provider-only latency.

## Confirmed defects fixed and checks repeated

| Finding | Reproduction and change | Result |
|---|---|---|
| Hybrid provider path referenced undefined `source_evidence` on return | New offline regression called the real hybrid orchestration around a disposable structured provider response and reproduced `NameError`. Bind and retain the dictionary returned by `verify_extracted_evidence` | Focused regression passes; all four actual provider-backed cases return and persist real evidence |
| No way to select a Mantle project on inference | New config/header regression exposed missing setting/header. Add optional `MANTLE_PROJECT_ID`; send it as `OpenAI-Project` when configured | Unit check passes; project-restricted key successfully made all four real requests; default-project access denied |
| Provisioning API response/dependent permissions differed from abbreviated docs | Actual CLI returns `ServiceCredentialSecret` rather than `ServiceApiKeyValue`; added supported-field handling and owned setup resume. Tagged project operations also require `TagResource` / `ListTagsForResource`; grant these only for setup, then remove from application policy | New identity/project/key provisioned; final least-privilege policy verified. Setup 401/403 diagnostics were not invoice-generation results |
| Supabase delete succeeds with non-JSON CLI confirmation | Parser failed after deletion; reconcile exact owned ID through inventory and accept text success for this operation | Cleanup rerun confirmed project absent and existing projects preserved |
| Requested project retention was not applied during creation | Final signed metadata GET showed **`inherit`**, despite the original top-level `data_retention_mode: none` request. Do **not** claim zero retention for this run. Provisioner now explicitly updates `data_retention: {mode: none}` and reads it back before granting inference | Separate newly-owned project probe verified `mode=none`, made **zero inference calls**, then archived successfully. No global/account retention setting was changed |

The retention probe validates the provisioning fix, not a retrospective change to the four inference requests. Those requests used inherited retention. Data was synthetic; the effective account/model retention policy was not independently assessed. Functional case results are unchanged. A future run using the corrected provisioner still needs to establish its desired retention policy before sending data.

New unit baseline: **2 failures and 1 teardown error** (missing settings field during the header test); both regressions pass after the fixes. Raw baseline is preserved.

| Final check | Exact result | Evidence under `docs/inspection-evidence/provider-full-20261106/` |
|---|---|---|
| Full provider-backed prepared acceptance | **5/5 cases matched**, four real generations | `acceptance-attempt-1.json` |
| Broad offline selection | **335 passed, 36 skipped**, 31.22s | `broad.txt` |
| Same broad selection, reverse order | **335 passed, 36 skipped**, 18.76s | `reverse.txt` |
| Focused extraction/run/lease/security regression selection | **65 passed**, 5.67s | `focused.txt` |
| Disposable native PostgreSQL selection | **46 passed**, 67.49s | `postgres.txt` |
| Python syntax / whitespace | Passed | syntax compilation, `diff-check.txt` |

Counts overlap. The 36 offline skips are 33 PostgreSQL cases exercised separately plus live Pub/Sub, live Supabase backup/restore and Docker build. The PostgreSQL selection includes 33 actual PG cases and 13 supporting SQLite/schema checks. The same legacy stage-9 shared-resource module was not run wholesale; its backup/global checks are not implied by this scoped new-project acceptance. No legacy mock benchmark was used. Deprecation warnings remain in logs. Frontend source did not change; no browser/build rerun is claimed for this backend/harness change.

Commands used (each separately):

```powershell
.\.venv-inspection\Scripts\python.exe scripts/acceptance_storage_identity.py --owned-state scratch/ps1-acceptance-20261106-040e6a53/private-state.json --full --attempt 1 --evidence-dir docs/inspection-evidence/provider-full-20261106
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests --ignore=tests/phase_b/test_stage9_live_supabase_verification.py -q --tb=short -rs
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests --ignore=tests/phase_b/test_stage9_live_supabase_verification.py --reverse-order -q --tb=short -rs
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests/test_mantle_live_path.py tests/test_processing_events.py tests/test_pipeline_lease_reliability.py tests/test_production_inspection.py tests/test_indian_ap_and_mantle.py -q --tb=short -rs
.\.venv-inspection\Scripts\python.exe scripts/inspect_postgres.py --bin-dir scratch/pg-inspection/runtime/pgsql/bin --tb=short
```

The first command describes the measured run; its deleted credential journal **cannot be reused**. Future runs require a new ownership marker/directory, restricted local ACL, fresh evidence directory and `scripts/provision_ps1_full.py --owned-root <new-owned-root> --evidence-dir <new-evidence-directory>`, followed by the harness with that same directory. Cleanup uses the provisioner's `--cleanup` mode. The scripts intentionally require clear ownership/provenance and will not use an existing project's credentials as if newly created. Fixture PDFs/ground truth remain unchanged.

## Cleanup and retained resources

- **Supabase project deleted**, including both synthetic identities, test bucket/objects and dedicated databases; account inventory confirms previous project IDs remain present.
- **Service credential and temporary IAM user/policy deleted**; a subsequent IAM lookup confirms `NoSuchEntity` for the new username.
- **Main Mantle project archived**, verified by a separate signed metadata GET returning `status=archived`. The separate no-inference retention-probe project `proj_qwktc74xicasegzwirf2` was also archived. Archived project metadata/history may remain under AWS retention; these are not active inference projects. No provisioned capacity, reservation or paid subscription was created.
- Native regression PostgreSQL cluster stopped and removed. No application/Docker server was started. No active test compute/database/storage/credential resource is intentionally retained; no recurring test resource was left running. The Supabase organization was Free and no billing upgrade occurred. Actual invoices/charges were not inspected.
- Retained: synthetic fixture pack, harness/provisioner, focused regressions, sanitized JSON/raw test evidence and reports. The main ignored credential journal was stripped of secrets.

**Local cleanup exception:** automatic approval review rejected deletion of four files with **“blocked by policy”**: `private-acceptance-1.log`, `private-cleanup.log`, `private-provision.log`, `private-credential-response.json` under `scratch/ps1-acceptance-20261106-040e6a53/`. They remain current-user access-restricted and git-ignored. Their service credential was revoked; the main journal is pruned. No alternative deletion method was attempted. This did not block cloud cleanup.

## Changed files, prerequisites and limits

Application changes: `backend/core/config.py`, `engine/mantle_client.py`, `engine/hybrid_extractor.py`, `.env.example`. Added `tests/test_mantle_live_path.py` and `scripts/provision_ps1_full.py`; extended `scripts/acceptance_storage_identity.py`; added reports/index links and evidence. No migration or dependency change. Existing uncommitted workspace work/data was preserved. No production environment variables, infrastructure, users, invoices or integrations were altered.

For later authorized runs/releases, configure `MANTLE_PROJECT_ID` alongside a credential that can infer only in that project, keep existing private storage/identity/database setup and migrations 010–012, and verify retention using the corrected provisioning readback. The empty optional project setting preserves existing request behavior; least-privilege policies should enforce a project when isolation is required. No deployment occurred.

Remaining unverified: browser/UI behavior, interviewer-operated live demo, scanned/image documents, large/ambiguous or adversarial PDFs on the live model, broad model accuracy, load/throughput/rate-limit saturation, live provider interruption/failover/slow-response recovery, real ERP/Gmail/payment integration, current billed costs and production security/compliance. The prior disposable slow-call/process-loss tests remain useful **separate** evidence; these four fast provider calls do not prove those live failure cases. Retention was inherited for this acceptance execution, as disclosed above. No production-readiness guarantee follows from five simple synthetic cases.

## Sources and skills

Observed code and newly recorded API/SQL responses are the basis for every pass/fail result. Official [Bedrock API-key permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-permissions.html), [IAM service-specific credential response fields](https://docs.aws.amazon.com/cli/latest/reference/iam/create-service-specific-credential.html), [Mantle project isolation](https://docs.aws.amazon.com/bedrock/latest/userguide/projects.html), [project attribution/cost granularity](https://docs.aws.amazon.com/bedrock/latest/userguide/cost-mgmt-projects.html), and [project retention controls](https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html) informed setup. Policy details were validated against actual IAM simulation and provider behavior. No account-wide billing/retention setting was changed. Karpathy guidelines were used for surgical fixes and regression-first verification; the existing synthetic PDF pack was reused without modification. No browser or subagent was used.
