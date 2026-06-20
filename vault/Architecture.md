---
tags: [architecture, pipeline, multi-agent]
---

# 🏗️ System Architecture

Source: `orchestrator/agent.py` · See also: [[Home]], [[Agents/Orchestrator]]

---

## Agent Pipeline

```mermaid
graph TD
    UI["🖥️ Streamlit UI\nfrontend/app.py"]
    PRE["⚙️ FraudHookManager\npre_process\nValidate · Rate limit · Correlation ID"]
    ORCH["🧠 FraudDetectionOrchestrator\norchestrator/agent.py"]
    RULES["📋 RulesAgent\ncore/rules.py\nPython — no LLM"]
    PATTERN["🔍 PatternAgent\nclaude-sonnet-4-6\nBehavioral analysis"]
    RISK["📊 RiskScorerAgent\nclaude-opus-4-8 + extended thinking\n0–100 score"]
    COORD["✅ CoordinatorAgent\nclaude-opus-4-8\nFinal decision"]
    POST["⚙️ FraudHookManager\npost_process\nCompliance · Fairness · Audit log"]
    RESULT["🏁 Result\nSafe / Suspicious / High Risk"]

    UI --> PRE --> ORCH
    ORCH --> RULES --> PATTERN --> RISK --> COORD
    COORD --> POST --> RESULT
```

---

## Data Flow

```mermaid
sequenceDiagram
    participant UI as Streamlit UI
    participant Hook as HookManager
    participant Orch as Orchestrator
    participant Rules as RulesAgent
    participant Pattern as PatternAgent
    participant Risk as RiskScorer
    participant Coord as Coordinator
    participant Obs as Observability

    UI->>Hook: Transaction dict
    Hook->>Hook: Validate + assign correlation_id
    Hook->>Orch: Enriched transaction
    Orch->>Rules: evaluate(txn, all_txns)
    Rules-->>Orch: risk_level, fraud_reasons, rule_details
    Orch->>Pattern: Claude messages.create (Sonnet)
    Pattern-->>Orch: behavioral analysis (≤3 sentences)
    Orch->>Risk: Claude messages.create (Opus + thinking)
    Risk-->>Orch: risk_score 0–100
    Orch->>Coord: Claude messages.create (Opus)
    Coord-->>Orch: final report + recommended_action
    Orch->>Obs: trace() for each agent
    Orch-->>Hook: result dict
    Hook->>Hook: Compliance + fairness + audit_log
    Hook-->>UI: Final result
```

---

## Directory Map

```
capstone/
├── frontend/app.py          ← Streamlit dashboard (entry point)
├── orchestrator/agent.py    ← Multi-agent coordinator
├── core/
│   ├── rules.py             ← 4 fraud rules (pure Python)
│   ├── data.py              ← 22 sample transactions
│   ├── tools.py             ← Claude tool schemas
│   ├── hooks.py             ← Pre/post middleware
│   ├── governance.py        ← Compliance, audit, rate limiter
│   └── graph.py             ← NetworkX property graph
├── mcp/
│   ├── mcp_server_fraud.py  ← Port 8002
│   ├── mcp_server_geo.py    ← Port 8003
│   └── mcp_server_orchestrator.py ← Port 8004
├── observability/
│   └── observability.py     ← OTEL + in-memory traces
├── rag/retriever.py         ← TF-IDF knowledge retriever
├── config/settings.py       ← All thresholds and model names
└── tests/                   ← pytest unit + integration tests
```
