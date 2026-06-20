---
tags: [mcp, fraud-db, server, port-8002]
---

# 🗄️ Fraud DB MCP Server

Source: `mcp/mcp_server_fraud.py` · Port: **8002** · See also: [[../Architecture]], [[Geo-Risk]], [[Orchestrator-MCP]]

---

## Start

```bash
python mcp/mcp_server_fraud.py
# → Starting Fraud DB MCP Server on port 8002...
```

---

## Tools (4)

### `get_transaction_history`

```bash
curl -X POST http://localhost:8002/tools/get_transaction_history \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST_L", "hours": 24}'
```

Returns: `{customer_id, hours_window, transaction_count, transactions, velocity_flag}`

`velocity_flag` is `true` if `transaction_count >= 2` (RAPID_TXN_COUNT - 1).

---

### `get_fraud_blacklist`

```bash
curl -X POST http://localhost:8002/tools/get_fraud_blacklist \
  -H "Content-Type: application/json" -d '{}'
```

Returns: `{blacklisted_count, accounts}` — 3 pre-seeded blacklisted accounts.

---

### `report_fraud_transaction`

```bash
curl -X POST http://localhost:8002/tools/report_fraud_transaction \
  -H "Content-Type: application/json" \
  -d '{"transaction_id": "TXN020", "reason": "Confirmed card fraud"}'
```

Returns: `{status: "recorded", transaction_id, reason, message}`

---

### `get_fraud_statistics`

```bash
curl -X POST http://localhost:8002/tools/get_fraud_statistics \
  -H "Content-Type: application/json" -d '{}'
```

Returns aggregate statistics: `{period, total_transactions_processed, fraud_detected, fraud_rate_pct, avg_fraud_amount, top_fraud_locations, top_fraud_types}`

---

## Registration (`.mcp.json`)

```json
"fraud-db": {
  "command": "python",
  "args": ["mcp/mcp_server_fraud.py"],
  "description": "Fraud transaction database — history, blacklist, statistics"
}
```
