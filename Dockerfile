# =============================================================================
# Autonomous AP Command Center — Multi-Stage Production Container
# =============================================================================
# Architecture:
#   Stage 1: Node.js 20 LTS for compiling React/TypeScript frontend SPA.
#   Stage 2: Python 3.12-slim runtime for FastAPI backend and static serving.
# Security Invariants:
#   - Non-root unprivileged execution (user: appuser, uid: 1000).
#   - Least-privilege filesystem permissions.
#   - Cloud Run standard port 8080.
#   - Liveness healthcheck probe on /api/v1/liveness.
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Frontend SPA Builder
# -----------------------------------------------------------------------------
FROM node:20-slim AS frontend-builder

WORKDIR /build/frontend

# Install dependencies with frozen lockfile
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# Copy frontend source code and compile production assets
COPY frontend/ ./
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2: Production Python Application Runtime
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runner

# Container environment flags
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    APP_ENV=production \
    APP_HOST=0.0.0.0

# Install minimal OS runtime dependencies and certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libpq5 \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user and group (UID/GID 1000)
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -m -s /bin/bash appuser

WORKDIR /app

# Install Python production dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy compiled frontend assets from Stage 1 builder
COPY --from=frontend-builder --chown=appuser:appgroup /build/frontend/dist ./frontend/dist

# Copy application source code, Alembic migrations, and launcher
COPY --chown=appuser:appgroup backend/ ./backend/
COPY --chown=appuser:appgroup engine/ ./engine/
COPY --chown=appuser:appgroup alembic.ini ./
COPY --chown=appuser:appgroup run_production.py ./

# Create backups directory with unprivileged user ownership
RUN mkdir -p /app/backups && chown -R appuser:appgroup /app/backups

# Switch to unprivileged user
USER appuser

# Expose Cloud Run default ingress port
EXPOSE 8080

# Container liveness health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/liveness || exit 1

# Launch production server via uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2", "--proxy-headers"]
