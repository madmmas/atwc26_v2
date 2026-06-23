# k6 performance baseline (v1)

Establish latency and error-rate baselines for the v1 monolith before the v2
refactor. Default target is production: [atwc26.com](https://atwc26.com).

## Prerequisites

Install [k6](https://grafana.com/docs/k6/latest/set-up/install-k6/):

```bash
# macOS
brew install k6

# Linux (Debian/Ubuntu) — see docs for other distros
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

## Quick start

From the repo root:

```bash
make k6-smoke      # 1 VU, health + overview
make k6-journey    # ramped VUs, full API journey + JSON report
```

Or run the wrapper directly:

```bash
./k6/run.sh smoke
./k6/run.sh journey
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ATWC26_BASE_URL` | `https://atwc26.com` | API origin (no trailing slash) |
| `ATWC26_REPORT_DIR` | `reports/` | Where journey baseline JSON is written |
| `ATWC26_K6_PAUSE_SEC` | `0.15` | Pause between API calls (respects prod rate limits) |

Examples:

```bash
# Local Docker stack (nginx on :8080)
ATWC26_BASE_URL=http://localhost:8080 make k6-smoke

# Custom report location
ATWC26_REPORT_DIR=/tmp/atwc26-reports make k6-journey
```

## Layout

```text
k6/
  lib/
    config.js      # base URL, headers
    scenarios.js   # VU / duration profiles
    thresholds.js  # pass/fail gates
    api.js         # shared HTTP helpers + user journey
    summary.js     # baseline JSON shape for Issue 8 A/B
  scripts/
    smoke.js       # minimal readiness check
    journey.js     # overview → explore → predict flow
  run.sh
  README.md
reports/           # gitignored baseline JSON (journey only)
```

## Scripts

### `smoke.js`

Single iteration against `/api/health` and `/api/overview`. Use after deploys or
before a longer journey run.

### `journey.js`

Simulates a typical session:

1. Health + overview
2. Teams list, players, leaderboard
3. Match list + first match detail
4. Build two 4-3-3 XIs and `POST /api/predict`

Writes `reports/baseline-<timestamp>.json` with aggregate latency, error rate,
and per-endpoint `p95` values. This file is the v1 reference for v2 A/B
comparison (Issue 8).

## Makefile targets

| Target | Description |
|--------|-------------|
| `make k6-smoke` | Fast smoke test |
| `make k6-journey` | Journey + baseline JSON |

See also [docs/TESTING.md](../docs/TESTING.md) for the full QA guide.
