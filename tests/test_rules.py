"""
Unit tests for fraud_detection/rules.py

Tests every rule function in isolation using boundary-value analysis:
  - Values just below threshold (should NOT trigger)
  - Values exactly at threshold (edge case)
  - Values above threshold (SHOULD trigger)
  - Aggregate decision covering all three outcome paths

Run with:
  pytest tests/test_rules.py -v
"""

import sys
import os
import pytest

# Allow importing from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fraud_detection.rules import FraudDetectionRules, _parse_time
from fraud_detection.data import SAMPLE_TRANSACTIONS
from shared.config import config


@pytest.fixture
def rules():
    """Return a fresh FraudDetectionRules instance for each test."""
    return FraudDetectionRules()


# ──────────────────────────────────────────────────────────────────
# Rule 1: High Amount
# ──────────────────────────────────────────────────────────────────

class TestHighAmountRule:

    def test_safe_amount_below_threshold(self, rules):
        """Amount clearly below threshold should NOT trigger."""
        triggered, msg = rules.check_high_amount(50000.0)
        assert triggered is False
        assert "normal" in msg.lower()

    def test_borderline_amount_just_below(self, rules):
        """₹99,999 is just below ₹1,00,000 — should not trigger."""
        triggered, _ = rules.check_high_amount(99999.0)
        assert triggered is False

    def test_exact_threshold_triggers(self, rules):
        """₹1,00,000 exactly must trigger the rule."""
        triggered, msg = rules.check_high_amount(config.HIGH_AMOUNT_THRESHOLD)
        assert triggered is True
        assert "high amount" in msg.lower()

    def test_above_threshold_triggers(self, rules):
        """₹1,50,000 is above threshold — must trigger."""
        triggered, msg = rules.check_high_amount(150000.0)
        assert triggered is True

    def test_very_large_amount_triggers(self, rules):
        """₹5,00,000 is very large — extra severity message expected."""
        triggered, msg = rules.check_high_amount(500000.0)
        assert triggered is True
        assert "very high" in msg.lower()

    def test_zero_amount_is_safe(self, rules):
        """Zero-amount transaction should not trigger high amount rule."""
        triggered, _ = rules.check_high_amount(0.0)
        assert triggered is False


# ──────────────────────────────────────────────────────────────────
# Rule 2: Unusual Location
# ──────────────────────────────────────────────────────────────────

class TestUnusualLocationRule:

    def test_known_fraud_location_triggers(self, rules):
        """Lagos, Nigeria is a known fraud hotspot."""
        triggered, msg = rules.check_unusual_location("Lagos, Nigeria")
        assert triggered is True
        assert "nigeria" in msg.lower() or "unusual" in msg.lower()

    def test_unknown_location_triggers(self, rules):
        """'Unknown' location must trigger the rule."""
        triggered, msg = rules.check_unusual_location("Unknown")
        assert triggered is True

    def test_panamanian_offshore_triggers(self, rules):
        """Panama is in the fraud locations list."""
        triggered, _ = rules.check_unusual_location("Panama City, Panama")
        assert triggered is True

    def test_domestic_city_does_not_trigger(self, rules):
        """Normal Indian city should NOT trigger unusual location."""
        triggered, _ = rules.check_unusual_location("Mumbai, India")
        assert triggered is False

    def test_offshore_keyword_triggers(self, rules):
        """'Offshore' keyword should trigger."""
        triggered, _ = rules.check_unusual_location("Offshore Account")
        assert triggered is True

    def test_standard_international_city_safe(self, rules):
        """London, UK is not in the fraud list (international but not fraud hotspot)."""
        triggered, _ = rules.check_unusual_location("London, UK")
        assert triggered is False


# ──────────────────────────────────────────────────────────────────
# Rule 3: Rapid Succession
# ──────────────────────────────────────────────────────────────────

class TestRapidSuccessionRule:

    def test_rapid_transactions_trigger(self, rules):
        """TXN014 is the 3rd transaction from CUST_L within 4 minutes — must trigger."""
        txn014 = next(t for t in SAMPLE_TRANSACTIONS if t["transaction_id"] == "TXN014")
        triggered, msg = rules.check_rapid_succession(txn014, SAMPLE_TRANSACTIONS)
        assert triggered is True
        assert "rapid" in msg.lower()

    def test_single_transaction_does_not_trigger(self, rules):
        """A customer with only one transaction never triggers rapid succession."""
        isolated_txn = {
            "transaction_id": "TXN_ISOLATED",
            "customer_id": "CUST_UNIQUE_999",
            "amount": 1000,
            "location": "Delhi",
            "transaction_type": "purchase",
            "time": "2024-06-15T10:00:00",
        }
        triggered, _ = rules.check_rapid_succession(isolated_txn, SAMPLE_TRANSACTIONS)
        assert triggered is False

    def test_two_transactions_do_not_trigger(self, rules):
        """Two transactions (below the rapid threshold of 3) should NOT trigger."""
        txn_a = {
            "transaction_id": "TXN_A", "customer_id": "CUST_PAIR",
            "amount": 500, "location": "Pune",
            "transaction_type": "purchase", "time": "2024-06-15T14:00:00",
        }
        txn_b = {
            "transaction_id": "TXN_B", "customer_id": "CUST_PAIR",
            "amount": 500, "location": "Pune",
            "transaction_type": "purchase", "time": "2024-06-15T14:02:00",
        }
        triggered, _ = rules.check_rapid_succession(txn_b, [txn_a, txn_b])
        assert triggered is False

    def test_transactions_outside_window_do_not_trigger(self, rules):
        """Transactions more than 5 minutes apart do not count as rapid."""
        txn_old = {
            "transaction_id": "TXN_OLD", "customer_id": "CUST_SLOW",
            "amount": 1000, "location": "Chennai",
            "transaction_type": "payment", "time": "2024-06-15T08:00:00",
        }
        txn_new = {
            "transaction_id": "TXN_NEW", "customer_id": "CUST_SLOW",
            "amount": 1000, "location": "Chennai",
            "transaction_type": "payment", "time": "2024-06-15T10:00:00",  # 2 hours later
        }
        triggered, _ = rules.check_rapid_succession(txn_new, [txn_old, txn_new])
        assert triggered is False


# ──────────────────────────────────────────────────────────────────
# Rule 4: International
# ──────────────────────────────────────────────────────────────────

class TestInternationalRule:

    def test_usa_is_international(self, rules):
        """New York, USA is outside India — must trigger."""
        triggered, msg = rules.check_international("New York, USA")
        assert triggered is True
        assert "international" in msg.lower()

    def test_uk_is_international(self, rules):
        """London, UK is international."""
        triggered, _ = rules.check_international("London, UK")
        assert triggered is True

    def test_mumbai_is_domestic(self, rules):
        """Mumbai, India is domestic — must NOT trigger."""
        triggered, _ = rules.check_international("Mumbai, India")
        assert triggered is False

    def test_india_string_is_domestic(self, rules):
        """Bare 'India' string is domestic."""
        triggered, _ = rules.check_international("India")
        assert triggered is False

    def test_bangalore_is_domestic(self, rules):
        """Bangalore (without 'India') is still domestic."""
        triggered, _ = rules.check_international("Bangalore")
        assert triggered is False


# ──────────────────────────────────────────────────────────────────
# Aggregate decision
# ──────────────────────────────────────────────────────────────────

class TestAggregateRisk:

    def test_no_triggers_is_safe(self, rules):
        """Zero triggered rules → Safe."""
        risk_level, reasons, score = rules.aggregate_risk(
            (False, "normal"), (False, "normal"),
            (False, "normal"), (False, "domestic"),
        )
        assert risk_level == "Safe"
        assert reasons == []
        assert score == 0.0

    def test_one_trigger_is_suspicious(self, rules):
        """One triggered rule → Suspicious."""
        risk_level, reasons, score = rules.aggregate_risk(
            (True, "High amount: ₹1,50,000"), (False, "normal"),
            (False, "normal"), (False, "domestic"),
        )
        assert risk_level == "Suspicious"
        assert len(reasons) == 1
        assert score > 0

    def test_two_triggers_is_high_risk(self, rules):
        """Two triggered rules → High Risk."""
        risk_level, reasons, score = rules.aggregate_risk(
            (True, "High amount"), (True, "Unusual location"),
            (False, "normal"), (False, "domestic"),
        )
        assert risk_level == "High Risk"
        assert len(reasons) == 2

    def test_three_triggers_is_high_risk(self, rules):
        """Three triggered rules → High Risk."""
        risk_level, _, score = rules.aggregate_risk(
            (True, "High amount"), (True, "Unusual location"),
            (True, "Rapid"), (False, "domestic"),
        )
        assert risk_level == "High Risk"
        assert score >= 70

    def test_all_four_triggers_max_score(self, rules):
        """All four rules triggered → High Risk, score near 100."""
        risk_level, reasons, score = rules.aggregate_risk(
            (True, "High amount"), (True, "Unusual location"),
            (True, "Rapid"), (True, "International"),
        )
        assert risk_level == "High Risk"
        assert len(reasons) == 4
        assert score == 100.0  # capped at 100


# ──────────────────────────────────────────────────────────────────
# Evaluate convenience method
# ──────────────────────────────────────────────────────────────────

class TestEvaluate:

    def test_known_safe_transaction(self, rules):
        """TXN001 is a small domestic transaction — should be Safe."""
        txn = next(t for t in SAMPLE_TRANSACTIONS if t["transaction_id"] == "TXN001")
        result = rules.evaluate(txn, SAMPLE_TRANSACTIONS)
        assert result["risk_level"] == "Safe"
        assert result["fraud_reasons"] == []
        assert result["risk_score"] == 0.0

    def test_multi_flag_high_risk(self, rules):
        """TXN020: high amount + Lagos Nigeria → High Risk."""
        txn = next(t for t in SAMPLE_TRANSACTIONS if t["transaction_id"] == "TXN020")
        result = rules.evaluate(txn, SAMPLE_TRANSACTIONS)
        assert result["risk_level"] == "High Risk"
        assert len(result["fraud_reasons"]) >= 2

    def test_international_transaction(self, rules):
        """TXN018: New York, USA → at least Suspicious."""
        txn = next(t for t in SAMPLE_TRANSACTIONS if t["transaction_id"] == "TXN018")
        result = rules.evaluate(txn, SAMPLE_TRANSACTIONS)
        assert result["risk_level"] in ("Suspicious", "High Risk")

    def test_result_has_all_required_fields(self, rules):
        """Every result must have the required fields."""
        txn = SAMPLE_TRANSACTIONS[0]
        result = rules.evaluate(txn, SAMPLE_TRANSACTIONS)
        for field in ["transaction_id", "risk_level", "fraud_reasons",
                      "risk_score", "rule_details"]:
            assert field in result, f"Missing field: {field}"

    def test_rule_details_structure(self, rules):
        """rule_details must contain all four rule keys."""
        result = rules.evaluate(SAMPLE_TRANSACTIONS[0], SAMPLE_TRANSACTIONS)
        for key in ["high_amount", "unusual_location", "rapid_succession", "international"]:
            assert key in result["rule_details"]
            assert "triggered" in result["rule_details"][key]
            assert "message"   in result["rule_details"][key]


# ──────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────

class TestParseTime:

    def test_iso_format_parses(self):
        dt = _parse_time("2024-06-15T10:30:00")
        assert dt.year  == 2024
        assert dt.month == 6
        assert dt.hour  == 10

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            _parse_time("not-a-date")
