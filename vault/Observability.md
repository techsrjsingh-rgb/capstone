---
tags: [observability, opentelemetry, tracing, metrics, signoz]
---

# 📡 Observability — Tracing, Metrics & OTEL

Source: `observability/observability.py` · Docker: `docker-compose.yml` · See also: [[Architecture]], [[Governance]]

---

## Two Modes

| Mode | When | Storage |
|------|------|---------|
| **In-memory** | `OTEL_EXPORTER_OTLP_ENDPOINT` not set | Python dict, lost on restart |
| **OpenTelemetry** | Endpoint configured | SigNoz / Grafana (persistent) |

---

## Correlation ID

Every transaction request gets a unique UUID that ties together all agent calls end-to-end:

```python
from observability.observability import observability
cid = observability.generate_correlation_id()  # "3f8a2b1c-…"
```

The ID is visible in the Streamlit dashboard under each transaction's expander.

---

## OpenTelemetry Setup

### Environment Variables

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=fraud-detection
```

### What is instrumented

Each named agent call emits a span with attributes:

| Attribute | Value |
|-----------|-------|
| `correlation_id` | UUID linking all spans for one request |
| `agent.name` | `RulesAgent`, `PatternAgent`, etc. |
| `duration_ms` | Execution time in milliseconds |

Each metric emitted via `observability.emit_metric()` is forwarded as an OTEL counter.

---

## Starting SigNoz

```bash
# Start SigNoz only (no app)
docker compose up signoz -d

# Start everything
docker compose up -d
```

SigNoz UI: **http://localhost:3301**
- Services → `fraud-detection` → Traces
- Metrics explorer → `fraud_classification`, `risk_score`, `response_time_ms`

---

## Programmatic Access (in-memory mode)

```python
from observability.observability import observability

# Get all events for a transaction
events = observability.get_audit_trail(correlation_id)

# Get metrics summary
summary = observability.get_metrics_summary()
# → {"risk_score": {"count": 22, "avg": 45.2, "min": 0, "max": 100}, ...}

# Get all traces
all_traces = observability.get_all_traces()
```

---

## Metrics Emitted

| Metric | When | Tags |
|--------|------|------|
| `fraud_classification` | After each decision | `risk_level` |
| `risk_score` | After each analysis | `transaction_id` |
| `response_time_ms` | Per agent call | `agent_name` |
| `agent_error` | On any pipeline error | `error_type` |
