/** k6 executor scenarios. */

export const smoke = {
  smoke: {
    executor: 'shared-iterations',
    vus: 1,
    iterations: 1,
    maxDuration: '1m',
  },
};

export const journey = {
  journey: {
    executor: 'constant-vus',
    vus: 1,
    duration: '1m',
  },
};

export const load = {
  load: {
    executor: 'ramping-vus',
    startVUs: 0,
    stages: [
      { duration: '30s', target: 5 },
      { duration: '1m', target: 5 },
      { duration: '30s', target: 0 },
    ],
    gracefulRampDown: '15s',
  },
};

export const stress = {
  stress: {
    executor: 'ramping-vus',
    startVUs: 0,
    stages: [
      { duration: '1m', target: 10 },
      { duration: '2m', target: 10 },
      { duration: '30s', target: 0 },
    ],
    gracefulRampDown: '30s',
  },
};
