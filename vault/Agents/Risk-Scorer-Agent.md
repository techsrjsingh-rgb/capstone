---
tags: [agent, risk-scoring, extended-thinking, opus]
---

# 📊 Risk Scorer Agent

Source: `orchestrator/agent.py:_run_risk_scorer_agent` · Definition: `.claude/agents/risk-scorer-agent.md` · See also: [[Orchestrator]], [[../Fraud-Rules]]

---

## Role

Computes a precise 0–100 fraud risk score using extended thinking. Synthesizes all rule flags and behavioral context into a single numeric score.

Runs **after** [[Pattern-Agent]].

---

## Configuration

| Setting | Value |
|---------|-------|
| Model | `claude-opus-4-8` |
| Extended thinking | ✅ Enabled (5,000 token budget) |
| Tool call | Must call `calculate_fraud_score` |

---

## Tool: `calculate_fraud_score`

```json
{
  "high_amount_triggered":       true,
  "unusual_location_triggered":  false,
  "rapid_succession_triggered":  false,
  "international_triggered":     false,
  "amount":                      150000.0
}
```

---

## Score Formula

```
base = 0
if high_amount:     base += 35  (up to +50 for very large amounts)
if unusual_loc:     base += 30
if rapid:           base += 25
if international:   base += 15
score = min(base, 100)
```

## Risk Bands

| Score | Classification |
|-------|---------------|
| 0–39  | ✅ Safe |
| 40–69 | ⚠️ Suspicious |
| 70–100 | 🚨 High Risk |

---

## Extended Thinking

The 5,000-token thinking budget allows the model to reason through edge cases:
- Should a large domestic transfer to a trusted location score 35 or 50?
- Does the behavioral pattern context from [[Pattern-Agent]] suggest a lower risk for a usually-high-score location?

The first 400 characters of thinking output are included in `agent_trace` for inspection.
