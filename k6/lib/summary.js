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

export function baselineSummary(data) {
  return {
    generated_at: new Date().toISOString(),
    base_url: baseUrlFromEnv(),
    test_type: 'journey',
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

function baseUrlFromEnv() {
  return (__ENV.ATWC26_BASE_URL || 'https://atwc26.com').replace(/\/$/, '');
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
