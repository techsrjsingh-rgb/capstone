---
tags: [agent, pattern, behavioral-analysis, sonnet]
---

# 🔍 Pattern Agent

Source: `orchestrator/agent.py:_run_pattern_agent` · Definition: `.claude/agents/pattern-agent.md` · See also: [[Orchestrator]]

---

## Role

Analyzes the behavioral context of a banking transaction — is it unusual for this customer, and what known fraud pattern does it match?

Runs **after** [[Rules-Agent]], enriching its findings with LLM reasoning.

---

## Configuration

| Setting | Value |
|---------|-------|
| Model | `claude-sonnet-4-6` (fallback model — cheaper, faster) |
| Max tokens | 512 |
| Output | ≤ 3 sentences |

---

## Input

The agent receives:
- The transaction dict
- Rules Agent output (risk level, fraud reasons, rule details)

## Output

A concise behavioral analysis string (≤ 3 sentences), covering:
- Is this transaction unusual for this customer?
- Which known fraud pattern does it match (card testing, account takeover, velocity fraud, geo anomaly)?
- Any mitigating context?

---

## Fraud Patterns Detected

- **Card testing**: many small transactions probing card validity
- **Account takeover**: unusual location + high amount
- **Velocity fraud**: rapid succession from same customer
- **Geographic anomaly**: location inconsistent with history
- **Time anomaly**: transaction at unusual hours
