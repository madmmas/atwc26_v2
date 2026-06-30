#!/usr/bin/env bash
# Package v2 Lambda functions and a shared dependency layer.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD="$ROOT/infra/build/lambdas"
LAYER_REQ="$ROOT/infra/lambda-layer/requirements.txt"
# Lambda dev stack uses arm64 (see terraform envs/dev/main.tf).
LAMBDA_PLATFORM="${ATWC26_LAMBDA_PLATFORM:-manylinux2014_aarch64}"
LAMBDA_PYTHON="${ATWC26_LAMBDA_PYTHON:-3.11}"

prune_layer() {
  local root="$1"
  find "$root" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
  find "$root" -type d \( -name tests -o -name test \) -prune -exec rm -rf {} + 2>/dev/null || true
  find "$root" -name '*.pyc' -delete 2>/dev/null || true
  find "$root" -name '*.pyo' -delete 2>/dev/null || true
  # Headers / extras not needed at runtime for parquet reads.
  rm -rf "$root/pyarrow/include" 2>/dev/null || true
  # Never bundle AWS SDK — Lambda runtime includes boto3/botocore.
  rm -rf "$root/boto3" "$root/botocore" "$root/s3transfer" 2>/dev/null || true
}

rm -rf "$BUILD"
mkdir -p "$BUILD/layer/python"

echo "==> Building Lambda layer (linux/arm64 wheels for Lambda)"
python3 -m pip install -r "$LAYER_REQ" -t "$BUILD/layer/python" --upgrade \
  --platform "$LAMBDA_PLATFORM" \
  --implementation cp \
  --python-version "$LAMBDA_PYTHON" \
  --only-binary=:all:
python3 -m pip install "$ROOT/packages/atwc26_core" -t "$BUILD/layer/python" --upgrade --no-deps

prune_layer "$BUILD/layer/python"

(
  cd "$BUILD/layer"
  zip -qr "$BUILD/layer.zip" python
)

package_function() {
  local name="$1"
  local pkg_dir="$2"
  local out="$BUILD/${name}.zip"
  local stage="$BUILD/stage-${name}"

  echo "==> Packaging ${name}"
  rm -rf "$stage"
  # Flat layout for Lambda handler analytics_api.handler.handler (not nested package dir).
  mkdir -p "$stage/${pkg_dir}" "$stage/services"
  cp -r "$ROOT/services/${pkg_dir}/${pkg_dir}/"* "$stage/${pkg_dir}/"
  cp -r "$ROOT/services/shared" "$stage/services/shared"
  touch "$stage/services/__init__.py"

  (
    cd "$stage"
    zip -qr "$out" .
  )
  rm -rf "$stage"
}

package_function "analytics" "analytics_api"
package_function "predict" "predict_api"

echo "Artifacts:"
ls -lh "$BUILD"/*.zip
unzip -l "$BUILD/layer.zip" | tail -1
echo "Tip: layer must be <250MB unzipped and <50MB for direct Terraform upload; use S3 publish in terraform if larger."
