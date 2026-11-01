# Production Deployment Runbook

This runbook specifies the containerization, environment provisioning, database migration, and operational health checks for deploying the Autonomous AP Command Center.

> [!NOTE]
> **Deployment Status:** As of Phase E closure, deployment to Render is **on HOLD** awaiting explicit executive sign-off. The application is packaged, tested, and container-ready.

---

## 1. Container Architecture & Dockerfile

The application uses a multi-stage Docker build ([`Dockerfile`](../Dockerfile)) that compiles the React 19 frontend and packages the FastAPI backend into a secure, non-root Linux container:

```dockerfile
# Stage 1: Build Frontend Assets
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Runtime
FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY backend/ ./backend/
COPY engine/ ./engine/
COPY alembic.ini ./
COPY run_production.py ./
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Non-root user execution
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["python", "run_production.py"]
```

---

## 2. Target Platforms: Render & Google Cloud Run

### Option A: Render Web Service (`render.yaml`)

The repository includes a ready-to-deploy [`render.yaml`](../render.yaml) blueprint:
- **Service Type:** Web Service (Docker runtime).
- **Plan:** Starter / Standard.
- **Port:** Configured dynamically via `PORT` environment variable.
- **Health Check Path:** `/api/v1/health`.

### Option B: Google Cloud Run (Mumbai `asia-south1`)

- **Container Port:** `8080`.
- **CPU / Memory:** 2 vCPU, 2 GB RAM.
- **Scaling:** Min 0 (scale-to-zero supported), Max 10.
- **Container Timeout:** 300 seconds.

---

## 3. Pre-Deployment Secret Provisioning

Before initiating deployment, configure the following environment secrets in your cloud provider:

1. `APP_ENV=production`
2. `SECRET_KEY`: Random 64-character hex string.
3. `DATABASE_URL`: Supabase Transaction Pooler connection string (`port 6543`).
4. `MIGRATION_DATABASE_URL`: Supabase Direct connection string (`port 5432`).
5. `SUPABASE_URL`: Supabase project URL.
6. `SUPABASE_ANON_KEY`: Public client key.
7. `SUPABASE_SERVICE_ROLE_KEY`: Server-side admin key.
8. `SUPABASE_JWT_SECRET`: Signing secret for Supabase Auth JWTs.
9. `MANTLE_API_KEY`: AWS Bedrock Mantle inference key.
10. `ENABLE_DEV_SESSION=false`: Strictly false in production.

---

## 4. Deployment Execution Steps

1. **Run Database Migrations:**
   Before routing live traffic, execute Alembic migrations against the direct database port:
   ```bash
   alembic upgrade head
   ```

2. **Trigger Container Build & Deploy:**
   ```bash
   # Render: Git push triggers automated build via render.yaml
   # Cloud Run:
   gcloud run deploy ap-command-center \
       --image gcr.io/<PROJECT_ID>/ap-command-center:latest \
       --region asia-south1 \
       --platform managed
   ```

3. **Verify Post-Deployment Health:**
   ```bash
   curl -s -f https://<DEPLOYED_DOMAIN>/api/v1/health | jq .
   ```
   Confirm that `overall_status` is `"READY"` and `database` is `"CONNECTED"`.

4. **Verify Liveness Probe:**
   ```bash
   curl -s -f https://<DEPLOYED_DOMAIN>/api/v1/liveness | jq .
   ```
   Confirm HTTP 200 with `status: "ALIVE"`.
