#!/usr/bin/env bash
# Build the Next.js frontend as static HTML/JS/CSS in frontend/out/ for S3 upload.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND="$ROOT/frontend"

# v2 split APIs (Issue 7). When unset, api.ts falls back to NEXT_PUBLIC_API_URL.
export NEXT_PUBLIC_ANALYTICS_API_URL="${NEXT_PUBLIC_ANALYTICS_API_URL:-}"
export NEXT_PUBLIC_PREDICT_API_URL="${NEXT_PUBLIC_PREDICT_API_URL:-}"

# v1 monolith fallback (used when split URLs are unset).
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-https://atwc26.com}"
export NEXT_OUTPUT_MODE=export
export NEXT_TELEMETRY_DISABLED=1

if [[ -n "$NEXT_PUBLIC_ANALYTICS_API_URL" || -n "$NEXT_PUBLIC_PREDICT_API_URL" ]]; then
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
