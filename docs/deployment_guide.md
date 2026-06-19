# Deployment Guide
## Fraud Detection AI Agent

**Version:** 1.0  
**Date:** June 2026

---

## 1. Prerequisites

| Requirement | Minimum Version | Check Command |
|-------------|----------------|---------------|
| Python | 3.11+ | `python3 --version` |
| pip | 23+ | `pip --version` |
| Anthropic API Key | — | Obtain from console.anthropic.com |
| Git | 2.x | `git --version` |

---

## 2. Local Development Setup

### Step 1: Clone the repository
```bash
git clone https://github.com/your-username/capstone.git
cd capstone
```

### Step 2: Create virtual environment
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows
```

### Step 3: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure environment
```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your API key
# ANTHROPIC_API_KEY=sk-ant-...
```

### Step 5: Start MCP servers (two separate terminals)
```bash
# Terminal 1 — Fraud database server (port 8002)
python fraud_detection/mcp_server_fraud.py

# Terminal 2 — Geo risk server (port 8003)
python fraud_detection/mcp_server_geo.py
```

### Step 6: Launch the dashboard
```bash
# Terminal 3
streamlit run fraud_detection/app.py
```

Open **http://localhost:8501** in your browser.

### Step 7: Run tests (verify everything works)
```bash
pytest tests/ -v
```

---

## 3. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ Yes | — | Your Anthropic API key |
| `PRIMARY_MODEL` | No | `claude-opus-4-8` | Primary LLM model |
| `FALLBACK_MODEL` | No | `claude-sonnet-4-6` | Fallback model |
| `FRAUD_MCP_PORT` | No | `8002` | Fraud DB MCP server port |
| `GEO_MCP_PORT` | No | `8003` | Geo risk MCP server port |

---

## 4. Running Without an API Key (Demo Mode)

The dashboard works without an API key using rule-based analysis only:
1. Set up the `.env` file but leave `ANTHROPIC_API_KEY` empty
2. In the Streamlit sidebar, **uncheck** "Use AI Agent"
3. Click "Run Fraud Analysis" — uses pure Python rules, no LLM calls

---

## 5. Docker Deployment (Optional)

Create a `Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501 8002 8003
CMD streamlit run fraud_detection/app.py --server.port 8501 --server.address 0.0.0.0
```

Build and run:
```bash
docker build -t fraud-agent .
docker run -p 8501:8501 -e ANTHROPIC_API_KEY=your_key fraud-agent
```

---

## 6. Production Considerations

| Concern | Recommendation |
|---------|---------------|
| API key storage | Use AWS Secrets Manager or HashiCorp Vault |
| MCP servers | Deploy as separate microservices with health checks |
| Audit logs | Ship `audit.jsonl` to a SIEM (e.g., Splunk, ELK) |
| Rate limiting | Increase `RATE_LIMIT_REQUESTS` for production load |
| Scaling | Use async processing queue (Celery/Redis) for batch analysis |
| Monitoring | Add Prometheus metrics exporter from ObservabilityManager |
| Model updates | Pin exact model versions; test before upgrading |

---

## 7. Project Structure Quick Reference

```
capstone/
├── fraud_detection/
│   ├── app.py              → streamlit run fraud_detection/app.py
│   ├── agent.py            → Multi-agent orchestrator
│   ├── mcp_server_fraud.py → python fraud_detection/mcp_server_fraud.py
│   └── mcp_server_geo.py   → python fraud_detection/mcp_server_geo.py
├── shared/                 → Shared utilities
├── tests/                  → pytest tests/
└── docs/                   → This file and other docs
```

---

## 8. Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `ANTHROPIC_API_KEY not set` | Missing .env file | Run `cp .env.example .env` and add key |
| `ModuleNotFoundError: streamlit` | Dependencies not installed | Run `pip install -r requirements.txt` |
| `Connection refused on port 8002` | MCP server not running | Run `python fraud_detection/mcp_server_fraud.py` |
| `RateLimitError` | Too many API calls | Wait 60 seconds; reduce request rate |
| `ValidationError` on transaction | Invalid field value | Check transaction_type is a valid enum value |
