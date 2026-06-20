/**
 * k6_script.js — Load Tests for Fraud Detection Services
 * ========================================================
 * Targets the load_test_server.py shim (port 8010) which exposes
 * all MCP tool functions as plain JSON POST endpoints.
 *
 * Start the shim first:
 *   python load_tests/load_test_server.py   # port 8010
 *
 * Run (all scenarios):
 *   k6 run load_tests/k6_script.js --summary-export=reports/k6_summary.json
 *
 * Run smoke only (30 seconds):
 *   k6 run --vus 1 --duration 30s load_tests/k6_script.js \
 *     --summary-export=reports/k6_summary.json
 *
 * Also tests Streamlit dashboard health (port 8501).
 *
 * NOTE: analyze_transaction is excluded — it calls the Anthropic API
 * and would exhaust the rate limiter + incur API costs under load.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate   = new Rate('custom_errors');
const fraudDbRt   = new Trend('fraud_db_rt',       true);
const geoRt       = new Trend('geo_rt',             true);
const orchestRt   = new Trend('orchestrator_rt',    true);
const streamlitRt = new Trend('streamlit_rt',       true);

export const options = {
  scenarios: {
    smoke: {
      executor:  'constant-vus',
      vus:       1,
      duration:  '30s',
      tags:      { scenario: 'smoke' },
    },
    load: {
      executor:  'constant-vus',
      vus:       50,
      duration:  '5m',
      startTime: '35s',
      tags:      { scenario: 'load' },
    },
    stress: {
      executor: 'ramping-vus',
      startVUs: 50,
      stages: [
        { duration: '2m', target: 200 },
        { duration: '5m', target: 200 },
        { duration: '3m', target: 0   },
      ],
      startTime: '340s',
      tags:      { scenario: 'stress' },
    },
  },
  thresholds: {
    'http_req_duration': ['p(95)<3000'],
    'http_req_failed':   ['rate<0.15'],
    'custom_errors':     ['rate<0.10'],
  },
};

const BASE     = 'http://localhost:8010';
const DASH     = 'http://localhost:8501';
const HEADERS  = { 'Content-Type': 'application/json' };

function post(path, body) {
  return http.post(`${BASE}${path}`, JSON.stringify(body || {}), { headers: HEADERS });
}

// ── Fraud DB tools ────────────────────────────────────────────────

const CUSTOMERS = ['CUST_L', 'CUST_M', 'CUST_A', 'CUST_B'];

function testFraudDb() {
  const cust = CUSTOMERS[Math.floor(Math.random() * CUSTOMERS.length)];

  const r1 = post('/fraud/get_transaction_history', { customer_id: cust, hours: 24 });
  fraudDbRt.add(r1.timings.duration);
  errorRate.add(!check(r1, {
    'fraud_history 200':  (r) => r.status === 200,
    'fraud_history body': (r) => r.body.length > 2,
  }));

  const r2 = post('/fraud/get_fraud_blacklist', {});
  fraudDbRt.add(r2.timings.duration);
  errorRate.add(!check(r2, { 'fraud_blacklist 200': (r) => r.status === 200 }));

  const r3 = post('/fraud/get_fraud_statistics', {});
  fraudDbRt.add(r3.timings.duration);
  errorRate.add(!check(r3, { 'fraud_stats 200': (r) => r.status === 200 }));

  if (Math.random() < 0.25) {
    const r4 = post('/fraud/report_fraud_transaction', {
      transaction_id: `TXN_K6_${__VU}_${__ITER}`,
      reason:         'automated load test report',
    });
    errorRate.add(!check(r4, { 'fraud_report 200': (r) => r.status === 200 }));
  }
}

// ── Geo Risk tools ────────────────────────────────────────────────

const LOCATIONS = [
  'Lagos, Nigeria', 'Mumbai, India', 'London, UK',
  'Unknown', 'Panama', 'New York, USA', 'Cayman Islands',
];

function testGeoRisk() {
  const loc = LOCATIONS[Math.floor(Math.random() * LOCATIONS.length)];

  const r1 = post('/geo/get_country_risk_score', { location: loc });
  geoRt.add(r1.timings.duration);
  errorRate.add(!check(r1, { 'geo_risk_score 200': (r) => r.status === 200 }));

  const r2 = post('/geo/verify_domestic_location', { location: 'Mumbai, India' });
  geoRt.add(r2.timings.duration);
  errorRate.add(!check(r2, { 'geo_domestic 200': (r) => r.status === 200 }));

  if (Math.random() < 0.30) {
    const r3 = post('/geo/get_high_risk_regions', {});
    geoRt.add(r3.timings.duration);
    errorRate.add(!check(r3, { 'geo_high_risk 200': (r) => r.status === 200 }));
  }

  if (Math.random() < 0.20) {
    const r4 = post('/geo/check_ip_location', { ip_address: '41.0.0.1' });
    geoRt.add(r4.timings.duration);
    errorRate.add(!check(r4, { 'geo_ip 200': (r) => r.status === 200 }));
  }
}

// ── Orchestrator tools (no AI calls) ─────────────────────────────

function testOrchestrator() {
  const r1 = post('/orch/get_system_status', {});
  orchestRt.add(r1.timings.duration);
  errorRate.add(!check(r1, {
    'orch_status 200':     (r) => r.status === 200,
    'orch_status healthy': (r) => r.body.includes('healthy'),
  }));

  if (Math.random() < 0.40) {
    const r2 = post('/orch/get_audit_trail', { correlation_id: 'k6-probe' });
    orchestRt.add(r2.timings.duration);
    errorRate.add(!check(r2, { 'orch_audit 200': (r) => r.status === 200 }));
  }
}

// ── Streamlit dashboard health ────────────────────────────────────

function testDashboard() {
  const r = http.get(`${DASH}/_stcore/health`);
  streamlitRt.add(r.timings.duration);
  errorRate.add(!check(r, { 'dashboard_health 200': (res) => res.status === 200 }));
}

// ── Default VU function ───────────────────────────────────────────

export default function () {
  const roll = Math.random();
  if      (roll < 0.35) testFraudDb();
  else if (roll < 0.65) testGeoRisk();
  else if (roll < 0.85) testOrchestrator();
  else                  testDashboard();

  sleep(0.5 + Math.random() * 1.5);
}
