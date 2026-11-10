# Local Development Setup Guide

This guide details how to install, configure, run, and verify the Autonomous Accounts Payable (AP) Command Center locally on Windows, macOS, or Linux.

---

## 1. System Requirements & Prerequisites

- **Python:** 3.10, 3.11, or 3.12 (Python 3.12 recommended).
- **Node.js:** v18, v20, or v22 LTS with `npm`.
- **Database:** PostgreSQL 15+ (local instance or cloud-hosted Supabase PostgreSQL).
- **Git:** 2.30+.
- **OCR System Dependency (Optional for Scanned Invoices):** `tesseract-ocr` installed and available on system `PATH` (for fallback local raster OCR).

---

## 2. Repository Setup & Environment Configuration

1. **Clone the repository:**
   ```bash
   git clone https://github.com/neerajs22is-ux/Zamp-Case-Study-PS-1-.git
   cd Zamp-Case-Study-PS-1-
   ```

2. **Set up Python Virtual Environment:**
   ```bash
   python -m venv venv
   # On Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Python Dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Install Frontend Dependencies:**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

5. **Configure Environment Variables:**
   ```bash
   cp .env.example .env
   ```
   Open `.env` in your editor and configure the operational values.
   For minimal local development:
   - Set `APP_ENV=development`
   - Set `DATABASE_URL` pointing to your local PostgreSQL or Supabase instance.
   - For AWS Bedrock Mantle document intelligence, provide `MANTLE_API_KEY` (or the pipeline will safely route documents to HITL if unconfigured).
   - Set `ENABLE_DEV_SESSION=true` to enable quick local authentication session minting on loopback (`127.0.0.1`).

---

## 3. Database Initialization & Migrations

The AP Command Center uses SQLAlchemy 2.0 and Alembic for database migrations.

1. **Apply Alembic Migrations:**
   ```bash
   alembic upgrade head
   ```

2. **Verify Database Connectivity:**
   ```bash
   python -c "from backend.core.database import check_database_health; print('Database Health:', check_database_health())"
   ```

3. **Seed Evaluation Tenant & Synthetic Reference Data (Optional):**
   To seed the `org_sme_eval` tenant with vendors, POs, GRNs, QC certificates, and persona users for testing:
   ```bash
   python engine/sme_eval_setup.py
   ```

---

## 4. Running the Application

The application consists of a FastAPI backend and a React 19 / Vite frontend.

### Option A: Running Backend and Frontend Concurrently (Development Mode)

1. **Start the FastAPI Backend Server:**
   ```bash
   # From repository root:
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   Backend will be live at:
   - API Root: `http://127.0.0.1:8000`
   - Health Probe: `http://127.0.0.1:8000/api/v1/health`
   - Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`

2. **Start the Vite Frontend Dev Server:**
   ```bash
   # In a separate terminal:
   cd frontend
   npm run dev
   ```
   Frontend will be live at `http://localhost:5173`.
   Vite is configured with a reverse-proxy routing all `/api` requests to `http://127.0.0.1:8000`.

### Option B: Unified Production / Single-Port Mode

FastAPI serves the compiled frontend production bundle directly from `frontend/dist`:

1. **Build the Frontend Assets:**
   ```bash
   npm --prefix frontend run build
   ```

2. **Launch Unified Local Server:**
   ```bash
   python run.py
   ```
   Access the Flagship application on `http://127.0.0.1:8001` and the Sandbox on `http://127.0.0.1:8001/sandbox`.
   
   For containerized production runtimes respecting `$PORT`:
   ```bash
   python run_production.py
   ```

---

## 5. Verification & Test Execution

Run the complete automated test suite (authoritative baseline: 520 passed, 0 failed, 43 skipped across 563 collected Python tests; 20 frontend unit tests):
```bash
python -m pytest tests/ -q
npm test --prefix frontend
```

Run specific test phases:
```bash
# Phase A: Security invariants, audit immutability, RBAC
python -m pytest tests/phase_a/ -v

# Phase B: Tenant isolation, Gmail OAuth, Cloud Run invariants
python -m pytest tests/phase_b/ -v

# Phase D: Modality classification & pipeline routing
python -m pytest tests/phase_d/ -v

# Phase E: Acceptance security guards & financial approval controls
python -m pytest tests/phase_e/ -v
```

---

## 6. Local SME Personas & Logging In

When `ENABLE_DEV_SESSION=true` is set in local development, navigate to `http://localhost:5173` (or `http://127.0.0.1:8000`). Click any persona quick-login button on the authentication screen:

| Persona Name | Email | Role | Granted Permissions |
| :--- | :--- | :--- | :--- |
| **Priya Sharma** | `sme_lead@company.internal` | `AP_LEAD` | View inbox, 2-column review workspace, approve invoices (< ₹5,00,000), place query holds, reject invoices. |
| **Rajesh Nair** | `sme_controller@company.internal` | `CONTROLLER` | Financial dashboards, metrics, secondary dual-control approval on high-value invoices ($\ge ₹5,00,000$). |
| **Ananya Iyer** | `sme_assoc@company.internal` | `AP_ASSOCIATE` | Document ingestion, viewing, initial triage. |
| **Vikram Malhotra** | `sme_auditor@company.internal` | `AUDITOR` | Strictly read-only inspection; all mutation actions return HTTP 403 Forbidden. |

---

## 7. Troubleshooting

- **Port Conflict on 8000 or 5173:**
  Identify and terminate conflicting processes:
  ```powershell
  # Windows PowerShell:
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
  ```
  ```bash
  # Linux / macOS:
  lsof -ti:8000 | xargs kill -9
  ```
- **PostgreSQL Connection Refused:**
  Verify that your connection string in `.env` uses `postgresql+psycopg://` and that network access / SSL modes (`sslmode=require`) match your provider.
- **Frontend Reverse Proxy 502 / Connection Refused:**
  Ensure the FastAPI backend server is running on `127.0.0.1:8000` before accessing the Vite dev server on `localhost:5173`.
