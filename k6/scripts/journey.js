import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.4/index.js';

import { runUserJourney } from '../lib/api.js';
import { reportDir } from '../lib/config.js';
import { baselineSummary } from '../lib/summary.js';
import { journey as scenarios } from '../lib/scenarios.js';
import { journey as thresholds } from '../lib/thresholds.js';

export const options = {
  scenarios,
  thresholds,
};

export default function () {
  runUserJourney();
}

export function handleSummary(data) {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const reportPath = `${reportDir}/baseline-${stamp}.json`;

  return {
    [reportPath]: JSON.stringify(baselineSummary(data), null, 2),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}
