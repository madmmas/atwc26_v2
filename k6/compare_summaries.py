#!/usr/bin/env python3
"""Compare two k6 baseline JSON summaries (v1 vs v2 A/B)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Cutover gates — documented in docs/ops/TESTING.md and docs/ops/CUTOVER.md
P95_REGRESSION_FACTOR = 1.25
ERROR_RATE_MAX = 0.10
ERROR_RATE_REGRESSION_FACTOR = 1.10
KEY_ENDPOINTS = ('health', 'overview', 'teams', 'predict')


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _metric(summary: dict, name: str) -> dict | None:
    return (summary.get('metrics') or {}).get(name)


def _p95(metric: dict | None) -> float | None:
    if not metric:
        return None
    return metric.get('p95')


def _rate(metric: dict | None) -> float | None:
    if not metric:
        return None
    return metric.get('rate')


def compare(baseline: dict, candidate: dict) -> dict:
    results: list[dict] = []
    passed = True

    base_fail = _rate(_metric(baseline, 'http_req_failed'))
    cand_fail = _rate(_metric(candidate, 'http_req_failed'))
    if cand_fail is not None:
        ok = cand_fail <= ERROR_RATE_MAX
        if base_fail is not None and base_fail > 0:
            ok = ok and cand_fail <= base_fail * ERROR_RATE_REGRESSION_FACTOR
        elif base_fail == 0:
            ok = ok and cand_fail <= ERROR_RATE_MAX
        results.append({
            'metric': 'http_req_failed.rate',
            'baseline': base_fail,
            'candidate': cand_fail,
            'limit': ERROR_RATE_MAX,
            'passed': ok,
        })
        passed = passed and ok

    base_p95 = _p95(_metric(baseline, 'http_req_duration'))
    cand_p95 = _p95(_metric(candidate, 'http_req_duration'))
    if base_p95 is not None and cand_p95 is not None:
        limit = base_p95 * P95_REGRESSION_FACTOR
        ok = cand_p95 <= limit
        results.append({
            'metric': 'http_req_duration.p95',
            'baseline': base_p95,
            'candidate': cand_p95,
            'limit': limit,
            'passed': ok,
        })
        passed = passed and ok

    for endpoint in KEY_ENDPOINTS:
        base_ep = (baseline.get('endpoints') or {}).get(endpoint)
        cand_ep = (candidate.get('endpoints') or {}).get(endpoint)
        base_ep_p95 = _p95(base_ep)
        cand_ep_p95 = _p95(cand_ep)
        if base_ep_p95 is None or cand_ep_p95 is None:
            continue
        limit = base_ep_p95 * P95_REGRESSION_FACTOR
        ok = cand_ep_p95 <= limit
        results.append({
            'metric': f'endpoint:{endpoint}.p95',
            'baseline': base_ep_p95,
            'candidate': cand_ep_p95,
            'limit': limit,
            'passed': ok,
        })
        passed = passed and ok

    return {
        'passed': passed,
        'baseline': {
            'stack': baseline.get('stack'),
            'base_url': baseline.get('base_url'),
            'analytics_url': baseline.get('analytics_url'),
            'predict_url': baseline.get('predict_url'),
            'generated_at': baseline.get('generated_at'),
            'test_type': baseline.get('test_type'),
        },
        'candidate': {
            'stack': candidate.get('stack'),
            'base_url': candidate.get('base_url'),
            'analytics_url': candidate.get('analytics_url'),
            'predict_url': candidate.get('predict_url'),
            'generated_at': candidate.get('generated_at'),
            'test_type': candidate.get('test_type'),
        },
        'checks': results,
        'thresholds': {
            'p95_regression_factor': P95_REGRESSION_FACTOR,
            'error_rate_max': ERROR_RATE_MAX,
            'error_rate_regression_factor': ERROR_RATE_REGRESSION_FACTOR,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Compare k6 baseline JSON files')
    parser.add_argument('baseline', type=Path, help='v1 baseline summary JSON')
    parser.add_argument('candidate', type=Path, help='v2 candidate summary JSON')
    parser.add_argument('-o', '--output', type=Path, help='Write diff JSON here')
    args = parser.parse_args()

    diff = compare(_load(args.baseline), _load(args.candidate))
    text = json.dumps(diff, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + '\n')
        print(f"wrote {args.output}")

    for check in diff['checks']:
        status = 'OK' if check['passed'] else 'FAIL'
        print(
            f"[{status}] {check['metric']}: "
            f"baseline={check.get('baseline')} candidate={check.get('candidate')} "
            f"limit={check.get('limit')}"
        )

    print(f"\noverall: {'PASS' if diff['passed'] else 'FAIL'}")
    return 0 if diff['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
