import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('error_rate');

// Target URL injected via K6_STAGING_URL env var (set in CI)
const BASE_URL = __ENV.K6_STAGING_URL || 'http://localhost';

export const options = {
  // Smoke test: low load, quick — just proves the staging env is healthy
  stages: [
    { duration: '30s', target: 5 },   // ramp up to 5 users
    { duration: '1m',  target: 5 },   // hold for 1 minute
    { duration: '15s', target: 0 },   // ramp down
  ],
  thresholds: {
    // Gate: block PR to main if staging is unhealthy
    http_req_failed:   ['rate<0.01'],   // <1% errors
    http_req_duration: ['p(95)<2000'],  // 95% of requests under 2s
    error_rate:        ['rate<0.01'],
  },
};

export default function () {
  // 1. Homepage
  let res = http.get(`${BASE_URL}/`, { tags: { name: 'homepage' } });
  check(res, { 'homepage 200': (r) => r.status === 200 });
  errorRate.add(res.status !== 200);
  sleep(1);

  // 2. Register page loads
  res = http.get(`${BASE_URL}/register`, { tags: { name: 'register_page' } });
  check(res, { 'register page 200': (r) => r.status === 200 });
  errorRate.add(res.status !== 200);
  sleep(1);

  // 3. Login page loads
  res = http.get(`${BASE_URL}/login`, { tags: { name: 'login_page' } });
  check(res, { 'login page 200': (r) => r.status === 200 });
  errorRate.add(res.status !== 200);
  sleep(1);

  // 4. Auth service health (internal, via ingress)
  res = http.get(`${BASE_URL}/api/auth/health`, { tags: { name: 'auth_health' } });
  // 200 or 404 acceptable (depends on routing) — we just don't want 5xx
  check(res, { 'auth no 5xx': (r) => r.status < 500 });
  errorRate.add(res.status >= 500);
  sleep(1);
}
