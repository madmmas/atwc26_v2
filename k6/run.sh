#!/usr/bin/env bash
# Run k6 smoke or journey scripts against the v1 API (default: production).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
K6_DIR="$ROOT/k6"
REPORTS_DIR="${ATWC26_REPORT_DIR:-$ROOT/reports}"

export ATWC26_BASE_URL="${ATWC26_BASE_URL:-https://atwc26.com}"
export ATWC26_REPORT_DIR="$REPORTS_DIR"

if ! command -v k6 >/dev/null 2>&1; then
  echo "k6 is not installed. Install from https://grafana.com/docs/k6/latest/set-up/install-k6/" >&2
  echo "  macOS: brew install k6" >&2
  exit 1
fi

SCRIPT="${1:-}"
if [[ -z "$SCRIPT" ]]; then
  echo "usage: $0 smoke|journey" >&2
  exit 1
fi

mkdir -p "$REPORTS_DIR"

case "$SCRIPT" in
  smoke)
    exec k6 run "$K6_DIR/scripts/smoke.js"
    ;;
  journey)
    exec k6 run "$K6_DIR/scripts/journey.js"
    ;;
  *)
    echo "unknown script: $SCRIPT (expected smoke or journey)" >&2
    exit 1
    ;;
esac
