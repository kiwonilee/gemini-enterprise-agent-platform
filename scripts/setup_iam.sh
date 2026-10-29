#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project)}"
LOCATION="${GCP_RESOURCES_LOCATION:-us-central1}"
STAGING_BUCKET_URI="${STAGING_BUCKET_URI:-gs://adk-${PROJECT_ID}}"
SA_NAME="sa-agent-platform"
SA_EMAIL="${SERVICE_ACCOUNT:-${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"

echo "=================================================================="
echo "🛠️  Setting up GCP APIs, Bucket, and IAM for Project: ${PROJECT_ID}"
echo "=================================================================="

gcloud services enable \
  aiplatform.googleapis.com \
  agentregistry.googleapis.com \
  logging.googleapis.com \
  cloudtrace.googleapis.com \
  storage.googleapis.com \
  iam.googleapis.com \
  --project="${PROJECT_ID}"

if ! gcloud storage buckets describe "${STAGING_BUCKET_URI}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "🪣 Creating GCS Bucket: ${STAGING_BUCKET_URI} (${LOCATION})..."
  gcloud storage buckets create "${STAGING_BUCKET_URI}" --location="${LOCATION}" --project="${PROJECT_ID}"
else
  echo "✅ GCS Bucket already exists: ${STAGING_BUCKET_URI}"
fi

if ! gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "👤 Creating unified service account: ${SA_EMAIL}"
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Agent Platform Service Account" \
    --project="${PROJECT_ID}"
else
  echo "✅ Service account exists: ${SA_EMAIL}"
fi

ROLES=(
  "roles/aiplatform.user"
  "roles/cloudtrace.user"
  "roles/cloudtrace.agent"
  "roles/logging.viewer"
  "roles/logging.logWriter"
  "roles/storage.objectAdmin"
  "roles/serviceusage.serviceUsageConsumer"
  "roles/agentregistry.viewer"
  "roles/mcp.toolUser"
)

for role in "${ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${role}" \
    --quiet >/dev/null
done
echo "🔑 Bound IAM roles for ${SA_EMAIL}"

echo "✅ GCP IAM and infrastructure setup complete!"
