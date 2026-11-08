# Target Database Migration & Recovery Procedure (Revisions 011–013)

**Author:** Neeraj Shivkumar  
**Target Subsystem:** Multi-Tenant PostgreSQL Schema (`backend/migrations/`)  
**Scope:** Controlled verification, forward-repair strategy, and post-migration acceptance for Alembic migrations `011_require_assigned_roles`, `012_invitation_utc_expiry`, and `013_revoke_access_tokens`.  
**Safety Status:** Non-destructive; rejects unsafe DDL drops (`DROP ... CASCADE`) and manual `alembic_version` alterations.  

---

## 1. Target Database Identification & Connection Architecture

The flagship AP Command Center uses a dual-port PostgreSQL connection topology to separate low-latency serverless runtime queries from transactional schema migrations:

```
Runtime Application (FastAPI)
    │
    └── DATABASE_URL ────────► Port 6543 (PgBouncer Transaction Pooler)
                                aws-0-[REGION].pooler.supabase.com:6543/postgres
                                - Scale-to-zero serverless pooler
                                - Prepared statements disabled
                                - Barred from schema migrations (no transactional DDL locks)

Alembic Migration Runner / CLI
    │
    └── MIGRATION_DATABASE_URL ─► Port 5432 (Direct PostgreSQL Session)
                                db.[PROJECT_REF].supabase.co:5432/postgres
                                (or aws-0-[REGION].pooler.supabase.com:5432/postgres in session mode)
                                - Dedicated session-level locks
                                - Supports full transactional DDL (CREATE/ALTER TABLE, FUNCTIONS, RLS)
```

### Connection Resolution Order:
In [`backend/migrations/env.py`](../backend/migrations/env.py#L21-L32), Alembic resolves the connection string using the following strict precedence:
1. `settings.MIGRATION_DATABASE_URL` (Direct PostgreSQL port 5432)
2. `os.getenv("MIGRATION_DATABASE_URL")`
3. `config.get_main_option("sqlalchemy.url")` (from `alembic.ini`)
4. `settings.DATABASE_URL` (Fallback)
5. `os.getenv("DATABASE_URL")` (Fallback)
6. Fallback default: `"sqlite:///:memory:"` (Barred in production by `validate_production_invariants`)

> [!IMPORTANT]
> Alembic migrations **must never** be run against port 6543 (Transaction Pooler). PgBouncer in transaction mode does not support transactional advisory locks or multi-statement DDL transactions and will terminate mid-migration. Always specify `MIGRATION_DATABASE_URL` targeting direct port 5432.

---

## 2. Required Database Privileges & Roles

The schema enforces strict separation between the administrative migration executor and the least-privilege runtime application user:

| Role / User | Required Privileges | Justification |
| :--- | :--- | :--- |
| **Migration Administrator** (`postgres` / Cloud Admin) | `SUPERUSER` or `CREATEROLE`, `CREATE`, `USAGE` on schema `public`; owner of functions and tables | Must execute `CREATE OR REPLACE FUNCTION` (`SECURITY DEFINER`), create tables, create indexes, enable/force RLS, and grant/revoke object permissions. |
| **Runtime Application User** (`ap_app_user`) | Restricted DML: `SELECT, INSERT` on `revoked_access_tokens`; `SELECT, INSERT, UPDATE` on `model_quota_buckets`; standard tenant DML on domain tables | Follows principle of least privilege. Strictly barred from DDL, table drops, and cross-tenant reads. |

---

## 3. Existing Revision & Pending Migration Ledger

### Current Baseline:
- **Recorded Database State:** `010_identity_memberships` (observed 8 November 2026).
- **Core Schema in 010:** Organizations, users, identity memberships, domain AP tables, audit events, RLS policies.

### Pending Migrations (011 -> 012 -> 013):

```mermaid
flowchart LR
    A["010_identity_memberships<br/>(Current DB Baseline)"] --> B["011_require_assigned_roles<br/>(Function resolve_workspace_memberships)"]
    B --> C["012_invitation_utc_expiry<br/>(Function find_pending_invitation)"]
    C --> D["013_revoke_access_tokens<br/>(Tables: revoked_access_tokens, model_quota_buckets)"]
```

1. **`011_require_assigned_roles.py` (Down: `010_identity_memberships`):**
   - Replaces SQL function `resolve_workspace_memberships`.
   - Legacy users without explicit `role_assignments` return `NULL` and fail closed, preventing unauthorized write actions.
2. **`012_invitation_utc_expiry.py` (Down: `011_require_assigned_roles`):**
   - Replaces SQL function `find_pending_invitation`.
   - Enforces UTC comparison (`expires_at > (NOW() AT TIME ZONE 'UTC')`), removing server-session timezone ambiguity.
3. **`013_revoke_access_tokens.py` (Down: `012_invitation_utc_expiry`):**
   - Creates `revoked_access_tokens` table (`token_hash` primary key, `expires_at`, `revoked_at`).
   - Creates index `ix_revoked_access_tokens_expires_at`.
   - Creates `model_quota_buckets` table with tenant isolation RLS (`model_quota_tenant`).
   - Grants least-privilege permissions to `ap_app_user`.

---

## 4. Pre-Migration Verification & Backup Protocol

Before any migration is executed against the persistent database:

### Step 1: Logical Pre-Migration Backup (`pg_dump`)
```powershell
# Create an encrypted / compressed logical backup
pg_dump `
  --host=db.[PROJECT_REF].supabase.co `
  --port=5432 `
  --username=postgres `
  --dbname=postgres `
  --format=custom `
  --verbose `
  --file="backups/pre_migration_011_013_$(Get-Date -Format 'yyyyMMdd_HHmmss').dump"
```

### Step 2: Actual Restore Verification Against Isolated Target
> [!IMPORTANT]
> Archive readability (e.g. `pg_restore --list`) is **not** sufficient proof of recoverability. Corrupted blocks, missing roles, or broken extensions can still cause restore failures.
> Recoverability must be validated by performing an actual restore into an isolated disposable database:
```powershell
# 1. Restore the dump into an authorized isolated staging / test database
pg_restore `
  --host=127.0.0.1 `
  --port=5432 `
  --username=postgres `
  --dbname=ap_isolated_test `
  --clean --if-exists `
  --verbose `
  "backups/pre_migration_011_013_backup.dump"

# 2. Verify schema and row counts on the restored target
python -c "from sqlalchemy import create_engine, text; eng = create_engine('postgresql://postgres:test@127.0.0.1:5432/ap_isolated_test'); conn = eng.connect(); print('Restored Revision:', conn.execute(text('SELECT version_num FROM alembic_version')).scalar()); conn.close()"
```

### Step 3: Offline SQL Dry-Run Inspection
Generate the raw DDL script without touching the database:
```powershell
python -m alembic upgrade 010_identity_memberships:013_revoke_access_tokens --sql > scratch/migration_011_013_dry_run.sql
```
Review `scratch/migration_011_013_dry_run.sql` line by line to verify:
- No table drops or column deletions.
- RLS policies match `current_setting('app.current_org_id', true)`.
- Grant/Revoke statements scope correctly to `ap_app_user`.

---

## 5. Why Downgrades Raise RuntimeError & The Forward-Repair Strategy

### Intentional Invariant: Downgrade is Blocked by Design
In migrations 011, 012, and 013, the `downgrade()` function deliberately raises `RuntimeError`:
```python
# In 013_revoke_access_tokens.py:
def downgrade():
    raise RuntimeError("Removing token revocations would reactivate unexpired tokens; use a reviewed rollback after expiry.")

# In 011_require_assigned_roles.py:
def downgrade():
    raise RuntimeError("Restoring implicit role grants requires a reviewed authorization rollback.")
```

### Rejection of Unsafe Recovery Proposals:
- **Barred:** `DROP TABLE revoked_access_tokens CASCADE;`
- **Barred:** `DROP TABLE model_quota_buckets CASCADE;`
- **Barred:** Manually modifying `alembic_version` back to 010.

**Why Unsafe Drops Are Rejected:**
Dropping `revoked_access_tokens` deletes the session revocation ledger. Any compromised JWTs revoked by operators would immediately become valid again, compromising system security.

### Transaction Boundaries & Realistic Failure Behavior:
> [!WARNING]
> Do **not** assume that any migration failure magically restores the database to revision `010_identity_memberships`.
> Transaction boundaries depend strictly on execution granularity:
> 1. **Batch Execution (`alembic upgrade head`):** Alembic wraps the entire migration run in a single `context.begin_transaction()` block. If an unhandled PostgreSQL DDL error occurs midway through 013, PostgreSQL rolls back all uncommitted DDL within that active transaction, returning the schema to the state prior to that command.
> 2. **Incremental Execution:** If migrations are applied incrementally (e.g. upgrading to 011, then 012, then 013 in separate commands), revisions 011 and 012 have already committed. A subsequent failure during 013 rolls back *only* 013, leaving the database at revision `012_invitation_utc_expiry`.
> 3. **Connection Dropped / Network Abortion:** If a TCP connection drops mid-DDL or the database pooler kills a session, PostgreSQL automatically aborts in-flight uncommitted transactions, but locks may linger. The database state must be affirmatively verified via `python -m alembic current` rather than assumed.

### Safe Forward-Repair Recovery Procedure:
1. **Never Drop Revocation Ledger:**
   Never execute `DROP TABLE revoked_access_tokens CASCADE` or manually tamper with `alembic_version`. This avoids destroying the session revocation audit trail.
2. **Forward-Fix Migration:**
   If a post-migration defect is identified, deploy a forward migration (e.g. revision `014_...`) that corrects the constraint or policy while preserving audit trails and token revocations.
2. **Forward-Fix Migration:**
   If a post-migration issue is detected in staging or testing, the correct enterprise response is to deploy a forward migration (e.g. `014_fix_...`) that addresses the issue without destroying audit trails or revocation state.
3. **Disaster Recovery (Full Restore):**
   If an unrecoverable corruption occurs during deployment, recovery must use the verified pre-migration point-in-time backup rather than manual SQL surgery.

---

## 6. Post-Migration Acceptance Criteria

Following migration execution against any database clone or target instance, verify the following acceptance gates:

1. **Alembic Revision Check:**
   ```powershell
   python -m alembic current
   ```
   *Expected Output:* `013_revoke_access_tokens (head)`.
2. **Revocation Table Presence & Accessibility:**
   Verify `revoked_access_tokens` exists and accepts query without `UndefinedTable`:
   ```sql
   SELECT count(*) FROM public.revoked_access_tokens;
   ```
   *Expected Output:* `0` (or count of revoked tokens), no error.
3. **Model Quota Table & RLS Enforcement:**
   Verify `model_quota_buckets` has RLS enabled and forced:
   ```sql
   SELECT relname, relrowsecurity, relforcerowsecurity 
   FROM pg_class 
   WHERE relname = 'model_quota_buckets';
   ```
   *Expected Output:* `relrowsecurity = true`, `relforcerowsecurity = true`.
4. **Authenticated API Verification:**
   Execute an authenticated request using an authentic evaluator token:
   `GET /api/v1/dashboard/metrics` and `GET /api/v1/inbox` must return `HTTP 200 OK` rather than `HTTP 503 Service Unavailable`.

---

## 7. Isolated Hosted Evaluation Workspace Initialization

To support a live hosted demonstration without compromising production integrity:

1. **Strict Production Prohibition:**
   Synthetic seeding via `engine/sme_eval_setup.py` is permanently blocked in `production` and `staging` via `assert_seeding_permitted()`.
2. **Dedicated Evaluation Infrastructure:**
   The hosted evaluation environment must run against an isolated database instance or dedicated demo service instance.
3. **Explicit Initialization Command:**
   Initialization of synthetic fixtures for `org_sme_eval` is executed strictly in an authorized environment (`APP_ENV=development` or a dedicated isolated demo runner) before hosting deployment:
   ```powershell
   python -m engine.sme_eval_setup
   ```
4. **Tenant Fencing:**
   All synthetic fixtures are partitioned strictly within tenant `org_sme_eval`. Cross-tenant data leakage is prevented by PostgreSQL RLS.
