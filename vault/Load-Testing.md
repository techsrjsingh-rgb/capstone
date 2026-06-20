---
tags: [load-testing, k6, locust, performance]
---

# ⚡ Load Testing — K6 & Locust

Sources: `load_tests/k6_script.js`, `load_tests/locustfile.py` · See also: [[MCP-Servers/Orchestrator-MCP]]

---

## K6 (Primary Load Tester)

K6 is a Go-based load testing tool that produces JSON summary reports readable by the Streamlit dashboard's **Load Tests** tab.

### Installation

```bash
# Debian/Ubuntu
sudo gpg --no-default-keyring \
  --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 \
  --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

### Running Tests

```bash
# Full test (all 3 scenarios — ~16 minutes total)
k6 run load_tests/k6_script.js --summary-export=reports/k6_summary.json

# Quick smoke test only (30 seconds)
k6 run --vus 1 --duration 30s load_tests/k6_script.js \
  --summary-export=reports/k6_summary.json

# Dashboard test (Streamlit server)
k6 run load_tests/k6_dashboard_test.js \
  --summary-export=reports/k6_dashboard_summary.json
```

### Test Scenarios (`k6_script.js`)

| Scenario | VUs | Duration | Purpose |
|----------|-----|----------|---------|
| Smoke | 1 | 30s | Baseline — verify servers respond |
| Load | 50 | 5 min | Normal traffic — measure P95 latency |
| Stress | 50 → 200 | 10 min | Find breaking point |

### Targets

- Fraud DB MCP (port 8002): `get_transaction_history`, `get_fraud_blacklist`, `get_fraud_statistics`
- Geo Risk MCP (port 8003): `get_country_risk_score`, `verify_domestic_location`
- Orchestrator MCP (port 8004): `get_system_status` *(no `analyze_transaction` — avoids API cost)*

### Thresholds

- P95 latency (smoke) < 500 ms
- P95 latency (load) < 2000 ms
- Error rate < 10%

---

## Locust (Python-based Tester)

Locust is included for Python-native load testing with a browser UI.

### Running

```bash
locust -f load_tests/locustfile.py --host=http://localhost:8002
# Open http://localhost:8089 to configure and start
```

### User Classes

| Class | Target | Tasks |
|-------|--------|-------|
| `FraudMCPUser` | port 8002 | transaction history (3x), blacklist (2x), stats (1x), report (1x) |
| `GeoMCPUser` | port 8003 | country risk (3x), domestic verify (2x), high-risk regions (1x) |

---

## Viewing Results in Dashboard

After running K6, open the Streamlit dashboard → **⚡ Load Tests** tab.

The tab reads `reports/k6_summary.json` and displays:
- Latency percentiles (P50/P90/P95/P99) bar chart
- Error rate gauge
- Requests/second metric

If the file is missing, the tab shows the exact command to run.
