# Environment Variables Specification

This document provides a comprehensive reference for all configuration options supported by the Autonomous Accounts Payable (AP) Command Center.

Configuration is managed via Pydantic Settings in [`backend/core/config.py`](../backend/core/config.py). Variables are loaded from the environment or `.env` file.

---

## 1. Core Application Settings

| Variable | Type | Default | Allowed Values | Description |
| :--- | :---: | :---: | :---: | :--- |
| `APP_ENV` | `string` | `development` | `production`, `staging`, `development`, `test` | Runtime environment. Setting `production` enforces strict truth rules (rejects SQLite, requires external storage, bars dev endpoints). |
| `APP_NAME` | `string` | `"Autonomous AP Command Center"` | Free text | Application display title. |
| `APP_HOST` | `string` | `0.0.0.0` | IP Address | Host interface to bind server. |
| `APP_PORT` | `integer` | `8000` | Port number | TCP port to listen on. Automatically overridden by `PORT` if provided by platform (e.g. Cloud Run, Render). |
| `DEBUG` | `boolean` | `false` | `true`, `false` | Enables verbose stack traces in non-production environments. |
| `SECRET_KEY` | `string` | `dev-secret-...` | $\ge 32$ chars | Secret key used for cryptographic session signing and state nonces. In production, this must be a cryptographically random secret. |
| `BASE_URL` | `string` | `http://localhost:8000` | Valid URL | Canonical public URL used for OAuth callback redirection. |
| `APP_TIMEZONE` | `string` | `Asia/Kolkata` | IANA Timezone | Display timezone for financial timestamps, audit events, and statutory deadlines. |

---

## 2. Database Connection Separation

The application employs a 3-tier connection separation pattern for PostgreSQL:

| Variable | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `DATABASE_URL` | `string` | `None` | **Runtime Connection String:** Used for application transactions via connection pooler (e.g. Supabase Transaction Pooler on port 6543). SQLite is blocked in production. |
| `MIGRATION_DATABASE_URL`| `string` | `None` | **DDL Migration Connection String:** Used exclusively by Alembic for schema migrations via direct connection or session pooler (port 5432). |
| `BACKUP_DATABASE_URL` | `string` | `None` | **Backup & Recovery Connection String:** Used by CLI operator tools for pg_dump and cold backup streaming. |
| `DB_POOL_SIZE` | `integer` | `20` | Maximum number of permanent connections in SQLAlchemy connection pool. |
| `DB_MAX_OVERFLOW` | `integer` | `10` | Maximum number of transient overflow connections permitted during traffic spikes. |
| `DB_TIMEOUT_SECONDS` | `integer` | `30` | Connection checkout timeout before throwing operational database exception. |

---

## 3. Identity Provider & Authentication (Supabase Auth)

| Variable | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `IDP_PROVIDER` | `string` | `supabase_auth` | Active auth provider (`supabase_auth`, `google_workspace`, `oidc_generic`). |
| `SUPABASE_URL` | `string` | `None` | Supabase project URL (e.g. `https://<ref>.supabase.co`). |
| `SUPABASE_ANON_KEY` | `string` | `None` | Supabase public anonymous API key (client-safe). |
| `SUPABASE_SERVICE_ROLE_KEY`| `string` | `None` | Supabase service-role administrative key (**strictly server-side**). |
| `SUPABASE_JWT_SECRET` | `string` | `None` | Secret key used to sign and verify Supabase HS256 JWT tokens. |
| `SUPABASE_JWKS_URL` | `string` | `None` | URL endpoint serving public keys for asymmetric RS256/ES256 verification. |
| `SUPABASE_ISSUER` | `string` | `None` | Explicit trusted JWT issuer claim (`iss`). |
| `SUPABASE_AUDIENCE` | `string` | `authenticated`| Expected JWT audience claim (`aud`). |
| `LOCAL_AUTH_BYPASS` | `boolean` | `false` | Development-only testing bypass. **Strictly rejected in production.** |
| `ENABLE_DEV_SESSION` | `boolean` | `false` | Explicit feature flag controlling `POST /api/v1/auth/dev-session`. Must be `true` for local quick login. Strictly barred in staging/prod and external IPs. |

---

## 4. Encrypted Object Storage

| Variable | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `STORAGE_PROVIDER` | `string` | `supabase` | Active storage adapter (`supabase`, `s3`). |
| `SUPABASE_STORAGE_BUCKET`| `string` | `invoices` | Target Supabase storage bucket name for invoice files. |
| `STORAGE_REGION` | `string` | `ap-south-1` | Cloud storage region (e.g. AWS Mumbai). |
| `STORAGE_SIGNED_URL_EXPIRY_SECONDS`| `integer` | `900` | Signed URL expiration time in seconds (default: 15 minutes). |
| `MAX_UPLOAD_FILE_SIZE_BYTES` | `integer` | `52428800` | Hard cap on uploaded PDF file size (50 MB Supabase Free Tier limit). |

---

## 5. AWS Bedrock Mantle Document Intelligence (Qwen 235B)

| Variable | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `MANTLE_BASE_URL` | `string` | `https://bedrock-mantle.ap-south-1.api.aws/v1` | Bedrock Mantle API endpoint URL in AWS Mumbai (`ap-south-1`). |
| `MANTLE_API_KEY` | `string` | `None` | Bearer API credential for Bedrock Mantle inference. |
| `MANTLE_MODEL_ID` | `string` | `qwen.qwen3-235b-a22b-2507-v1:0` | Target 235-billion parameter foundation model ID. |
| `MANTLE_TIMEOUT_SECONDS` | `float` | `30.0` | Maximum network timeout for inference call before failing closed to HITL. |
| `MANTLE_MAX_TOKENS` | `integer` | `2048` | Maximum output tokens generated per invoice extraction call. |
| `MANTLE_TEMPERATURE` | `float` | `0.0` | Temperature setting (0.0 enforces deterministic structured JSON output). |
| `MANTLE_MAX_DOCUMENT_COST_USD` | `float` | `0.10` | Circuit-breaker spend ceiling per document. |
| `MANTLE_MONTHLY_BUDGET_USD` | `float` | `50.00` | Tenant-level monthly LLM cost ceiling. |

---

## 6. AWS Bedrock Palmyra Vision 7B Adapter

| Variable | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `ENABLE_PALMYRA_VISION` | `boolean` | `false` | Master feature flag for multimodal visual adapter. **Disabled by default.** |
| `PALMYRA_BASE_URL` | `string` | `https://bedrock-mantle.us-east-1.api.aws/v1` | Bedrock endpoint URL in AWS N. Virginia (`us-east-1`). |
| `PALMYRA_API_KEY` | `string` | `None` | Authentication credential for Palmyra endpoint. |
| `PALMYRA_MODEL_ID` | `string` | `writer.palmyra-vision-7b` | Model ID for Palmyra Vision 7B. |

---

## 7. Financial Control Policies & Tolerances

| Variable | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `DUAL_APPROVAL_THRESHOLD_INR` | `float` | `500000.00` | Invoices with net payable $\ge ₹5,00,000$ trigger mandatory dual control requiring secondary sign-off from `CONTROLLER`. |
| `RATE_TOLERANCE_PERCENT` | `float` | `1.50` | Maximum allowable unit rate variance percentage against agreed PO rate (e.g. 1.5%). |
| `ROUNDING_TOLERANCE_INR` | `float` | `20.00` | Maximum allowable penny/rounding discrepancy on GST or line totals in INR. |
| `DOCUMENT_RETENTION_DAYS` | `integer` | `2920` | Statutory retention policy (8 years / 2,920 days under Companies Act 2013). |
| `ENABLE_PERMANENT_PURGE` | `boolean` | `false` | Permanent deletion protection. Strictly disabled until certified. |

---

## 8. Gmail Ingestion & OAuth Integration (Optional)

| Variable | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `GMAIL_CLIENT_ID` | `string` | `None` | Google OAuth 2.0 Web Client ID. |
| `GMAIL_CLIENT_SECRET` | `string` | `None` | Google OAuth 2.0 Client Secret (**server-side only**). |
| `GMAIL_REDIRECT_URI` | `string` | `None` | Authorized OAuth redirect callback URL. |
| `GMAIL_ENCRYPTION_KEY` | `string` | `None` | 32-byte hex key used to encrypt OAuth refresh tokens stored in PostgreSQL. |
| `PUBSUB_TOPIC_NAME` | `string` | `None` | Google Cloud Pub/Sub topic receiving Gmail push notifications. |
| `PUBSUB_VERIFICATION_AUDIENCE` | `string` | `None` | Expected audience URL for Google Cloud Pub/Sub push HTTP requests. |
| `PUBSUB_SERVICE_ACCOUNT_EMAIL` | `string` | `None` | Google Service Account email authorized to push Pub/Sub webhook events. |
