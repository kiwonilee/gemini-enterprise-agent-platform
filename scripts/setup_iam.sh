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

create_sa_and_bind() {
  local sa_name="$1"
  local display_name="$2"
  shift 2
  local roles=("$@")
  local sa_email="${sa_name}@${PROJECT_ID}.iam.gserviceaccount.com"

  if ! gcloud iam service-accounts describe "${sa_email}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "👤 Creating service account: ${sa_email}"
    gcloud iam service-accounts create "${sa_name}" \
      --display-name="${display_name}" \
      --project="${PROJECT_ID}"
  else
    echo "✅ Service account exists: ${sa_email}"
  fi

  for role in "${roles[@]}"; do
    gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${sa_email}" \
      --role="${role}" \
      --quiet >/dev/null
  done
  echo "🔑 Bound IAM roles for ${sa_email}"
}

create_sa_and_bind "sa-agent-registry" "agent-registry-sa" \
  "roles/cloudtrace.user" "roles/cloudtrace.agent" "roles/logging.viewer" \
  "roles/logging.logWriter" "roles/storage.objectAdmin" "roles/aiplatform.user" \
  "roles/agentregistry.viewer" "roles/mcp.toolUser"

create_sa_and_bind "sa-agent-sandbox" "agent-sandbox-sa" \
  "roles/cloudtrace.user" "roles/cloudtrace.agent" "roles/logging.viewer" \
  "roles/logging.logWriter" "roles/storage.objectAdmin" "roles/aiplatform.user"

create_sa_and_bind "sa-skill-registry" "skill-registry-sa" \
  "roles/cloudtrace.user" "roles/cloudtrace.agent" "roles/logging.viewer" \
  "roles/logging.logWriter" "roles/aiplatform.user" \
  "roles/serviceusage.serviceUsageConsumer" "roles/agentregistry.viewer"

create_sa_and_bind "sa-graph-workflow" "graph-workflow-sa" \
  "roles/cloudtrace.user" "roles/cloudtrace.agent" "roles/logging.viewer" \
  "roles/logging.logWriter" "roles/aiplatform.user"

echo "✅ GCP IAM and infrastructure setup complete!"
