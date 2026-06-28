#!/usr/bin/env bash
# Deploy frontend/out/ using bucket + distribution IDs from Terraform dev outputs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TF_DIR="${ATWC26_TF_DIR:-$ROOT/infra/terraform/envs/dev}"

if [[ ! -d "$TF_DIR/.terraform" ]] && [[ ! -f "$TF_DIR/.terraform.lock.hcl" ]]; then
  echo "Initializing Terraform in $TF_DIR..."
  terraform -chdir="$TF_DIR" init -input=false
fi

export ATWC26_FRONTEND_BUCKET
export ATWC26_CLOUDFRONT_DISTRIBUTION_ID

ATWC26_FRONTEND_BUCKET="$(terraform -chdir="$TF_DIR" output -raw bucket_name)"
ATWC26_CLOUDFRONT_DISTRIBUTION_ID="$(terraform -chdir="$TF_DIR" output -raw cloudfront_distribution_id)"

echo "Bucket:      $ATWC26_FRONTEND_BUCKET"
echo "Distribution: $ATWC26_CLOUDFRONT_DISTRIBUTION_ID"

exec "$ROOT/infra/scripts/deploy_frontend.sh"
