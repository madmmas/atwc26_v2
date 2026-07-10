# k6 performance baseline (v1) and A/B (v2)

Establish latency and error-rate baselines for the v1 monolith before the v2
refactor. Default target is production: [atwc26.com](https://atwc26.com).

Issue 8 adds **A/B comparison** against the v2 split API stack.

## Prerequisites

Install [k6](https://grafana.com/docs/k6/latest/set-up/install-k6/):

```bash
# macOS
brew install k6
```

## Quick start

From the repo root:

```bash
make k6-smoke      # 1 VU, health + overview
make k6-journey    # ramped VUs, full API journey + JSON report
make k6-load       # 5 VU load test
make k6-stress     # 10 VU stress test
make k6-ab         # v1 vs v2 A/B (needs candidate URLs)
```

## A/B comparison (v1 vs v2)

```bash
make k6-ab \
  K6_BASELINE_URL=https://atwc26.com \
  K6_CANDIDATE_ANALYTICS_URL=http://localhost:8001 \
  K6_CANDIDATE_PREDICT_URL=http://localhost:8000
```

Outputs `reports/ab-diff-<timestamp>.json`. See [docs/ops/CUTOVER.md](../docs/ops/CUTOVER.md)
for pass thresholds.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ATWC26_BASE_URL` | `https://atwc26.com` | v1 monolith API origin |
| `ATWC26_ANALYTICS_URL` | falls back to base | v2 analytics origin |
| `ATWC26_PREDICT_URL` | falls back to base | v2 predict origin |
| `ATWC26_REPORT_DIR` | `reports/` | JSON report output |
| `ATWC26_K6_PAUSE_SEC` | `0.15` | Pause between calls (prod rate limit) |
| `ATWC26_K6_STACK` | `baseline` | Report prefix (`v1`, `v2`) |
| `K6_BASELINE_URL` | `https://atwc26.com` | Makefile: v1 A/B baseline |
| `K6_CANDIDATE_ANALYTICS_URL` | `http://localhost:8001` | Makefile: v2 analytics |
| `K6_CANDIDATE_PREDICT_URL` | `http://localhost:8000` | Makefile: v2 predict |

## Layout

```text
k6/
  lib/
    config.js      # base + split API URLs
    scenarios.js   # smoke, journey, load, stress profiles
    thresholds.js  # pass/fail gates
    api.js         # shared HTTP helpers + user journey
    summary.js     # baseline JSON shape + report paths
  scripts/
    smoke.js
    journey.js
    load.js
    stress.js
  compare_ab.sh      # run v1 + v2 journeys, diff summaries
  compare_summaries.py
  run.sh
  README.md
reports/           # gitignored JSON baselines and ab-diff files
```

See [docs/ops/TESTING.md](../docs/ops/TESTING.md) for the full QA guide.
