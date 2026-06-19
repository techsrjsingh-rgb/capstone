"""
Governance module: input validation, compliance checks, bias detection,
rate limiting, and append-only audit logging.

Every agent decision must pass through governance to ensure the system
is fair, explainable, and compliant with internal audit requirements.
"""

import json
import time
from datetime import datetime, timezone
from typing import Any

from .config import config


class GovernanceManager:
    """Enforces data quality, compliance, and fairness rules."""

    def __init__(self, audit_log_path: str = config.AUDIT_LOG_FILE):
        self.audit_log_path = audit_log_path

    # ──────────────────────────────────────────────────────────────
    # Transaction input validation
    # ──────────────────────────────────────────────────────────────

    def validate_transaction(self, txn: dict) -> tuple[bool, list[str]]:
        """
        Validate one transaction record before it enters the agent pipeline.
        Returns (is_valid, list_of_errors).
        """
        errors = []
        required = ["transaction_id", "customer_id", "amount",
                    "location", "transaction_type", "time"]

        for field in required:
            if field not in txn or txn[field] is None:
                errors.append(f"Missing required field: '{field}'")

        if errors:
            return False, errors

        # Amount must be a non-negative number
        try:
            amt = float(txn["amount"])
            if amt < 0:
                errors.append("Amount cannot be negative")
        except (ValueError, TypeError):
            errors.append("Amount must be a number")

        # transaction_type must be a known value
        valid_types = {"purchase", "withdrawal", "transfer",
                       "deposit", "payment", "refund"}
        if str(txn.get("transaction_type", "")).lower() not in valid_types:
            errors.append(
                f"Unknown transaction_type '{txn['transaction_type']}'. "
                f"Allowed: {', '.join(sorted(valid_types))}"
            )

        # IDs must not be empty strings
        for id_field in ["transaction_id", "customer_id"]:
            if not str(txn.get(id_field, "")).strip():
                errors.append(f"'{id_field}' cannot be empty")

        return len(errors) == 0, errors

    # ──────────────────────────────────────────────────────────────
    # Compliance check
    # ──────────────────────────────────────────────────────────────

    def check_compliance(self, decision: str, reasoning: str) -> tuple[bool, str]:
        """
        Ensure the agent's decision is explainable.
        Every fraud decision must have at least a brief justification.
        """
        valid = {"safe", "suspicious", "high risk"}
        if decision.lower() not in valid:
            return False, f"Unknown decision '{decision}'. Must be one of: {valid}"

        if not reasoning or len(reasoning.strip()) < 15:
            return False, "Decision must include a meaningful explanation (≥15 chars)"

        return True, "Compliant"

    # ──────────────────────────────────────────────────────────────
    # Bias / fairness check
    # ──────────────────────────────────────────────────────────────

    def check_fairness(self, txn: dict, decision: str) -> dict:
        """
        Basic fairness flag: ensure 'High Risk' decisions are not driven
        solely by location name without corroborating evidence.
        """
        flags = []
        location = str(txn.get("location", "")).lower()

        if decision.lower() == "high risk":
            # Flag if location is the only known trigger (check by amount too)
            amount = float(txn.get("amount", 0))
            if amount < config.HIGH_AMOUNT_THRESHOLD:
                flags.append(
                    f"High Risk assigned to low-amount transaction "
                    f"(₹{amount:,.0f}) — verify location '{location}' "
                    "is the sole trigger."
                )
        return {"has_flags": len(flags) > 0, "flags": flags}

    # ──────────────────────────────────────────────────────────────
    # Audit logging (append-only JSONL)
    # ──────────────────────────────────────────────────────────────

    def audit_log(
        self,
        correlation_id: str,
        agent: str,
        action: str,
        data: Any,
    ) -> None:
        """
        Append one record to the audit log file.
        Each line is valid JSON — easy to grep, stream, or ingest into SIEM.
        """
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": correlation_id,
            "agent": agent,
            "action": action,
            "data": _safe_str(data)[:400],
        }
        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            pass   # never let audit logging crash the main pipeline


# ──────────────────────────────────────────────────────────────────
# Rate limiter (token-bucket)
# ──────────────────────────────────────────────────────────────────

class RateLimiter:
    """
    Simple token-bucket rate limiter.
    Allows at most `max_requests` calls per `window_seconds`.
    """

    def __init__(
        self,
        max_requests: int = config.RATE_LIMIT_REQUESTS,
        window_seconds: int = 60,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: list[float] = []

    def check(self) -> tuple[bool, str]:
        """Returns (allowed, message). Call before each agent invocation."""
        now = time.time()
        # Drop timestamps outside the window
        self._timestamps = [t for t in self._timestamps if now - t < self.window_seconds]

        if len(self._timestamps) >= self.max_requests:
            wait = self.window_seconds - (now - self._timestamps[0])
            return False, f"Rate limit exceeded. Retry in {wait:.0f}s."

        self._timestamps.append(now)
        return True, "OK"


def _safe_str(data: Any) -> str:
    try:
        return json.dumps(data, default=str)
    except Exception:
        return str(data)


# Module-level singletons
governance = GovernanceManager()
rate_limiter = RateLimiter()
