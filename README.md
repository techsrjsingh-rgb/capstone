# Fraud Detection AI Agent

A multi-agent AI system that analyzes banking transactions and detects fraudulent activity using the Anthropic Claude API, Python, and Streamlit.

## What It Does

The agent analyzes each transaction against four fraud rules:
1. **High Amount** — transactions above ₹1,00,000 are flagged
2. **Unusual Location** — transactions from known fraud hotspots
3. **Rapid Succession** — 3+ transactions within 5 minutes from same customer
4. **International Transaction** — transactions from outside India

Each transaction is classified as:
- ✅ **Safe** — no fraud indicators
- ⚠️ **Suspicious** — one mild fraud indicator
- 🚨 **High Risk** — multiple or strong fraud indicators

---

## Project Structure

```
capstone/
├── README.md
├── requirements.txt
├── .env.example
│
├── shared/                     # Shared utilities used by the agent
│   ├── config.py               # Model names, thresholds, constants
│   ├── observability.py        # Logging, correlation IDs, metrics
│   └── governance.py           # Input validation, compliance, audit log
│
├── fraud_detection/
│   ├── data.py                 # 20+ sample transactions
│   ├── rules.py                # Pure Python fraud rules (no AI)
│   ├── tools.py                # Tool schemas for Claude
│   ├── hooks.py                # Pre/post processing middleware
│   ├── mcp_server_fraud.py     # FastMCP server: transaction history & blacklist
│   ├── mcp_server_geo.py       # FastMCP server: geolocation & country data
│   ├── agent.py                # Multi-agent orchestrator
│   ├── app.py                  # Streamlit dashboard
│   └── skills/
│       └── fraud_detection.md  # Agent skill instructions
│
├── tests/
│   ├── test_rules.py           # Unit tests for fraud rules
│   ├── test_agent.py           # Integration tests (mocked Claude)
│   └── test_shared.py          # Tests for governance & observability
│
└── docs/
    ├── architecture_diagram.md
    ├── technical_design.md
    ├── governance_report.md
    ├── testing_report.md
    ├── deployment_guide.md
    └── presentation.md
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up environment

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 3. Start the MCP servers (in separate terminals)

```bash
# Terminal 1 — Transaction history & blacklist data
python fraud_detection/mcp_server_fraud.py

# Terminal 2 — Geolocation data
python fraud_detection/mcp_server_geo.py
```

### 4. Run the Streamlit dashboard

```bash
streamlit run fraud_detection/app.py
```

Open http://localhost:8501 in your browser.

### 5. Run tests

```bash
pytest tests/ -v
```

---

## Agent Architecture

```
User clicks "Run Fraud Analysis"
        │
        ▼
ClaimHookManager.pre_process()       ← validate, rate-limit, add correlation ID
        │
        ▼
FraudDetectionOrchestrator (Coordinator Agent)
   ├──► RulesAgent          (deterministic Python rules — no API call)
   ├──► PatternAgent         (cross-transaction behavioral analysis — LLM)
   ├──► RiskScorerAgent      (extended thinking — Autonomous Planning Agent)
   └──► Coordinator          (synthesize → final Safe/Suspicious/High Risk)
        │
        ▼
FraudHookManager.post_process()      ← audit log, compliance check, metrics
        │
        ▼
ObservabilityManager.trace()         ← correlation ID, structured JSON log
        │
        ▼
MCP Servers (transaction history, geo data, fraud blacklist)
```

### Multi-Agent Roles

| Agent | Responsibility | Model |
|-------|---------------|-------|
| RulesAgent | Deterministic rule evaluation | No LLM (pure Python) |
| PatternAgent | Behavioral pattern analysis | claude-sonnet-4-6 |
| RiskScorerAgent | Deep risk analysis (extended thinking) | claude-opus-4-8 |
| Coordinator | Synthesize final decision + explanation | claude-opus-4-8 |

---

## Key Design Features

- **Skills**: `fraud_detection/skills/fraud_detection.md` loaded as system prompt context
- **Hooks**: Python middleware (`hooks.py`) wraps every call for validation, audit, compliance
- **MCP Integration**: Two FastMCP servers — fraud DB (port 8002) and geo data (port 8003)
- **Multi-MCP (Bonus)**: Two independent MCP servers
- **Extended Thinking (Bonus)**: RiskScorerAgent uses `thinking={"type": "enabled"}`
- **Self-Healing (Bonus)**: Retry + exponential backoff + fallback to smaller model
- **Multi-Agent Collaboration (Bonus)**: Coordinator delegates to 3 specialist agents

---

## Evaluation Criteria Coverage

| Criterion | Where Implemented |
|-----------|------------------|
| Problem Understanding (10) | README + docs/technical_design.md |
| Agent Architecture (15) | fraud_detection/agent.py |
| Skills & Subagents (20) | skills/fraud_detection.md + 3 specialist agents |
| Hooks & MCP Integration (20) | hooks.py + mcp_server_fraud.py + mcp_server_geo.py |
| Governance (10) | shared/governance.py |
| Observability & Traceability (10) | shared/observability.py |
| Testing & Evaluation (10) | tests/ + docs/testing_report.md |
| Deployment & Presentation (5) | docs/deployment_guide.md + docs/presentation.md |
