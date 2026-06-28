#!/usr/bin/env bash
# Package v2 Lambda functions and a shared dependency layer.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD="$ROOT/infra/build/lambdas"
LAYER_REQ="$ROOT/infra/lambda-layer/requirements.txt"

rm -rf "$BUILD"
mkdir -p "$BUILD/layer/python"

echo "==> Building Lambda layer"
python3 -m pip install -r "$LAYER_REQ" -t "$BUILD/layer/python" --upgrade
python3 -m pip install "$ROOT/packages/atwc26_core" -t "$BUILD/layer/python" --upgrade --no-deps

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
  mkdir -p "$stage/services"
  cp -r "$ROOT/services/${pkg_dir}" "$stage/"
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
