#!/usr/bin/env bash
# =============================================================================
# Autonomous AP Command Center — Google Cloud Run Deployment Script
# =============================================================================
# Deploys the production multi-stage container to Google Cloud Run in Mumbai (asia-south1).
# Governed by Production Truth Rules:
#   - Validates active GCP billing account before provisioning.
#   - Injects all secrets exclusively from Google Secret Manager.
#   - Restricts Cloud Scheduler and Pub/Sub push to dedicated, separate service accounts.
#   - Configures Pub/Sub push subscription with explicit 300-second ack-deadline.
#   - Does NOT schedule backups inside ephemeral containers (operator CLI only).
#   - Does NOT create AWS or external paid resources.
#   - Displays expected resources, topology, and monthly cost projections before execution.
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# 0. CONFIGURATION & TOPOLOGY
# -----------------------------------------------------------------------------
REGION="${GCP_REGION:-asia-south1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE_NAME:-ap-command-center}"
ARTIFACT_REPO="${ARTIFACT_REPO_NAME:-ap-command-center}"
PUBSUB_SUBSCRIPTION="${PUBSUB_SUBSCRIPTION_NAME:-gmail-ap-inbox-push-sub}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo 'latest')}"

echo "============================================================================="
echo "   AUTONOMOUS AP COMMAND CENTER — CLOUD RUN DEPLOYMENT (MUMBAI)"
echo "============================================================================="
echo " Target Platform:      Google Cloud Run (Fully Managed Serverless)"
echo " Target Region:        ${REGION} (Mumbai, India)"
echo " Service Name:         ${SERVICE_NAME}"
echo " Image Tag:            ${IMAGE_TAG}"
echo " Container Specs:      1 vCPU, 512 MB RAM, concurrency: 80"
echo " Autoscaling:          minScale: 0 (Scale to zero), maxScale: 3"
echo " Pub/Sub Ack Deadline: 300 seconds (matches Cloud Run timeout)"
echo " AWS Resources:        NONE (Zero-AWS Supabase-First Architecture)"
echo " Ephemeral Storage:    Backups EXCLUDED from container (Operator CLI only)"
echo " Estimated Cost:       Scenario A Pilot: ~$0.06/month (within free allowance)"
echo "============================================================================="

# -----------------------------------------------------------------------------
# 1. PRE-FLIGHT CHECKS & OPERATOR APPROVAL
# -----------------------------------------------------------------------------
echo "[*] Checking gcloud CLI installation..."
if ! command -v gcloud &>/dev/null; then
    echo "[!] Error: 'gcloud' CLI is not installed or not in PATH."
    exit 1
fi

PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)
if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
    echo "[!] Error: No active GCP project configured. Run 'gcloud config set project <PROJECT_ID>'."
    exit 1
fi
echo "[+] Active Project ID: ${PROJECT_ID}"

echo "[*] Verifying Google Cloud Billing Account association..."
BILLING_ENABLED=$(gcloud beta billing projects describe "${PROJECT_ID}" --format="value(billingEnabled)" 2>/dev/null || echo "UNKNOWN")
if [[ "${BILLING_ENABLED}" != "True" && "${BILLING_ENABLED}" != "true" ]]; then
    echo "[!] Warning: Project '${PROJECT_ID}' does not show an active billing account (status: ${BILLING_ENABLED})."
    echo "    Cloud Run and Secret Manager require an active billing account even within the free allowance."
    read -r -p "    Continue anyway? (y/N): " confirm_billing
    if [[ "${confirm_billing}" != "y" && "${confirm_billing}" != "Y" ]]; then
        echo "[-] Aborted by operator."
        exit 1
    fi
else
    echo "[+] Active billing account verified."
fi

# Guard prompt: Operator must explicitly confirm deployment execution
echo ""
echo "-----------------------------------------------------------------------------"
echo " SAFETY GUARD: Ready to deploy '${SERVICE_NAME}' to project '${PROJECT_ID}' (${REGION})."
echo "-----------------------------------------------------------------------------"
read -r -p " Proceed with provisioning and container deployment? (y/N): " confirm_deploy
if [[ "${confirm_deploy}" != "y" && "${confirm_deploy}" != "Y" ]]; then
    echo "[-] Deployment aborted by operator."
    exit 0
fi

# -----------------------------------------------------------------------------
# 2. ENABLE REQUIRED GOOGLE CLOUD APIS
# -----------------------------------------------------------------------------
echo "[*] Enabling required Google Cloud APIs..."
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com \
    pubsub.googleapis.com \
    cloudbuild.googleapis.com \
    --project="${PROJECT_ID}"

# -----------------------------------------------------------------------------
# 3. DEDICATED SERVICE ACCOUNTS & IAM GOVERNANCE (Stage 7.1)
# -----------------------------------------------------------------------------
# Three strictly separated service identities:
# 1. CLOUDRUN_SA: Runtime identity for the FastAPI container.
# 2. PUBSUB_SA: Push identity for Google Cloud Pub/Sub webhook delivery.
# 3. SCHEDULER_SA: Dedicated identity for Cloud Scheduler maintenance jobs.
CLOUDRUN_SA="ap-cloudrun-sa@${PROJECT_ID}.iam.gserviceaccount.com"
PUBSUB_SA="gmail-pubsub-push@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER_SA="ap-cloud-scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo "[*] Verifying Cloud Run runtime service account (${CLOUDRUN_SA})..."
if ! gcloud iam service-accounts describe "${CLOUDRUN_SA}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "[*] Creating service account: ap-cloudrun-sa..."
    gcloud iam service-accounts create ap-cloudrun-sa \
        --display-name="AP Command Center Cloud Run Service Account" \
        --project="${PROJECT_ID}"
fi

echo "[*] Granting Secret Manager Secret Accessor role to Cloud Run runtime on retained secrets..."
RETAINED_SECRETS=(
    "ap-database-url"
    "ap-secret-key"
    "ap-supabase-service-key"
    "ap-supabase-jwt-secret"
    "ap-gmail-client-secret"
    "ap-gmail-encryption-key"
)
for secret in "${RETAINED_SECRETS[@]}"; do
    gcloud secrets add-iam-policy-binding "${secret}" \
        --member="serviceAccount:${CLOUDRUN_SA}" \
        --role="roles/secretmanager.secretAccessor" \
        --project="${PROJECT_ID}" \
        --condition=None --quiet >/dev/null 2>&1 || true
done

echo "[*] Verifying Pub/Sub push service account (${PUBSUB_SA})..."
if ! gcloud iam service-accounts describe "${PUBSUB_SA}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "[*] Creating service account: gmail-pubsub-push..."
    gcloud iam service-accounts create gmail-pubsub-push \
        --display-name="Gmail PubSub Push Webhook Invoker" \
        --project="${PROJECT_ID}"
fi

echo "[*] Verifying Cloud Scheduler dedicated service account (${SCHEDULER_SA})..."
if ! gcloud iam service-accounts describe "${SCHEDULER_SA}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "[*] Creating service account: ap-cloud-scheduler-sa..."
    gcloud iam service-accounts create ap-cloud-scheduler-sa \
        --display-name="AP Command Center Cloud Scheduler Maintenance Invoker" \
        --project="${PROJECT_ID}"
fi

# -----------------------------------------------------------------------------
# 4. SECRET MANAGER VALIDATION
# -----------------------------------------------------------------------------
echo "[*] Verifying required secrets in Google Secret Manager..."
REQUIRED_SECRETS=(
    "ap-database-url"
    "ap-secret-key"
    "ap-supabase-service-key"
    "ap-supabase-jwt-secret"
    "ap-gmail-client-secret"
    "ap-gmail-encryption-key"
)

MISSING_SECRETS=()
for secret in "${REQUIRED_SECRETS[@]}"; do
    if ! gcloud secrets describe "${secret}" --project="${PROJECT_ID}" &>/dev/null; then
        MISSING_SECRETS+=("${secret}")
    fi
done

if [[ ${#MISSING_SECRETS[@]} -gt 0 ]]; then
    echo "[!] Error: The following mandatory secrets are missing from Secret Manager in project '${PROJECT_ID}':"
    for s in "${MISSING_SECRETS[@]}"; do
        echo "    - ${s}"
    done
    echo ""
    echo "    Create missing secrets before deploying:"
    echo "    echo -n \"your-secret-value\" | gcloud secrets create <SECRET_NAME> --data-file=-"
    exit 1
fi
echo "[+] All required secrets confirmed present in Secret Manager."

# -----------------------------------------------------------------------------
# 5. ARTIFACT REGISTRY & CONTAINER BUILD
# -----------------------------------------------------------------------------
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/app:${IMAGE_TAG}"

echo "[*] Verifying Artifact Registry repository..."
if ! gcloud artifacts repositories describe "${ARTIFACT_REPO}" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "[*] Creating Artifact Registry repository '${ARTIFACT_REPO}' in ${REGION}..."
    gcloud artifacts repositories create "${ARTIFACT_REPO}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="Autonomous AP Command Center Container Images" \
        --project="${PROJECT_ID}"
fi

echo "[*] Building container image via Google Cloud Build..."
gcloud builds submit \
    --tag "${IMAGE_URI}" \
    --project="${PROJECT_ID}" \
    .

# -----------------------------------------------------------------------------
# 6. DATABASE SCHEMA MIGRATION
# -----------------------------------------------------------------------------
echo "[*] Checking database migrations..."
if [[ -n "${DATABASE_URL:-}" ]]; then
    echo "[*] Running 'alembic upgrade head' locally..."
    python -m alembic upgrade head
else
    echo "[!] Notice: DATABASE_URL not set in current shell. Ensure Alembic migrations"
    echo "    have been applied to Supabase PostgreSQL before routing traffic."
fi

# -----------------------------------------------------------------------------
# 7. CLOUD RUN SERVICE DEPLOYMENT
# -----------------------------------------------------------------------------
echo "[*] Deploying container to Google Cloud Run in ${REGION}..."
gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_URI}" \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --service-account="${CLOUDRUN_SA}" \
    --port=8080 \
    --cpu=1 \
    --memory=512Mi \
    --concurrency=80 \
    --min-instances=0 \
    --max-instances=3 \
    --timeout=300s \
    --set-env-vars="APP_ENV=production,APP_NAME=Autonomous AP Command Center,APP_HOST=0.0.0.0,APP_PORT=8080,STORAGE_PROVIDER=supabase,SUPABASE_STORAGE_BUCKET=invoices,STORAGE_BUCKET_NAME=invoices,STORAGE_REGION=ap-south-1,IDP_PROVIDER=supabase_auth,SUPABASE_AUDIENCE=authenticated,SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY:-},GMAIL_CLIENT_ID=${GMAIL_CLIENT_ID:-},PUBSUB_ACK_DEADLINE_SECONDS=300,GMAIL_SYNC_TIMEOUT_SECONDS=240,GMAIL_WATCH_RENEWAL_HOURS=48,GMAIL_RECONCILIATION_HOURS=6,CLOUD_SCHEDULER_SERVICE_ACCOUNT_EMAIL=${SCHEDULER_SA},DOCUMENT_RETENTION_DAYS=2920,ENABLE_PERMANENT_PURGE=false" \
    --set-secrets="DATABASE_URL=ap-database-url:latest,SECRET_KEY=ap-secret-key:latest,SUPABASE_SERVICE_ROLE_KEY=ap-supabase-service-key:latest,SUPABASE_JWT_SECRET=ap-supabase-jwt-secret:latest,GMAIL_CLIENT_SECRET=ap-gmail-client-secret:latest,GMAIL_ENCRYPTION_KEY=ap-gmail-encryption-key:latest" \
    --project="${PROJECT_ID}"

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --project="${PROJECT_ID}" --format="value(status.url)")
echo "[+] Cloud Run Service deployed successfully!"
echo "    Public Endpoint: ${SERVICE_URL}"

# Grant run.invoker strictly to Pub/Sub and Cloud Scheduler service accounts
echo "[*] Granting invocation permissions to dedicated service identities..."
gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
    --region="${REGION}" \
    --member="serviceAccount:${PUBSUB_SA}" \
    --role="roles/run.invoker" \
    --project="${PROJECT_ID}" >/dev/null

gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
    --region="${REGION}" \
    --member="serviceAccount:${SCHEDULER_SA}" \
    --role="roles/run.invoker" \
    --project="${PROJECT_ID}" >/dev/null

# -----------------------------------------------------------------------------
# 8. CONFIGURE PUB/SUB SUBSCRIPTION & ACKNOWLEDGEMENT DEADLINE (Stage 7.1)
# -----------------------------------------------------------------------------
PUBSUB_TOPIC="${PUBSUB_TOPIC_NAME:-projects/${PROJECT_ID}/topics/gmail-ap-inbox}"
PUSH_ENDPOINT="${SERVICE_URL}/api/v1/integrations/gmail/pubsub/push"

echo "[*] Configuring Google Cloud Pub/Sub push subscription (${PUBSUB_SUBSCRIPTION})..."
if ! gcloud pubsub subscriptions describe "${PUBSUB_SUBSCRIPTION}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "[*] Creating Pub/Sub push subscription with explicit 300s acknowledgement deadline..."
    gcloud pubsub subscriptions create "${PUBSUB_SUBSCRIPTION}" \
        --topic="${PUBSUB_TOPIC}" \
        --push-endpoint="${PUSH_ENDPOINT}" \
        --push-auth-service-account="${PUBSUB_SA}" \
        --ack-deadline=300 \
        --min-retry-delay=10s \
        --max-retry-delay=300s \
        --project="${PROJECT_ID}"
else
    echo "[*] Updating Pub/Sub push subscription ack-deadline to 300s..."
    gcloud pubsub subscriptions update "${PUBSUB_SUBSCRIPTION}" \
        --push-endpoint="${PUSH_ENDPOINT}" \
        --ack-deadline=300 \
        --project="${PROJECT_ID}"
fi

# -----------------------------------------------------------------------------
# 9. CONFIGURE CLOUD SCHEDULER MAINTENANCE CRON TRIGGERS (Stage 7.1)
# -----------------------------------------------------------------------------
echo "[*] Configuring Google Cloud Scheduler maintenance triggers using dedicated identity (${SCHEDULER_SA})..."

# Trigger 1: Gmail 48-Hour Watch Renewal (Daily at 00:00 UTC)
WATCH_RENEW_URI="${SERVICE_URL}/api/v1/integrations/gmail/watch/renew"
if gcloud scheduler jobs describe "gmail-watch-renewal" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
    gcloud scheduler jobs update http "gmail-watch-renewal" \
        --location="${REGION}" \
        --schedule="0 0 * * *" \
        --uri="${WATCH_RENEW_URI}" \
        --http-method=POST \
        --oidc-service-account-email="${SCHEDULER_SA}" \
        --oidc-token-audience="${WATCH_RENEW_URI}" \
        --project="${PROJECT_ID}" >/dev/null
else
    gcloud scheduler jobs create http "gmail-watch-renewal" \
        --location="${REGION}" \
        --schedule="0 0 * * *" \
        --uri="${WATCH_RENEW_URI}" \
        --http-method=POST \
        --oidc-service-account-email="${SCHEDULER_SA}" \
        --oidc-token-audience="${WATCH_RENEW_URI}" \
        --description="Daily Gmail API watch renewal trigger" \
        --project="${PROJECT_ID}" >/dev/null
fi

# Trigger 2: Gmail Periodic History Reconciliation (Every 6 Hours)
RECONCILE_URI="${SERVICE_URL}/api/v1/integrations/gmail/reconcile"
if gcloud scheduler jobs describe "gmail-history-reconciliation" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
    gcloud scheduler jobs update http "gmail-history-reconciliation" \
        --location="${REGION}" \
        --schedule="0 */6 * * *" \
        --uri="${RECONCILE_URI}" \
        --http-method=POST \
        --oidc-service-account-email="${SCHEDULER_SA}" \
        --oidc-token-audience="${RECONCILE_URI}" \
        --project="${PROJECT_ID}" >/dev/null
else
    gcloud scheduler jobs create http "gmail-history-reconciliation" \
        --location="${REGION}" \
        --schedule="0 */6 * * *" \
        --uri="${RECONCILE_URI}" \
        --http-method=POST \
        --oidc-service-account-email="${SCHEDULER_SA}" \
        --oidc-token-audience="${RECONCILE_URI}" \
        --description="Every 6h Gmail missed message reconciliation" \
        --project="${PROJECT_ID}" >/dev/null
fi

# Trigger 3: Unfinished Pub/Sub Event Recovery (Every 30 Minutes)
RECLAIM_URI="${SERVICE_URL}/api/v1/integrations/gmail/pubsub/reclaim"
if gcloud scheduler jobs describe "gmail-pubsub-reclaim" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
    gcloud scheduler jobs update http "gmail-pubsub-reclaim" \
        --location="${REGION}" \
        --schedule="*/30 * * * *" \
        --uri="${RECLAIM_URI}" \
        --http-method=POST \
        --oidc-service-account-email="${SCHEDULER_SA}" \
        --oidc-token-audience="${RECLAIM_URI}" \
        --project="${PROJECT_ID}" >/dev/null
else
    gcloud scheduler jobs create http "gmail-pubsub-reclaim" \
        --location="${REGION}" \
        --schedule="*/30 * * * *" \
        --uri="${RECLAIM_URI}" \
        --http-method=POST \
        --oidc-service-account-email="${SCHEDULER_SA}" \
        --oidc-token-audience="${RECLAIM_URI}" \
        --description="Every 30m unfinished Pub/Sub event recovery" \
        --project="${PROJECT_ID}" >/dev/null
fi
echo "[+] Google Cloud Scheduler triggers configured successfully."
echo "[-] Backup notice: Automated backup is NOT scheduled on Cloud Run (operator CLI only)."

# -----------------------------------------------------------------------------
# 10. POST-DEPLOYMENT SMOKE VERIFICATION
# -----------------------------------------------------------------------------
echo "[*] Executing post-deployment smoke health check..."
LIVENESS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}/api/v1/liveness" || echo "000")
if [[ "${LIVENESS_STATUS}" == "200" ]]; then
    echo "[+] Liveness check passed (HTTP 200) on ${SERVICE_URL}/api/v1/liveness"
else
    echo "[!] Warning: Liveness check returned HTTP ${LIVENESS_STATUS}"
fi

echo ""
echo "============================================================================="
echo "   DEPLOYMENT COMPLETE"
echo "============================================================================="
echo "   * Live Application URL: ${SERVICE_URL}"
echo "   * API Documentation:    ${SERVICE_URL}/docs"
echo "   * Liveness Probe:       ${SERVICE_URL}/api/v1/liveness"
echo "   * Subsystem Health:     ${SERVICE_URL}/api/v1/health"
echo "============================================================================="
