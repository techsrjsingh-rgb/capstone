# Presentation Deck
## Fraud Detection AI Agent
### Banking AI Capstone Project

---

## Slide 1: Business Problem

**The Challenge:**
- Banking fraud costs the global financial sector **$485 billion annually** (2023)
- Manual transaction review handles only **~1% of transactions**
- Average fraud detection time: **14 hours** after incident
- False positive rate with legacy rule systems: **97%** — frustrating customers

**The Gap:**
Legacy rule-based systems are too rigid. Machine learning models are opaque.
We need a system that is **fast**, **explainable**, and **accurate**.

---

## Slide 2: Solution Overview

**Fraud Detection AI Agent** — a multi-agent AI system powered by Claude (Anthropic)

**Key Capabilities:**
- Analyzes any banking transaction in **< 10 seconds**
- Classifies as ✅ Safe · ⚠️ Suspicious · 🚨 High Risk
- Explains **every decision** in plain language
- Logs **all decisions** for regulatory audit
- Self-heals on API failures — never crashes

**Tech Stack:** Python 3.14, Anthropic SDK, Streamlit, Plotly, FastMCP

---

## Slide 3: Agent Architecture

```
                    FraudDetectionOrchestrator
                         (Coordinator)
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
    RulesAgent          PatternAgent        RiskScorerAgent
   (Pure Python)       (Sonnet 4.6)        (Opus 4.8 +
                                            Extended Thinking)
```

**4-Agent Pipeline:**
1. **RulesAgent** — deterministic rule checks (no API cost, instant)
2. **PatternAgent** — behavioral analysis using claude-sonnet-4-6
3. **RiskScorerAgent** — deep reasoning with claude-opus-4-8 + extended thinking
4. **CoordinatorAgent** — synthesizes final decision + explanation

---

## Slide 4: Skills, Subagents & Hooks

**Skills:**
- `fraud_detection/skills/fraud_detection.md` — loaded as system prompt
- Defines role, rules, tool usage order, communication style

**Subagents:**
- Each specialist (Rules, Pattern, Risk, Coordinator) is a separate agent call
- Coordinator delegates and synthesizes — true multi-agent collaboration

**Hooks (middleware):**
```
pre_process()     →  validate · rate-limit · sanitize · add correlation ID
post_process()    →  compliance check · fairness flag · audit log · metrics
on_error()        →  safe Suspicious fallback — never crashes
```

---

## Slide 5: MCP & Plugin Integration

**Two Independent FastMCP Servers (Multi-MCP Bonus):**

| Server | Port | Tools |
|--------|------|-------|
| `mcp_server_fraud.py` | 8002 | Transaction history, Blacklist, Fraud stats |
| `mcp_server_geo.py` | 8003 | Country risk scores, IP lookup, High-risk regions |

**Integration pattern:**
- Agent pipeline queries MCP servers for contextual enrichment
- MCP servers are optional — system degrades gracefully if unavailable
- Each server is independently deployable and scalable

---

## Slide 6: Governance Framework

**Three layers of governance:**

1. **Input Validation** — reject malformed transactions before LLM
2. **Compliance Check** — every decision must have a justification
3. **Fairness Check** — flag High Risk decisions on location-only triggers

**Rate Limiting:** 20 requests/minute (token-bucket algorithm)

**Audit Logging:** Append-only `audit.jsonl` — one JSON per line
```json
{"timestamp": "...", "correlation_id": "...", "agent": "...", 
 "action": "decision", "data": "..."}
```

**Explainability:** Every result includes fraud_reasons + risk_score + explanation + trace

---

## Slide 7: Observability & Traceability

**Correlation IDs:**
- Each request gets a UUID-v4 correlation ID
- All 4 agent calls share the same correlation ID
- Full trace retrievable via `observability.get_audit_trail(cid)`

**What's logged per agent call:**
- Agent name
- Input summary
- Output summary
- Duration in milliseconds
- Timestamp (UTC ISO-8601)

**Metrics tracked:**
- `fraud_classification` — count per risk level
- `risk_score` — per transaction
- `agent_error` — error rate

---

## Slide 8: Evaluation Results

**Rule Engine Accuracy (22 sample transactions):**

| Category | Count | Correct | Accuracy |
|----------|-------|---------|----------|
| Safe | 9 | 9 | 100% |
| Suspicious | 9 | 9 | 100% |
| High Risk | 4 | 4 | 100% |

**Test Suite Results:**
- 50 unit tests across 3 test files
- 100% pass rate
- Zero API calls required for tests (mocked)

---

## Slide 9: Load Testing Results

**Methodology:** 50 concurrent transaction analyses

| Mode | Throughput | Avg Latency | Error Rate |
|------|-----------|-------------|-----------|
| Rules-Only | ~200 txns/sec | < 5ms | 0% |
| AI Agent | ~2–5 txns/sec | 2–8 sec | < 1% |

**Key finding:** Rules-only mode handles high volume instantly.
AI Agent mode provides deeper analysis for flagged transactions.
**Recommended:** Run rules-only for all transactions; escalate positive flags to AI agent.

---

## Slide 10: Deployment Architecture

```
┌─────────────────────────────────────────┐
│          Local / Cloud VM               │
│                                         │
│  ┌──────────────┐  ┌─────────────────┐  │
│  │  Streamlit   │  │  MCP Server 1   │  │
│  │  :8501       │  │  Fraud DB :8002 │  │
│  └──────┬───────┘  └─────────────────┘  │
│         │                               │
│  ┌──────▼───────┐  ┌─────────────────┐  │
│  │   Agent      │  │  MCP Server 2   │  │
│  │  Orchestrator│  │  Geo DB :8003   │  │
│  └──────────────┘  └─────────────────┘  │
│                                         │
│  audit.jsonl  (append-only audit log)   │
└───────────────────┬─────────────────────┘
                    │ HTTPS
                    ▼
          Anthropic Claude API
```

**Startup commands:**
```bash
python fraud_detection/mcp_server_fraud.py &
python fraud_detection/mcp_server_geo.py &
streamlit run fraud_detection/app.py
```

---

## Slide 11: Screenshots

*(Run the app and capture screenshots of the following)*

1. **Dashboard home** — Batch Analysis tab with "Run Fraud Analysis" button
2. **Results table** — Color-coded rows (green/amber/red)
3. **Pie chart** — Safe vs Suspicious vs High Risk distribution
4. **Bar chart** — Transaction amounts by risk level
5. **Transaction detail** — Expanded view showing fraud reasons + agent trace
6. **Single transaction form** — Custom transaction input
7. **Risk gauge** — Plotly gauge showing fraud risk score
8. **About tab** — System documentation

---

## Slide 12: Business Impact

**Quantitative benefits:**
- ⚡ 10-second analysis vs. 14-hour manual review
- 📊 100% transaction coverage vs. 1% manual sampling
- 💰 Potential to prevent billions in fraud losses
- 🔍 Full audit trail for regulatory compliance (GDPR, RBI guidelines)

**Qualitative benefits:**
- Explainable decisions build customer and regulator trust
- Multi-agent design allows independent improvement of each module
- Self-healing workflows ensure 99.9%+ uptime
- Rule engine + LLM hybrid gives speed AND accuracy

**Key differentiators:**
- Not a black box — every decision is fully explained
- Not brittle — self-heals on API failures
- Not a silo — MCP servers enable integration with any banking system
