#!/usr/bin/env bash
# Build the Next.js frontend as static HTML/JS/CSS in frontend/out/ for S3 upload.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND="$ROOT/frontend"
TF_DIR="${ATWC26_TF_DIR:-$ROOT/infra/terraform/envs/dev}"

# Optional explicit API bases. When unset, build_frontend_static.sh may read Terraform outputs.
if [[ -n "${NEXT_PUBLIC_ANALYTICS_API_URL:-}" ]]; then
  export NEXT_PUBLIC_ANALYTICS_API_URL
fi
if [[ -n "${NEXT_PUBLIC_PREDICT_API_URL:-}" ]]; then
  export NEXT_PUBLIC_PREDICT_API_URL
fi
if [[ -n "${NEXT_PUBLIC_SAME_ORIGIN_API:-}" ]]; then
  export NEXT_PUBLIC_SAME_ORIGIN_API
fi

# CloudFront static deploy: same-origin /api/* (no CORS preflight; POST /api/predict works via /api/* behavior).
if [[ -z "${NEXT_PUBLIC_ANALYTICS_API_URL:-}" && -z "${NEXT_PUBLIC_PREDICT_API_URL:-}" && -z "${NEXT_PUBLIC_SAME_ORIGIN_API:-}" ]]; then
  if command -v terraform >/dev/null 2>&1 && [[ -d "$TF_DIR" ]]; then
    SITE_URL="$(terraform -chdir="$TF_DIR" output -raw site_url 2>/dev/null || true)"
    if [[ -n "$SITE_URL" && "$SITE_URL" != "null" ]]; then
      export NEXT_PUBLIC_SAME_ORIGIN_API=true
    else
      API_URL="$(terraform -chdir="$TF_DIR" output -raw api_gateway_url 2>/dev/null || true)"
      if [[ -n "$API_URL" && "$API_URL" != "null" ]]; then
        export NEXT_PUBLIC_ANALYTICS_API_URL="$API_URL"
        export NEXT_PUBLIC_PREDICT_API_URL="$API_URL"
      fi
    fi
  fi
fi

# v1 monolith fallback (used when split URLs are unset).
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-https://atwc26.com}"
export NEXT_OUTPUT_MODE=export
export NEXT_TELEMETRY_DISABLED=1

if [[ "${NEXT_PUBLIC_SAME_ORIGIN_API:-}" == "true" ]]; then
  echo "Building static frontend (same-origin /api/* via CloudFront)"
elif [[ -n "${NEXT_PUBLIC_ANALYTICS_API_URL:-}" || -n "${NEXT_PUBLIC_PREDICT_API_URL:-}" ]]; then
  echo "Building static frontend (v2 split APIs):"
  echo "  analytics: ${NEXT_PUBLIC_ANALYTICS_API_URL:-<falls back to NEXT_PUBLIC_API_URL>}"
  echo "  predict:   ${NEXT_PUBLIC_PREDICT_API_URL:-<falls back to NEXT_PUBLIC_API_URL>}"
else
  echo "Building static frontend (monolith API: ${NEXT_PUBLIC_API_URL})..."
fi

cd "$FRONTEND"

if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi

npm run build

if [[ ! -d out ]]; then
  echo "error: expected frontend/out/ after static export" >&2
  exit 1
fi

echo "Static export ready: ${FRONTEND}/out/"
echo "Preview: npx serve frontend/out -p 3000"
