#!/usr/bin/env bash
# Run k6 journey against v1 baseline and v2 candidate, then compare summaries.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
K6_DIR="$ROOT/k6"
REPORTS_DIR="${ATWC26_REPORT_DIR:-$ROOT/reports}"
COMPARE_PY="$K6_DIR/compare_summaries.py"

BASELINE_URL="${ATWC26_PERF_BASELINE_URL:-${ATWC26_BASE_URL:-https://atwc26.com}}"
CANDIDATE_ANALYTICS="${ATWC26_PERF_CANDIDATE_ANALYTICS_URL:-}"
CANDIDATE_PREDICT="${ATWC26_PERF_CANDIDATE_PREDICT_URL:-}"

if [[ -z "$CANDIDATE_ANALYTICS" || -z "$CANDIDATE_PREDICT" ]]; then
  echo "error: set ATWC26_PERF_CANDIDATE_ANALYTICS_URL and ATWC26_PERF_CANDIDATE_PREDICT_URL" >&2
  echo "  example: make k6-ab ATWC26_PERF_CANDIDATE_ANALYTICS_URL=http://localhost:8001 \\" >&2
  echo "                 ATWC26_PERF_CANDIDATE_PREDICT_URL=http://localhost:8000" >&2
  exit 1
fi

if ! command -v k6 >/dev/null 2>&1; then
  echo "k6 is not installed. Install from https://grafana.com/docs/k6/latest/set-up/install-k6/" >&2
  exit 1
fi

mkdir -p "$REPORTS_DIR"
STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
DIFF_PATH="$REPORTS_DIR/ab-diff-${STAMP}.json"

echo "==> v1 baseline journey: $BASELINE_URL"
ATWC26_BASE_URL="$BASELINE_URL" \
ATWC26_REPORT_DIR="$REPORTS_DIR" \
ATWC26_K6_STACK=v1 \
ATWC26_K6_TEST_TYPE=journey \
k6 run "$K6_DIR/scripts/journey.js"

BASELINE_JSON="$(ls -t "$REPORTS_DIR"/journey-v1-*.json 2>/dev/null | head -1)"
if [[ -z "$BASELINE_JSON" ]]; then
  BASELINE_JSON="$(ls -t "$REPORTS_DIR"/baseline-*.json 2>/dev/null | head -1)"
fi
if [[ -z "$BASELINE_JSON" || ! -f "$BASELINE_JSON" ]]; then
  echo "error: baseline summary JSON not found in $REPORTS_DIR" >&2
  exit 1
fi

echo "==> v2 candidate journey: analytics=$CANDIDATE_ANALYTICS predict=$CANDIDATE_PREDICT"
ATWC26_ANALYTICS_URL="$CANDIDATE_ANALYTICS" \
ATWC26_PREDICT_URL="$CANDIDATE_PREDICT" \
ATWC26_REPORT_DIR="$REPORTS_DIR" \
ATWC26_K6_STACK=v2 \
ATWC26_K6_TEST_TYPE=journey \
k6 run "$K6_DIR/scripts/journey.js"

CANDIDATE_JSON="$(ls -t "$REPORTS_DIR"/journey-v2-*.json 2>/dev/null | head -1)"
if [[ -z "$CANDIDATE_JSON" || ! -f "$CANDIDATE_JSON" ]]; then
  echo "error: candidate summary JSON not found in $REPORTS_DIR" >&2
  exit 1
fi

echo "==> comparing $BASELINE_JSON vs $CANDIDATE_JSON"
python3 "$COMPARE_PY" "$BASELINE_JSON" "$CANDIDATE_JSON" -o "$DIFF_PATH"
