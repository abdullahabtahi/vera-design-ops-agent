#!/usr/bin/env bash
# deploy.sh — Deploy Vera (backend + frontend) to Google Cloud Run
#
# Usage:
#   ./deploy.sh --setup   # one-time IAM + secrets setup (run first)
#   ./deploy.sh           # deploy both backend and frontend
#   ./deploy.sh backend   # deploy backend only
#   ./deploy.sh frontend  # deploy frontend only (requires BACKEND_URL set)
#
# Prerequisites:
#   gcloud CLI installed + authenticated
#   gcloud config set project <your-gcp-project-id>
#
# Required environment variables (set in .env or export before running):
#   GCP_PROJECT_ID       - Your GCP project ID
#   FIREBASE_API_KEY     - Firebase Web API key

set -euo pipefail

# ── Load .env if present ───────────────────────────────────────────────────────
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a; source .env; set +a
fi

PROJECT="${GCP_PROJECT_ID:?GCP_PROJECT_ID is required — set it in .env or export it}"
REGION="us-central1"
BACKEND_SERVICE="vera-backend"
FRONTEND_SERVICE="vera-frontend"
BACKEND_IMAGE="gcr.io/${PROJECT}/${BACKEND_SERVICE}"
FRONTEND_IMAGE="gcr.io/${PROJECT}/${FRONTEND_SERVICE}"

# Firebase web config — includes a public API key; access is enforced by Firebase Rules/App Check 
FIREBASE_API_KEY="${FIREBASE_API_KEY:?FIREBASE_API_KEY is required — set it in .env or export it}"
FIREBASE_AUTH_DOMAIN="${FIREBASE_AUTH_DOMAIN:-${PROJECT}.firebaseapp.com}"
FIREBASE_PROJECT_ID="${FIREBASE_PROJECT_ID:-${PROJECT}}"
FIREBASE_STORAGE_BUCKET="${FIREBASE_STORAGE_BUCKET:-${PROJECT}.firebasestorage.app}"
FIREBASE_MESSAGING_SENDER_ID="${FIREBASE_MESSAGING_SENDER_ID:?FIREBASE_MESSAGING_SENDER_ID is required — set it in .env or export it}"
FIREBASE_APP_ID="${FIREBASE_APP_ID:?FIREBASE_APP_ID is required — set it in .env or export it}"

# ── One-time setup ─────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--setup" ]]; then
  echo "→ Enabling required GCP APIs..."
  gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    aiplatform.googleapis.com \
    --project="${PROJECT}"

  echo "→ Creating Cloud Run service account..."
  SA_NAME="${BACKEND_SERVICE}-sa"
  SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Vera Backend Service Account" \
    --project="${PROJECT}" 2>/dev/null || echo "(SA already exists)"

  echo "→ Granting required permissions..."
  for ROLE in \
    roles/aiplatform.user \
    roles/datastore.user \
    roles/logging.logWriter \
    roles/secretmanager.secretAccessor; do
    gcloud projects add-iam-policy-binding "${PROJECT}" \
      --member="serviceAccount:${SA_EMAIL}" \
      --role="${ROLE}" --quiet
  done

  echo ""
  echo "→ Creating secrets in Secret Manager..."
  echo "  Paste each value when prompted, then press Enter + Ctrl+D."
  echo ""
  for SECRET in FIGMA_ACCESS_TOKEN JINA_API_KEY ALLOWED_ORIGINS; do
    if gcloud secrets describe "${SECRET}" --project="${PROJECT}" &>/dev/null; then
      echo "  (${SECRET} already exists — skipping)"
    else
      echo "→ Creating secret: ${SECRET}"
      printf "  Value for %s: " "${SECRET}"
      read -rs SECRET_VALUE; echo
      echo -n "${SECRET_VALUE}" | gcloud secrets create "${SECRET}" \
        --data-file=- --project="${PROJECT}"
    fi
  done

  echo ""
  echo "✓ Setup complete. Run: ./deploy.sh"
  exit 0
fi

# ── Helper: get backend URL ────────────────────────────────────────────────────
get_backend_url() {
  gcloud run services describe "${BACKEND_SERVICE}" \
    --project="${PROJECT}" --region="${REGION}" \
    --format="value(status.url)" 2>/dev/null || echo ""
}

# ── Deploy backend ─────────────────────────────────────────────────────────────
deploy_backend() {
  echo ""
  echo "══ Backend ════════════════════════════════════════"
  echo "→ Building backend image via Cloud Build..."
  gcloud builds submit backend/ \
    --tag="${BACKEND_IMAGE}:latest" \
    --project="${PROJECT}"

  echo "→ Deploying vera-backend to Cloud Run..."
  SA_EMAIL="${BACKEND_SERVICE}-sa@${PROJECT}.iam.gserviceaccount.com"
  gcloud run deploy "${BACKEND_SERVICE}" \
    --image="${BACKEND_IMAGE}:latest" \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --service-account="${SA_EMAIL}" \
    --memory=2Gi \
    --cpu=2 \
    --concurrency=10 \
    --timeout=300 \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=true,TEAM_DOCS_PATH=/tmp/team_docs" \
    --set-secrets="FIGMA_ACCESS_TOKEN=FIGMA_ACCESS_TOKEN:latest,JINA_API_KEY=JINA_API_KEY:latest,ALLOWED_ORIGINS=ALLOWED_ORIGINS:latest" \
    --project="${PROJECT}"

  BACKEND_URL=$(get_backend_url)
  echo "✓ Backend: ${BACKEND_URL}"
}

# ── Deploy frontend ────────────────────────────────────────────────────────────
deploy_frontend() {
  BACKEND_URL="${1:-$(get_backend_url)}"
  if [[ -z "${BACKEND_URL}" ]]; then
    echo "ERROR: backend not deployed yet. Run: ./deploy.sh backend first."
    exit 1
  fi

  echo ""
  echo "══ Frontend ═══════════════════════════════════════"
  echo "→ Building frontend image (NEXT_PUBLIC_BACKEND_URL=${BACKEND_URL})..."
  # Use frontend/cloudbuild.yaml — passes NEXT_PUBLIC_* vars as build args
  gcloud builds submit frontend/ \
    --project="${PROJECT}" \
    --config=frontend/cloudbuild.yaml \
    --substitutions="_BACKEND_URL=${BACKEND_URL},_FIREBASE_API_KEY=${FIREBASE_API_KEY},_FIREBASE_AUTH_DOMAIN=${FIREBASE_AUTH_DOMAIN},_FIREBASE_PROJECT_ID=${FIREBASE_PROJECT_ID},_FIREBASE_STORAGE_BUCKET=${FIREBASE_STORAGE_BUCKET},_FIREBASE_MESSAGING_SENDER_ID=${FIREBASE_MESSAGING_SENDER_ID},_FIREBASE_APP_ID=${FIREBASE_APP_ID}"

  echo "→ Deploying vera-frontend to Cloud Run..."
  gcloud run deploy "${FRONTEND_SERVICE}" \
    --image="${FRONTEND_IMAGE}:latest" \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --memory=512Mi \
    --cpu=1 \
    --concurrency=80 \
    --timeout=30 \
    --project="${PROJECT}"

  FRONTEND_URL=$(gcloud run services describe "${FRONTEND_SERVICE}" \
    --project="${PROJECT}" --region="${REGION}" \
    --format="value(status.url)")
  echo "✓ Frontend: ${FRONTEND_URL}"

  # Update ALLOWED_ORIGINS secret with actual frontend URL
  echo "→ Updating ALLOWED_ORIGINS secret → ${FRONTEND_URL}"
  echo -n "${FRONTEND_URL}" | gcloud secrets versions add ALLOWED_ORIGINS \
    --data-file=- --project="${PROJECT}"

  # Force backend to pick up the new secret version
  gcloud run services update "${BACKEND_SERVICE}" \
    --region="${REGION}" --project="${PROJECT}" \
    --set-secrets="ALLOWED_ORIGINS=ALLOWED_ORIGINS:latest" &>/dev/null

  echo ""
  echo "══════════════════════════════════════════════════"
  echo " Vera is live!"
  echo " Frontend: ${FRONTEND_URL}"
  echo " Backend:  $(get_backend_url)"
  echo "══════════════════════════════════════════════════"
  echo ""
  echo " POST-DEPLOY:"
  echo " 1. Firebase Console → Authentication → Settings → Authorized Domains"
  echo "    Add: $(echo "${FRONTEND_URL}" | sed 's|https://||')"
  echo " 2. Deploy Firestore rules:"
  echo "    firebase deploy --only firestore:rules --project ${PROJECT}"
}

# ── Entrypoint ─────────────────────────────────────────────────────────────────
case "${1:-all}" in
  backend)  deploy_backend ;;
  frontend) deploy_frontend "${2:-}" ;;
  all)
    deploy_backend
    deploy_frontend
    ;;
  *)
    echo "Usage: ./deploy.sh [--setup | backend | frontend | all]"
    exit 1
    ;;
esac
