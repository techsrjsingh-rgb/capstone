"""
Hooks (middleware) for the Fraud Detection Agent.

Hooks wrap every agent invocation to ensure:
  pre_process  – validate input, rate-limit, sanitize, add correlation ID
  post_process – compliance check, fairness flag, audit log, emit metrics
  on_error     – safe fallback, error logging (never crash the pipeline)
"""

from core.governance import governance, rate_limiter
from observability.observability import observability


class FraudHookManager:
    """
    Middleware that wraps every fraud detection agent call.
    Think of this as a pipeline interceptor — it runs automatically
    before and after the AI agent processes each transaction.
    """

    # ──────────────────────────────────────────────────────────────
    # Pre-processing hook
    # ──────────────────────────────────────────────────────────────

    def pre_process(self, transaction: dict) -> dict:
        """
        Run before the agent receives a transaction.
        Steps:
          1. Rate limit check — reject if too many requests
          2. Input sanitization — strip whitespace, normalize types
          3. Schema validation — all required fields present and valid
          4. Generate correlation ID — unique ID for end-to-end tracing
        Returns enriched transaction dict (with correlation_id added).
        Raises ValueError if any check fails.
        """
        # 1. Rate limit
        allowed, msg = rate_limiter.check()
        if not allowed:
            raise ValueError(f"Rate limit: {msg}")

        # 2. Sanitize
        txn = _sanitize(transaction)

        # 3. Validate
        is_valid, errors = governance.validate_transaction(txn)
        if not is_valid:
            raise ValueError(f"Invalid transaction: {'; '.join(errors)}")

        # 4. Correlation ID
        cid = observability.generate_correlation_id()
        txn["correlation_id"] = cid

        # Audit entry: transaction entered the system
        governance.audit_log(
            correlation_id=cid,
            agent="FraudHookManager",
            action="pre_process",
            data={
                "transaction_id": txn.get("transaction_id"),
                "amount": txn.get("amount"),
                "location": txn.get("location"),
            },
        )

        return txn

    # ──────────────────────────────────────────────────────────────
    # Post-processing hook
    # ──────────────────────────────────────────────────────────────

    def post_process(self, result: dict, correlation_id: str) -> dict:
        """
        Run after the agent produces a classification result.
        Steps:
          1. Compliance check — decision must be explainable
          2. Fairness check — ensure no unfair bias in High Risk decisions
          3. Audit log the final decision
          4. Emit telemetry metrics
        Returns enriched result dict.
        """
        decision  = result.get("risk_level", "")
        reasoning = "; ".join(result.get("fraud_reasons", [])) or "No fraud indicators detected"

        # 1. Compliance
        compliant, compliance_msg = governance.check_compliance(decision, reasoning)
        result["compliance_status"] = compliance_msg
        if not compliant:
            # Override to Suspicious if decision is malformed
            result["risk_level"] = "Suspicious"
            result["compliance_override"] = True

        # 2. Fairness check (uses original transaction stored in result)
        original_txn = result.pop("_original_txn", {})
        fairness = governance.check_fairness(original_txn, decision)
        result["fairness_flags"] = fairness.get("flags", [])

        # 3. Audit log
        governance.audit_log(
            correlation_id=correlation_id,
            agent="FraudDetectionAgent",
            action="decision",
            data={
                "transaction_id": result.get("transaction_id"),
                "risk_level": decision,
                "compliance": compliance_msg,
            },
        )

        # 4. Metrics
        observability.log_decision(
            correlation_id=correlation_id,
            entity_id=result.get("transaction_id", "unknown"),
            decision=decision,
            reasoning=reasoning,
            confidence=result.get("confidence", 0.8),
        )
        observability.emit_metric(
            "fraud_classification",
            1.0,
            tags={"risk_level": decision},
        )
        observability.emit_metric(
            "risk_score",
            result.get("risk_score", 0.0),
            tags={"transaction_id": result.get("transaction_id")},
        )

        result["correlation_id"] = correlation_id
        return result

    # ──────────────────────────────────────────────────────────────
    # Error hook
    # ──────────────────────────────────────────────────────────────

    def on_error(self, error: Exception, context: dict) -> dict:
        """
        Called when any unhandled exception occurs in the pipeline.
        Returns a safe fallback result — never crashes the dashboard.
        """
        cid = context.get("correlation_id", "unknown")
        txn_id = context.get("transaction_id", "unknown")

        observability.emit_metric(
            "agent_error", 1.0,
            tags={"error_type": type(error).__name__}
        )
        governance.audit_log(
            correlation_id=cid,
            agent="FraudHookManager",
            action="error",
            data={"error": str(error), "transaction_id": txn_id},
        )

        # Safe fallback — mark as Suspicious so a human reviews it
        return {
            "transaction_id": txn_id,
            "risk_level": "Suspicious",
            "fraud_reasons": ["Automated assessment failed — flagged for manual review"],
            "risk_score": 50.0,
            "explanation": "An error occurred during analysis. Manual review required.",
            "correlation_id": cid,
            "error": str(error),
        }


# ──────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────

def _sanitize(txn: dict) -> dict:
    """Strip whitespace from string fields and normalize transaction_type to lowercase."""
    clean = dict(txn)
    for k, v in clean.items():
        if isinstance(v, str):
            clean[k] = v.strip()
    if "transaction_type" in clean:
        clean["transaction_type"] = clean["transaction_type"].lower()
    return clean
