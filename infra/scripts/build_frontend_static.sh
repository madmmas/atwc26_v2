#!/usr/bin/env bash
# Build the Next.js frontend as static HTML/JS/CSS in frontend/out/ for S3 upload.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND="$ROOT/frontend"

# v1 production API until Issue 7 split (override for local/staging backends).
export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-https://atwc26.com}"
export NEXT_OUTPUT_MODE=export
export NEXT_TELEMETRY_DISABLED=1

echo "Building static frontend (API: ${NEXT_PUBLIC_API_URL})..."

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
