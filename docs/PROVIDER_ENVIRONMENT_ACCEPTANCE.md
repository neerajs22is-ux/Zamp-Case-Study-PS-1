# Disposable provider environment and partial PS-1 acceptance

**Completed full-run follow-up:** [PS-1 live acceptance results](PS1_LIVE_ACCEPTANCE_RESULTS.md) supersedes the expired-AWS/full-extraction blocker below. A fresh isolated environment and project-scoped model credential exercised all five prepared cases successfully. Setup/app fixes, measured usage, retention caveat and cleanup are documented there. Historical subset results below remain unchanged.

6 November 2026 (Asia/Calcutta). This supersedes the earlier **no setup authorization/designated workspace** blocker in the prepared acceptance plan (`docs/inspection-evidence/provider-acceptance/local_checks.json`). The user authorized new disposable setup. A separate provider project was created and used, then deleted. **Full extraction/matching acceptance remains blocked by expired AWS account sessions, not by lack of setup permission.**

## Environment actually created and exercised

| Resource | Observed setup |
|---|---|
| Dedicated Supabase project | `ps1-acceptance-20261106-abb798f9`, project ID `ppcmermepbdsfypzepcd`, Mumbai `ap-south-1`; separate from the existing project |
| Dedicated application database | `ps1_acceptance_abb798f9` on that new project; actual PostgreSQL **17.11** |
| Schema | Actual Alembic migrations through **012_invitation_utc_expiry** |
| Runtime database identity | Direct `ap_app_user` login: non-superuser, non-BYPASSRLS, no createdb/createrole; administrator used only for disposable schema/reference setup |
| Private storage | New `ps1-acceptance-abb798f9` bucket, `public=false`, PDF-only, 1 MiB limit; new project's service credential only |
| Identity | Two newly created synthetic `@example.test` users in the new provider project; real password sign-in and **ES256** access tokens; application verifies provider JWKS and explicit tenant memberships |
| Application membership | Two isolated synthetic tenants; **AP_ASSOCIATE** role, no local auth bypass, no dev-session minting |
| Harness | In-process actual FastAPI app, **staging mode** and `SupabaseStorageAdapter`; no application server/browser/deployment |
| Extraction | Separate principal/key could not be provisioned: both available AWS CLI account sessions are expired. No inference requests sent |

No existing project API keys, users, database rows, buckets or ACLs were changed. Available Supabase CLI account metadata was used to identify the organization and protect existing project IDs. New test credentials were held in an ignored scratch directory with Windows ACL inheritance removed and access granted to the current user; none were printed or committed. The generated credential journal was stripped of secrets after cloud deletion.

Synthetic vendor, PO, line, receipt and QC references were seeded from the prepared manifest, including the deliberately missing QC case. No approval, payment or ERP-posting action was submitted. Background dispatch was explicitly disabled because the isolated extraction prerequisite was unavailable. Real intake jobs remained queued; no stage was completed by inference or assumption.

## Measured case results

The actual app received all five prepared requests. One is the exact-byte duplicate of the happy input, so four accepted documents/jobs were created. Provider-backed identity, database and storage behavior below is newly exercised evidence; it is not an offline/mock substitute for extraction.

| Case | Expected end-to-end outcome | Observed protected-app result | Upload/request latency |
|---|---|---|---|
| Happy PDF | All matching gates pass; `PENDING_APPROVAL / MATCH_CANDIDATE` | Upload **200**; real private storage and readbacks verified; persisted `INTAKE / QUEUED`; final outcome **BLOCKED/NOT TESTED** | **1514.87 ms** |
| Exact duplicate | HTTP 409, original invoice/document reference, no additional job/model call | **409 DUPLICATE_DETECTED**; same original invoice ID; job count unchanged at one at this point. **PASS for duplicate intake behavior** | **491.84 ms** |
| Price variance | Gate 6 FAIL; `ACTION_REQUIRED / FLAGGED_EXCEPTION` if extraction is valid | Upload **200**, integrity and intake event verified; extraction/matching/outcome **BLOCKED/NOT TESTED** | **1541.88 ms** |
| Missing QC | Gate 4 FAIL; `ACTION_REQUIRED / FLAGGED_EXCEPTION` if extraction is valid | Upload **200**, integrity and intake event verified; extraction/matching/outcome **BLOCKED/NOT TESTED** | **1431.80 ms** |
| Payment receipt | Non-payable classification; `REJECTED / REJECTED` | Upload **200**, integrity and intake event verified; classification/outcome **BLOCKED/NOT TESTED** | **1491.27 ms** |

For **each of the four accepted PDFs**, the original file SHA-256 matched the upload response, authenticated download bytes, authenticated preview bytes and actual provider signed-download bytes. Signed downloads were fetched over HTTPS; capability URLs were not saved in evidence. Unsigned public-object access returned **400**, without document bytes. A separate privileged metadata check confirmed the bucket was **private**. The combined download/preview/sign-and-download/unsigned checks took **3252.63–3359.98 ms per PDF**. These measured times include several API/provider round trips and local verification; they are not individual storage-operation or inference timings. There is one sample per case, not a performance benchmark.

New tenant B's genuine signed identity received **404** for tenant A's known new invoice detail, processing run, document metadata, download, preview and signed-URL minting routes. Anonymous run access returned **401**. A forged `X-Tenant-ID` using tenant A's token to select B returned **403**. Direct non-bypass PostgreSQL tenant B queries returned no tenant A invoice/document rows. These are **11 passing grouped auth/isolation checks**, including the two authenticated identity/membership checks. Signed URLs remain bearer capabilities until expiry; no session-bound privacy guarantee is claimed for a leaked signed URL.

Final database verification before cleanup found exactly **4 documents, 4 invoices, 4 jobs and 4 intake audit events** in the fresh application database. All invoices were `RECEIVED / NEEDS_REVIEW`. **0 extraction runs, 0 match runs, 0 approval requests** existed. Each snapshot contained only its true intake event and actual queued status. No success, rejection or completed matching was invented for the model-dependent cases.

## Extraction access blocker and provider usage

Both configured AWS profiles were tested with `sts get-caller-identity`, initially and again after the run. Each exited **255** with **“Your session has expired”** and a request to reauthenticate with `aws login`. Thus no current IAM session was available to create a separate least-privilege extraction principal/service credential. No IAM permission-denial claim is made: authorization could not be evaluated without valid authentication. Browser-based reauthentication was not attempted under the no-browser restriction.

The existing `.env` Mantle bearer key was used for **one read-only `/models` catalog request**, which returned **200** and 41 catalog entries. That proves catalog access for that existing key; it does not prove it is isolated to this new environment or capable of minting another credential. It was **not** passed to the staging app and **no synthetic PDF/text was sent for inference through it**. The app's environment removed inherited model/provider keys and disabled dotenv loading before application imports.

**Inference requests: 0. Tokens/model used: unmeasured. Inference latency: unmeasured. Billed model cost: unknown/not queried.** No configured token-rate estimate or zero-token fallback was reported as actual usage. The read-only catalog request is reported separately from inference. A refreshed AWS IAM session capable of provisioning a restricted test extraction credential is the remaining account prerequisite; an existing broad application key was not relabeled as a disposable key.

## Setup failures, fixes and exclusions

1. Supabase rejected specifying an instance size for the account's **Free** organization. Retrying project creation with the size omitted succeeded; no paid plan or billing change was made.
2. The initial harness attempted `ALTER ROLE ... NOSUPERUSER NOBYPASSRLS PASSWORD ...`. Managed PostgreSQL rejected restating the superuser attribute. The harness now first **asserts** the migrated role has all four restricted attributes, then changes only that new role's password. The least-privilege checks were retained. The schema migrations themselves succeeded through 012.
3. The initial harness used `APP_ENV=test`, which selects the application’s in-memory test storage. A failed signed-download check exposed this configuration mistake. That run is **rejected as provider-storage evidence**, and no result from it is counted above. The corrected run used a fresh dedicated application database in the new disposable project, staging mode, a generated session secret, and an explicit `SupabaseStorageAdapter` type assertion. The complete identity/storage/intake subset was rerun successfully using real providers. The earlier synthetic test-mode records remained only in the same disposable project's initial database until project cleanup; no audit rows were deleted or rewritten to make the rerun pass.

Application financial/security logic was not changed. Changes are confined to the acceptance harness, reports and sanitized evidence. The harness refuses a deleted ownership journal and refuses a runtime mock storage adapter. Python syntax compilation and `git diff --check` passed. The existing broad/offline suite was not rerun because no application implementation changed; historical results remain separate.

## Cleanup, costs and retained reproduction materials

The CLI deleted **only** project `ppcmermepbdsfypzepcd`, after checking its exact generated name and excluding all pre-existing project IDs. A subsequent account inventory confirmed the new project was absent and the previous project's ID remained present. This removes the new project's PostgreSQL databases, test auth identities, bucket and uploaded objects. **No cloud test resources were intentionally retained**, and no local app/Docker/PostgreSQL server was started. No recurring test resource remains in account inventory.

The account identified the organization as **Free** during creation. No subscription upgrade, paid size, new AWS principal, inference request or app deployment occurred. Provider billing was not queried, so no exact invoice-total/cost guarantee is made. For future runs, leaving a created project active consumes its plan's project quota; paid-plan project resources may incur recurring charges. This run's project was removed rather than left running for the demo.

Automatic approval review **rejected deletion of two local scratch logs** with **“blocked by policy.”** They remain at `scratch/ps1-acceptance-20261106-abb798f9/private-harness.log` and `private-creation-response.txt`, inside the access-restricted, git-ignored directory. No alternative deletion method was attempted. The credential journal was already pruned after project deletion. The cloud project cleanup succeeded independently.

Retained materials:

- `scripts/acceptance_storage_identity.py`: the real-provider subset harness, isolated configuration, non-bypass runtime assertions and explicit no-mock guard. It requires an ownership journal for a **newly created current project**; the deleted project's journal cannot be reused.
- `output/pdf/ps1-acceptance-20261106/`: synthetic PDF/PO inputs and manifest from the prepared plan, unchanged; no credentials or live outcomes were written into the fixture ground truth.
- `docs/inspection-evidence/provider-environment/`: setup/account-access/catalog metadata, real subset results, migration/runtime/resource verification, cleanup confirmation and checksum summary. No tokens, passwords or signed URLs are included.

Reproduction requires new disposable setup, not reconnecting to the deleted project: generate a new unique `ps1-acceptance-<date>-<suffix>` label, create a Free project with size omitted, capture only its newly returned ID/keys into a private ignored ownership journal, create a private PDF-only bucket and two confirmed synthetic auth users, obtain their real provider sessions, create an isolated `ps1_acceptance_<suffix>` database, and record the guarded setup success JSON. Then invoke:

```powershell
.\.venv-inspection\Scripts\python.exe scripts/acceptance_storage_identity.py --owned-state scratch/<new-owned-run>/private-state.json
```

The ownership journal fields consumed by the script are explicit in source; never supply an existing project or production credentials as a new ownership record. The `setup.json` guard must describe that same newly created project. Preserve previous evidence before a future run because this scoped harness writes to its documented evidence directory. This is a **subset reproduction harness**, not a completed model-backed acceptance runner; it will continue to leave jobs queued until an isolated extraction credential is available. Once IAM access is restored, the remaining provider-backed extraction/grounding/matching/decision/run-event checks must be added and run with the existing four edge expectations, without submitting approval/payment actions.

## Sources and remaining readiness limits

Official [Supabase management authentication](https://supabase.com/docs/reference/api/introduction), [billing/project isolation guidance](https://supabase.com/docs/guides/platform/billing-faq), [AWS Bedrock API-key creation](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html), and [AWS CLI sign-in guidance](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html) informed the setup/access investigation. Results above come from actual CLI/API/SQL responses, not these documents or prior summaries. Tools observed: Supabase CLI **2.117.0**, PostgreSQL **17.11**, Python **3.12.10**, and the current authenticated app. Karpathy guidelines were used for bounded setup/harness changes and explicit evidence boundaries; prepared PDFs were reused without modification.

This is a successful **real identity/storage/database/intake/isolation subset**, not full PS-1 acceptance. Extraction quality, semantic grounding on actual provider outputs, matching and terminal decisions for the happy/price/QC/receipt cases, complete live run events, provider retries/latency/cost, and browser demonstration remain untested here. No production-readiness or live-demo sign-off is given.
