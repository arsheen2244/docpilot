// k6 load test:  k6 run -e BASE=http://127.0.0.1:8080 -e API_KEY=secret loadtest/ask.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '20s', target: 10 },
    { duration: '40s', target: 30 },
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'],       // 429s from the rate limiter count as failures: raise DOCPILOT_RATE_PER_MIN
    http_req_duration: ['p(95)<2000'],
  },
};

const QUESTIONS = [
  'What does a Kubernetes liveness probe do when it fails repeatedly?',
  'What is the default isolation level in PostgreSQL?',
  'Which eviction policy fits a general purpose cache?',
  'What is the default port of MongoDB?',
];

export default function () {
  const q = QUESTIONS[Math.floor(Math.random() * QUESTIONS.length)];
  const res = http.post(`${__ENV.BASE}/ask`, JSON.stringify({ question: q }), {
    headers: { 'Content-Type': 'application/json', 'X-API-Key': __ENV.API_KEY || '' },
  });
  check(res, { 'status 200': (r) => r.status === 200, 'has answer': (r) => !!r.json('answer') });
  sleep(0.2);
}
