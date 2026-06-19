# Technical Design Document
## Fraud Detection AI Agent

**Version:** 1.0  
**Date:** June 2026  
**Project:** Banking Fraud Detection Capstone

---

## 1. Executive Summary

The Fraud Detection AI Agent is a multi-agent AI system that analyzes banking transactions in real time and classifies each as **Safe**, **Suspicious**, or **High Risk**. It uses the Anthropic Claude API with a Coordinator + 3 Specialist agent architecture, supported by deterministic rule engines, Python middleware hooks, two MCP data servers, and a Streamlit web dashboard.

---

## 2. Problem Statement

Banking fraud causes significant financial losses globally. Manual transaction review is too slow and too expensive to scale. An automated agent system is needed that can:
- Analyze each transaction against multiple fraud rules simultaneously
- Explain its reasoning in plain language (explainable AI)
- Log all decisions for regulatory audit
- Handle edge cases gracefully without human intervention

---

## 3. System Components

### 3.1 Transaction Data (`fraud_detection/data.py`)
22 pre-built sample transactions covering all fraud scenarios:
- Normal domestic transactions (Safe)
- High-amount transfers (High Risk)
- Transactions from fraud hotspots (Suspicious/High Risk)
- Rapid-succession from same customer (Suspicious)
- International transactions (Suspicious)
- Multi-flag combinations (High Risk)

Fields: `transaction_id`, `customer_id`, `amount`, `location`, `transaction_type`, `time`

### 3.2 Rule Engine (`fraud_detection/rules.py`)
Pure Python — no LLM dependency. Four rules:

| Rule | Threshold | Weight |
|------|-----------|--------|
| High Amount | ≥ ₹1,00,000 | 35 pts |
| Unusual Location | Fraud hotspot list | 30 pts |
| Rapid Succession | 3+ txns in 5 min | 25 pts |
| International | Outside India | 15 pts |

Risk classification: 0 rules = Safe; 1 rule = Suspicious; 2+ rules = High Risk.

### 3.3 Tool Schemas (`fraud_detection/tools.py`)
Four JSON schemas passed to `client.messages.create(tools=...)`:
- `analyze_transaction` — trigger all four rules
- `check_customer_history` — behavioral context
- `calculate_fraud_score` — numeric 0–100 score
- `generate_fraud_report` — final structured report

### 3.4 Hooks (`fraud_detection/hooks.py`)
Python middleware class `FraudHookManager`:
- `pre_process()` — validate, sanitize, rate-limit, generate correlation ID
- `post_process()` — compliance check, fairness check, audit log, metrics
- `on_error()` — safe fallback (Suspicious) instead of crash

### 3.5 MCP Servers
Two independent FastMCP servers (Multi-MCP bonus):

**mcp_server_fraud.py (port 8002):**
- `get_transaction_history` — past transactions for a customer
- `get_fraud_blacklist` — known fraudulent accounts
- `report_fraud_transaction` — mark transaction as confirmed fraud
- `get_fraud_statistics` — aggregate fraud metrics

**mcp_server_geo.py (port 8003):**
- `get_country_risk_score` — 0–100 risk score for a location
- `check_ip_location` — IP → country mapping
- `get_high_risk_regions` — list all high-risk regions
- `verify_domestic_location` — confirm India vs. international

### 3.6 Skills (`fraud_detection/skills/fraud_detection.md`)
Markdown file loaded as system prompt context for every agent call. Describes:
- Agent role and output format
- Four fraud rules with thresholds
- Tool usage sequence
- Communication guidelines

### 3.7 Multi-Agent Orchestrator (`fraud_detection/agent.py`)

```
FraudDetectionOrchestrator
├── _run_rules_agent()        → deterministic Python (no API call)
├── _run_pattern_agent()      → claude-sonnet-4-6, behavioral analysis
├── _run_risk_scorer_agent()  → claude-opus-4-8 + extended thinking
└── _run_coordinator_agent()  → claude-opus-4-8, final synthesis
```

Self-healing: `_retry()` applies exponential backoff (1s, 2s, 4s) on API errors.

### 3.8 Streamlit Dashboard (`fraud_detection/app.py`)
- **Batch tab**: analyze all 22 transactions, colored table, pie chart, bar chart
- **Single tab**: custom transaction form, risk gauge, per-transaction detail
- **About tab**: system documentation

---

## 4. API Usage Patterns

### 4.1 Standard Tool Use Loop
```python
# Send message with tools defined
response = client.messages.create(
    model=config.PRIMARY_MODEL,
    max_tokens=4096,
    system=skill_text + agent_persona,
    messages=[{"role": "user", "content": prompt}],
    tools=[GENERATE_FRAUD_REPORT_TOOL],
)

# Loop until no more tool calls
while response.stop_reason == "tool_use":
    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            result = execute_tool(block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })
    messages.append({"role": "assistant", "content": response.content})
    messages.append({"role": "user", "content": tool_results})
    response = client.messages.create(...)
```

### 4.2 Extended Thinking (Autonomous Planning)
```python
response = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=4096,
    thinking={"type": "enabled", "budget_tokens": 5000},
    ...
)
# Response content includes a "thinking" block before the text block
for block in response.content:
    if block.type == "thinking":
        reasoning = block.thinking   # internal chain-of-thought
```

### 4.3 Self-Healing Retry
```python
for attempt in range(MAX_RETRIES):
    try:
        return api_call()
    except anthropic.RateLimitError:
        time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
    except anthropic.APIError:
        if attempt == MAX_RETRIES - 1:
            raise
        time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
```

---

## 5. Design Decisions

| Decision | Rationale |
|----------|-----------|
| Pure Python RulesAgent (no LLM) | Fast, deterministic, testable without API key |
| Two MCP servers (not one) | Separation of concerns; fraud data vs. geo data |
| Fallback model in PatternAgent | Cost optimization — behavioral analysis doesn't need Opus |
| Extended thinking in RiskScorerAgent | Deep reasoning improves score accuracy |
| Hooks as Python middleware | Clean separation of cross-cutting concerns |
| Correlation IDs on every request | Full traceability across all 4 agents |
| JSONL audit log | Machine-readable, streamable, grep-friendly |

---

## 6. Security Considerations

- API keys stored in `.env` file, never committed to git
- Input validation rejects malformed transactions before reaching LLM
- Rate limiter prevents abuse
- Audit log is append-only (no delete operation exposed)
- No customer PII passed to external APIs beyond what is necessary
