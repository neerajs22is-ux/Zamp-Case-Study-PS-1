# Contributing & Engineering Standards

Thank you for contributing to the Autonomous Accounts Payable (AP) Command Center. This guide outlines repository structure, engineering conventions, security mandates, testing requirements, and safe modification procedures.

---

## 1. Repository Structure

```
├── backend/                       # FastAPI application
│   ├── api/v1/                   # REST API routes (auth, invoices, dashboard, webhooks)
│   ├── core/                     # Core services (config, auth, database, storage, gmail)
│   ├── models/                   # SQLAlchemy ORM models (invoice, enterprise, erp, audit)
│   └── migrations/               # Alembic database migrations
│
├── frontend/                      # React 19 / Vite SPA
│   ├── src/                      # TypeScript components, pages, and API client
│   └── dist/                     # Compiled production assets (built via npm run build)
│
├── engine/                        # Provider-independent business logic & AI adapters
│   ├── mantle_client.py          # AWS Bedrock Mantle client (Qwen 235B)
│   ├── palmyra_vision_adapter.py # AWS Bedrock Palmyra Vision 7B adapter
│   ├── indian_tax_rules.py       # GST arithmetic & match gate engine
│   ├── duplicate_detector.py     # Cryptographic SHA-256 deduplication
│   └── ocr_engine.py             # PDF text extraction & contrast pre-screening
│
├── docs/                          # Comprehensive technical documentation
│   ├── project-history/          # Preserved milestone reports (Phases A, C, D, E)
│   └── images/                   # Architecture diagrams & browser verification screenshots
│
├── tests/                         # Pytest test suite (256 items across Phases A–E)
├── Dockerfile                     # Multi-stage production container build
├── render.yaml                    # Render Web Service deployment blueprint
├── requirements.txt               # Locked Python dependencies
└── .env.example                   # Safe environment configuration template
```

---

## 2. Development Workflow

1. **Branching Strategy:**
   - Default branch: `master`
   - Feature branches: `feature/<short-description>`
   - Bugfix branches: `fix/<short-description>`
   - Handoff / Release branches: `handoff/<target-name>`

2. **Commit Message Conventions:**
   Follow Conventional Commits:
   - `feat(scope): add new capability`
   - `fix(scope): resolve defect or regression`
   - `docs(scope): update documentation or specifications`
   - `test(scope): add or improve test coverage`
   - `chore(scope): repository maintenance or dependency update`

---

## 3. Security Mandates (Zero Tolerance)

All contributors must adhere to strict security policies:

1. **Never Commit Secrets:**
   - Never commit `.env` files, API keys, AWS credentials, Supabase service-role keys, JWT secrets, or OAuth refresh tokens.
   - Run our automated secret scanner before staging files.
2. **Never Weaken Authentication:**
   - Do not introduce mock tokens or test harness tokens in non-test code.
   - All protected endpoints must require valid Bearer JWTs verified against Supabase Auth.
   - `ENABLE_DEV_SESSION` must remain `False` by default and barred in production.
3. **Preserve Audit Immutability:**
   - Do not alter or bypass the PostgreSQL trigger `prevent_audit_events_mutation()`.
   - Never write code that attempts to `UPDATE` or `DELETE` records from `audit_events`.
4. **Preserve Multi-Tenant Isolation:**
   - Every database query must be scoped by `org_id`. Never execute unscoped `SELECT` or `UPDATE` queries across tenant boundaries.

---

## 4. Testing & Quality Requirements

Before submitting changes or staging commits:

1. **Run Full Test Suite:**
   All 244 automated tests must pass:
   ```bash
   python -m pytest tests/ -v
   ```
2. **Verify Frontend Build:**
   The frontend build must succeed with 0 errors:
   ```bash
   cd frontend
   npm run build
   cd ..
   ```
3. **Verify Migrations:**
   If modifying SQLAlchemy models, generate and test Alembic migrations:
   ```bash
   alembic revision --autogenerate -m "description"
   alembic upgrade head
   alembic downgrade -1
   alembic upgrade head
   ```

---

## 5. UI/UX Audit & Redesign Guidelines (For Reviewing AI Models)

If you are an independent AI model conducting a UI/UX audit or redesign:
- Read [`docs/KNOWN_LIMITATIONS.md`](./docs/KNOWN_LIMITATIONS.md) first to understand existing operator pain points.
- Review the 3-pane workflow in [`frontend/src/pages/InvoiceDetailPage.tsx`](./frontend/src/pages/InvoiceDetailPage.tsx).
- Respect business terminology: `MATCH_CANDIDATE` (recommendation), `MANUALLY_APPROVED` (human sign-off), `AUTO_APPROVED` (STP only), `HOLD_PENDING_EVIDENCE` (query hold), `QUARANTINED` (non-payable document).
- Maintain statutory compliance: Action justification must remain mandatory for audit trails.
