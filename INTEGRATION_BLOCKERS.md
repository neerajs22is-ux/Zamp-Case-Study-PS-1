# AP Command Center — External Dependencies & Integration Blockers

**Current State:** Phase A Foundation (All external integrations blocked pending credentials)  
**Security Policy:** Variable names and endpoint categories only; no secrets or tokens are stored in this file.

The table below lists all external integrations required for Phase B through Phase E operations. In accordance with the Production Truth Rules, an integration is reported as `CONNECTED` only after genuine authentication and a successful live API health check. Until valid credentials and network access are provisioned, each integration is marked `BLOCKED`.

---

| Integration Pillar | Required Configuration / Credentials | Status | Blocker Description & Next Action Required |
| :--- | :--- | :--- | :--- |
| **PostgreSQL Database** | `DATABASE_URL` (Host, Port, DB, User, Password with SSL mode) | **BLOCKED** | Live PostgreSQL instance not provisioned in current environment. Required before staging/production deployment. Schema migrations prepared in Alembic. |
| **Identity Provider (OIDC / SAML)** | `IDP_PROVIDER`, `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI` | **BLOCKED** | Customer enterprise SSO (Google Workspace / Azure AD / Okta) credentials not provisioned. Server-side token validation and role-mapping ready. |
| **Encrypted Object Storage** | `STORAGE_PROVIDER` (`s3` / `gcs` / `azure`), `STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` | **BLOCKED** | Private encrypted S3/GCS bucket not provisioned. Object storage adapter structure implemented; rejects local-disk fallback in production. |
| **Gmail OAuth 2.0 Ingestion** | `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `GMAIL_TARGET_MAILBOX` | **BLOCKED** | Google Cloud Project with `gmail.readonly` scope and authorized service account / mailbox not provisioned. Worker and sync cursor schema ready. |
| **SAP S/4HANA ERP Adapter** | `SAP_API_BASE_URL`, `SAP_AUTH_TYPE`, `SAP_CLIENT_ID`, `SAP_CLIENT_SECRET`, `SAP_COMPANY_CODE` | **BLOCKED** | Read-only OData/RFC API endpoint and credentials for PO, GRN, and QC tables not provisioned. Read-only snapshot schema ready. |
| **GSTN / GSTR-2B Verification** | `GST_API_PROVIDER`, `GST_API_ENDPOINT`, `GST_API_KEY`, `GST_API_SECRET` | **BLOCKED** | Authorized GST Suvidha Provider (GSP) or direct GSTN API credentials not provisioned. Format check only is insufficient for verification. |
| **MSME / Udyam Verification** | `UDYAM_API_PROVIDER`, `UDYAM_API_KEY` | **BLOCKED** | Authoritative Udyam registration verification API not provisioned. MSME status remains `UNKNOWN` pending authoritative verification source. |
| **Bank / Penny-Drop Verification** | `BANK_VERIFICATION_PROVIDER`, `BANK_API_KEY` | **BLOCKED** | Bank account verification / NPCI penny-drop API credentials not provisioned. |
| **Document AI / OCR Provider** | `OCR_PROVIDER` (`google_document_ai` / `aws_textract` / `azure_form_recognizer`), API Keys | **BLOCKED** | Customer-approved document intelligence service not configured. Text-layer extraction (`pdfplumber`) active for digital PDFs only. |
