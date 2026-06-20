---
tags: [mcp, orchestrator, server, port-8004, pipeline]
---

# 🔌 Orchestrator MCP Server

Source: `mcp/mcp_server_orchestrator.py` · Port: **8004** · See also: [[../Architecture]], [[../Agents/Orchestrator]], [[Fraud-DB]], [[Geo-Risk]]

---

## Start

```bash
python mcp/mcp_server_orchestrator.py
# → Starting Fraud Orchestrator MCP Server on port 8004...
```

---

## Purpose

Exposes the full 4-agent fraud detection pipeline as MCP tools. Any MCP-compatible client (Claude Desktop, other agents, load testers) can analyze transactions without touching Python directly.

---

## Tools (4)

### `analyze_transaction`

Runs the complete Rules → Pattern → Risk Scorer → Coordinator pipeline.

```bash
curl -X POST http://localhost:8004/tools/analyze_transaction \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id":   "TXN001",
    "customer_id":      "CUST_A",
    "amount":           1500,
    "location":         "Mumbai, India",
    "transaction_type": "purchase",
    "time":             "2024-06-15T09:30:00"
  }'
```

Returns: `{transaction_id, risk_level, risk_score, fraud_reasons, explanation, recommended_action, confidence, pattern_analysis, correlation_id, agent_trace}`

⚠️ This tool calls the Anthropic API — **do not use in load tests**.

---

### `analyze_batch`

```bash
curl -X POST http://localhost:8004/tools/analyze_batch \
  -H "Content-Type: application/json" \
  -d '{"transaction_ids": ["TXN001", "TXN009", "TXN020"]}'
```

Looks up transactions by ID from the sample dataset, runs the full pipeline on each.
Returns: `{results: [...], summary: {total, safe, suspicious, high_risk}}`

---

### `get_system_status`

Safe for load testing — no AI call.

```bash
curl -X POST http://localhost:8004/tools/get_system_status \
  -H "Content-Type: application/json" -d '{}'
```

Returns: `{status: "healthy", timestamp, primary_model, fallback_model, sample_transactions, metrics_summary, ...}`

---

### `get_audit_trail`

```bash
curl -X POST http://localhost:8004/tools/get_audit_trail \
  -H "Content-Type: application/json" \
  -d '{"correlation_id": "3f8a2b1c-..."}'
```

Returns all OTEL/in-memory trace events for the given correlation ID.

---

## Registration (`.mcp.json`)

```json
"fraud-orchestrator": {
  "command": "python",
  "args": ["mcp/mcp_server_orchestrator.py"],
  "description": "Full 4-agent fraud detection pipeline — analyze transactions via MCP"
}
```

---

## Load Testing Note

Only `get_system_status` and `get_audit_trail` are safe for load tests (no Anthropic API calls). See [[../Load-Testing]] for K6 scripts.
