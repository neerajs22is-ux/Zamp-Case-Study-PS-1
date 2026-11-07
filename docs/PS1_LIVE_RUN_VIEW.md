# PS-1 persisted processing run — 6 November 2026

**Reliability follow-up:** Bounded lease renewal and interrupted-worker recovery document Gmail intake checkpoints, late-result fencing, crash/concurrency tests and remaining provider limits (see `backend/core/processing_events.py` and `tests/test_processing_events.py`). Historical results below are retained.

Continuation of production inspection and offline verification suites. This change adds a small authenticated run view. It does **not** establish live-demo or production readiness.

## Observed path and implementation

The protected application uses `backend.main`, not the separate legacy `engine.server` mock benchmark. Signed identity resolves to an active server-side membership and assigned role. `/connections/upload` delegates to `/documents/upload`. The accepted PDF is validated, stored privately, and committed with an invoice, ingestion job and attributed `DOCUMENT_UPLOADED` audit record. A background task, or the role-protected `/documents/process-next` recovery action, claims one tenant job with a lock token and lease. `execute_document_pipeline` reads storage, verifies the SHA-256 digest, invokes `HybridAPExtractor.extract_hybrid`, then persists extraction evidence and computes matching against tenant procurement snapshots. The result transaction records the processing decision, match checks, existing `DOCUMENT_PROCESSED` audit and completed job. Human approvals remain separate financial actions/history.

Before this change, jobs exposed current status/error and the audit exposed intake/final results. No durable intermediate checkpoints existed. Detail polling repeatedly fetched financial detail and signed document URLs. A processing persistence exception rolled back financial writes but left the job processing until lease recovery.

The implementation reuses the append-only, tenant-protected audit table. No new table, migration, event broker, SSE server or model call is introduced. The intake audit keeps its action and actual user attribution and gains versioned checkpoint metadata. Subsequent `PIPELINE_STAGE` audits retain service attribution. Each event has a job ID, per-job sequence, attempt, UTC timestamp, stage, status and message. Only a recorded outcome carries the committed processing decision/reason. Old records are preserved without backfill.

| Checkpoint | Actual boundary |
|---|---|
| Intake / queued (attempt 0) | Validated upload, invoice, job and intake audit committed together |
| Run / started | Worker claim committed |
| Document read / started, succeeded | Stored bytes requested, then SHA-256 verified |
| Extraction / started, succeeded | Actual adapter invocation and return; grounding, document classification and validation are bundled here |
| Matching / started | Tenant matching/result persistence about to run |
| Matching / succeeded + outcome / recorded | Written in the **same transaction** as match checks, decision, original processing audit and job completion |
| Stage / failed | Observed read, extraction or matching/persistence exception; generic public error, bounded retry |
| Run / interrupted | Recovery actually observes an expired lease; unfinished completion explicitly unconfirmed |

“Succeeded” describes an operation returning/committing, **not** a payable or approved invoice. Rejected, ungrounded and failed-gate results still require their actual recorded financial outcome. No substage of the extraction adapter is invented. There is no percentage, timer-driven stage advance or synthetic completed-stage backfill.

Checkpoint writers lock the job and verify its tenant, token, processing state and lease, including expiry after waiting for the lock. Sequential numbers span retries and are allocated under that lock. External storage/model operations hold no checked-out database connection in the tested managed background path. Failed result transactions roll back before a fresh fenced error transaction queues another attempt or marks terminal failure at three failed/interrupted attempts. Stale workers cannot append completion or error/retry records. Expired leases stay visibly unconfirmed until recovery is requested.

`GET /api/v1/invoices/{invoice_id}/processing` requires active membership and first authorizes the invoice in the current workspace. It returns complete tenant-scoped job/event snapshots; it never claims jobs, signs URLs or mutates data. Lock tokens, storage keys and raw provider exceptions are omitted. Read-only auditors may inspect; mutation permissions on queue recovery remain AP associate/lead, controller or system administrator.

`InvoiceRunView` shows job status, created/completed timestamps, actual ordered attempts/checkpoints, sanitized errors and recorded outcome. Its list contains only persisted events. Legacy invoices with no jobs/events receive explicit absence text. Polling runs every three seconds while queued/processing, with 15-second request timeout and bounded reconnect backoff (6–30 seconds after errors). Complete snapshots replace prior snapshots, so reconnects do not duplicate events. Transient failure keeps the last snapshot visibly stale; 401/403/404 clears the run snapshot and stops automatic reconnects. Cleanup aborts requests and ignores late responses. Manual refresh is available after completion or reconnect failure. A new recorded outcome or terminal failure refreshes financial detail once; periodic polling no longer mints document URLs. The existing queue action clearly acts on the workspace queue, potentially another invoice first.

## Verification and reproducibility

All fixtures are disposable. No configured dotenv credentials, production data, browser, app server or deployment was used. Environment: Windows/PowerShell, Python **3.12.10**, Node **26.7.0**, portable PostgreSQL **17.11**, React **19.3.1**, TypeScript **7.0.2**, Vite **8.3.5**, oxlint **1.89.0**. Existing inspection runners disable dotenv/inherited integration credentials and restrict network connections to loopback. PostgreSQL runs in its own temporary loopback cluster, uses actual migration head **012**, and drops only its own test databases/cluster.

| Check | Before this task | Final | Evidence under `inspection-evidence/live-run/` |
|---|---|---|---|
| Same broad offline selection | 320 passed, 26 skipped | 329 passed, 27 skipped; 18.84s | `broad.txt` |
| Same broad selection in reverse | 320 passed, 26 skipped | 329 passed, 27 skipped; 17.54s | `reverse.txt` |
| Focused security/workflow suite, plus new run tests | 95 passed | 104 passed; 8.59s | `focused.txt` |
| Disposable PostgreSQL selection | 36 passed | 37 passed; 28.88s | `postgres.txt` |
| Polling/reconnect controller | Absent | 6 passed | `polling.txt` |
| Frontend build | Existing baseline passed | Passed, >500 kB chunk warning | `build.txt` |
| Frontend lint | Existing warnings | Exit 0, 28 warnings; none in new run component/controller | `lint.txt` |
| Local UI mechanical scan | Not applicable | No findings (`[]`); no rendering performed | `ui-scan.json` |
| Targeted Python compilation / git whitespace | Existing passed | Passed | `diff-check.txt` (Git line-ending notices may remain) |

Counts overlap and must not be added. Nine new offline tests exercise real pipeline transactions with disposable provider responses, actual signed-identity ASGI requests, ordered matching/outcome, authenticated upload attribution, cross-tenant denial, anonymous denial, legacy absence, idempotent snapshot reads, stale/replayed workers, expired leases, three bounded failures, digest tampering, provider failure, atomic rollback and managed-session connection release around provider calls. The new PostgreSQL case uses `ap_app_user` with `rolsuper=false`, `rolbypassrls=false`, two concurrent checkpoint writers, ordered sequences, expired-worker denial, retry attribution, cross-tenant read/write denial and the database append-only trigger. The other migrated PostgreSQL invitation, identity/audit preservation and financial concurrency checks remain in the same selection. Of 37 PostgreSQL-selection passes, **24 exercise PostgreSQL** and 13 are supporting SQLite/schema tests.

The first broad attempt found a duplicate test-module basename collection error. The PostgreSQL test was renamed; no tests were excluded to fix it. Original evidence is retained as `broad-initial-collection-error.txt`. The prior source assertion denying any run view was updated to require the implemented persisted-checkpoint disclosure and explicit missing-event uncertainty. Security assertions were retained.

Reproduce from the repository root (each command separately):

```powershell
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests --ignore=tests/phase_b/test_stage9_live_supabase_verification.py -q --tb=short -rs
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests --ignore=tests/phase_b/test_stage9_live_supabase_verification.py --reverse-order -q --tb=short -rs
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests/test_processing_events.py tests/test_production_inspection.py tests/phase_b/test_stage3_storage_ingestion.py tests/phase_d/test_phase_d2_tenant_security.py tests/phase_d/test_phase_d3_e2e_workflow.py tests/phase_d/test_phase_d4_reliability_recovery.py tests/phase_e/test_security_and_financial_controls.py tests/phase_a/test_auth_and_rbac.py tests/test_indian_ap_and_mantle.py -q --tb=short -rs
.\.venv-inspection\Scripts\python.exe scripts/inspect_postgres.py --bin-dir scratch/pg-inspection/runtime/pgsql/bin --tb=short
.\.venv-inspection\Scripts\python.exe -m compileall -q backend/core/processing_events.py backend/core/pipeline.py backend/api/v1/documents.py backend/api/v1/invoices.py tests/test_processing_events.py tests/postgres/test_processing_events_postgres.py
git diff --check
```

From `frontend`: `node --test tests/runPolling.test.mjs`, `npm run build`, `npm run lint`. No dev-server command is required. The 27 offline skips comprise 24 PostgreSQL cases run separately and three unchanged blockers: live Google Pub/Sub, live Supabase backup/restore, and Docker build. The same stage-9 provider verification module remains excluded; its eight provider checks are unrun, and the previous separate bundle-pattern result is unchanged. Deprecation warnings remain visible in the raw logs. The legacy mock benchmark remains separate and was not rerun or used as authenticated workflow evidence.

## Handoff and remaining limits

Changed for this task: `backend/core/processing_events.py`, `backend/core/pipeline.py`, `backend/api/v1/documents.py`, `backend/api/v1/invoices.py`, `frontend/src/api/client.ts`, `frontend/src/components/InvoiceRunView.tsx`, its CSS, `frontend/src/utils/runPolling.ts`, `frontend/src/pages/InvoiceDetailPage.tsx`, `frontend/tests/runPolling.test.mjs`, `tests/test_processing_events.py`, `tests/postgres/test_processing_events_postgres.py`, the truthful-copy assertion in `tests/phase_1/test_phase1_truth_and_plain_language.py`, and this report/evidence/index. Existing workspace changes were retained. No schema/configuration change, dependency installation, new credential or infrastructure is required by this view. Existing authenticated backend, private storage, extraction-provider configuration, worker dispatch and migrations 010–012 remain prerequisites for a future authorized live run. Frontend/backend must be released together by the authorized operator later; nothing was deployed here.

Before calling the PS-1 demonstration live, an authorized disposable provider-backed run must demonstrate: actual identity/session access; real private upload and rendering; actual extraction/grounding/matching and decision evidence; visible provider delay/failure; refresh/reconnect and worker restart/lease recovery; and subsequent human decisions/history. Browser keyboard, layout, responsive behavior and screen-reader announcements remain unverified. No screenshot or browser-level acceptance is claimed.

The existing 180-second lease is not a heartbeat mechanism. A slow provider can exceed it; stale results are rejected and an authorized queue request must recover the job. Recovery is opportunistic, not a newly added autonomous scheduler. Requests/manual refresh can detect gaps but cannot determine whether an interrupted external call finished. Terminal failure needs administrator investigation; no new automatic reprocessing of completed/historic invoices is added. Other intake paths that do not create these structured events remain visibly without stage history. Large-history pagination and provider throughput/load testing are outside this small view. Existing authentication/session, storage/provider and broader readiness limitations in the inspection remain applicable.

Sources: the actual code paths and disposable test results above; existing PS-1 reference `specs/PS1_INVOICE_PROCESSING_SPEC.md`; prior primary-source security/platform research in the linked inspection. No new external research was needed for this scoped persistence/polling implementation. Skills used: Karpathy guidelines (surgical, testable changes) and Impeccable (existing operational UI, truthful failure/empty states and local mechanical check). No production-readiness, compliance or flaw-free guarantee is made.
