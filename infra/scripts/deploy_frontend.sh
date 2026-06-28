#!/usr/bin/env bash
# Sync frontend/out/ to the S3 origin bucket; invalidate CloudFront if configured.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_DIR="$ROOT/frontend/out"
BUCKET="${ATWC26_FRONTEND_BUCKET:?Set ATWC26_FRONTEND_BUCKET to the target S3 bucket name}"

if [[ ! -d "$OUT_DIR" ]]; then
  echo "error: $OUT_DIR not found — run ./infra/scripts/build_frontend_static.sh first" >&2
  exit 1
fi

echo "Syncing ${OUT_DIR}/ -> s3://${BUCKET}/"

aws s3 sync "$OUT_DIR/" "s3://${BUCKET}/" \
  --delete \
  --cache-control "public,max-age=31536000,immutable" \
  --exclude "*.html" \
  --exclude "*.json"

# HTML and JSON: short cache so deploys propagate quickly (CloudFront invalidation in Issue 5).
aws s3 sync "$OUT_DIR/" "s3://${BUCKET}/" \
  --exclude "*" \
  --include "*.html" \
  --include "*.json" \
  --cache-control "public,max-age=60,must-revalidate"

if [[ -n "${ATWC26_CLOUDFRONT_DISTRIBUTION_ID:-}" ]]; then
  echo "Invalidating CloudFront distribution ${ATWC26_CLOUDFRONT_DISTRIBUTION_ID}..."
  aws cloudfront create-invalidation \
    --distribution-id "$ATWC26_CLOUDFRONT_DISTRIBUTION_ID" \
    --paths "/*"
fi

echo "Deploy complete: s3://${BUCKET}/"
