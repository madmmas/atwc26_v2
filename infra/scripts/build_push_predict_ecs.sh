#!/usr/bin/env bash
# Build predict_api Docker image and push to ECR (invoked from Terraform apply).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DOCKERFILE="${ATWC26_PREDICT_DOCKERFILE:-$ROOT/services/predict_api/Dockerfile}"
ECR_REPOSITORY_URL="${ECR_REPOSITORY_URL:?Set ECR_REPOSITORY_URL (no tag)}"
IMAGE_TAG="${IMAGE_TAG:?Set IMAGE_TAG}"
AWS_REGION="${AWS_REGION:-us-east-1}"
PLATFORM="${ATWC26_ECS_PLATFORM:-linux/amd64}"

if ! command -v docker >/dev/null 2>&1; then
  echo "error: docker is required to build the predict ECS image" >&2
  exit 1
fi

ECR_HOST="${ECR_REPOSITORY_URL%%/*}"
IMAGE_URI="${ECR_REPOSITORY_URL}:${IMAGE_TAG}"

echo "==> ECR login (${ECR_HOST})"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_HOST"

echo "==> Building ${IMAGE_URI} (${PLATFORM})"
docker build \
  --platform "$PLATFORM" \
  -f "$DOCKERFILE" \
  -t "$IMAGE_URI" \
  "$ROOT"

echo "==> Pushing ${IMAGE_URI}"
docker push "$IMAGE_URI"

# Mutable :latest helps manual debugging; ECS uses the content-hash tag from Terraform.
LATEST_URI="${ECR_REPOSITORY_URL}:latest"
docker tag "$IMAGE_URI" "$LATEST_URI"
docker push "$LATEST_URI"

echo "predict ECS image published: ${IMAGE_URI}"
