// k6 load test:  k6 run -e BASE=http://127.0.0.1:8080 -e API_KEY=secret loadtest/ask.js
//
// For an honest latency number, start the server with the semantic cache off and the rate limit raised:
//   $env:DOCPILOT_CACHE = "0"; $env:DOCPILOT_RATE_PER_MIN = "100000"
// Otherwise repeated questions are served from the cache and one API key hits the 429 limiter.
// Optional: -e VUS=30 (peak virtual users), -e HOLD=40s (time at peak).
import http from 'k6/http';
import { check, sleep } from 'k6';

const PEAK = parseInt(__ENV.VUS || '30');

export const options = {
  stages: [
    { duration: '20s', target: Math.max(1, Math.floor(PEAK / 3)) },
    { duration: __ENV.HOLD || '40s', target: PEAK },
    { duration: '20s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'],       // 429s from the rate limiter count as failures
    http_req_duration: ['p(95)<2000'],
  },
  summaryTrendStats: ['avg', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

// All 63 eval questions (answerable and unanswerable), not a handful that the cache would absorb.
const QUESTIONS = open('../data/eval/questions.jsonl')
  .split('\n')
  .filter((l) => l.trim())
  .map((l) => JSON.parse(l).question);

export default function () {
  const q = QUESTIONS[Math.floor(Math.random() * QUESTIONS.length)];
  const res = http.post(`${__ENV.BASE}/ask`, JSON.stringify({ question: q }), {
    headers: { 'Content-Type': 'application/json', 'X-API-Key': __ENV.API_KEY || '' },
  });
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(0.2);
}
