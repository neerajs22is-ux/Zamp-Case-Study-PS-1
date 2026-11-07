# Offline and disposable PostgreSQL verification — 6 November 2026

Continuation of [the production inspection](PRODUCTION_INSPECTION.md). This report supersedes its broad-suite failures and its statement that PostgreSQL isolation/concurrency were untested. Other product, integration and readiness limitations still apply.

## Final results

| Check | Result | Evidence |
|---|---|---|
| Continuation baseline, same broad selection | 291 passed, 19 failed, 10 errors, 14 skipped; 30.88s | `inspection-evidence/continuation/baseline.txt` |
| Final broad offline suite | **320 passed, 26 skipped**, no failures/errors; 25.59s | `inspection-evidence/continuation/broad.txt` |
| Same broad suite, reverse order | **320 passed, 26 skipped**, no failures/errors; 24.39s | `inspection-evidence/continuation/reverse.txt` |
| Same focused inspection suite | **95 passed**, no skips/failures/errors; 11.33s | `inspection-evidence/continuation/focused.txt` |
| Disposable PostgreSQL selection | **36 passed**, no skips/failures/errors; 34.23s | `inspection-evidence/continuation/postgres.txt` |
| Separate frontend bundle pattern check | **1 passed**; narrow literal-pattern check, not a complete secret scan | `inspection-evidence/continuation/bundle_hygiene.txt` |
| Python compilation / whitespace check | Passed | `compileall` and `git diff --check` |

The PostgreSQL selection comprises **23 tests exercising actual PostgreSQL** and 13 supporting SQLite/schema tests in the original tenant-isolation module. Do not add the counts together: suites overlap. The broad-suite denominator increased because 12 PostgreSQL regression cases were added, not because previous failures were removed. Every original failing/error test remains collected and now passes.

The legacy mock benchmark was not used to satisfy any authenticated workflow assertion. Its previous separate result remains unchanged; it is not a hosted/live acceptance test.

## Failure investigation and disposable fixtures

All 19 failures and 10 errors were reproduced before changes. Findings were checked against current API implementation and assertions, rather than assuming every failure was an obsolete test.

| Original group | Investigation and correction |
|---|---|
| Phase 1 policy/detail/approvals tests | Three tests required an uninitialized global database and signed identities from a prior setup script. Function-scoped synthetic workspaces now supply users, server-side roles and computed checks. The failed-approval test still requires HTTP 400 and verifies no approval mutation; it asserts the current validation error instead of older exact wording. |
| Phase 1 UI source assertion | The unfinished redesign moved/reworded extraction guidance. The test retains truthful sign-off/provenance, policy, blocked-approval and verification assertions; it now checks the current source-inspection instructions and explicit absence of a live stage stream. No frontend behavior was changed to satisfy the test. |
| Ten vertical-slice setup errors | Each test gets a fresh in-memory database/session factory and test storage. No implicit production/global schema initialization. The formerly unreachable tests then exposed outdated positive assumptions: fake SHA replaced with the real PDF hash; actual procurement records supplied; unknown confidence remains `None`; rejected direct-handler calls roll back their transaction before another request. SQLite state checks are explicitly not labeled as PostgreSQL concurrency proof. |
| Four phase 2 failures | Replaced historical invoice IDs with fixture-returned IDs. Missing receipts/QC remain genuinely absent; positive reference snapshots and blocking checks are computed using current matching code. Failed approval still has to leave the invoice unapproved. |
| Four buyer-trust failures | Explicit clean, missing-evidence, price-variance and unreadable records replace dependence on a previously seeded evaluation database. Checks are produced by `reevaluate_match_gates`, not hard-coded success rows. |
| Seven roadmap failures | Signed users and a known clean invoice/line come from the test's own workspace. Correction audit, auditor denial, stale-write rejection, approval invalidation, temporal filtering, test-workspace reset and exposure contracts remain exercised. Arbitrary `.first()` selection was replaced with the fixture's intended clean invoice. |

`tests/conftest.py` patches imported session factories and the ASGI dependency explicitly for the affected tests, restores overrides afterwards and disposes the in-memory engine. No production setup script is invoked. The test-only `record_valid_match` helper can seed procurement without pre-recording a match, allowing the pipeline test to compute its own result. These records cannot appear in the application's configured database.

`pytest.ini` now sets `testpaths = tests`. Both runners supply explicit suite paths. `--reverse-order` reverses the same collected tests without deselection, exposing order-dependent state. The reverse run passed with the same counts.

## Disposable PostgreSQL method

Docker remained unavailable. Instead, portable PostgreSQL **17.11**, Windows x64, MSVC 19.44.35228, was downloaded from the official [EDB binary distribution](https://productsdl.enterprisedb.com/download-postgresql-binaries), which is linked by [PostgreSQL's Windows download guidance](https://www.postgresql.org/download/windows/). No installer, system service or application server was started.

Archive: `postgresql-17.11-3-windows-x64-binaries.zip`; local SHA-256:

```text
4B8DB0930C38F6EF845DB919551DEDDA3B6B845AEB0927B3D79A6E8E9E4537CF
```

This records the downloaded bytes, not an independently verified vendor checksum/signature. The portable runtime remains cached under ignored `scratch/pg-inspection/runtime/pgsql/` for repeat runs.

`scripts/inspect_postgres.py` disables dotenv/inherited integration settings, initializes a unique cluster under `scratch/postgres-tests-<uuid>`, chooses an available loopback port, binds only `127.0.0.1`, and uses disposable local trust authentication. That authentication mode is for this owned test cluster only. The runner stops and removes the cluster in `finally`, including failed runs. Native subprocesses use hidden Windows execution and regular log files to avoid child-inherited pipe hangs.

Each PostgreSQL test gets a separate UUID-named `_test` database, migrated using the actual Alembic chain. The fixture checks the ownership sentinel, PID file, port and server data directory before creating anything. It does not accept an arbitrary configured database URL. Privileged connections perform migrations and synthetic setup/verification only. Application exercises connect **directly as `ap_app_user`**, with assertions for `current_user`, `NOSUPERUSER`, `NOBYPASSRLS`, and no membership in `postgres`. Tests also retain the earlier effective-role and pooled-context checks. Application connections do not own the tables or receive schema/bootstrap privileges.

No existing account, financial record, integration or external database was used. Current PostgreSQL processes were checked after the runs: no test server remains running.

## Migration, identity, invitation and financial evidence

- **Actual migration sequence:** bootstrap to 009; insert existing users (including one without a role), assigned roles, financial ownership and historical audit; apply 010 and 011 separately. Compare complete role/audit/invoice rows and user identity fields before/after. An identity binding added after 010 survives 011. A provider subject bound to an existing local user still produces the existing local actor ID in a new audit event, preserving financial owner attribution.
- **Authorization:** assigned legacy identities continue to resolve. Missing roles fail closed after 011. The old email-based membership function is not executable by the app role, and the binding table remains inaccessible directly. Bound identities, multiple-workspace selection, invalid selection, revocation, same-email different-subject denial and pooled tenant-context reset were exercised.
- **Real RLS:** own-tenant rows are present, foreign rows remain invisible, foreign inserts fail, updates/deletes affect zero foreign rows, cross-tenant composite references fail with PostgreSQL `23503`. Missing/invalid tenant context returns no rows. App-role audit UPDATE/DELETE fails and historical actor IDs remain unchanged.
- **Current invitations:** real signed test JWTs through in-process ASGI; wrong identity, expired invitation, replay, successful acceptance/profile, cross-tenant header denial and one audit actor. Concurrent acceptance yields one success, one rejection, one role assignment and one acceptance event.
- **Concurrent PO commitments:** two initially valid ₹600 candidates share a ₹1,000 PO. One request deliberately holds the PO lock; `pg_stat_activity` confirms the other app-role transaction is actually waiting for a lock. After release, one approval succeeds and the other returns 400. Approved sum is ₹600 and there is one approval event. This tests contention, not just two sequential calls.
- **Same-invoice replay:** concurrent requests yield one `SUCCESS` and one `ALREADY_APPROVED`, with one audit effect.
- **High value:** ₹750,000 requires the first lead and a distinct controller. Same-actor retry is rejected; an auditor's signed controller claim does not override the database role. Final events are attributed to `lead/AP_LEAD` and `controller/CONTROLLER`.

### Real defects found and fixed

1. **Timezone-dependent invitation expiry — medium correctness/authorization defect.** Existing UTC-naive expiry was compared to `NOW()` with implicit session timezone conversion. On the actual 011 schema, the same valid invitation is found in UTC but absent in Asia/Calcutta. New **migration 012** compares to `NOW() AT TIME ZONE 'UTC'` without rewriting invitation rows. The test reproduces the old behavior before applying 012, then verifies consistent lookup in UTC, Asia/Calcutta and America/New_York. Expired invitations remain denied in all three zones. Function owner/ACL and historical audit/financial rows are unchanged across 012. PostgreSQL documents the relevant [timestamp/timezone conversion semantics](https://www.postgresql.org/docs/17/datatype-datetime.html).
2. **Existing-email/different-identity invitation — medium reliability and identity-integrity defect.** After expiry was corrected, a signed identity sharing an existing user's email produced a foreign-key error while attempting to grant a role to a different subject. `accept_invitation` now returns a clear **409 before changing that account**. Its existing ID, role and pending invitation survive. Cross-workspace joins that this endpoint cannot safely bind also return 409 instead of reusing tenant-local IDs. This is an explicit limitation requiring administrator reconciliation, not a newly implemented workspace onboarding flow. A valid same-account/new-user invitation still works.

Migrations 010/011 were not rewritten. Migration 012 is a new deployment prerequisite, **not applied to any existing/shared database**. Downgrade is deliberately blocked rather than silently restoring timezone-dependent expiry. Existing broader verified-email/onboarding limitations from the inspection remain.

## Commands and environment

From `C:\Zamp Casse Study`; Python 3.12.10 and the existing inspection venv/dependency versions. No dependency or production infrastructure changes in this continuation.

```powershell
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests -q --ignore=tests/phase_b/test_stage9_live_supabase_verification.py --tb=short -rs
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests -q --ignore=tests/phase_b/test_stage9_live_supabase_verification.py --tb=short -rs --reverse-order
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests/test_production_inspection.py tests/phase_b/test_stage3_storage_ingestion.py tests/phase_d/test_phase_d2_tenant_security.py tests/phase_d/test_phase_d3_e2e_workflow.py tests/phase_d/test_phase_d4_reliability_recovery.py tests/phase_e/test_security_and_financial_controls.py tests/phase_a/test_auth_and_rbac.py tests/test_indian_ap_and_mantle.py -q --tb=short -rs
.\.venv-inspection\Scripts\python.exe scripts/inspect_postgres.py --bin-dir scratch/pg-inspection/runtime/pgsql/bin --tb=short
.\.venv-inspection\Scripts\python.exe scripts/inspect_offline.py tests/phase_b/test_stage9_live_supabase_verification.py::test_09_frontend_bundle_secret_hygiene -q --tb=short
.\.venv-inspection\Scripts\python.exe -m compileall -q backend scripts tests
git diff --check
```

## Remaining skips, limitations and retained resources

The offline run's **26 skips** are explicit, not suppressed failures:

- **23 PostgreSQL cases** require the owned cluster option: 12 new migration/invitation/financial cases, nine original RLS cases and two original workspace/identity cases. All 23 execute and pass in the PostgreSQL selection.
- **One live Google Pub/Sub test** needs real GCP credentials/services, which were not used.
- **One live Supabase backup/restore test** needs a dedicated provider project, which was not used.
- **One Docker image-build test** skips because Docker's engine is unavailable. The portable database does not replace a container build.

The same broad command still excludes the nine-test live Supabase verification module. Its standalone offline-capable bundle check was run separately; its eight service/schema/provider checks remain unexecuted in their original live-environment form. Local PostgreSQL tests cover related database properties but do not verify Supabase service configuration, cloud storage, JWKS delivery or transaction poolers.

These results cover PostgreSQL 17.11 on this host, not a Supabase deployment/version, full sustained load, all deadlock schedules or provider outages. Frontend layout/accessibility, live model extraction, full browser workflow, managed storage, external identity/email verification and hosted demo remain unverified. The original non-INR, general tax, source freshness, receipt-consumption, quota and onboarding limitations remain. No live-demo or production-readiness claim is made.

**Harness incident:** an early runner argument bug invoked pytest without test paths and collected unrelated scratch scripts. Four collection errors included scratch Playwright scripts that launched a browser and attempted navigation to the unavailable local app. This violated the requested browser restriction; no application server was started. That invalid discovery run is not counted as PostgreSQL verification. Explicit paths plus `pytest.ini` now prevent accidental scratch collection. No further browser invocation was used.

**Cleanup exception:** all clusters/databases created by the corrected runner were stopped and removed automatically, and the manually initialized setup server was stopped. Automatic approval review rejected recursive deletion of `C:\Zamp Casse Study\scratch\pg-inspection\data` with “blocked by policy.” The two stopped, test-only setup directories are retained:

```text
C:\Zamp Casse Study\scratch\pg-inspection\data
C:\Zamp Casse Study\scratch\postgres-tests-659b910b99884354a925f1690554767c
```

Their resolved paths and absence of `postmaster.pid` were checked before cleanup was attempted. No other workspace data was deleted. Existing unfinished workspace/UI changes remain preserved.

Changes in this continuation: explicit fixtures and affected tests, new PostgreSQL tests/runner, reusable offline setup, `pytest.ini`, the guarded invitation path, migration 012 and this evidence/report. Reused Karpathy implementation/verification guidance from the original inspection; official sources are linked above. No new agent delegation or external account integration was used.
