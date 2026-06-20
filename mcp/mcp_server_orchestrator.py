"""
MCP Server 3 – Fraud Detection Orchestrator Pipeline
Exposes the full 4-agent fraud detection pipeline as MCP tools.

Run this server before using orchestrator-based analysis:
  python mcp/mcp_server_orchestrator.py

Tools exposed:
  analyze_transaction  – run full 4-agent pipeline on a single transaction
  analyze_batch        – run pipeline on multiple transactions by ID
  get_system_status    – health check and system configuration
  get_audit_trail      – retrieve trace events by correlation ID
"""

from mcp.server.fastmcp import FastMCP
from config.settings import config
from observability.observability import observability
from core.data import SAMPLE_TRANSACTIONS
from datetime import datetime, timezone

app = FastMCP("fraud-orchestrator", port=config.ORCHESTRATOR_MCP_PORT)

# Lazy singleton — created on first tool call to avoid import-time API init
_orchestrator = None


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        from orchestrator.agent import FraudDetectionOrchestrator
        _orchestrator = FraudDetectionOrchestrator()
    return _orchestrator


# ──────────────────────────────────────────────────────────────────
# Tool 1: Analyze a single transaction through the full pipeline
# ──────────────────────────────────────────────────────────────────

@app.tool()
def analyze_transaction(
    transaction_id: str,
    customer_id: str,
    amount: float,
    location: str,
    transaction_type: str,
    time: str,
) -> dict:
    """
    Run the full 4-agent fraud detection pipeline on a single transaction.
    Returns risk_level (Safe/Suspicious/High Risk), risk_score (0-100),
    fraud_reasons, explanation, recommended_action, and correlation_id.
    """
    txn = {
        "transaction_id":   transaction_id,
        "customer_id":      customer_id,
        "amount":           float(amount),
        "location":         location,
        "transaction_type": transaction_type,
        "time":             time,
    }
    try:
        orch = _get_orchestrator()
        result = orch.analyze(txn, SAMPLE_TRANSACTIONS)
        # Ensure serializable — convert any non-serializable values
        return {
            "transaction_id":     result.get("transaction_id", transaction_id),
            "risk_level":         result.get("risk_level", "Suspicious"),
            "risk_score":         float(result.get("risk_score", 0)),
            "fraud_reasons":      result.get("fraud_reasons", []),
            "explanation":        result.get("explanation", ""),
            "recommended_action": result.get("recommended_action", "monitor"),
            "confidence":         float(result.get("confidence", 0.5)),
            "pattern_analysis":   result.get("pattern_analysis", ""),
            "correlation_id":     result.get("correlation_id", ""),
            "agent_trace":        result.get("agent_trace", []),
        }
    except Exception as e:
        return {
            "transaction_id":     transaction_id,
            "risk_level":         "Suspicious",
            "risk_score":         50.0,
            "fraud_reasons":      [f"Pipeline error: {str(e)}"],
            "explanation":        "Pipeline failed — transaction flagged for manual review.",
            "recommended_action": "monitor",
            "confidence":         0.5,
            "pattern_analysis":   "",
            "correlation_id":     "",
            "agent_trace":        [],
        }


# ──────────────────────────────────────────────────────────────────
# Tool 2: Analyze a batch of transactions by ID
# ──────────────────────────────────────────────────────────────────

@app.tool()
def analyze_batch(transaction_ids: list) -> dict:
    """
    Run the full pipeline on a list of transaction IDs from the sample dataset.
    Returns results for each transaction plus summary counts.
    """
    matched = [t for t in SAMPLE_TRANSACTIONS if t["transaction_id"] in transaction_ids]
    if not matched:
        return {
            "error": "No matching transactions found",
            "requested_ids": transaction_ids,
            "results": [],
            "summary": {"total": 0, "safe": 0, "suspicious": 0, "high_risk": 0},
        }

    try:
        orch = _get_orchestrator()
        results = orch.analyze_all(matched)
        summary = {
            "total":     len(results),
            "safe":      sum(1 for r in results if r.get("risk_level") == "Safe"),
            "suspicious": sum(1 for r in results if r.get("risk_level") == "Suspicious"),
            "high_risk": sum(1 for r in results if r.get("risk_level") == "High Risk"),
        }
        # Serialize results
        serialized = []
        for r in results:
            serialized.append({
                "transaction_id":     r.get("transaction_id", ""),
                "risk_level":         r.get("risk_level", "Suspicious"),
                "risk_score":         float(r.get("risk_score", 0)),
                "fraud_reasons":      r.get("fraud_reasons", []),
                "recommended_action": r.get("recommended_action", "monitor"),
                "correlation_id":     r.get("correlation_id", ""),
            })
        return {"results": serialized, "summary": summary}
    except Exception as e:
        return {
            "error": str(e),
            "results": [],
            "summary": {"total": 0, "safe": 0, "suspicious": 0, "high_risk": 0},
        }


# ──────────────────────────────────────────────────────────────────
# Tool 3: System health check and configuration
# ──────────────────────────────────────────────────────────────────

@app.tool()
def get_system_status() -> dict:
    """
    Return current system configuration and metrics summary.
    No AI call is made — safe to use in load tests.
    """
    metrics = observability.get_metrics_summary()
    return {
        "status":           "healthy",
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "primary_model":    config.PRIMARY_MODEL,
        "fallback_model":   config.FALLBACK_MODEL,
        "fraud_mcp_port":   config.FRAUD_MCP_PORT,
        "geo_mcp_port":     config.GEO_MCP_PORT,
        "orchestrator_port": config.ORCHESTRATOR_MCP_PORT,
        "sample_transactions": len(SAMPLE_TRANSACTIONS),
        "high_amount_threshold": config.HIGH_AMOUNT_THRESHOLD,
        "rapid_txn_window_sec":  config.RAPID_TXN_WINDOW_SEC,
        "rate_limit_per_min":    config.RATE_LIMIT_REQUESTS,
        "metrics_summary":       metrics,
    }


# ──────────────────────────────────────────────────────────────────
# Tool 4: Retrieve audit trail by correlation ID
# ──────────────────────────────────────────────────────────────────

@app.tool()
def get_audit_trail(correlation_id: str) -> dict:
    """
    Return all trace events for a given correlation ID.
    Correlation IDs are returned in analyze_transaction responses.
    """
    events = observability.get_audit_trail(correlation_id)
    return {
        "correlation_id": correlation_id,
        "event_count":    len(events),
        "events":         events,
    }


# ──────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Starting Fraud Orchestrator MCP Server on port {config.ORCHESTRATOR_MCP_PORT}...")
    print("Tools: analyze_transaction, analyze_batch, get_system_status, get_audit_trail")
    app.run(transport="sse")
