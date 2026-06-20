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
python mcp/mcp_server_fraud.py   # port 8002
python mcp/mcp_server_geo.py     # port 8003

# 4. Start dashboard
streamlit run frontend/app.py --server.port 8501

# 5. Run tests
pytest tests/ -v

# 6. Run load tests (requires locust)
locust -f load_tests/locustfile.py --host=http://localhost:8002
```

## Project Structure
```
capstone/
├── CLAUDE.md                        ← You are here
├── .mcp.json                        ← MCP server definitions
├── .worktreeinclude                 ← Worktree path includes
├── .claude/
│   ├── settings.json                ← Permissions scaffold
│   ├── settings.local.json          ← Local overrides (gitignored)
│   ├── agents/
│   │   ├── agent.md                 ← Orchestrator agent definition
│   │   ├── rules-agent.md           ← Rules agent definition
│   │   ├── pattern-agent.md         ← Pattern agent definition
│   │   ├── risk-scorer-agent.md     ← Risk scorer definition
│   │   └── coordinator-agent.md     ← Coordinator agent definition
│   ├── skills/
│   │   ├── fraud-detection.md       ← Main fraud detection skill
│   │   ├── governance-compliance.md ← Compliance skill
│   │   └── risk-scoring.md          ← Risk scoring skill
│   ├── rules/                       ← Project rules (ready for .md files)
│   └── commands/                    ← Custom commands (ready for .md files)
├── config/
│   └── settings.py                  ← All settings and thresholds
├── core/
│   ├── data.py                      ← 22 sample transactions
│   ├── rules.py                     ← 4 fraud rules (pure Python)
│   ├── tools.py                     ← Claude tool schemas
│   ├── hooks.py                     ← Pre/post middleware
│   └── governance.py                ← Validation, audit log, rate limiter
├── frontend/
│   └── app.py                       ← Streamlit dashboard (entry point)
├── mcp/
│   ├── mcp_server_fraud.py          ← MCP server 1 (port 8002)
│   └── mcp_server_geo.py            ← MCP server 2 (port 8003)
├── observability/
│   └── observability.py             ← Logging, correlation IDs, metrics
├── orchestrator/
│   ├── agent.py                     ← Multi-agent orchestrator
│   └── skills/
│       └── fraud_detection.md       ← Loaded as agent system prompt
├── rag/
│   └── retriever.py                 ← TF-IDF knowledge retriever
├── tests/                           ← Unit + integration tests
├── load_tests/
│   └── locustfile.py                ← Locust load test scripts
├── docs/                            ← Architecture, design, governance docs
└── reports/                         ← Runtime output (gitignored)
```

## Architecture
```
Streamlit UI  (frontend/app.py)
    ↓
FraudHookManager (core/hooks.py — pre_process)
    ↓
FraudDetectionOrchestrator  (orchestrator/agent.py)
    ├── RulesAgent       (core/rules.py — Python, no LLM)
    ├── PatternAgent     (claude-sonnet-4-6)
    ├── RiskScorerAgent  (claude-opus-4-8 + extended thinking)
    └── CoordinatorAgent (claude-opus-4-8)
    ↓
FraudHookManager (post_process)
    ↓
Result: Safe / Suspicious / High Risk
```

## Claude Code Agents
- `.claude/agents/agent.md` — orchestrator, coordinates all 4 sub-agents
- `.claude/agents/rules-agent.md` — pure Python rules engine
- `.claude/agents/pattern-agent.md` — behavioral pattern analysis (Sonnet)
- `.claude/agents/risk-scorer-agent.md` — extended thinking risk scorer (Opus)
- `.claude/agents/coordinator-agent.md` — final synthesis (Opus)

## Skills
- `.claude/skills/fraud-detection.md` — loaded as system prompt for all agents
- `.claude/skills/governance-compliance.md` — compliance officer agent
- `.claude/skills/risk-scoring.md` — risk scorer with extended thinking

## Key Files
- **Entry point:** `frontend/app.py`
- **Agent logic:** `orchestrator/agent.py`
- **Fraud rules:** `core/rules.py`
- **Config/thresholds:** `config/settings.py`
- **Audit log:** `audit.jsonl` (auto-created on first run)
- **RAG retriever:** `rag/retriever.py`
