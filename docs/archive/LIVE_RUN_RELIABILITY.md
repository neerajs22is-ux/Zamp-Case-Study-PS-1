# Authenticated run lease and recovery hardening — 6 November 2026

Follow-up to [the persisted run view](PS1_LIVE_RUN_VIEW.md). Existing dirty workspace work, financial rules, permissions and historic audit records were preserved. No application server, browser, production data access or deployment was used. All providers in these tests are disposable stubs; PostgreSQL is an owned loopback-only cluster.

## Findings and smallest fix

| Verified finding | Impact | Resolution |
|---|---|---|
| Provider work did not call the existing renewal function | A healthy call exceeding the 180-second lease could lose ownership and require another provider attempt | Bounded independent keepalive during storage and extraction |
| Renewal checked token/status but not expiry | An expired worker could resurrect its lease before recovery claimed it | Lock the job, refresh ORM state and check expiry **after obtaining the lock**; reject expired/mismatched/foreign-tenant jobs |
| Phase A/C ownership checks used a time captured before lock acquisition | A blocked worker could pass a stale time check | Recheck the lease after locking, before document access or result writes; release the transaction on abort |
| Lease comparisons depended on each worker's host clock | Clock differences could disagree about valid ownership | PostgreSQL `clock_timestamp()` converted to UTC for claim, renewal, checkpoint, recovery and snapshot expiry; SQLite keeps the test clock |
| Gmail intake had an attributed audit but no structured intake checkpoint | Accepted Gmail jobs showed no intake event before an eventual worker claim | Version the existing `GMAIL_INVOICE_INGESTED` audit as an intake checkpoint; preserve its action, actor ID and existing role label |

The renewal regression was run before the fix: `test_expired_lease_cannot_be_resurrected` **failed** because the old renewal returned `True` on an expired job. It now passes unchanged. No failure was suppressed or reclassified as expected behavior. These are reliability/ownership findings; no production exploitation or financial duplication was observed.

`_ProviderLease` renews through its own short tenant-scoped sessions while the provider worker holds no database transaction. It renews once before dispatch, then at most every 30 seconds, extending valid ownership by 180 seconds. It never shares a SQLAlchemy Session across threads. The first periodic successful renewal adds a factual `LEASE / RENEWED` audit, explicitly stating that renewal is **not provider progress**. Current lease expiry remains available in the existing snapshot API. PostgreSQL renewal transactions bound lock/statement waiting to 2/3 seconds. ORM rows are refreshed under lock rather than trusting cached ownership.

`PIPELINE_PROVIDER_BUDGET_SECONDS` defaults to **900 seconds**, validated between **180 and 3600**. It bounds renewal and acceptance of provider results for the combined storage/extraction operation. A local monotonic deadline avoids wall-clock changes affecting the budget. On budget expiry, renewal stops and, where fenced DB access remains available, records `LEASE / RENEWAL_STOPPED`: external completion remains unconfirmed and late results will not be accepted. On renewal failure, the worker fails closed and discards a later provider result/error. No provider call is started if initial renewal cannot establish ownership. Each aborted attempt remains subject to the existing lease-expiry recovery and three-attempt retry bound.

Heartbeat records are operational facts, not stage completion. A returned provider result must still pass the current token/status/tenant/expiry checks before matching. The result transaction holds the job row lock through extraction persistence, deterministic matching, existing financial decisions/audit, run outcome and job completion. Recovery cannot take ownership of that locked job. A replay/stale worker cannot append another outcome or overwrite the completed job. Approval/PO commitment rules were not changed.

Recovery retains `FOR UPDATE SKIP LOCKED` and records `RUN / INTERRUPTED` only when it observes an expired lease. The message now explicitly says that external completion is unknown, provider work may repeat, and stale results cannot commit. Concurrent queue requests increment retries and claim that attempt once. No retrospective stage success is synthesized. Existing history is append-only; no backfill or migration is needed.

## Intake coverage traced in current source

| Entry path | Invoice run events and remaining limits |
|---|---|
| Authenticated `/api/v1/connections/upload` | Delegates to `/documents/upload`; real intake event, role-attributed user audit, then worker checkpoints when actually claimed |
| Authenticated `/api/v1/documents/upload` | Same accepted-document/job transaction; automatic background dispatch when enabled or existing authorized queue action |
| Gmail full/manual sync | Shared `process_single_message_ingestion` now commits an intake checkpoint with the existing Gmail audit |
| Gmail history/PubSub, expired-history full fallback, periodic reconciliation | Same shared accepted-attachment function; intake checkpoint then common worker checkpoints after an actual claim. Delivery/mailbox status does not imply invoice extraction occurred |
| Gmail downstream processing | Currently queues jobs; Gmail does **not** dispatch the document pipeline itself. An authorized `/documents/process-next` action must claim the queue. This behavior was observed and preserved |
| Legacy/imported/evaluation invoices without jobs/events | Explicit absence remains; no synthetic history |
| Duplicate uploads/attachments, quarantine and pre-intake failures | No new accepted invoice/job, hence no new invoice run; existing duplicate/quarantine/error behavior retained |
| `DIRECT_API` source enum and separate legacy mock server | An enum is not an implemented intake route. No authenticated direct-invoice creation route was found. Legacy mock activity is not authenticated run evidence |

The Gmail event preserves its existing `SYSTEM_ADMIN` actor-role convention; this is not a newly verified authorization role for every originating human/service. The actual actor identifier and historical audits remain unchanged. Existing role enforcement on queue resume and active membership on run inspection are unchanged.

## Verification

Environment: Windows/PowerShell, Python 3.12.10, PostgreSQL **17.11**, SQLAlchemy **2.0.45**, psycopg **3.3.5**, HTTPX **0.28.1**; Node 26.7.0 for unchanged polling-controller tests. The runner disables dotenv and inherited integration credentials, blocks outbound network access, applies actual migration head **012**, and exercises the non-superuser, non-bypass **`ap_app_user`**. Only its own temporary databases, cluster and child process are removed/stopped.

| Check | Result | Raw evidence in `inspection-evidence/lease-reliability/` |
|---|---|---|
| Broad offline selection | 333 passed, 36 skipped | `broad.txt` |
| Same broad tests reversed | 333 passed, 36 skipped | `reverse.txt` |
| Focused lease, stage, Gmail, security and recovery selection | 90 passed, 1 skipped | `focused.txt` |
| Actual migrated PostgreSQL selection | 46 passed | `postgres.txt` |
| Existing UI polling/reconnect controller | 6 passed | `polling.txt` |
| Targeted Python compilation / whitespace | Passed | `compileall`, `diff-check.txt` |

Counts overlap; do not add them. Compared with the previous view, the broad suite adds four offline regression cases and nine PostgreSQL cases. The PostgreSQL selection has **33 actual PostgreSQL cases plus 13 supporting SQLite/schema cases**. Deprecation warnings remain visible. The broad skips comprise those 33 PostgreSQL cases (run separately), live Google Pub/Sub, live Supabase backup/restore, and Docker build. The same `test_stage9_live_supabase_verification.py` provider module remains excluded: eight live provider checks unrun, its prior separate bundle-pattern result unchanged. The focused skip is live Pub/Sub. The legacy mock benchmark was not run or used as authenticated workflow evidence.

New PostgreSQL adversarial cases exercise:

- Storage and extraction calls held past the original lease: keepalive extends ownership, recovery cannot claim a healthy worker, and no completion event appears while the provider remains blocked.
- A stopped keepalive, exhausted provider budget, and renewal DB failure: a late response cannot commit after recovery. Two simultaneous recovery/claim requests produce one retry claim and one interruption event. The restarted attempt records its own ordered outcome.
- A **real disposable Python child process terminated during provider work**, without cleanup: the last renewed lease expires, recovery claims it and processing completes once.
- Actual row-lock contention observed through `pg_stat_activity`: a waiting renewal rejects a lease that became expired before it acquired the lock.
- Wrong-tenant renewal/recovery denial through RLS, even with a known real token; no tenant history returned.
- Gmail intake checkpoint, audit attribution and tenant denial under the application role.

After retry/replay, fixtures require exactly one extraction run, one persisted invoice line, one `DOCUMENT_PROCESSED` audit and one recorded processing outcome. Approval is exercised twice and must yield one approval audit, `ALREADY_APPROVED` on replay and one 118-INR approved commitment. Existing PostgreSQL competing-invoice/PO and approval-lock tests also remain in the full selection. These checks validate the exercised financial effects; they are not a universal exactly-once guarantee for external providers.

Short leases (two seconds), subsecond test-only budgets and blocking disposable providers accelerate the same execution path. No wall-clock stage progress is inferred. The process-loss child disables dotenv before any application imports, validates its database URL as loopback `ap_app_user` on an inspection `_test` database, and uses only fixture PDF bytes and a local provider stub. A test failure captures child output rather than silently accepting early termination.

Reproduce from the repository root, each command separately:

```powershell
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests --ignore=tests/phase_b/test_stage9_live_supabase_verification.py -q --tb=short -rs
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests --ignore=tests/phase_b/test_stage9_live_supabase_verification.py --reverse-order -q --tb=short -rs
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests/test_pipeline_lease_reliability.py tests/test_processing_events.py tests/phase_b/test_stage4_gmail_ingestion.py tests/phase_b/test_stage5_gmail_pubsub.py tests/test_production_inspection.py tests/phase_d/test_phase_d4_reliability_recovery.py -q --tb=short -rs
.\.venv-inspection\Scripts\python.exe scripts/inspect_postgres.py --bin-dir scratch/pg-inspection/runtime/pgsql/bin --tb=short
.\.venv-inspection\Scripts\python.exe -m compileall -q backend/core/pipeline.py backend/core/processing_events.py backend/core/gmail.py backend/core/config.py tests/test_pipeline_lease_reliability.py tests/postgres/test_pipeline_lease_reliability_postgres.py tests/helpers/disposable_invoice_worker.py
git diff --check
```

From `frontend`: `node --test tests/runPolling.test.mjs`. Frontend source was unchanged in this task; the previous build/lint findings remain applicable.

## Remaining limits and handoff

No provider cancellation or external idempotency protocol is claimed. A timed-out/interrupted request may have finished remotely and may incur cost again on retry. The keeper cannot terminate an arbitrary synchronous call or guarantee a worker thread exits immediately. It stops renewing at its budget; recovery becomes possible after the last valid lease expires (normally at most another 180 seconds), and requires an authorized queue request. A database/network stall can delay the keeper thread's cleanup; the four-second join bound causes the caller to fail closed if that thread has not exited. Connection acquisition may still depend on existing pool/driver timeouts. The PostgreSQL token/row-lock fence remains authoritative for accepting results. No autonomous scheduler or remote result lookup was added.

Real provider latency, trickling responses, billing/idempotency, container suspension, resource saturation, database failover and real service restart behavior remain unverified. Browser rendering was not exercised. Provider-backed upload/storage/extraction and interview demo acceptance still require a separately authorized disposable live run. Existing Gmail validation/deduplication limits, broader authentication/session issues and production-readiness limits in the original inspection remain applicable. This patch does not claim production readiness or guaranteed security.

Changed in this task: `backend/core/pipeline.py`, `backend/core/processing_events.py`, `backend/core/gmail.py`, `backend/core/config.py`, `.env.example`; new offline/PostgreSQL lease tests and disposable crash helper; focused Gmail intake/history assertions; this report, index links and evidence. No migration, new dependency, credentials or infrastructure change is required. The new renewal budget is optional configuration; its validated default applies without setting an environment variable. Existing migrations 010–012 and correctly configured authenticated services remain deployment prerequisites for any later authorized release. Existing workspace files/data were retained.

## Sources and skills

Decisions use observed code and executable tests. Official [HTTPX timeout guidance](https://www.python-httpx.org/advanced/timeouts/) distinguishes read-chunk inactivity limits from an overall operation deadline; the existing 30-second Mantle/vision timeout therefore does not prove the full operation finishes within a lease. Official [PostgreSQL 17 row-lock guidance](https://www.postgresql.org/docs/17/explicit-locking.html) supports retaining row locks through the result transaction. These sources were checked on 6 November 2026; tested library/server versions are above.

Karpathy guidelines were used for focused changes and regression-first verification. Graphify's existing graph was discovered but its CLI was unavailable on PATH; current source searches/reads were used directly and no graph was rebuilt or treated as fresh evidence. No frontend/browser skill workflow or subagent was required for this backend change.
