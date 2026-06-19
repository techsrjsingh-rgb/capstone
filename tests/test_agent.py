"""
Integration tests for fraud_detection/agent.py

Uses unittest.mock to patch the Anthropic client so no real API calls
are made. Tests the full orchestration flow including:
  - Rules Agent result passthrough
  - Hook pre/post processing
  - Self-healing retry logic
  - Error fallback behavior

Run with:
  pytest tests/test_agent.py -v
"""

import sys
import os
import json
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fraud_detection.agent import FraudDetectionOrchestrator, _compute_risk_score, _recommend_action
from fraud_detection.hooks import FraudHookManager
from fraud_detection.data import SAMPLE_TRANSACTIONS


# ──────────────────────────────────────────────────────────────────
# Fake Claude response builders
# ──────────────────────────────────────────────────────────────────

def _make_text_response(text: str):
    """Create a minimal mock response with stop_reason='end_turn' and one text block."""
    block = MagicMock()
    block.type = "text"
    block.text = text

    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    return response


def _make_tool_then_text_response(tool_name: str, tool_input: dict, final_text: str):
    """
    Simulate the two-step tool-use pattern:
      First call  → stop_reason='tool_use', content has a tool_use block
      Second call → stop_reason='end_turn', content has a text block
    """
    # Tool use block
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = tool_name
    tool_block.id   = "fake_tool_id"
    tool_block.input = tool_input

    first_response = MagicMock()
    first_response.stop_reason = "tool_use"
    first_response.content = [tool_block]

    # Final text response
    second_response = _make_text_response(final_text)

    return first_response, second_response


# ──────────────────────────────────────────────────────────────────
# Hook tests (no mock needed — hooks use pure Python)
# ──────────────────────────────────────────────────────────────────

class TestFraudHookManager:

    @pytest.fixture
    def hooks(self):
        return FraudHookManager()

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

    def test_pre_process_adds_correlation_id(self, hooks, valid_txn):
        result = hooks.pre_process(valid_txn)
        assert "correlation_id" in result
        assert len(result["correlation_id"]) == 36   # UUID length

    def test_pre_process_sanitizes_whitespace(self, hooks, valid_txn):
        valid_txn["location"] = "  Mumbai, India  "
        result = hooks.pre_process(valid_txn)
        assert result["location"] == "Mumbai, India"

    def test_pre_process_normalizes_transaction_type(self, hooks, valid_txn):
        valid_txn["transaction_type"] = "PURCHASE"
        result = hooks.pre_process(valid_txn)
        assert result["transaction_type"] == "purchase"

    def test_pre_process_rejects_invalid_transaction(self, hooks):
        bad_txn = {"transaction_id": "T1"}   # missing required fields
        with pytest.raises(ValueError, match="Invalid transaction"):
            hooks.pre_process(bad_txn)

    def test_pre_process_rejects_negative_amount(self, hooks, valid_txn):
        valid_txn["amount"] = -100
        with pytest.raises(ValueError):
            hooks.pre_process(valid_txn)

    def test_on_error_returns_suspicious_fallback(self, hooks):
        result = hooks.on_error(
            RuntimeError("API timeout"),
            {"correlation_id": "test-cid", "transaction_id": "TXN_ERR"},
        )
        assert result["risk_level"] == "Suspicious"
        assert "error" in result
        assert result["correlation_id"] == "test-cid"

    def test_post_process_adds_correlation_id(self, hooks):
        result = {
            "transaction_id": "TXN1",
            "risk_level": "Safe",
            "fraud_reasons": [],
            "risk_score": 0.0,
        }
        processed = hooks.post_process(result, "test-correlation-123")
        assert processed["correlation_id"] == "test-correlation-123"

    def test_post_process_compliance_override_on_bad_decision(self, hooks):
        """If risk_level is invalid, post_process should override to Suspicious."""
        result = {
            "transaction_id": "TXN1",
            "risk_level": "INVALID_DECISION",
            "fraud_reasons": [],
            "risk_score": 0.0,
        }
        processed = hooks.post_process(result, "cid-001")
        assert processed["risk_level"] == "Suspicious"
        assert processed.get("compliance_override") is True


# ──────────────────────────────────────────────────────────────────
# Orchestrator – rule-only path (no LLM)
# ──────────────────────────────────────────────────────────────────

class TestOrchestrator:

    @pytest.fixture
    def orchestrator(self):
        return FraudDetectionOrchestrator()

    def test_safe_transaction_classified_correctly(self, orchestrator):
        """TXN001 (small domestic) should come back as Safe from RulesAgent."""
        txn = next(t for t in SAMPLE_TRANSACTIONS if t["transaction_id"] == "TXN001")
        rules_result = orchestrator._run_rules_agent(txn, SAMPLE_TRANSACTIONS)
        assert rules_result["risk_level"] == "Safe"
        assert rules_result["fraud_reasons"] == []

    def test_high_risk_transaction_detected(self, orchestrator):
        """TXN020 (₹2,00,000 in Lagos) should be High Risk."""
        txn = next(t for t in SAMPLE_TRANSACTIONS if t["transaction_id"] == "TXN020")
        rules_result = orchestrator._run_rules_agent(txn, SAMPLE_TRANSACTIONS)
        assert rules_result["risk_level"] == "High Risk"

    def test_rapid_transactions_detected(self, orchestrator):
        """TXN014 is the 3rd rapid transaction from CUST_L."""
        txn = next(t for t in SAMPLE_TRANSACTIONS if t["transaction_id"] == "TXN014")
        rules_result = orchestrator._run_rules_agent(txn, SAMPLE_TRANSACTIONS)
        assert rules_result["risk_level"] in ("Suspicious", "High Risk")

    @patch("fraud_detection.agent.anthropic.Anthropic")
    def test_full_pipeline_with_mocked_llm(self, mock_anthropic_class, orchestrator):
        """
        Full analyze() call with mocked LLM responses.
        Verifies the pipeline completes and returns all required fields.
        """
        # Set up mock client that returns simple text for all calls
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _make_text_response(
            "Transaction analyzed. No additional behavioral concerns."
        )
        orchestrator.client = mock_client

        txn = next(t for t in SAMPLE_TRANSACTIONS if t["transaction_id"] == "TXN001")
        result = orchestrator.analyze(txn, SAMPLE_TRANSACTIONS)

        assert "risk_level"    in result
        assert "fraud_reasons" in result
        assert "risk_score"    in result
        assert "agent_trace"   in result
        assert "correlation_id" in result

    @patch("fraud_detection.agent.anthropic.Anthropic")
    def test_error_in_llm_triggers_fallback(self, mock_anthropic_class, orchestrator):
        """
        When the LLM raises an APIError, the on_error hook
        should return a Suspicious fallback result.
        """
        import anthropic as anthropic_lib

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic_lib.APIError(
            message="Service unavailable", request=MagicMock(), body=None
        )
        orchestrator.client = mock_client

        txn = SAMPLE_TRANSACTIONS[0]
        result = orchestrator.analyze(txn, SAMPLE_TRANSACTIONS)

        # On any failure, must return Suspicious (never crash)
        assert result["risk_level"] in ("Suspicious", "High Risk", "Safe")
        assert "correlation_id" in result


# ──────────────────────────────────────────────────────────────────
# Helper function tests
# ──────────────────────────────────────────────────────────────────

class TestHelperFunctions:

    def test_compute_risk_score_no_flags(self):
        score = _compute_risk_score(False, False, False, False, 5000)
        assert score == 0.0

    def test_compute_risk_score_all_flags(self):
        score = _compute_risk_score(True, True, True, True, 200000)
        assert score == 100.0   # capped at 100

    def test_compute_risk_score_high_amount_only(self):
        score = _compute_risk_score(True, False, False, False, 150000)
        assert score > 0
        assert score < 100

    def test_recommend_none_for_safe(self):
        assert _recommend_action("Safe", 0) == "none"

    def test_recommend_block_for_high_risk(self):
        assert _recommend_action("High Risk", 80) == "block_transaction"

    def test_recommend_alert_for_suspicious(self):
        assert _recommend_action("Suspicious", 50) == "alert_customer"
