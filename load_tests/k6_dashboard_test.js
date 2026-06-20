/**
 * k6_dashboard_test.js — Load Test for Streamlit Dashboard (port 8501)
 * ======================================================================
 * Tests the Streamlit HTTP server directly.
 *
 * Run:
 *   k6 run load_tests/k6_dashboard_test.js \
 *     --summary-export=reports/k6_dashboard_summary.json
 *
 * Prerequisites:
 *   streamlit run frontend/app.py --server.port 8501
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('dashboard_errors');

export const options = {
  vus:      10,
  duration: '2m',
  thresholds: {
    'http_req_duration': ['p(95)<3000'],
    'dashboard_errors':  ['rate<0.1'],
  },
};

const BASE = 'http://localhost:8501';

export default function () {
  const roll = Math.random();

  if (roll < 0.5) {
    // Health check endpoint — very fast
    const r = http.get(`${BASE}/_stcore/health`);
    errorRate.add(!check(r, {
      'dashboard health 200': (res) => res.status === 200,
    }));
  } else if (roll < 0.8) {
    // Main page load
    const r = http.get(`${BASE}/`);
    errorRate.add(!check(r, {
      'dashboard page 200': (res) => res.status === 200,
      'dashboard has html': (res) => res.body && res.body.includes('<html'),
    }));
  } else {
    // Static assets endpoint
    const r = http.get(`${BASE}/static/`);
    // Static may return 404 or redirect — just check it responds
    errorRate.add(!check(r, {
      'dashboard static responds': (res) => res.status < 500,
    }));
  }

  sleep(0.5 + Math.random() * 1.5);
}
