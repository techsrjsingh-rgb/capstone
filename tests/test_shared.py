"""
Unit tests for shared/governance.py and shared/observability.py

Tests:
  - Transaction validation (valid and invalid inputs)
  - Compliance checks
  - Fairness/bias flags
  - Rate limiter
  - Correlation ID generation
  - Observability tracing and metrics

Run with:
  pytest tests/test_shared.py -v
"""

import sys
import os
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.governance import GovernanceManager, RateLimiter
from shared.observability import ObservabilityManager


# ──────────────────────────────────────────────────────────────────
# Governance – transaction validation
# ──────────────────────────────────────────────────────────────────

class TestTransactionValidation:

    @pytest.fixture
    def gov(self):
        return GovernanceManager(audit_log_path="/dev/null")

    @pytest.fixture
    def valid_txn(self):
        return {
            "transaction_id":   "TXN_TEST",
            "customer_id":      "CUST_TEST",
            "amount":           5000.0,
            "location":         "Mumbai, India",
            "transaction_type": "purchase",
            "time":             "2024-06-15T10:00:00",
        }

    def test_valid_transaction_passes(self, gov, valid_txn):
        is_valid, errors = gov.validate_transaction(valid_txn)
        assert is_valid is True
        assert errors == []

    def test_missing_required_field_fails(self, gov, valid_txn):
        del valid_txn["amount"]
        is_valid, errors = gov.validate_transaction(valid_txn)
        assert is_valid is False
        assert any("amount" in e for e in errors)

    def test_negative_amount_fails(self, gov, valid_txn):
        valid_txn["amount"] = -100
        is_valid, errors = gov.validate_transaction(valid_txn)
        assert is_valid is False
        assert any("negative" in e.lower() for e in errors)

    def test_invalid_transaction_type_fails(self, gov, valid_txn):
        valid_txn["transaction_type"] = "illegal_type"
        is_valid, errors = gov.validate_transaction(valid_txn)
        assert is_valid is False
        assert any("transaction_type" in e for e in errors)

    def test_zero_amount_passes(self, gov, valid_txn):
        """Zero is an unusual but technically valid amount (no minimum enforced)."""
        valid_txn["amount"] = 0
        is_valid, _ = gov.validate_transaction(valid_txn)
        assert is_valid is True

    def test_empty_transaction_id_fails(self, gov, valid_txn):
        valid_txn["transaction_id"] = "   "
        is_valid, errors = gov.validate_transaction(valid_txn)
        assert is_valid is False

    def test_all_valid_transaction_types(self, gov, valid_txn):
        """All six valid transaction types must pass validation."""
        for t in ["purchase", "withdrawal", "transfer", "deposit", "payment", "refund"]:
            valid_txn["transaction_type"] = t
            is_valid, _ = gov.validate_transaction(valid_txn)
            assert is_valid is True, f"Type '{t}' should be valid"


# ──────────────────────────────────────────────────────────────────
# Governance – compliance check
# ──────────────────────────────────────────────────────────────────

class TestComplianceCheck:

    @pytest.fixture
    def gov(self):
        return GovernanceManager(audit_log_path="/dev/null")

    def test_valid_safe_decision_passes(self, gov):
        ok, msg = gov.check_compliance("Safe", "No fraud indicators found in this transaction.")
        assert ok is True

    def test_valid_suspicious_decision_passes(self, gov):
        ok, _ = gov.check_compliance("Suspicious", "High transaction amount detected.")
        assert ok is True

    def test_valid_high_risk_decision_passes(self, gov):
        ok, _ = gov.check_compliance("High Risk", "Multiple fraud indicators triggered.")
        assert ok is True

    def test_unknown_decision_fails(self, gov):
        ok, msg = gov.check_compliance("Fraud", "some reasoning")
        assert ok is False
        assert "Unknown decision" in msg

    def test_empty_reasoning_fails(self, gov):
        ok, msg = gov.check_compliance("Safe", "")
        assert ok is False

    def test_short_reasoning_fails(self, gov):
        """Less than 15 characters is too short to be meaningful."""
        ok, msg = gov.check_compliance("Safe", "ok")
        assert ok is False


# ──────────────────────────────────────────────────────────────────
# Governance – fairness check
# ──────────────────────────────────────────────────────────────────

class TestFairnessCheck:

    @pytest.fixture
    def gov(self):
        return GovernanceManager(audit_log_path="/dev/null")

    def test_high_risk_low_amount_only_location_triggers_flag(self, gov):
        """High Risk on a low-amount transaction driven purely by location → should flag."""
        txn = {"transaction_id": "T1", "amount": 500, "location": "lagos"}
        result = gov.check_fairness(txn, "High Risk")
        assert result["has_flags"] is True

    def test_high_risk_large_amount_no_flag(self, gov):
        """High Risk on a large amount (≥ threshold) → no fairness flag."""
        txn = {"transaction_id": "T2", "amount": 200000, "location": "lagos"}
        result = gov.check_fairness(txn, "High Risk")
        assert result["has_flags"] is False

    def test_safe_decision_no_flags(self, gov):
        """Safe decisions never generate fairness flags."""
        txn = {"transaction_id": "T3", "amount": 5000, "location": "nigeria"}
        result = gov.check_fairness(txn, "Safe")
        assert result["has_flags"] is False


# ──────────────────────────────────────────────────────────────────
# Rate limiter
# ──────────────────────────────────────────────────────────────────

class TestRateLimiter:

    def test_first_request_allowed(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        allowed, msg = limiter.check()
        assert allowed is True
        assert msg == "OK"

    def test_within_limit_allowed(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            allowed, _ = limiter.check()
        assert allowed is True

    def test_over_limit_rejected(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.check()
        # 4th request should fail
        allowed, msg = limiter.check()
        assert allowed is False
        assert "Rate limit" in msg

    def test_window_resets_after_expiry(self):
        """After the time window passes, requests should be allowed again."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        limiter.check()
        limiter.check()
        # Over limit now
        allowed, _ = limiter.check()
        assert allowed is False
        # Wait for window to expire
        time.sleep(1.1)
        allowed, _ = limiter.check()
        assert allowed is True


# ──────────────────────────────────────────────────────────────────
# Observability
# ──────────────────────────────────────────────────────────────────

class TestObservability:

    @pytest.fixture
    def obs(self):
        return ObservabilityManager()

    def test_generate_correlation_id_is_unique(self, obs):
        """Every call returns a different UUID."""
        ids = {obs.generate_correlation_id() for _ in range(10)}
        assert len(ids) == 10

    def test_trace_is_stored(self, obs):
        cid = obs.generate_correlation_id()
        obs.trace(cid, "TestAgent", {"input": "x"}, {"output": "y"}, 42.0)
        trail = obs.get_audit_trail(cid)
        assert len(trail) == 1
        assert trail[0]["agent_name"] == "TestAgent"
        assert trail[0]["duration_ms"] == 42.0

    def test_multiple_traces_accumulate(self, obs):
        cid = obs.generate_correlation_id()
        obs.trace(cid, "AgentA", {}, {}, 10.0)
        obs.trace(cid, "AgentB", {}, {}, 20.0)
        obs.trace(cid, "AgentC", {}, {}, 30.0)
        assert len(obs.get_audit_trail(cid)) == 3

    def test_unknown_correlation_id_returns_empty(self, obs):
        assert obs.get_audit_trail("nonexistent-id") == []

    def test_log_decision_appended_to_trail(self, obs):
        cid = obs.generate_correlation_id()
        obs.log_decision(cid, "TXN001", "Safe", "No indicators found", 0.95)
        trail = obs.get_audit_trail(cid)
        assert any(e.get("type") == "decision" for e in trail)

    def test_emit_metric_stored(self, obs):
        obs.emit_metric("risk_score", 75.0, tags={"txn": "TXN001"})
        summary = obs.get_metrics_summary()
        assert "risk_score" in summary
        assert summary["risk_score"]["count"] == 1
        assert summary["risk_score"]["avg"] == 75.0

    def test_metrics_summary_calculates_avg(self, obs):
        for v in [10.0, 20.0, 30.0]:
            obs.emit_metric("test_metric", v)
        s = obs.get_metrics_summary()["test_metric"]
        assert s["avg"] == 20.0
        assert s["min"] == 10.0
        assert s["max"] == 30.0
        assert s["count"] == 3
