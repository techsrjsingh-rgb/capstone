"""
Observability module: structured logging, correlation IDs, and metrics.

Every agent call is assigned a unique correlation_id so the full chain
of decisions (Rules → Pattern → Risk → Coordinator) can be traced end-to-end.
"""

import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Any

# Configure the root logger to output one JSON line per log event
logging.basicConfig(level=logging.INFO, format="%(message)s")
_logger = logging.getLogger("fraud_agent")


class ObservabilityManager:
    """
    Tracks every agent invocation and decision with a correlation ID.
    Stores everything in memory for the dashboard to display.
    """

    def __init__(self):
        # correlation_id → list of trace events
        self._traces: dict[str, list[dict]] = {}
        # metric_name → list of {value, tags, timestamp}
        self._metrics: dict[str, list[dict]] = {}

    # ──────────────────────────────────────────────────────────────
    # Correlation ID – one per transaction / batch
    # ──────────────────────────────────────────────────────────────

    def generate_correlation_id(self) -> str:
        """Create a unique ID that ties together all agent calls for one request."""
        cid = str(uuid.uuid4())
        self._traces[cid] = []
        return cid

    # ──────────────────────────────────────────────────────────────
    # Agent tracing
    # ──────────────────────────────────────────────────────────────

    def trace(
        self,
        correlation_id: str,
        agent_name: str,
        input_data: Any,
        output_data: Any,
        duration_ms: float,
    ) -> None:
        """Record one agent invocation: who was called, what was input/output, how long."""
        event = {
            "type": "agent_trace",
            "correlation_id": correlation_id,
            "agent_name": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": round(duration_ms, 2),
            "input_summary": _shorten(input_data),
            "output_summary": _shorten(output_data),
        }
        self._traces.setdefault(correlation_id, []).append(event)
        _logger.info(json.dumps(event))

    def log_decision(
        self,
        correlation_id: str,
        entity_id: str,
        decision: str,
        reasoning: str,
        confidence: float,
    ) -> None:
        """Record the final classification decision for a transaction."""
        event = {
            "type": "decision",
            "correlation_id": correlation_id,
            "entity_id": entity_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
            "reasoning_snippet": reasoning[:300],
            "confidence": confidence,
        }
        self._traces.setdefault(correlation_id, []).append(event)
        _logger.info(json.dumps(event))

    # ──────────────────────────────────────────────────────────────
    # Metrics
    # ──────────────────────────────────────────────────────────────

    def emit_metric(self, metric_name: str, value: float, tags: dict | None = None) -> None:
        """Emit a numeric metric (e.g. response_time_ms, risk_score, fraud_count)."""
        entry = {
            "metric": metric_name,
            "value": value,
            "tags": tags or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._metrics.setdefault(metric_name, []).append(entry)
        _logger.info(json.dumps({"type": "metric", **entry}))

    def get_metrics_summary(self) -> dict:
        """Return count/avg/min/max for every collected metric."""
        out = {}
        for name, entries in self._metrics.items():
            vals = [e["value"] for e in entries]
            out[name] = {
                "count": len(vals),
                "avg":   round(sum(vals) / len(vals), 2) if vals else 0,
                "min":   min(vals) if vals else 0,
                "max":   max(vals) if vals else 0,
            }
        return out

    # ──────────────────────────────────────────────────────────────
    # Audit trail retrieval
    # ──────────────────────────────────────────────────────────────

    def get_audit_trail(self, correlation_id: str) -> list[dict]:
        """Return all events for a given correlation ID."""
        return self._traces.get(correlation_id, [])

    def get_all_traces(self) -> dict:
        return dict(self._traces)


def _shorten(data: Any, max_len: int = 250) -> str:
    """Convert any value to a short string for log output."""
    if data is None:
        return "None"
    text = json.dumps(data, default=str) if isinstance(data, (dict, list)) else str(data)
    return text[:max_len] + "…" if len(text) > max_len else text


# Module-level singleton – import this everywhere
observability = ObservabilityManager()
