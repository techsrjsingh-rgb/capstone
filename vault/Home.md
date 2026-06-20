---
tags: [home, dashboard, index]
---

# 🛡️ Fraud Detection AI — Knowledge Vault

> Multi-agent AI system that detects banking fraud using Anthropic Claude API, Python, and Streamlit.

---

## Quick Navigation

| Section | Notes |
|---------|-------|
| 🏗️ [[Architecture]] | Mermaid agent pipeline diagram |
| 📋 [[Fraud-Rules]] | 4 fraud detection rules with thresholds |
| 🛡️ [[Governance]] | Compliance, audit log, fairness, rate limiting |
| 📡 [[Observability]] | OpenTelemetry, SigNoz, correlation ID tracing |
| ⚡ [[Load-Testing]] | K6 and Locust usage guide |

---

## Agents

| Agent | Note | Model |
|-------|------|-------|
| Orchestrator | [[Agents/Orchestrator]] | claude-opus-4-8 |
| Rules Agent | [[Agents/Rules-Agent]] | Python (no LLM) |
| Pattern Agent | [[Agents/Pattern-Agent]] | claude-sonnet-4-6 |
| Risk Scorer | [[Agents/Risk-Scorer-Agent]] | claude-opus-4-8 + extended thinking |
| Coordinator | [[Agents/Coordinator-Agent]] | claude-opus-4-8 |

---

## MCP Servers

| Server | Note | Port |
|--------|------|------|
| Fraud DB | [[MCP-Servers/Fraud-DB]] | 8002 |
| Geo Risk | [[MCP-Servers/Geo-Risk]] | 8003 |
| Orchestrator | [[MCP-Servers/Orchestrator-MCP]] | 8004 |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set API key
cp .env.example .env  # then edit ANTHROPIC_API_KEY

# 3. Start MCP servers (separate terminals)
python mcp/mcp_server_fraud.py          # port 8002
python mcp/mcp_server_geo.py            # port 8003
python mcp/mcp_server_orchestrator.py   # port 8004

# 4. Start dashboard
streamlit run frontend/app.py --server.port 8501

# 5. Run tests
pytest tests/ -v
```

---

*Entry point: `frontend/app.py` · Agent logic: `orchestrator/agent.py` · Config: `config/settings.py`*
