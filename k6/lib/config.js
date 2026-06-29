/** Shared k6 configuration (override via env vars). */
export const baseUrl = (__ENV.ATWC26_BASE_URL || 'https://atwc26.com').replace(/\/$/, '');

// v2 split APIs — fall back to baseUrl (v1 monolith) when unset.
export const analyticsUrl = (
  __ENV.ATWC26_ANALYTICS_URL ||
  __ENV.ATWC26_PERF_CANDIDATE_ANALYTICS_URL ||
  baseUrl
).replace(/\/$/, '');

export const predictUrl = (
  __ENV.ATWC26_PREDICT_URL ||
  __ENV.ATWC26_PERF_CANDIDATE_PREDICT_URL ||
  baseUrl
).replace(/\/$/, '');

export const reportDir = __ENV.ATWC26_REPORT_DIR || 'reports';
export const stackLabel = __ENV.ATWC26_K6_STACK || 'baseline';
export const testType = __ENV.ATWC26_K6_TEST_TYPE || 'journey';

export const defaultHeaders = {
  Accept: 'application/json',
  'Content-Type': 'application/json',
};
