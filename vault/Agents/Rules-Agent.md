---
tags: [agent, rules, python, no-llm]
---

# 📋 Rules Agent

Source: `core/rules.py` · Definition: `.claude/agents/rules-agent.md` · See also: [[../Fraud-Rules]], [[Orchestrator]]

---

## Role

Evaluates a transaction against the 4 hardcoded fraud rules. Runs **instantly** with no AI API call.

Runs **first** in the pipeline before any LLM agents.

---

## Class: `FraudDetectionRules`

```python
rules = FraudDetectionRules()
result = rules.evaluate(transaction, all_transactions)
```

**Result dict:**
```python
{
    "transaction_id":  "TXN001",
    "risk_level":      "Safe",       # Safe / Suspicious / High Risk
    "fraud_reasons":   [],
    "risk_score":      0.0,
    "rule_details": {
        "high_amount":       {"triggered": False, "message": "..."},
        "unusual_location":  {"triggered": False, "message": "..."},
        "rapid_succession":  {"triggered": False, "message": "..."},
        "international":     {"triggered": False, "message": "..."},
    }
}
```

---

## Classification Logic

| Rules Triggered | Risk Level |
|-----------------|------------|
| 0 | ✅ Safe |
| 1 | ⚠️ Suspicious |
| 2+ | 🚨 High Risk |

---

## The Four Rules

See [[../Fraud-Rules]] for detailed thresholds and test transactions.
