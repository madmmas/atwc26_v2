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
