/** Build a compact JSON baseline from k6 summary data (for v2 A/B in Issue 8). */

function metricValues(data, name) {
  const metric = data.metrics[name];
  if (!metric || !metric.values) {
    return null;
  }
  const values = metric.values;
  if ('rate' in values) {
    const out = { rate: values.rate };
    if ('passes' in values) out.passes = values.passes;
    if ('fails' in values) out.fails = values.fails;
    if ('count' in values) out.count = values.count;
    return out;
  }
  const { avg, min, med, max, 'p(90)': p90, 'p(95)': p95, 'p(99)': p99 } = values;
  return { avg, min, med, max, p90, p95, p99 };
}

function endpointMetrics(data) {
  const out = {};
  for (const name of Object.keys(data.metrics)) {
    const match = name.match(/^http_req_duration\{endpoint:([^}]+)\}$/);
    if (!match) {
      continue;
    }
    out[match[1]] = metricValues(data, name);
  }
  return out;
}

function urlsFromEnv() {
  const base = (__ENV.ATWC26_BASE_URL || 'https://atwc26.com').replace(/\/$/, '');
  const analytics = (
    __ENV.ATWC26_ANALYTICS_URL ||
    __ENV.ATWC26_PERF_CANDIDATE_ANALYTICS_URL ||
    base
  ).replace(/\/$/, '');
  const predict = (
    __ENV.ATWC26_PREDICT_URL ||
    __ENV.ATWC26_PERF_CANDIDATE_PREDICT_URL ||
    base
  ).replace(/\/$/, '');
  return { base, analytics, predict };
}

export function reportFilename(testType = 'journey') {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const stack = __ENV.ATWC26_K6_STACK || 'baseline';
  const dir = __ENV.ATWC26_REPORT_DIR || 'reports';
  if (stack === 'baseline' && !__ENV.ATWC26_K6_STACK) {
    return `${dir}/baseline-${stamp}.json`;
  }
  return `${dir}/${testType}-${stack}-${stamp}.json`;
}

export function baselineSummary(data) {
  const urls = urlsFromEnv();
  const testType = __ENV.ATWC26_K6_TEST_TYPE || 'journey';
  return {
    generated_at: new Date().toISOString(),
    stack: __ENV.ATWC26_K6_STACK || 'baseline',
    base_url: urls.base,
    analytics_url: urls.analytics,
    predict_url: urls.predict,
    test_type: testType,
    state: data.state || {},
    metrics: {
      http_req_duration: metricValues(data, 'http_req_duration'),
      http_req_failed: metricValues(data, 'http_req_failed'),
      http_reqs: metricValues(data, 'http_reqs'),
      iterations: metricValues(data, 'iterations'),
      checks: metricValues(data, 'checks'),
    },
    endpoints: endpointMetrics(data),
    threshold_results: summarizeThresholds(data),
  };
}

function summarizeThresholds(data) {
  const results = [];
  const root = data.root_group;
  if (!root || !root.checks) {
    return results;
  }
  for (const check of root.checks) {
    results.push({
      name: check.name,
      passes: check.passes,
      fails: check.fails,
    });
  }
  return results;
}
