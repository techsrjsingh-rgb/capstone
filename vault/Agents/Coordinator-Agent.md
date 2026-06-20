---
tags: [agent, coordinator, final-decision, opus]
---

# ✅ Coordinator Agent

Source: `orchestrator/agent.py:_run_coordinator_agent` · Definition: `.claude/agents/coordinator-agent.md` · See also: [[Orchestrator]]

---

## Role

Synthesizes the outputs of all three sub-agents into a final, human-readable fraud report with a classification, risk score, recommended action, and explanation.

Runs **last** in the pipeline.

---

## Configuration

| Setting | Value |
|---------|-------|
| Model | `claude-opus-4-8` |
| Tool call | Must call `generate_fraud_report` |

---

## Tool: `generate_fraud_report`

```json
{
  "transaction_id":     "TXN020",
  "risk_level":         "High Risk",
  "fraud_reasons":      ["High amount: ₹2,00,000", "Unusual location: Lagos, Nigeria"],
  "risk_score":         85.0,
  "amount":             200000.0,
  "location":           "Lagos, Nigeria",
  "customer_id":        "CUST_T",
  "recommended_action": "block_transaction"
}
```

---

## Decision Guidelines

1. **Rules Agent** output is the primary signal — never override a High Risk from 2+ rules
2. **Risk Scorer** provides the tiebreaker for borderline Suspicious/High Risk
3. **Pattern Agent** provides nuance for edge cases

## Action Mapping

| Risk Level | Score | Action |
|------------|-------|--------|
| Safe | any | `none` |
| Suspicious | < 50 | `alert_customer` |
| Suspicious | ≥ 50 | `alert_customer` |
| High Risk | < 85 | `block_transaction` |
| High Risk | ≥ 85 (+ multiple rules) | `escalate` |

---

## Output

Returns the final result dict with all 9 keys including `explanation` (markdown-formatted) and `confidence` (0.0–1.0).
