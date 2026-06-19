# Fraud Detection AI Agent — Project Guide

## Project Overview
A multi-agent AI system that detects banking fraud using the Anthropic Claude API, Python, and Streamlit.

## Running the App
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API key (optional — rule-only mode works without it)
cp .env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=your_key_here

# 3. Start MCP servers (in separate terminals)
python fraud_detection/mcp_server_fraud.py   # port 8002
python fraud_detection/mcp_server_geo.py     # port 8003

# 4. Start dashboard
streamlit run fraud_detection/app.py --server.port 8501

# 5. Run tests
pytest tests/ -v
```

## Project Structure
```
capstone/
├── CLAUDE.md                          ← You are here
├── .claude/
│   └── skills/
│       ├── fraud-detection.md         ← Main agent skill
│       ├── governance-compliance.md   ← Compliance skill
│       └── risk-scoring.md            ← Risk scoring skill
├── fraud_detection/
│   ├── app.py          ← Streamlit dashboard (entry point)
│   ├── agent.py        ← Multi-agent orchestrator
│   ├── rules.py        ← 4 fraud rules (pure Python)
│   ├── data.py         ← 22 sample transactions
│   ├── tools.py        ← Claude tool schemas
│   ├── hooks.py        ← Pre/post middleware
│   ├── mcp_server_fraud.py  ← MCP server 1 (port 8002)
│   ├── mcp_server_geo.py    ← MCP server 2 (port 8003)
│   └── skills/
│       └── fraud_detection.md  ← Loaded as agent system prompt
├── shared/
│   ├── config.py        ← Settings and thresholds
│   ├── observability.py ← Logging, correlation IDs, metrics
│   └── governance.py    ← Validation, audit log, rate limiter
├── tests/               ← 79 unit + integration tests
└── docs/                ← Architecture, design, governance docs
```

## Architecture
```
Streamlit UI
    ↓
FraudHookManager (pre_process)
    ↓
FraudDetectionOrchestrator
    ├── RulesAgent       (Python, no LLM)
    ├── PatternAgent     (claude-sonnet-4-6)
    ├── RiskScorerAgent  (claude-opus-4-8 + extended thinking)
    └── CoordinatorAgent (claude-opus-4-8)
    ↓
FraudHookManager (post_process)
    ↓
Result: Safe / Suspicious / High Risk
```

## Skills
- `.claude/skills/fraud-detection.md` — loaded as system prompt for all agents
- `.claude/skills/governance-compliance.md` — compliance officer agent
- `.claude/skills/risk-scoring.md` — risk scorer with extended thinking

## Key Files
- **Entry point:** `fraud_detection/app.py`
- **Agent logic:** `fraud_detection/agent.py`
- **Fraud rules:** `fraud_detection/rules.py`
- **Config/thresholds:** `shared/config.py`
- **Audit log:** `audit.jsonl` (auto-created on first run)
