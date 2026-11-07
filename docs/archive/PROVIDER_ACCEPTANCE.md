# PS-1 provider-backed acceptance — blocked on disposable target

**Authorized setup follow-up:** [New disposable provider environment and measured subset](PROVIDER_ENVIRONMENT_ACCEPTANCE.md) supersedes the no-designated-target blocker below. A separate Supabase project was created, real identity/storage/database/intake/isolation checks passed, and the project was deleted. Full extraction/matching acceptance remains blocked by expired AWS sessions needed for an isolated extraction credential. Historical preparation evidence below is unchanged.

Date: 6 November 2026. **Provider-backed acceptance was not run.** When asked which workspace and provider project/bucket were explicitly disposable, the user answered **“none.”** That is the blocker, not a demonstrated provider outage or invalid credential.

No remote database reads/writes, identity-provider requests, storage uploads, model calls, financial actions, deployments, browser use or app-server startup occurred. Existing workspace changes and data were preserved. Only local fixture preparation, PDF rendering and read-only source/fixture checks were performed. No existing live test module was executed against its configured endpoints.

## Preflight and actual exercise

Only credential **presence** was inspected locally, without printing values or importing application configuration. `.env` contains database, migration database, Supabase URL/service-role/signing/issuer and Mantle key entries. The corresponding process environment entries were absent. Presence is not proof of a working service, test designation, sufficient authorization or valid credentials. No test workspace/project/bucket designation was found in configuration; the user's answer confirmed its absence. The credentials were not validated. The available old stage-9 live suite targets configured shared resources and inserts named test records, so it was not a safe substitute for a designated disposable acceptance target.

The permitted local preparation produced **four synthetic document PDFs plus one procurement-reference PDF**, and a JSON case/ground-truth/source-data manifest at `output/pdf/ps1-acceptance-20261106/manifest.json`. The duplicate case intentionally reuses the happy PDF's exact bytes rather than generating a different document. The source data has fictional supplier/GST identifiers, four independent PO references, receipts and deliberate QC absence. **None of these records has been inserted into a database.** The PDFs explicitly disclaim commercial validity and prohibit payment/approval use.

Six grouped local checks passed: each of the four documents' manually supplied expected schema/field occurrences, arithmetic and local SHA-256; duplicate-input byte identity; and the procurement PDF's page count/hash. All 16 supplied ground-truth fields per document were found in source text. This verifies fixture consistency, **not model extraction, semantic grounding accuracy or financial matching**. No deterministic mock engine was used to manufacture acceptance outcomes. All case `observed` values remain `null` and execution is explicitly `NOT_RUN_NO_DISPOSABLE_TARGET`.

Each of the five one-page PDFs was rendered with Poppler and visually inspected: readable, no observed clipping/overlap. Poppler emitted Symbol/ArialUnicode font notices; the rendered fixture text remained legible. Local per-document schema/source/arithmetic/hash checks took **3.766–4.788 ms** in this one small run. Those measured local times exclude all providers, uploads, database work and rendering; they are not PS-1 end-to-end latency or a benchmark.

Evidence: `docs/inspection-evidence/provider-acceptance/preflight.json`, `local_checks.json`, and `summary.json`. Hashes and source checks are also in the fixture manifest. The report does not relabel prior disposable PostgreSQL/offline tests as new provider acceptance evidence.

## Prepared expected outcomes versus observations

These expectations derive from current authenticated pipeline/gate code and require accurate, grounded provider extraction. They were fixed before any provider execution, which remains blocked.

| Case | Synthetic input/setup | Expected protected-app outcome | Observed acceptance outcome |
|---|---|---|---|
| Happy path | 1 service at INR 100; CGST 9 + SGST 9; grand total 118. Active synthetic supplier; open INR PO, contracted rate 100, authorized/received quantity 10; QC accepted | Gates 1–7 PASS; `PENDING_APPROVAL / MATCH_CANDIDATE`; one committed processing outcome, **no approval/payment** | **NOT RUN** |
| Duplicate | Upload exact happy PDF again in the same disposable workspace | HTTP 409 `DUPLICATE_DETECTED`; original document/invoice reference; no new job or additional model call | **NOT RUN** |
| Price variance | Unit rate 120 against contracted rate 100; taxable 120, GST 21.60, gross 141.60 | Gate 6 FAIL (+20%, above current 1.50% tolerance); `ACTION_REQUIRED / FLAGGED_EXCEPTION` if extraction is otherwise valid/grounded | **NOT RUN** |
| Missing QC | Valid separate invoice/PO/receipt; deliberately omit the QC record | Gate 4 FAIL; `ACTION_REQUIRED / FLAGGED_EXCEPTION` if other evidence is valid | **NOT RUN** |
| Non-payable receipt | Payment receipt acknowledges payment already made; gross 118; full source references remain available | Classified non-payable; `REJECTED / REJECTED`, never a payable candidate | **NOT RUN** |

Fixture-generation command (use a **new** output directory; it refuses to overwrite one):

```powershell
.\.venv-inspection\Scripts\python.exe scripts/prepare_ps1_acceptance.py --output output/pdf/ps1-acceptance-20261106
```

This script only creates local inputs; it is deliberately **not** a live acceptance runner and does not read `.env` or connect to application/providers. Do not run the legacy mock benchmark or the old shared-resource stage-9 suite as a substitute.

## Current-code trace and eventual live protocol

Read-only inspection confirmed the real path: signed identity → active server-side membership/role → `/api/v1/connections/upload` delegating to `/documents/upload` → PDF validation, private storage, invoice/job/intake audit transaction → fenced claim → storage read and SHA-256 verification → `HybridAPExtractor.extract_hybrid` → actual Mantle request for these text-bearing PDFs → structured schema and deterministic source-occurrence/financial validation → tenant procurement matching → atomic decision, extraction evidence, `DOCUMENT_PROCESSED` audit, outcome checkpoint and job completion. Bounded lease renewal/recovery remains as described in [live-run reliability](LIVE_RUN_RELIABILITY.md).

Once a disposable database/workspace and provider project/private bucket are explicitly identified, an authorized local ASGI harness can exercise this path without opening a browser or serving the app publicly. It must use the real configured storage/extraction adapters. A generated local test JWT, if chosen for the harness, must use a **new disposable signing secret** with synthetic users/memberships and be reported as local-token authentication, not live IdP/SSO acceptance. Otherwise an explicitly designated existing test identity/session is required. A configured production signing secret must not be used to impersonate test users.

For the happy path, retain these concrete observations before reporting success:

1. Workspace/second-tenant identifiers and ownership/designation; non-bypass application role and current migrations. Seed only the manifest's synthetic vendor/PO/line/receipt/QC records in the designated disposable target. Never enumerate production invoices or alter existing users.
2. Authenticated upload response IDs and HTTP status. Read only its new document/job/audit records. Compare local original SHA-256, document's recorded SHA-256, private-storage readback and authenticated preview/signed-download readback. Do not save credentials or signed URLs in evidence.
3. Verify the existing test bucket is private without changing its ACL. An unsigned request for the **new test object only** must not expose bytes. Test the second tenant against the known new invoice detail, run API, document metadata, preview and signed-URL minting routes: deny with 403/404 and no data leakage. Signed URLs are bearer capabilities until expiry; possession is not a tenant-session isolation guarantee.
4. Claim/execute through the real ingestion workflow; poll persisted full snapshots. Require ordered intake/read/extraction/matching/outcome records for the actual attempt, current status, timestamps, source evidence and terminal decision. No timer-derived completed stages. Match the final outcome event to the committed financial record. Do not call approval/action, payment or ERP-posting endpoints.
5. Run the four edge cases above, compare exact observed outcomes with expectations, and retain failures without replacing them with mock responses or weakening the assertions. Do not repeatedly retry provider failures without recording each call and cost uncertainty.

Measure upload/storage, provider response, processing and total wall-clock latency separately using monotonic timers; include UTC start/end and job/event timestamps. Do not attribute checkpoint time intervals exclusively to a model. Record provider HTTP status and response usage **where actually present**, the requested model ID and any provider-returned model ID. Current Mantle code stamps the **requested** model ID and defaults absent usage to zero; acceptance instrumentation must distinguish missing usage from a genuine zero. The authenticated pipeline currently persists source/model parser metadata but not the complete usage/cost telemetry, so capture sanitized telemetry alongside this acceptance evidence rather than infer it from audit event counts. Never record raw headers, credentials, signed URLs or provider error bodies containing sensitive material.

Costs computed from configured per-token rates are **estimates**, not billing records. This run made **zero provider calls**; provider latency, token usage, actual model used and billed cost are **unmeasured/not applicable**. No billing API was queried and no dollar cost estimate was invented.

## Blockers, changes and limits

Exact blocker: **no explicitly designated disposable workspace/database and associated private storage/provider project**. Required next inputs are non-secret target identifiers and which existing credential/config entries belong to those test services, plus test identity/session or approval of a clearly labeled local-token harness. Existing credential presence alone does not satisfy this. These inputs have not been supplied; the user explicitly answered “none.” No further provider calls should be attempted under this authorization.

Consequently upload/storage privacy and round-trip integrity, provider extraction, provider-grounded financial matching, persisted live events, real identity access and live tenant denial remain **unverified in this acceptance run**. Prior offline/PostgreSQL results remain separate historical evidence. Live-demo readiness is still blocked. Browser behavior remains untested under the preserved restriction.

Changes are confined to `scripts/prepare_ps1_acceptance.py`, the new synthetic local case pack/previews, this report/index and sanitized local evidence. No backend/frontend behavior, migration, credential, existing workspace data, permission or infrastructure was changed. No remote resource needs cleanup.

Skills: PDF (ReportLab generation, pypdf parsing, Poppler render/visual verification) and Karpathy guidelines (minimal preparation, explicit blocker and measured-versus-unrun evidence). Source authority for this run is current repository code and the user's explicit disposable-target answer; no external research or service probing was needed.
