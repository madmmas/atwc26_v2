import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.4/index.js';

import { getJson } from '../lib/api.js';
import { smoke as scenarios } from '../lib/scenarios.js';
import { smoke as thresholds } from '../lib/thresholds.js';

export const options = {
  scenarios,
  thresholds,
};

export default function () {
  getJson('/api/health', 'health');
  getJson('/api/overview', 'overview');
}

export function handleSummary(data) {
  return {
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}
