/** Pass/fail thresholds for smoke and journey runs. */

export const smoke = {
  http_req_failed: ['rate<0.01'],
  http_req_duration: ['p(95)<3000'],
  checks: ['rate>0.99'],
};

export const journey = {
  http_req_failed: ['rate<0.10'],
  http_req_duration: ['p(95)<8000'],
  'http_req_duration{endpoint:health}': ['p(95)<2000'],
  'http_req_duration{endpoint:overview}': ['p(95)<3000'],
  'http_req_duration{endpoint:teams}': ['p(95)<3000'],
  'http_req_duration{endpoint:players}': ['p(95)<3000'],
  'http_req_duration{endpoint:matches}': ['p(95)<3000'],
  'http_req_duration{endpoint:predict}': ['p(95)<10000'],
  checks: ['rate>0.90'],
};
