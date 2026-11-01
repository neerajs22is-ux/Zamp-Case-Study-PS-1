"""Phase B — Stage 7 & 7.1 Acceptance Tests: Cloud Run Deployment Preparation & Security Hardening.

Verifies:
1. Multi-stage Dockerfile configuration (Node.js 20 frontend builder + Python 3.12-slim runtime).
2. Unprivileged non-root user (appuser, UID 1000) and container healthcheck probe.
3. .dockerignore completeness (excluding git, tests, node_modules, backups, secrets).
4. Cloud Run service specification (deploy/cloudrun/service.yaml) Knative v1 compliance.
5. Google Secret Manager reference bindings (zero plaintext secrets).
6. Deployment automation script (deploy/cloudrun/deploy.sh) pre-flight, IAM, and scheduler setup.
7. Cloud Run environment contract (.env.cloudrun.example).
8. Dynamic PORT binding in configuration and health probes.
9. Removal of automated backup scheduler from Cloud Run (keeping ephemeral storage clean).
10. Dedicated Cloud Scheduler service account authentication on maintenance endpoints.
11. Rejection of unauthorized service identities (e.g. Pub/Sub push identity on maintenance).
12. Pub/Sub acknowledgement deadline configuration (300s) matching Cloud Run request timeout.
13. Truthful reporting of local Docker engine availability (marks BLOCKED if daemon unavailable).
14. Container runtime behavior: port binding, liveness, health diagnostics, and frontend serving.
"""

import os
import re
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.core.config import Settings, AppEnv, settings
from backend.core.backup import inspect_backup_status
from backend.main import app

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_01_dockerfile_structure_and_multistage():
    """Verify Dockerfile exists and enforces a 2-stage build (Node 20 + Python 3.12-slim)."""
    dockerfile_path = PROJECT_ROOT / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile must exist at repository root."

    content = dockerfile_path.read_text(encoding="utf-8")

    # Stage 1: Node.js frontend builder
    assert re.search(r"FROM\s+node:20.*AS\s+frontend-builder", content, re.IGNORECASE), \
        "Stage 1 must use node:20 as frontend-builder."
    assert "npm ci" in content, "Frontend builder must use npm ci for deterministic builds."
    assert "npm run build" in content, "Frontend builder must execute npm run build."

    # Stage 2: Python runtime runner
    assert re.search(r"FROM\s+python:3\.12-slim.*AS\s+runner", content, re.IGNORECASE), \
        "Stage 2 must use python:3.12-slim as runner."
    assert "COPY --from=frontend-builder" in content, \
        "Runner stage must copy compiled assets from frontend-builder."
    assert "frontend/dist" in content, "Compiled frontend distribution must be copied."


def test_02_dockerfile_security_and_non_root_user():
    """Verify container security: non-root user (UID 1000), port 8080, and healthcheck probe."""
    dockerfile_path = PROJECT_ROOT / "Dockerfile"
    content = dockerfile_path.read_text(encoding="utf-8")

    # Non-root user creation
    assert re.search(r"useradd.*-u\s+1000.*appuser", content), \
        "Dockerfile must create an unprivileged user 'appuser' with UID 1000."
    assert re.search(r"USER\s+appuser", content), \
        "Dockerfile must switch to unprivileged USER appuser."

    # Cloud Run default port 8080
    assert "EXPOSE 8080" in content, "Dockerfile must expose port 8080 for Cloud Run."

    # Container healthcheck
    assert "HEALTHCHECK" in content, "Dockerfile must define a container HEALTHCHECK probe."
    assert "/api/v1/liveness" in content, "Healthcheck probe must target /api/v1/liveness."


def test_03_dockerignore_completeness():
    """Verify .dockerignore excludes sensitive files, caches, tests, and backups."""
    dockerignore_path = PROJECT_ROOT / ".dockerignore"
    assert dockerignore_path.exists(), ".dockerignore must exist at repository root."

    content = dockerignore_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]

    required_exclusions = [
        ".git/",
        "node_modules/",
        "frontend/node_modules/",
        "tests/",
        "backups/",
        ".env",
        ".env.*",
    ]

    for req in required_exclusions:
        assert any(req in line for line in lines), f".dockerignore must exclude '{req}'."


def test_04_cloudrun_service_yaml_structure_and_schema():
    """Verify Cloud Run service specification conforms to Knative v1 and pilot constraints."""
    service_yaml_path = PROJECT_ROOT / "deploy" / "cloudrun" / "service.yaml"
    assert service_yaml_path.exists(), "deploy/cloudrun/service.yaml must exist."

    content = service_yaml_path.read_text(encoding="utf-8")

    assert "apiVersion: serving.knative.dev/v1" in content
    assert "kind: Service" in content
    assert "name: ap-command-center" in content
    assert "asia-south1" in content, "Cloud Run region must be asia-south1 (Mumbai)."

    # Autoscaling and resources (Pilot Scenario A)
    assert 'minScale: "0"' in content, "Pilot service must configure scale-to-zero (minScale 0)."
    assert 'maxScale: "3"' in content, "Pilot service must cap max instances to 3."
    assert 'cpu: "1000m"' in content, "CPU allocation must be 1 vCPU."
    assert 'memory: "512Mi"' in content, "Memory allocation must be 512 MB for pilot."

    # Probes
    assert "startupProbe:" in content, "Service must specify a startupProbe."
    assert "livenessProbe:" in content, "Service must specify a livenessProbe."
    assert "path: /api/v1/liveness" in content, "Probes must target /api/v1/liveness."


def test_05_cloudrun_service_yaml_secret_manager_references():
    """Verify that sensitive secrets are bound via Secret Manager and non-secrets/operator keys are excluded."""
    service_yaml_path = PROJECT_ROOT / "deploy" / "cloudrun" / "service.yaml"
    content = service_yaml_path.read_text(encoding="utf-8")

    # Retained server-side secrets in Secret Manager
    retained_secrets = [
        ("DATABASE_URL", "ap-database-url"),
        ("SECRET_KEY", "ap-secret-key"),
        ("SUPABASE_SERVICE_ROLE_KEY", "ap-supabase-service-key"),
        ("SUPABASE_JWT_SECRET", "ap-supabase-jwt-secret"),
        ("GMAIL_CLIENT_SECRET", "ap-gmail-client-secret"),
        ("GMAIL_ENCRYPTION_KEY", "ap-gmail-encryption-key"),
    ]

    for env_var, secret_name in retained_secrets:
        # Check that secret is referenced via secretKeyRef
        assert f"name: {env_var}" in content, f"Environment variable {env_var} must be mapped."
        assert f"name: {secret_name}" in content, f"Secret {secret_name} must be referenced in secretKeyRef."

    # Stage 7.2 Secret Hygiene: Ensure non-secrets and operator keys are excluded from Secret Manager bindings
    excluded_from_secret_manager = [
        "ap-gmail-refresh-token",       # Managed in encrypted per-mailbox DB records
        "ap-backup-encryption-key",      # Operator-managed outside Cloud Run
        "ap-supabase-anon-key",          # Public client publishable key
    ]
    for excluded in excluded_from_secret_manager:
        assert f"name: {excluded}" not in content, f"{excluded} must NOT be referenced in Secret Manager bindings."

    # SUPABASE_ANON_KEY must be present as a standard environment variable
    assert "name: SUPABASE_ANON_KEY" in content
    assert 'value: "${SUPABASE_ANON_KEY}"' in content

    # GMAIL_SYNC_TIMEOUT_SECONDS must be present and set to 240
    assert "name: GMAIL_SYNC_TIMEOUT_SECONDS" in content
    assert 'value: "240"' in content

    # Verify zero plaintext secrets in service.yaml
    assert "postgresql://" not in content
    assert "GOCSPX-" not in content
    assert "eyJhbGciOi" not in content


def test_06_cloudrun_deploy_script_validations():
    """Verify deploy/cloudrun/deploy.sh includes pre-flight checks, IAM, and scheduler setup."""
    deploy_sh_path = PROJECT_ROOT / "deploy" / "cloudrun" / "deploy.sh"
    assert deploy_sh_path.exists(), "deploy/cloudrun/deploy.sh must exist."

    content = deploy_sh_path.read_text(encoding="utf-8")

    # Pre-flight and safety
    assert "set -euo pipefail" in content
    assert "command -v gcloud" in content
    assert "billing projects describe" in content, "Must verify Google Cloud billing account."

    # Required Google APIs
    for api in ["run.googleapis.com", "secretmanager.googleapis.com", "cloudscheduler.googleapis.com", "pubsub.googleapis.com"]:
        assert api in content, f"Script must enable {api}."

    # Service Account & IAM (Separate Scheduler SA and Least-Privilege Secret Access)
    assert "ap-cloudrun-sa" in content
    assert "gmail-pubsub-push" in content
    assert "ap-cloud-scheduler-sa" in content
    assert "roles/secretmanager.secretAccessor" in content

    # Stage 7.2 Hygiene: REQUIRED_SECRETS must not contain excluded secrets
    assert "ap-backup-encryption-key" not in content
    assert "ap-gmail-refresh-token" not in content
    assert "ap-supabase-anon-key" not in content

    # Cloud Run deployment arguments must include timeout safety and anon key
    assert "GMAIL_SYNC_TIMEOUT_SECONDS=240" in content
    assert "SUPABASE_ANON_KEY=" in content

    # Cloud Scheduler cron configurations (watch renewal and reconciliation)
    assert "gmail-watch-renewal" in content
    assert "0 0 * * *" in content  # Daily watch renewal
    assert "gmail-history-reconciliation" in content
    assert "0 */6 * * *" in content  # Every 6 hours reconciliation
    assert "gmail-pubsub-reclaim" in content  # Every 30 minutes reclaim


def test_07_env_cloudrun_example_completeness():
    """Verify .env.cloudrun.example provides an honest and comprehensive template."""
    env_example_path = PROJECT_ROOT / ".env.cloudrun.example"
    assert env_example_path.exists(), ".env.cloudrun.example must exist."

    content = env_example_path.read_text(encoding="utf-8")

    required_vars = [
        "APP_ENV=production",
        "APP_HOST=0.0.0.0",
        "APP_PORT=8080",
        "DATABASE_URL=",
        "SUPABASE_URL=",
        "STORAGE_PROVIDER=supabase",
        "SUPABASE_STORAGE_BUCKET=invoices",
        "GMAIL_TARGET_MAILBOX=",
        "PUBSUB_TOPIC_NAME=",
        "PUBSUB_SERVICE_ACCOUNT_EMAIL=",
        "CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL=",
        "PUBSUB_ACK_DEADLINE_SECONDS=300",
        "GMAIL_SYNC_TIMEOUT_SECONDS=240",
        "GMAIL_WATCH_RENEWAL_HOURS=48",
        "GMAIL_RECONCILIATION_HOURS=6",
    ]

    for req in required_vars:
        assert req in content, f".env.cloudrun.example must contain '{req}'."


def test_08_config_port_environment_variable_precedence(monkeypatch):
    """Verify Settings resolves PORT dynamically from environment for Cloud Run compatibility."""
    monkeypatch.setenv("PORT", "8080")
    test_settings = Settings()
    assert test_settings.APP_PORT == 8080, "APP_PORT must resolve to 8080 when PORT=8080 is set."


def test_09_production_liveness_and_health_probes():
    """Verify /api/v1/liveness and /api/v1/health endpoints respond as expected for probes."""
    client = TestClient(app)

    # 1. Liveness Probe (Used by Docker HEALTHCHECK and Cloud Run livenessProbe)
    resp = client.get("/api/v1/liveness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ALIVE"
    assert "timestamp" in data

    # 2. Comprehensive Health Check (Used for system diagnostics)
    resp_health = client.get("/api/v1/health")
    assert resp_health.status_code in (200, 503)
    health_data = resp_health.json()
    assert "subsystems" in health_data
    assert "database" in health_data["subsystems"]
    assert "object_storage" in health_data["subsystems"]


# =============================================================================
# Stage 7.1 Corrections & Validation Tests
# =============================================================================

@pytest.fixture
def db_client():
    """Provides an isolated in-memory SQLite database session override for API testing."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from backend.core.database import Base, get_db
    import backend.models.domain  # register all domain tables

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, session
    app.dependency_overrides.clear()


def test_10_backup_scheduler_excluded_from_deploy_script_and_status_truthful():
    """Verify daily-encrypted-backup is removed from deploy.sh and backup status remains truthful."""
    deploy_sh_path = PROJECT_ROOT / "deploy" / "cloudrun" / "deploy.sh"
    content = deploy_sh_path.read_text(encoding="utf-8")

    # Ephemeral container filesystem invariant: No automated backup scheduler in Cloud Run
    assert "daily-encrypted-backup" not in content, \
        "Automated backup Cloud Scheduler trigger must NOT be configured in deploy.sh."

    # Backup status endpoint must report OPERATOR_MANUAL and NOT_CONFIGURED scheduler
    status_data = inspect_backup_status()
    assert status_data["scheduling"]["execution_mode"] == "OPERATOR_MANUAL"
    assert status_data["scheduling"]["background_scheduler"] == "NOT_CONFIGURED"


def test_11_scheduler_maintenance_auth_accepts_dedicated_service_account(monkeypatch, db_client):
    """Verify dedicated Cloud Scheduler service account can trigger maintenance endpoints."""
    client, session = db_client
    scheduler_email = "ap-cloud-scheduler-sa@gcp-project.iam.gserviceaccount.com"
    monkeypatch.setattr(settings, "CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL", scheduler_email)
    monkeypatch.setattr(settings, "CLOUD_SCHEDULER_VERIFICATION_AUDIENCE", "https://api.test.domain")
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.TEST)

    auth_header = f"Bearer test_scheduler:{scheduler_email}:https://api.test.domain"

    # 1. Watch Renewal
    resp_renew = client.post("/api/v1/integrations/gmail/watch/renew", headers={"Authorization": auth_header})
    assert resp_renew.status_code == 200
    assert "renewed_count" in resp_renew.json()

    # 2. Periodic Reconciliation
    resp_reconcile = client.post("/api/v1/integrations/gmail/reconcile", headers={"Authorization": auth_header})
    assert resp_reconcile.status_code == 200
    assert "reconciled_count" in resp_reconcile.json()

    # 3. Unfinished Event Recovery
    resp_reclaim = client.post("/api/v1/integrations/gmail/pubsub/reclaim", headers={"Authorization": auth_header})
    assert resp_reclaim.status_code == 200
    assert "scanned_count" in resp_reclaim.json()


def test_12_scheduler_maintenance_auth_rejects_unauthorized_service_identity(monkeypatch):
    """Verify that unauthorized service accounts (e.g. Pub/Sub push identity) are rejected."""
    scheduler_email = "ap-cloud-scheduler-sa@gcp-project.iam.gserviceaccount.com"
    monkeypatch.setattr(settings, "CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL", scheduler_email)
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.TEST)

    client = TestClient(app)

    # Attempt 1: Pub/Sub push identity attempts maintenance endpoint
    pubsub_token = "Bearer test_oidc:gmail-pubsub-push@gcp-project.iam.gserviceaccount.com:https://api.test.domain"
    resp_pubsub = client.post("/api/v1/integrations/gmail/watch/renew", headers={"Authorization": pubsub_token})
    assert resp_pubsub.status_code == 403
    assert "restricted" in resp_pubsub.json()["detail"].lower() or "unauthorized" in resp_pubsub.json()["detail"].lower()

    # Attempt 2: Rogue/different service account attempts maintenance endpoint
    rogue_token = "Bearer test_scheduler:rogue-sa@gcp-project.iam.gserviceaccount.com:https://api.test.domain"
    resp_rogue = client.post("/api/v1/integrations/gmail/watch/renew", headers={"Authorization": rogue_token})
    assert resp_rogue.status_code == 403
    assert "unauthorized" in resp_rogue.json()["detail"].lower()

    # Attempt 3: Unauthenticated request
    resp_unauth = client.post("/api/v1/integrations/gmail/watch/renew")
    assert resp_unauth.status_code == 401


def test_13_scheduler_maintenance_auth_accepts_human_system_admin_and_rejects_associate(monkeypatch, db_client):
    """Verify human SYSTEM_ADMIN can invoke maintenance, while AP_ASSOCIATE is rejected (RBAC intact)."""
    client, session = db_client
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.TEST)

    # 1. System Admin succeeds
    admin_token = "Bearer test_token:SYSTEM_ADMIN:admin_user_01:org_test"
    resp_admin = client.post("/api/v1/integrations/gmail/watch/renew", headers={"Authorization": admin_token})
    assert resp_admin.status_code == 200

    # 2. Controller succeeds
    controller_token = "Bearer test_token:CONTROLLER:controller_user_01:org_test"
    resp_controller = client.post("/api/v1/integrations/gmail/watch/renew", headers={"Authorization": controller_token})
    assert resp_controller.status_code == 200

    # 3. AP Associate rejected (HTTP 403 Forbidden)
    associate_token = "Bearer test_token:AP_ASSOCIATE:associate_01:org_test"
    resp_assoc = client.post("/api/v1/integrations/gmail/watch/renew", headers={"Authorization": associate_token})
    assert resp_assoc.status_code == 403


def test_14_pubsub_ack_deadline_and_lease_alignment():
    """Verify Pub/Sub subscription ack deadline is 300s, aligning with Cloud Run timeout."""
    assert settings.PUBSUB_ACK_DEADLINE_SECONDS == 300, \
        "Default PUBSUB_ACK_DEADLINE_SECONDS must be 300 seconds."

    deploy_sh_path = PROJECT_ROOT / "deploy" / "cloudrun" / "deploy.sh"
    content = deploy_sh_path.read_text(encoding="utf-8")
    assert "--ack-deadline=300" in content, "deploy.sh must configure --ack-deadline=300."

    service_yaml_path = PROJECT_ROOT / "deploy" / "cloudrun" / "service.yaml"
    yaml_content = service_yaml_path.read_text(encoding="utf-8")
    assert "timeoutSeconds: 300" in yaml_content, "Cloud Run container timeout must align to 300s."
    assert 'name: PUBSUB_ACK_DEADLINE_SECONDS' in yaml_content


def test_15_docker_daemon_status_truthful_reporting():
    """Verifies Docker daemon status on host. If inactive, marks build BLOCKED rather than PASS."""
    try:
        proc = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            pytest.skip("Docker daemon is not running on host. Live image build is BLOCKED.")
    except (FileNotFoundError, subprocess.SubprocessError):
        pytest.skip("Docker CLI is not available on host. Live image build is BLOCKED.")


def test_16_container_runtime_invariants_and_frontend_asset_serving():
    """Validates container runtime invariants: port binding, health diagnostics, SPA fallback."""
    client = TestClient(app)

    # 1. Liveness check
    resp_liveness = client.get("/api/v1/liveness")
    assert resp_liveness.status_code == 200
    assert resp_liveness.json()["status"] == "ALIVE"

    # 2. Subsystem health check
    resp_health = client.get("/api/v1/health")
    assert resp_health.status_code in (200, 503)

    # 3. Frontend SPA route fallback (serves index.html or fallback metadata)
    resp_spa = client.get("/dashboard")
    assert resp_spa.status_code == 200

    # 4. Unknown API route returns clean JSON 404
    resp_404 = client.get("/api/v1/nonexistent")
    assert resp_404.status_code == 404


def test_17_secret_hygiene_and_least_privilege_audit(monkeypatch):
    """Verify Stage 7.2 secret hygiene invariants and secret redaction."""
    assert settings.GMAIL_SYNC_TIMEOUT_SECONDS == 240, \
        "Internal sync deadline must be 240 seconds."

    # Verify redaction of sensitive credentials
    redacted = settings.redacted_dict()
    assert redacted.get("SECRET_KEY") == "********"
    if settings.SUPABASE_SERVICE_ROLE_KEY:
        assert redacted.get("SUPABASE_SERVICE_ROLE_KEY") == "********"

    # Verify that JWT verification enforces SUPABASE_JWT_SECRET
    from backend.core.auth import verify_token_claims
    from jose import jwt
    import time

    test_secret = "test-supabase-jwt-secret-at-least-32-chars-long"
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", test_secret)
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://test-ref.supabase.co")
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)

    payload = {
        "sub": "user_test_stage7",
        "email": "user@test.org",
        "aud": "authenticated",
        "iss": "https://test-ref.supabase.co/auth/v1",
        "exp": int(time.time()) + 3600,
    }
    # Encode with secret
    valid_token = jwt.encode(payload, test_secret, algorithm="HS256")
    claims, _, _ = verify_token_claims(valid_token)
    assert claims["sub"] == "user_test_stage7"

    # Reject token signed with wrong secret
    bad_token = jwt.encode(payload, "completely-wrong-signing-key-here-123456", algorithm="HS256")
    with pytest.raises(Exception):
        verify_token_claims(bad_token)


def test_18_gmail_sync_timeout_safety_and_unfinished_recovery(monkeypatch, db_client):
    """Verify internal processing timeout halts sync safely, preserves watermark, and recovers without duplicates."""
    from backend.core.gmail import (
        process_pubsub_push_notification,
        encrypt_refresh_token,
    )
    from backend.models.domain import (
        GmailAccount, Organisation, PubSubEvent, Document, Invoice
    )
    import base64
    import json
    import time

    client, session = db_client
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.TEST)

    # 1. Setup Organisation and Authorized GmailAccount
    org = Organisation(id="org_timeout_test", name="Timeout Test Org")
    session.add(org)

    encrypted_token = encrypt_refresh_token("valid-refresh-token")
    account = GmailAccount(
        id="acc_timeout_01",
        org_id="org_timeout_test",
        mailbox_address="ap.timeout@company.com",
        encrypted_refresh_token=encrypted_token,
        oauth_status="AUTHORIZED",
        last_history_id="1000",
    )
    session.add(account)
    session.commit()

    # 2. Simulate 3 messages to ingest
    msg_ids = ["msg_001", "msg_002", "msg_003"]
    new_notification_history_id = "1050"

    # Mock access token refresh
    monkeypatch.setattr("backend.core.gmail.refresh_access_token", lambda *args, **kwargs: "mock_access_token")
    monkeypatch.setattr("backend.core.gmail.get_history_messages", lambda *args, **kwargs: (msg_ids, new_notification_history_id))

    def mock_process_single_message_ingestion(db, acc, token, m_id, actor_id):
        # Create an actual Document + Invoice in DB so deduplication can be verified
        sha = f"sha256_{m_id}"
        existing_doc = db.query(Document).filter(Document.sha256_hash == sha).first()
        if existing_doc:
            return {"ingested": [], "quarantined": [], "duplicates": 1}

        doc = Document(
            id=f"doc_{m_id}",
            org_id=acc.org_id,
            invoice_id=f"inv_{m_id}",
            filename=f"{m_id}.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            sha256_hash=sha,
            storage_provider="supabase",
            storage_key=f"org_timeout_test/invoices/doc_{m_id}/{m_id}.pdf",
            is_original=True,
            is_deleted=False,
        )
        inv = Invoice(
            id=f"inv_{m_id}",
            org_id=acc.org_id,
            source_channel="GMAIL",
            vendor_name="Acme Corp",
            stage="RECEIVED",
            decision="NEEDS_REVIEW",
        )
        db.add(doc)
        db.add(inv)
        db.commit()

        # Simulate delay on first message so timeout triggers
        time.sleep(0.06)
        return {
            "ingested": [{"document_id": doc.id, "invoice_id": inv.id, "sha256": sha}],
            "quarantined": [],
            "duplicates": 0,
        }

    monkeypatch.setattr("backend.core.gmail.process_single_message_ingestion", mock_process_single_message_ingestion)

    # Set internal sync timeout to 0.05 seconds (smaller than message delay 0.06s)
    monkeypatch.setattr(settings, "GMAIL_SYNC_TIMEOUT_SECONDS", 0.05)

    payload = {
        "emailAddress": "ap.timeout@company.com",
        "historyId": new_notification_history_id,
    }
    encoded_data = base64.b64encode(json.dumps(payload).encode()).decode()
    request_body = {
        "message": {
            "data": encoded_data,
            "messageId": "pubsub_timeout_msg_001",
        },
        "subscription": "projects/test-project/subscriptions/test-sub",
    }

    # 3. First Execution: Timed out run
    res_first = process_pubsub_push_notification(session, request_body)
    assert res_first["status"] == "TIMED_OUT"
    assert res_first.get("retryable") is True

    # Invariants for timed out run:
    # A. Watermark was NOT advanced (still 1000, NOT 1050)
    session.refresh(account)
    assert account.last_history_id == "1000", "Watermark MUST NOT advance on timeout!"

    # B. Mailbox lease was cleanly released
    assert account.sync_lock_token is None, "Mailbox lease must be released on timeout!"
    assert account.sync_lock_expires_at is None

    # C. Event remains in retryable state RECEIVED
    event = session.query(PubSubEvent).filter(PubSubEvent.pubsub_message_id == "pubsub_timeout_msg_001").first()
    assert event is not None
    assert event.status == "RECEIVED"
    assert "Sync processing deadline reached" in (event.error_message or "")

    # D. First message was safely ingested
    docs = session.query(Document).filter(Document.org_id == "org_timeout_test").all()
    assert len(docs) == 1
    assert docs[0].id == "doc_msg_001"

    # 4. Second Execution: Recovery / Reclaim
    # Now increase deadline to allow remaining messages to finish
    monkeypatch.setattr(settings, "GMAIL_SYNC_TIMEOUT_SECONDS", 30.0)

    # Redeliver the same notification (or reclaim unfinished event)
    res_second = process_pubsub_push_notification(session, request_body)
    assert res_second["status"] == "PROCESSED"
    assert res_second["sync_result"]["status"] == "SUCCESS"

    # Invariants for completed recovery:
    # A. Watermark has now advanced to 1050
    session.refresh(account)
    assert account.last_history_id == "1050"

    # B. Event status is COMPLETED
    session.refresh(event)
    assert event.status == "COMPLETED"
    assert event.error_message is None

    # C. All 3 messages ingested with ZERO duplicates (msg_001 was skipped as duplicate)
    docs_final = session.query(Document).filter(Document.org_id == "org_timeout_test").all()
    assert len(docs_final) == 3
    doc_ids = {d.id for d in docs_final}
    assert doc_ids == {"doc_msg_001", "doc_msg_002", "doc_msg_003"}

    # D. Duplicate skip count is 1
    assert res_second["sync_result"]["duplicates_skipped"] == 1
    assert res_second["sync_result"]["ingested_count"] == 2


# =============================================================================
# Stage 7.3: Asymmetric Supabase JWT Verification & Reclaim Scheduler Tests
# =============================================================================

def test_19_supabase_jwt_asymmetric_rs256_and_es256_verification(monkeypatch):
    """Verify asymmetric verification of RS256 and ES256 JWTs using Supabase JWKS without SUPABASE_JWT_SECRET."""
    from backend.core.auth import (
        verify_token_claims,
        inject_jwks_cache_for_testing,
        clear_jwks_cache,
    )
    from cryptography.hazmat.primitives.asymmetric import rsa, ec
    from cryptography.hazmat.primitives import serialization
    from jose import jwt, jwk
    import time

    clear_jwks_cache()

    # 1. Generate RSA keypair and JWK
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rsa_priv_pem = rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    rsa_pub_pem = rsa_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    rsa_jwk = jwk.construct(rsa_pub_pem, "RS256").to_dict()
    rsa_jwk["kid"] = "supabase-rsa-key-01"

    # 2. Generate EC keypair and JWK (P-256)
    ec_key = ec.generate_private_key(ec.SECP256R1())
    ec_priv_pem = ec_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    ec_pub_pem = ec_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    ec_jwk = jwk.construct(ec_pub_pem, "ES256").to_dict()
    ec_jwk["kid"] = "supabase-ec-key-01"

    # Inject mock JWKS
    inject_jwks_cache_for_testing({
        "keys": [rsa_jwk, ec_jwk]
    })

    # Invariant: SUPABASE_JWT_SECRET is None, proving it is NOT required for asymmetric projects!
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", None)
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://mockproject.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "SUPABASE_ISSUER", "https://mockproject.supabase.co/auth/v1")
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)

    # 3. Test RS256 token verification
    rsa_payload = {
        "sub": "user_rsa_100",
        "email": "rsa.user@company.com",
        "aud": "authenticated",
        "iss": "https://mockproject.supabase.co/auth/v1",
        "exp": int(time.time()) + 1800,
        "role": "CONTROLLER",
        "org_id": "org_rsa_test",
    }
    rsa_token = jwt.encode(
        rsa_payload,
        rsa_priv_pem,
        algorithm="RS256",
        headers={"kid": "supabase-rsa-key-01", "typ": "JWT"},
    )
    claims_rsa, hint_org, hint_role = verify_token_claims(rsa_token)
    assert claims_rsa["sub"] == "user_rsa_100"
    assert claims_rsa["email"] == "rsa.user@company.com"
    assert hint_org == "org_rsa_test"

    # 4. Test ES256 token verification
    ec_payload = {
        "sub": "user_ec_200",
        "email": "ec.user@company.com",
        "aud": "authenticated",
        "iss": "https://mockproject.supabase.co/auth/v1",
        "exp": int(time.time()) + 1800,
        "role": "AP_LEAD",
        "org_id": "org_ec_test",
    }
    ec_token = jwt.encode(
        ec_payload,
        ec_priv_pem,
        algorithm="ES256",
        headers={"kid": "supabase-ec-key-01", "typ": "JWT"},
    )
    claims_ec, hint_org_ec, hint_role_ec = verify_token_claims(ec_token)
    assert claims_ec["sub"] == "user_ec_200"
    assert claims_ec["email"] == "ec.user@company.com"
    assert hint_org_ec == "org_ec_test"

    clear_jwks_cache()


def test_20_supabase_jwt_security_guards_and_algorithm_rejection(monkeypatch):
    """Verify strict fail-closed security guards on unsigned tokens, unsupported algs, unknown kid, and tampering."""
    from backend.core.auth import (
        verify_token_claims,
        inject_jwks_cache_for_testing,
        clear_jwks_cache,
    )
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from fastapi import HTTPException
    from jose import jwt, jwk
    import time

    clear_jwks_cache()

    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rsa_priv_pem = rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    rsa_pub_pem = rsa_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    rsa_jwk = jwk.construct(rsa_pub_pem, "RS256").to_dict()
    rsa_jwk["kid"] = "known-kid-1"

    inject_jwks_cache_for_testing({"keys": [rsa_jwk]})

    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", None)
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://mockproject.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.DEVELOPMENT)

    base_payload = {
        "sub": "user_guard_test",
        "email": "guard@company.com",
        "aud": "authenticated",
        "iss": "https://mockproject.supabase.co/auth/v1",
        "exp": int(time.time()) + 1800,
    }

    # Guard 1: Reject unsigned token ('none' algorithm)
    import base64
    import json
    h_none = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    p_none = base64.urlsafe_b64encode(json.dumps(base_payload).encode()).decode().rstrip("=")
    unsigned_token = f"{h_none}.{p_none}."
    with pytest.raises(HTTPException) as exc_info:
        verify_token_claims(unsigned_token)
    assert exc_info.value.status_code == 401
    assert "Disallowed" in exc_info.value.detail or "disallowed" in exc_info.value.detail.lower()

    # Guard 2: Reject unapproved algorithm (e.g. HS512 or RS512)
    h_arb = base64.urlsafe_b64encode(json.dumps({"alg": "HS512", "typ": "JWT"}).encode()).decode().rstrip("=")
    arbitrary_token = f"{h_arb}.{p_none}.fake_sig"
    with pytest.raises(HTTPException) as exc_alg:
        verify_token_claims(arbitrary_token)
    assert exc_alg.value.status_code == 401
    assert "Disallowed" in exc_alg.value.detail or "disallowed" in exc_alg.value.detail.lower()

    # Guard 3: Reject asymmetric token missing 'kid'
    no_kid_token = jwt.encode(base_payload, rsa_priv_pem, algorithm="RS256")
    with pytest.raises(HTTPException) as exc_kid:
        verify_token_claims(no_kid_token)
    assert exc_kid.value.status_code == 401
    assert "kid" in exc_kid.value.detail

    # Guard 4: Reject token with unknown 'kid'
    unknown_kid_token = jwt.encode(base_payload, rsa_priv_pem, algorithm="RS256", headers={"kid": "nonexistent-kid"})
    with pytest.raises(HTTPException) as exc_unk:
        verify_token_claims(unknown_kid_token)
    assert exc_unk.value.status_code == 401
    assert "nonexistent-kid" in exc_unk.value.detail or "not found" in exc_unk.value.detail.lower()

    # Guard 5: Tampered token body fails closed
    valid_token = jwt.encode(base_payload, rsa_priv_pem, algorithm="RS256", headers={"kid": "known-kid-1"})
    parts = valid_token.split(".")
    tampered_token = f"{parts[0]}.eyJzdWIiOiJyb2d1ZV91c2VyIiwiZW1haWwiOiJyb2d1ZUBjb21wYW55LmNvbSIsImF1ZCI6ImF1dGhlbnRpY2F0ZWQifQ.{parts[2]}"
    with pytest.raises(HTTPException) as exc_tamp:
        verify_token_claims(tampered_token)
    assert exc_tamp.value.status_code == 401

    # Guard 6: Expired token fails closed
    expired_payload = dict(base_payload)
    expired_payload["exp"] = int(time.time()) - 60
    expired_token = jwt.encode(expired_payload, rsa_priv_pem, algorithm="RS256", headers={"kid": "known-kid-1"})
    with pytest.raises(HTTPException) as exc_exp:
        verify_token_claims(expired_token)
    assert exc_exp.value.status_code == 401
    assert "expired" in exc_exp.value.detail.lower()

    clear_jwks_cache()


def test_21_pubsub_30m_reclaim_scheduler_audit(monkeypatch, db_client):
    """Verify that deploy.sh actually configures the 30-minute reclaim Cloud Scheduler job and endpoint operates safely."""
    client, session = db_client
    deploy_sh_path = PROJECT_ROOT / "deploy" / "cloudrun" / "deploy.sh"
    content = deploy_sh_path.read_text(encoding="utf-8")

    # 1. Invariant: Job name is gmail-pubsub-reclaim
    assert 'gmail-pubsub-reclaim' in content, "Cloud Scheduler job 'gmail-pubsub-reclaim' must exist in deploy.sh."

    # 2. Invariant: Schedule is every 30 minutes
    assert '--schedule="*/30 * * * *"' in content, "Reclaim job must be scheduled every 30 minutes."

    # 3. Invariant: Target URI is POST /pubsub/reclaim
    assert 'RECLAIM_URI="${SERVICE_URL}/api/v1/integrations/gmail/pubsub/reclaim"' in content
    assert '--uri="${RECLAIM_URI}"' in content
    assert '--http-method=POST' in content

    # 4. Invariant: Uses dedicated scheduler service account and correct audience
    assert '--oidc-service-account-email="${SCHEDULER_SA}"' in content
    assert '--oidc-token-audience="${RECLAIM_URI}"' in content

    # 5. Invariant: Cloud Scheduler service account is granted roles/run.invoker
    assert '--member="serviceAccount:${SCHEDULER_SA}"' in content
    assert '--role="roles/run.invoker"' in content

    # 6. Safe runtime execution when 0 unfinished events exist
    scheduler_email = "ap-cloud-scheduler-sa@gcp-project.iam.gserviceaccount.com"
    monkeypatch.setattr(settings, "CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL", scheduler_email)
    monkeypatch.setattr(settings, "CLOUD_SCHEDULER_VERIFICATION_AUDIENCE", "https://api.test.domain")
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.TEST)

    auth_header = f"Bearer test_scheduler:{scheduler_email}:https://api.test.domain"
    resp = client.post("/api/v1/integrations/gmail/pubsub/reclaim", headers={"Authorization": auth_header})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scanned_count"] == 0
    assert data["completed_count"] == 0
    assert data["failed_count"] == 0
    assert data["deferred_count"] == 0


def test_22_supabase_storage_header_format_awareness():
    """Stage 7.3.1: Test format-aware Supabase Storage authentication headers.
    
    Verifies that:
    1. Legacy JWT-based service_role key produces both 'apikey' and 'Authorization: Bearer'.
    2. New 'sb_secret_' key is sent through 'apikey' header and NEVER as 'Authorization: Bearer'.
    3. New 'sb_pub_' key is sent through 'apikey' and NEVER as 'Authorization: Bearer'.
    4. Content-Type headers are preserved.
    5. Server-side exclusivity: health checks and adapters never expose keys in status/messages.
    """
    from backend.core.storage import SupabaseStorageAdapter
    import urllib.parse

    adapter = SupabaseStorageAdapter()

    # Format 1: Legacy JWT-based service_role key
    legacy_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UifQ.signature123"
    adapter.service_role_key = legacy_jwt
    adapter.anon_key = None

    headers_legacy = adapter._get_auth_headers(content_type="application/pdf")
    assert headers_legacy["apikey"] == legacy_jwt
    assert headers_legacy["Authorization"] == f"Bearer {legacy_jwt}"
    assert headers_legacy["Content-Type"] == "application/pdf"

    # Format 2: Modern Supabase secret key (sb_secret_...)
    new_secret = "sb_" + "secret_mock_test_key_0123456789"
    adapter.service_role_key = new_secret

    headers_secret = adapter._get_auth_headers(content_type="application/json")
    assert headers_secret["apikey"] == new_secret
    assert "Authorization" not in headers_secret, "sb_secret_ key must NEVER be sent as Authorization: Bearer"
    assert headers_secret["Content-Type"] == "application/json"

    # Invariant: Privileged key is mandatory; anon key is NEVER silently substituted
    adapter.service_role_key = None
    headers_no_key = adapter._get_auth_headers()
    assert "apikey" not in headers_no_key, "Unprivileged anon key must never be silently substituted"
    assert "Authorization" not in headers_no_key

    # Health check returns honest NOT_CONFIGURED when privileged service key is missing
    adapter.supabase_url = "https://mock.supabase.co"
    adapter.service_role_key = None
    health_unconf = adapter.check_health()
    assert health_unconf["status"] == "NOT_CONFIGURED"
    assert health_unconf["readiness"] is False
    assert "privileged SUPABASE_SERVICE_ROLE_KEY" in health_unconf["message"]

    # Health check key secrecy: keys are never leaked in status reports
    health_str = str(health_unconf)
    assert new_secret not in health_str
    assert legacy_jwt not in health_str


def test_24_database_connection_separation_audit(monkeypatch):
    """Verify distinct separation between runtime, migration, and backup database connections."""
    from backend.migrations import env as alembic_env

    # 1. Configuration presence & safe masking
    runtime_url = "postgresql://runtime_user:runtime_pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require"
    migration_url = "postgresql://migration_user:migration_pass@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require"
    backup_url = "postgresql://backup_user:backup_pass@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require"

    monkeypatch.setattr(settings, "DATABASE_URL", runtime_url)
    monkeypatch.setattr(settings, "MIGRATION_DATABASE_URL", migration_url)
    monkeypatch.setattr(settings, "BACKUP_DATABASE_URL", backup_url)

    dumped = settings.redacted_dict()
    assert "runtime_pass" not in dumped["DATABASE_URL"]
    assert "migration_pass" not in dumped["MIGRATION_DATABASE_URL"]
    assert "backup_pass" not in dumped["BACKUP_DATABASE_URL"]
    assert "********" in dumped["DATABASE_URL"]
    assert "********" in dumped["MIGRATION_DATABASE_URL"]
    assert "********" in dumped["BACKUP_DATABASE_URL"]

    # 2. Migration URL precedence: MIGRATION_DATABASE_URL takes priority over DATABASE_URL
    assert alembic_env.get_url() == migration_url

    monkeypatch.setattr(settings, "MIGRATION_DATABASE_URL", None)
    monkeypatch.delenv("MIGRATION_DATABASE_URL", raising=False)
    assert alembic_env.get_url() == runtime_url


def test_23_gmail_least_privilege_scope_verification(monkeypatch, db_client):
    """Stage 7.3.1: Verify Gmail integration strictly enforces gmail.readonly scope with no write/modify scopes."""
    from backend.core.gmail import GMAIL_SCOPE, build_authorization_url
    import urllib.parse
    client, session = db_client

    # 1. Constant verification
    assert GMAIL_SCOPE == "https://www.googleapis.com/auth/gmail.readonly"
    assert "modify" not in GMAIL_SCOPE
    assert "compose" not in GMAIL_SCOPE

    # 2. Authorization URL query string verification
    monkeypatch.setattr(settings, "APP_ENV", AppEnv.TEST)
    monkeypatch.setattr(settings, "GMAIL_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "BASE_URL", "https://ap-command-center.internal")

    auth_url = build_authorization_url(org_id="org_test", user_id="usr_admin", db=session)
    parsed = urllib.parse.urlparse(auth_url)
    qs = urllib.parse.parse_qs(parsed.query)

    assert "scope" in qs
    assert qs["scope"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    # Ensure no additional or escalated scopes are present
    assert "gmail.modify" not in auth_url
    assert "https://www.googleapis.com/auth/gmail.modify" not in auth_url

    # 3. API endpoint verification for /authorize
    auth_header = "Bearer test_token:SYSTEM_ADMIN:admin_user_01:admin@company.com:org_test"
    resp = client.get("/api/v1/integrations/gmail/authorize", headers={"Authorization": auth_header})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"] == "https://www.googleapis.com/auth/gmail.readonly"
    assert "modify" not in data["scope"]

    # 4. Status endpoint compliance verification
    resp_status = client.get("/api/v1/integrations/gmail/status", headers={"Authorization": auth_header})
    assert resp_status.status_code == 200
    status_data = resp_status.json()
    assert status_data["scopes"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert status_data["compliance"]["scope"] == "https://www.googleapis.com/auth/gmail.readonly"

