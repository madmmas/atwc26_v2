import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.4/index.js';

import { runUserJourney } from '../lib/api.js';
import { baselineSummary, reportFilename } from '../lib/summary.js';
import { stress as scenarios } from '../lib/scenarios.js';
import { stress as thresholds } from '../lib/thresholds.js';

export const options = {
  scenarios,
  thresholds,
};

export default function () {
  runUserJourney();
}

export function handleSummary(data) {
  const reportPath = reportFilename('stress');
  return {
    [reportPath]: JSON.stringify(baselineSummary(data), null, 2),
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
  };
}
