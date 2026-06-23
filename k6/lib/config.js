/** Shared k6 configuration (override via env vars). */
export const baseUrl = (__ENV.ATWC26_BASE_URL || 'https://atwc26.com').replace(/\/$/, '');
export const reportDir = __ENV.ATWC26_REPORT_DIR || 'reports';

export const defaultHeaders = {
  Accept: 'application/json',
  'Content-Type': 'application/json',
};
